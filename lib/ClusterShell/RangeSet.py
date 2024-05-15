#
# Copyright (C) 2012-2016 CEA/DAM
# Copyright (C) 2012-2016 Aurelien Degremont <aurelien.degremont@cea.fr>
# Copyright (C) 2015-2017 Stephane Thiell <sthiell@stanford.edu>
#
# This file is part of ClusterShell.
#
# ClusterShell is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# ClusterShell is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with ClusterShell; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

"""
Cluster range set module.

Instances of RangeSet provide similar operations than the builtin set type,
extended to support cluster ranges-like format and stepping support ("0-8/2").
"""

from functools import reduce
from itertools import product
from operator import mul

__all__ = ['RangeSetException',
           'RangeSetParseError',
           'RangeSetPaddingError',
           'RangeSet',
           'RangeSetND',
           'AUTOSTEP_DISABLED']

# Special constant used to force turn off autostep feature.
# Note: +inf is 1E400, but a bug in python 2.4 makes it impossible to be
# pickled, so we use less. Later, we could consider sys.maxint here.
AUTOSTEP_DISABLED = 1E100


class RangeSetException(Exception):
    """Base RangeSet exception class."""

class RangeSetParseError(RangeSetException):
    """Raised when RangeSet parsing cannot be done properly."""
    def __init__(self, part, msg):
        if part:
            msg = "%s : \"%s\"" % (msg, part)
        RangeSetException.__init__(self, msg)
        # faulty subrange; this allows you to target the error
        self.part = part

class RangeSetPaddingError(RangeSetParseError):
    """Raised when a fatal padding incoherence occurs"""
    def __init__(self, part, msg):
        RangeSetParseError.__init__(self, part, "padding mismatch (%s)" % msg)


class RangeSet(set):
    """
    Mutable set of cluster node indexes featuring a fast range-based API.

    This class aims to ease the management of potentially large cluster range
    sets and is used by the :class:`.NodeSet` class.

    RangeSet basic constructors:

       >>> rset = RangeSet()            # empty RangeSet
       >>> rset = RangeSet("5,10-42")   # contains '5', '10' to '42'
       >>> rset = RangeSet("0-10/2")    # contains '0', '2', '4', '6', '8', '10'
       >>> rset = RangeSet("00-10/2")   # contains '00', '02', '04', '06', '08', '10'

    Also any iterable of integers can be specified as first argument:

       >>> RangeSet([3, 6, 8, 7, 1])
       1,3,6-8
       >>> rset2 = RangeSet(rset)

    Padding of ranges (eg. "003-009") is inferred from input arguments and
    managed automatically. This is new in ClusterShell v1.9, where mixed lengths
    zero padding is now supported within the same RangeSet. The instance
    variable `padding` has become a property that can still be used to either
    get the max padding length in the set, or force a fixed length zero-padding
    on the set.

    RangeSet is itself a set and as such, provides an iterator over its items
    as strings (strings are used since v1.9). It is recommended to use the
    explicit iterators :meth:`RangeSet.intiter` and :meth:`RangeSet.striter`
    when iterating over a RangeSet.

    RangeSet provides methods like :meth:`RangeSet.union`,
    :meth:`RangeSet.intersection`, :meth:`RangeSet.difference`,
    :meth:`RangeSet.symmetric_difference` and their in-place versions
    :meth:`RangeSet.update`, :meth:`RangeSet.intersection_update`,
    :meth:`RangeSet.difference_update`,
    :meth:`RangeSet.symmetric_difference_update` which conform to the Python
    Set API.
    """
    _VERSION = 4    # serial version number

    def __init__(self, pattern=None, autostep=None):
        """Initialize RangeSet object.

        :param pattern: optional string pattern
        :param autostep: optional autostep threshold
        """
        set.__init__(self)

        if pattern is not None and not isinstance(pattern, str):
            pattern = ",".join("%s" % i for i in pattern)

        if isinstance(pattern, RangeSet):
            self._autostep = pattern._autostep
        else:
            self._autostep = None
        self.autostep = autostep #: autostep threshold public instance attribute

        if isinstance(pattern, str):
            self._parse(pattern)

    def _parse(self, pattern):
        """Parse string of comma-separated x-y/step -like ranges"""
        # Comma separated ranges
        for subrange in pattern.split(','):
            subrange = subrange.strip()  # ignore whitespaces
            if subrange.find('/') < 0:
                baserange, step = subrange, 1
            else:
                baserange, step = subrange.split('/', 1)

            try:
                step = int(step)
            except ValueError:
                raise RangeSetParseError(subrange,
                                         "cannot convert string to integer")

            begin_sign = end_sign = 1  # sign "scale factor"

            if baserange.find('-') < 0:
                if step != 1:
                    raise RangeSetParseError(subrange, "invalid step usage")
                begin = end = baserange
            else:
                # ignore whitespaces in a range
                try:
                    begin, end = (n.strip() for n in baserange.split('-'))
                    if not begin:  # single negative number "-5"
                        begin = end
                        begin_sign = end_sign = -1
                except ValueError:
                    try:
                        # -0-3
                        _, begin, end = (n.strip()
                                         for n in baserange.split('-'))
                        begin_sign = -1
                    except ValueError:
                        # -8--4
                        _, begin, _, end = (n.strip()
                                            for n in baserange.split('-'))
                        begin_sign = end_sign = -1

            # compute padding and return node range info tuple
            try:
                pad = endpad = 0
                if int(begin) != 0:
                    begins = begin.lstrip("0")
                    if len(begin) - len(begins) > 0:
                        pad = len(begin)
                    start = int(begins)
                else:
                    if len(begin) > 1:
                        pad = len(begin)
                    start = 0
                if int(end) != 0:
                    ends = end.lstrip("0")
                else:
                    ends = end
                # explicit padding for begin and end must match
                if len(end) - len(ends) > 0:
                    endpad = len(end)
                if (pad > 0 or endpad > 0) and len(begin) != len(end):
                    raise RangeSetParseError(subrange,
                                             "padding length mismatch")

                stop = int(ends)
            except ValueError:
                if len(subrange) == 0:
                    msg = "empty range"
                else:
                    msg = "cannot convert string to integer"
                raise RangeSetParseError(subrange, msg)

            # check preconditions
            if pad > 0 and begin_sign < 0:
                errmsg = "padding not supported in negative ranges"
                raise RangeSetParseError(subrange, errmsg)

            if stop > 1e100 or start * begin_sign > stop * end_sign or step < 1:
                raise RangeSetParseError(subrange, "invalid values in range")

            self.add_range(start * begin_sign, stop * end_sign + 1, step, pad)

    @classmethod
    def fromlist(cls, rnglist, autostep=None):
        """Class method that returns a new RangeSet with ranges from provided
        list."""
        inst = RangeSet(autostep=autostep)
        inst.updaten(rnglist)
        return inst

    @classmethod
    def fromone(cls, index, pad=0, autostep=None):
        """
        Class method that returns a new RangeSet of one single item or
        a single range. Accepted input arguments can be:
        - integer and padding length
        - slice object and padding length
        - string (1.9+) with padding automatically detected (pad is ignored)
        """
        inst = RangeSet(autostep=autostep)
        # support slice object with duck-typing
        try:
            inst.add(index, pad)
        except TypeError:
            if not index.stop:
                raise ValueError("Invalid range upper limit (%s)" % index.stop)
            inst.add_range(index.start or 0, index.stop, index.step or 1, pad)
        return inst

    @property
    def padding(self):
        """Get largest padding value of whole set"""
        result = None
        for si in self:
            idx, digitlen = int(si), len(si)
            # explicitly padded?
            if digitlen > 1 and si[0] == '0':
                # result always grows bigger as we iterate over a sorted set
                # with largest padded values at the end
                result = digitlen
        return result

    @padding.setter
    def padding(self, value):
        """Force padding length on the whole set"""
        if value is None:
            value = 1
        cpyset = set(self)
        self.clear()
        for i in cpyset:
            self.add(int(i), pad=value)

    def get_autostep(self):
        """Get autostep value (property)"""
        if self._autostep >= AUTOSTEP_DISABLED:
            return None
        else:
            # +1 as user wants node count but it means real steps here
            return self._autostep + 1

    def set_autostep(self, val):
        """Set autostep value (property)"""
        if val is None:
            # disabled by default for compat with other cluster tools
            self._autostep = AUTOSTEP_DISABLED
        else:
            # - 1 because user means node count, but we mean real steps
            # (this operation has no effect on AUTOSTEP_DISABLED value)
            self._autostep = int(val) - 1

    autostep = property(get_autostep, set_autostep)

    def dim(self):
        """Get the number of dimensions of this RangeSet object. Common
        method with RangeSetND.  Here, it will always return 1 unless
        the object is empty, in that case it will return 0."""
        return int(len(self) > 0)

    def _sorted(self):
        """Get sorted list from inner set."""
        # For mixed padding support, sort by both string length and index
        return sorted(set.__iter__(self),
                      key=lambda x: (-len(x), int(x)) if x.startswith('-') \
                                    else (len(x), x))

    def __iter__(self):
        """Iterate over each element in RangeSet, currently as integers, with
        no padding information.
        To guarantee future compatibility, please use the methods intiter()
        or striter() instead."""
        return iter(self._sorted())

    def striter(self):
        """Iterate over each element in RangeSet as strings with optional
        zero-padding."""
        return iter(self._sorted())

    def intiter(self):
        """Iterate over each element in RangeSet as integer.
        Zero padding info is ignored."""
        for e in self._sorted():
            yield int(e)

    def contiguous(self):
        """Object-based iterator over contiguous range sets."""
        for sli, pad in self._contiguous_slices():
            yield RangeSet.fromone(slice(sli.start, sli.stop, sli.step), pad)

    def __reduce__(self):
        """Return state information for pickling."""
        return self.__class__, (str(self),), \
            { 'padding': self.padding, \
              '_autostep': self._autostep, \
              '_version' : RangeSet._VERSION }

    def __setstate__(self, dic):
        """called upon unpickling"""
        self.__dict__.update(dic)
        if getattr(self, '_version', 0) < RangeSet._VERSION:
            # unpickle from old version?
            if getattr(self, '_version', 0) <= 1:
                # v1 (no object versioning) - CSv1.3
                setattr(self, '_ranges', [(slice(start, stop + 1, step), pad) \
                    for start, stop, step, pad in getattr(self, '_ranges')])
            elif hasattr(self, '_ranges'):
                # v2 - CSv1.4-1.5
                self_ranges = getattr(self, '_ranges')
                if self_ranges and not isinstance(self_ranges[0][0], slice):
                    # workaround for object pickled from Python < 2.5
                    setattr(self, '_ranges', [(slice(start, stop, step), pad) \
                        for (start, stop, step), pad in self_ranges])

            if hasattr(self, '_ranges'):
                # convert to v3
                for sli, pad in getattr(self, '_ranges'):
                    self.add_range(sli.start, sli.stop, sli.step, pad)
                delattr(self, '_ranges')
                delattr(self, '_length')

            if getattr(self, '_version', 0) == 3:  # 1.6 - 1.8
                padding = getattr(self, 'padding', 0)
                # convert integer set to string set
                cpyset = set(self)
                self.clear()
                for i in cpyset:
                    self.add(i, pad=padding)  # automatic conversion

    def _strslices(self):
        """Stringify slices list (x-y/step format)"""
        for sli, pad in self._folded_slices():
            if sli.start + 1 == sli.stop:
                yield "%0*d" % (pad, sli.start)
            else:
                assert sli.step >= 0, "Internal error: sli.step < 0"
                if sli.step == 1:
                    yield "%0*d-%0*d" % (pad, sli.start, pad, sli.stop - 1)
                else:
                    yield "%0*d-%0*d/%d" % (pad, sli.start, pad, sli.stop - 1, \
                                            sli.step)

    def __str__(self):
        """Get comma-separated range-based string (x-y/step format)."""
        return ','.join(self._strslices())

    # __repr__ is the same as __str__ as it is a valid expression that
    # could be used to recreate a RangeSet with the same value
    __repr__ = __str__

    def _slices_padding(self, autostep=AUTOSTEP_DISABLED):
        """Iterator over (slices, padding).

        Iterator over RangeSet slices, either a:b:1 slices if autostep
        is disabled (default), or a:b:step slices if autostep is specified.
        """
        #
        # Now support mixed lengths zero-padding (v1.9)
        cur_pad = 0
        cur_padded = False
        cur_start = None
        cur_step = None
        last_idx = None

        for si in self._sorted():

            # numerical index and length of digits
            idx, digitlen = int(si), len(si)

            # is current digit zero-padded?
            padded = (digitlen > 1 and si[0] == '0')

            if cur_start is not None:
                padding_mismatch = False
                step_mismatch = False

                # check conditions to yield
                # - padding mismatch
                # - step check (step=1 is just a special case if contiguous)

                if cur_padded:
                    # currently strictly padded, our next item could be
                    # unpadded but with the same length
                    if digitlen != cur_pad:
                        padding_mismatch = True
                else:
                    # current not padded, and because the set is sorted,
                    # it should stay that way
                    if padded:
                        padding_mismatch = True

                if not padding_mismatch:
                    # does current range lead to broken step?
                    if cur_step is not None:
                        # only consider it if step is defined
                        if cur_step != idx - last_idx:
                            step_mismatch = True

                if padding_mismatch or step_mismatch:
                    if cur_step is not None:
                        # stepped is True when autostep setting does apply
                        stepped = (cur_step == 1) or (last_idx - cur_start >= autostep * cur_step)
                        step = cur_step
                    else:
                        stepped = True
                        step = 1

                    if stepped:
                        yield slice(cur_start, last_idx + 1, step), cur_pad if cur_padded else 0
                        cur_start = idx
                        cur_padded = padded
                        cur_pad = digitlen
                    else:
                        if padding_mismatch:
                            stop = last_idx + 1
                        else:
                            stop = last_idx - step + 1

                        for j in range(cur_start, stop, step):
                            yield slice(j, j + 1, 1), cur_pad if cur_padded else 0

                        if padding_mismatch:
                            cur_start = idx
                            cur_padded = padded
                            cur_pad = digitlen
                        else:
                            cur_start = last_idx

                    cur_step = idx - last_idx if step_mismatch else None
                    last_idx = idx
                    continue

            else:
                # first index
                cur_padded = padded
                cur_pad = digitlen
                cur_start = idx
                cur_step = None
                last_idx = idx
                continue

            cur_step = idx - last_idx
            last_idx = idx

        if cur_start is not None:
            if cur_step is not None:
                # stepped is True when autostep setting does apply
                stepped = (last_idx - cur_start >= self._autostep * cur_step)
            else:
                stepped = True

            if stepped or cur_step == 1:
                yield slice(cur_start, last_idx + 1, cur_step), cur_pad if cur_padded else 0
            else:
                for j in range(cur_start, last_idx + 1, cur_step):
                    yield slice(j, j + 1, 1), cur_pad if cur_padded else 0

    def _contiguous_slices(self):
        """Internal iterator over contiguous slices in RangeSet."""
        return self._slices_padding()

    def _folded_slices(self):
        """Internal generator over ranges organized by step."""
        return self._slices_padding(self._autostep)

    def slices(self):
        """
        Iterate over RangeSet ranges as Python slide objects.
        NOTE: zero-padding info is not provided
        """
        for sli, pad in self._folded_slices():
            yield sli

    def __getitem__(self, index):
        """
        Return the element at index or a subrange when a slice is specified.
        """
        if isinstance(index, slice):
            inst = RangeSet()
            inst._autostep = self._autostep
            inst.update(self._sorted()[index])
            return inst
        elif isinstance(index, int):
            return self._sorted()[index]
        else:
            raise TypeError("%s indices must be integers" %
                            self.__class__.__name__)

    def split(self, nbr):
        """
        Split the rangeset into nbr sub-rangesets (at most). Each
        sub-rangeset will have the same number of elements more or
        less 1. Current rangeset remains unmodified. Returns an
        iterator.

        >>> RangeSet("1-5").split(3) 
        RangeSet("1-2")
        RangeSet("3-4")
        RangeSet("foo5")
        """
        assert(nbr > 0)

        # We put the same number of element in each sub-nodeset.
        slice_size = len(self) // int(nbr)
        left = len(self) % nbr

        begin = 0
        for i in range(0, min(nbr, len(self))):
            length = slice_size + int(i < left)
            yield self[begin:begin + length]
            begin += length

    def add_range(self, start, stop, step=1, pad=0):
        """
        Add a range (start, stop, step and padding length) to RangeSet.
        Like the Python built-in function *range()*, the last element
        is the largest start + i * step less than stop.
        """
        assert start < stop, "please provide ordered node index ranges"
        assert step > 0
        assert pad >= 0
        assert stop - start < 1e9, "range too large"

        if pad == 0:
            set.update(self, ("%d" % i for i in range(start, stop, step)))
        else:
            set.update(self, ("%0*d" % (pad, i) for i in range(start, stop, step)))

    def copy(self):
        """Return a shallow copy of a RangeSet."""
        cpy = self.__class__()
        cpy._autostep = self._autostep
        cpy.update(self)
        return cpy

    __copy__ = copy # For the copy module

    def __eq__(self, other):
        """
        RangeSet equality comparison.
        """
        # Return NotImplemented instead of raising TypeError, to
        # indicate that the comparison is not implemented with respect
        # to the other type (the other comparand then gets a chance to
        # determine the result, then it falls back to object address
        # comparison).
        if not isinstance(other, RangeSet):
            return NotImplemented
        return len(self) == len(other) and self.issubset(other)

    # Standard set operations: union, intersection, both differences.
    # Each has an operator version (e.g. __or__, invoked with |) and a
    # method version (e.g. union).
    # Subtle:  Each pair requires distinct code so that the outcome is
    # correct when the type of other isn't suitable.  For example, if
    # we did "union = __or__" instead, then Set().union(3) would return
    # NotImplemented instead of raising TypeError (albeit that *why* it
    # raises TypeError as-is is also a bit subtle).

    def __or__(self, other):
        """Return the union of two RangeSets as a new RangeSet.

        (I.e. all elements that are in either set.)
        """
        if not isinstance(other, set):
            return NotImplemented
        return self.union(other)

    def union(self, other):
        """Return the union of two RangeSets as a new RangeSet.

        (I.e. all elements that are in either set.)
        """
        self_copy = self.copy()
        self_copy.update(other)
        return self_copy

    def __and__(self, other):
        """Return the intersection of two RangeSets as a new RangeSet.

        (I.e. all elements that are in both sets.)
        """
        if not isinstance(other, set):
            return NotImplemented
        return self.intersection(other)

    def intersection(self, other):
        """Return the intersection of two RangeSets as a new RangeSet.

        (I.e. all elements that are in both sets.)
        """
        self_copy = self.copy()
        self_copy.intersection_update(other)
        return self_copy

    def __xor__(self, other):
        """Return the symmetric difference of two RangeSets as a new RangeSet.

        (I.e. all elements that are in exactly one of the sets.)
        """
        if not isinstance(other, set):
            return NotImplemented
        return self.symmetric_difference(other)

    def symmetric_difference(self, other):
        """Return the symmetric difference of two RangeSets as a new RangeSet.

        (ie. all elements that are in exactly one of the sets.)
        """
        self_copy = self.copy()
        self_copy.symmetric_difference_update(other)
        return self_copy

    def __sub__(self, other):
        """Return the difference of two RangeSets as a new RangeSet.

        (I.e. all elements that are in this set and not in the other.)
        """
        if not isinstance(other, set):
            return NotImplemented
        return self.difference(other)

    def difference(self, other):
        """Return the difference of two RangeSets as a new RangeSet.

        (I.e. all elements that are in this set and not in the other.)
        """
        self_copy = self.copy()
        self_copy.difference_update(other)
        return self_copy

    # Membership test

    def __contains__(self, element):
        """Report whether an element is a member of a RangeSet.
        Element can be either another RangeSet object, a string or an
        integer.

        Called in response to the expression ``element in self``.
        """
        if isinstance(element, set):
            return element.issubset(self)

        return set.__contains__(self, str(element))

    # Subset and superset test

    def issubset(self, other):
        """Report whether another set contains this RangeSet."""
        self._binary_sanity_check(other)
        return set.issubset(self, other)

    def issuperset(self, other):
        """Report whether this RangeSet contains another set."""
        self._binary_sanity_check(other)
        return set.issuperset(self, other)

    # Inequality comparisons using the is-subset relation.
    __le__ = issubset
    __ge__ = issuperset

    def __lt__(self, other):
        self._binary_sanity_check(other)
        return len(self) < len(other) and self.issubset(other)

    def __gt__(self, other):
        self._binary_sanity_check(other)
        return len(self) > len(other) and self.issuperset(other)

    # Assorted helpers

    def _binary_sanity_check(self, other):
        """Check that the other argument to a binary operation is also  a set,
        raising a TypeError otherwise."""
        if not isinstance(other, set):
            raise TypeError("Binary operation only permitted between sets")

    # In-place union, intersection, differences.
    # Subtle:  The xyz_update() functions deliberately return None,
    # as do all mutating operations on built-in container types.
    # The __xyz__ spellings have to return self, though.

    def __ior__(self, other):
        """Update a RangeSet with the union of itself and another."""
        self._binary_sanity_check(other)
        set.__ior__(self, other)
        return self

    def union_update(self, other):
        """Update a RangeSet with the union of itself and another."""
        self.update(other)

    def __iand__(self, other):
        """Update a RangeSet with the intersection of itself and another."""
        self._binary_sanity_check(other)
        set.__iand__(self, other)
        return self

    def intersection_update(self, other):
        """Update a RangeSet with the intersection of itself and another."""
        set.intersection_update(self, other)

    def __ixor__(self, other):
        """Update a RangeSet with the symmetric difference of itself and
        another."""
        self._binary_sanity_check(other)
        set.symmetric_difference_update(self, other)
        return self

    def symmetric_difference_update(self, other):
        """Update a RangeSet with the symmetric difference of itself and
        another."""
        set.symmetric_difference_update(self, other)

    def __isub__(self, other):
        """Remove all elements of another set from this RangeSet."""
        self._binary_sanity_check(other)
        set.difference_update(self, other)
        return self

    def difference_update(self, other, strict=False):
        """Remove all elements of another set from this RangeSet.

        If strict is True, raise KeyError if an element cannot be removed.
        (strict is a RangeSet addition)"""
        if strict and other not in self:
            raise KeyError(set.difference(other, self).pop())
        set.difference_update(self, other)

    # Python dict-like mass mutations: update, clear

    def update(self, iterable):
        """Add all indexes (as strings) from an iterable (such as a list)."""
        assert not isinstance(iterable, str)
        set.update(self, iterable)

    def updaten(self, rangesets):
        """
        Update a rangeset with the union of itself and several others.
        """
        for rng in rangesets:
            if isinstance(rng, set):
                self.update(str(i) for i in rng)  # 1.9+: force cast to str
            else:
                self.update(RangeSet(rng))

    def clear(self):
        """Remove all elements from this RangeSet."""
        set.clear(self)

    # Single-element mutations: add, remove, discard

    def add(self, element, pad=0):
        """Add an element to a RangeSet.
        This has no effect if the element is already present.

        ClusterShell 1.9+ uses strings instead of integers to better manage
        zero-padded ranges with mixed lengths. This method supports either a
        string or an integer with padding info.

        :param element: the element to add (integer or string)
        :param pad: zero padding length (integer); ignored if element is string
        """
        if isinstance(element, str):
            set.add(self, element)
        else:
            set.add(self, "%0*d" % (pad, int(element)))

    def remove(self, element, pad=0):
        """Remove an element from a RangeSet.

        ClusterShell 1.9+ uses strings instead of integers to better manage
        zero-padded ranges with mixed lengths. This method supports either a
        string or an integer with padding info.

        :param element: the element to remove (integer or string)
        :param pad: zero padding length (integer); ignored if element is string
        :raises KeyError: element is not contained in RangeSet
        :raises ValueError: element is not castable to integer
        """
        if isinstance(element, str):
            set.remove(self, element)
        else:
            set.remove(self, "%0*d" % (pad, int(element)))

    def discard(self, element, pad=0):
        """Discard an element from a RangeSet if it is a member.

        If the element is not a member, do nothing.

        ClusterShell 1.9+ uses strings instead of integers to better manage
        zero-padded ranges with mixed lengths. This method supports either a
        string or an integer with padding info.

        :param element: the element to remove (integer or string)
        :param pad: zero padding length (integer); ignored if element is string
        """
        try:
            if isinstance(element, str):
                set.discard(self, element)
            else:
                set.discard(self, "%0*d" % (pad, int(element)))
        except ValueError:
            pass # ignore other object types


class RangeSetND(object):
    """
    Build a N-dimensional RangeSet object.

    .. warning:: You don't usually need to use this class directly, use
        :class:`.NodeSet` instead that has ND support.

    Empty constructor::

        RangeSetND()

    Build from a list of list of :class:`RangeSet` objects::

        RangeSetND([[rs1, rs2, rs3, ...], ...])

    Strings are also supported::

        RangeSetND([["0-3", "4-10", ...], ...])

    Integers are also supported::

        RangeSetND([(0, 4), (0, 5), (1, 4), (1, 5), ...]
    """
    def __init__(self, args=None, pads=None, autostep=None, copy_rangeset=True):
        """RangeSetND initializer

        All parameters are optional.

        :param args: generic "list of list" input argument (default is None)
        :param pads: list of 0-padding length (default is to not pad any
                     dimensions)
        :param autostep: autostep threshold (use range/step notation if more
                         than #autostep items meet the condition) - default is
                         off (None)
        :param copy_rangeset: (advanced) if set to False, do not copy RangeSet
                              objects from args (transfer ownership), which is
                              faster. In that case, you should not modify these
                              objects afterwards (default is True).
        """
        # RangeSetND are arranged as a list of N-dimensional RangeSet vectors
        self._veclist = []
        # Dirty flag to avoid doing veclist folding too often
        self._dirty = True
        # Initialize autostep through property
        self._autostep = None
        self.autostep = autostep #: autostep threshold public instance attribute
        # Hint on whether several dimensions are varying or not
        self._multivar_hint = False
        if args is None:
            return
        for rgvec in args:
            if rgvec:
                if isinstance(rgvec[0], str):
                    self._veclist.append([RangeSet(rg, autostep=autostep) \
                                          for rg in rgvec])
                elif isinstance(rgvec[0], RangeSet):
                    if copy_rangeset:
                        self._veclist.append([rg.copy() for rg in rgvec])
                    else:
                        self._veclist.append(rgvec)
                else:
                    if pads is None:
                        self._veclist.append( \
                            [RangeSet.fromone(rg, autostep=autostep) \
                                for rg in rgvec])
                    else:
                        self._veclist.append( \
                            [RangeSet.fromone(rg, pad, autostep) \
                                for rg, pad in zip(rgvec, pads)])

    class precond_fold(object):
        """Decorator to ease internal folding management"""
        def __call__(self, func):
            def inner(*args, **kwargs):
                rgnd, fargs = args[0], args[1:]
                if rgnd._dirty:
                    rgnd._fold()
                return func(rgnd, *fargs, **kwargs)
            # modify the decorator meta-data for pydoc
            # Note: should be later replaced  by @wraps (functools)
            # as of Python 2.5
            inner.__name__ = func.__name__
            inner.__doc__ = func.__doc__
            inner.__dict__ = func.__dict__
            inner.__module__ = func.__module__
            return inner

    @precond_fold()
    def copy(self):
        """Return a new, mutable shallow copy of a RangeSetND."""
        cpy = self.__class__()
        # Shallow "to the extent possible" says the copy module, so here that
        # means calling copy() on each sub-RangeSet to keep mutability.
        cpy._veclist = [[rg.copy() for rg in rgvec] for rgvec in self._veclist]
        cpy._dirty = self._dirty
        return cpy

    __copy__ = copy # For the copy module

    def __eq__(self, other):
        """RangeSetND equality comparison."""
        # Return NotImplemented instead of raising TypeError, to
        # indicate that the comparison is not implemented with respect
        # to the other type (the other comparand then gets a change to
        # determine the result, then it falls back to object address
        # comparison).
        if not isinstance(other, RangeSetND):
            return NotImplemented
        return len(self) == len(other) and self.issubset(other)

    def __bool__(self):
        return bool(self._veclist)

    __nonzero__ = __bool__  # Python 2 compat

    def __len__(self):
        """Count unique elements in N-dimensional rangeset."""
        return sum([reduce(mul, [len(rg) for rg in rgvec]) \
                                 for rgvec in self.veclist])

    @precond_fold()
    def __str__(self):
        """String representation of N-dimensional RangeSet."""
        result = ""
        for rgvec in self._veclist:
            result += "; ".join([str(rg) for rg in rgvec])
            result += "\n"
        return result

    @precond_fold()
    def __iter__(self):
        return self._iter()

    def _iter(self):
        """Iterate through individual items as tuples."""
        for vec in self._veclist:
            for ivec in product(*vec):
                yield ivec

    @precond_fold()
    def iter_padding(self):
        """Iterate through individual items as tuples with padding info.
        As of v1.9, this method returns the largest padding value of each
        items, as mixed length padding is allowed."""
        for vec in self._veclist:
            for ivec in product(*vec):
                yield ivec, [rg.padding for rg in vec]

    @precond_fold()
    def _get_veclist(self):
        """Get folded veclist"""
        return self._veclist

    def _set_veclist(self, val):
        """Set veclist and set dirty flag for deferred folding."""
        self._veclist = val
        self._dirty = True

    veclist = property(_get_veclist, _set_veclist)

    def vectors(self):
        """Get underlying :class:`RangeSet` vectors"""
        return iter(self.veclist)

    def dim(self):
        """Get the current number of dimensions of this RangeSetND
        object.  Return 0 when object is empty."""
        try:
            return len(self._veclist[0])
        except IndexError:
            return 0

    def pads(self):
        """Get a tuple of padding length info for each dimension."""
        # return a tuple of max padding length for each axis
        pad_veclist = ((rg.padding or 0 for rg in vec) for vec in self._veclist)
        return tuple(max(pads) for pads in zip(*pad_veclist))

    def get_autostep(self):
        """Get autostep value (property)"""
        if self._autostep >= AUTOSTEP_DISABLED:
            return None
        else:
            # +1 as user wants node count but _autostep means real steps here
            return self._autostep + 1

    def set_autostep(self, val):
        """Set autostep value (property)"""
        # Must conform to RangeSet.autostep logic
        if val is None:
            self._autostep = AUTOSTEP_DISABLED
        else:
            # Like in RangeSet.set_autostep(): -1 because user means node count,
            # but we mean real steps (this operation has no effect on
            # AUTOSTEP_DISABLED value)
            self._autostep = int(val) - 1

        # Update our RangeSet objects
        for rgvec in self._veclist:
            for rg in rgvec:
                rg._autostep = self._autostep

    autostep = property(get_autostep, set_autostep)

    @precond_fold()
    def __getitem__(self, index):
        """
        Return the element at index or a subrange when a slice is specified.
        """
        if isinstance(index, slice):
            iveclist = []
            for rgvec in self._veclist:
                iveclist += product(*rgvec)
            assert(len(iveclist) == len(self))
            rnd = RangeSetND(iveclist[index], autostep=self.autostep)
            return rnd

        elif isinstance(index, int):
            # find a tuple of integer (multi-dimensional) at position index
            if index < 0:
                length = len(self)
                if index >= -length:
                    index = length + index
                else:
                    raise IndexError("%d out of range" % index)
            length = 0
            for rgvec in self._veclist:
                cnt = reduce(mul, [len(rg) for rg in rgvec])
                if length + cnt < index:
                    length += cnt
                else:
                    for ivec in product(*rgvec):
                        if index == length:
                            return ivec
                        length += 1
            raise IndexError("%d out of range" % index)
        else:
            raise TypeError("%s indices must be integers" %
                            self.__class__.__name__)

    @precond_fold()
    def contiguous(self):
        """Object-based iterator over contiguous range sets."""
        veclist = self._veclist
        try:
            dim = len(veclist[0])
        except IndexError:
            return
        for dimidx in range(dim):
            new_veclist = []
            for rgvec in veclist:
                for rgsli in rgvec[dimidx].contiguous():
                    rgvec = list(rgvec)
                    rgvec[dimidx] = rgsli
                    new_veclist.append(rgvec)
            veclist = new_veclist
        for rgvec in veclist:
            yield RangeSetND([rgvec])

    # Membership test

    @precond_fold()
    def __contains__(self, element):
        """Report whether an element is a member of a RangeSetND.
        Element can be either another RangeSetND object, a string or
        an integer.

        Called in response to the expression ``element in self``.
        """
        if isinstance(element, RangeSetND):
            rgnd_element = element
        else:
            rgnd_element = RangeSetND([[str(element)]])
        return rgnd_element.issubset(self)

    # Subset and superset test

    def issubset(self, other):
        """Report whether another set contains this RangeSetND."""
        self._binary_sanity_check(other)
        return other.issuperset(self)

    @precond_fold()
    def issuperset(self, other):
        """Report whether this RangeSetND contains another RangeSetND."""
        self._binary_sanity_check(other)
        if self.dim() == 1 and other.dim() == 1:
            return self._veclist[0][0].issuperset(other._veclist[0][0])
        if not other._veclist:
            return True
        test = other.copy()
        test.difference_update(self)
        return not bool(test)

    # Inequality comparisons using the is-subset relation.
    __le__ = issubset
    __ge__ = issuperset

    def __lt__(self, other):
        self._binary_sanity_check(other)
        return len(self) < len(other) and self.issubset(other)

    def __gt__(self, other):
        self._binary_sanity_check(other)
        return len(self) > len(other) and self.issuperset(other)

    # Assorted helpers

    def _binary_sanity_check(self, other):
        """Check that the other argument to a binary operation is also a
        RangeSetND, raising a TypeError otherwise."""
        if not isinstance(other, RangeSetND):
            msg = "Binary operation only permitted between RangeSetND"
            raise TypeError(msg)

    def _sort(self):
        """N-dimensional sorting."""
        def rgveckeyfunc(rgvec):
            # key used for sorting purposes, based on the following
            # conditions:
            #   (1) larger vector first (#elements)
            #   (2) larger dim first  (#elements)
            #   (3) lower first index first
            #   (4) lower last index first
            return (-reduce(mul, [len(rg) for rg in rgvec]), \
                    tuple((-len(rg), rg[0], rg[-1]) for rg in rgvec))
        self._veclist.sort(key=rgveckeyfunc)

    @precond_fold()
    def fold(self):
        """Explicit folding call. Please note that folding of RangeSetND
        nD vectors are automatically managed, so you should not have to
        call this method. It may be still useful in some extreme cases
        where the RangeSetND is heavily modified."""
        pass

    def _fold(self):
        """In-place N-dimensional folding."""
        assert self._dirty
        if len(self._veclist) > 1:
            self._fold_univariate() or self._fold_multivariate()
        else:
            self._dirty = False

    def _fold_univariate(self):
        """Univariate nD folding. Return True on success and False when
        a multivariate folding is required."""
        dim = self.dim()
        vardim = dimdiff = 0
        if dim > 1:
            # We got more than one dimension, see if only one is changing...
            for i in range(dim):
                # Are all rangesets on this dimension the same?
                slist = [vec[i] for vec in self._veclist]
                if slist.count(slist[0]) != len(slist):
                    dimdiff += 1
                    if dimdiff > 1:
                        break
                    vardim = i
        univar = (dim == 1 or dimdiff == 1)
        if univar:
            # Eligible for univariate folding (faster!)
            for vec in self._veclist[1:]:
                self._veclist[0][vardim].update(vec[vardim])
            del self._veclist[1:]
            self._dirty = False
        self._multivar_hint = not univar
        return univar

    def _fold_multivariate(self):
        """Multivariate nD folding"""
        # PHASE 1: expand with respect to uniqueness
        self._fold_multivariate_expand()
        # PHASE 2: merge
        self._fold_multivariate_merge()
        self._dirty = False

    def _fold_multivariate_expand(self):
        """Multivariate nD folding: expand [phase 1]"""
        self._veclist = [[RangeSet.fromone(i, autostep=self.autostep)
                          for i in tvec]
                         for tvec in set(self._iter())]

    def _fold_multivariate_merge(self):
        """Multivariate nD folding: merge [phase 2]"""
        full = False  # try easy O(n) passes first
        chg = True    # new pass (eg. after change on veclist)
        while chg:
            chg = False
            self._sort()  # sort veclist before new pass
            index1, index2 = 0, 1
            while (index1 + 1) < len(self._veclist):
                # use 2 references on iterator to compare items by couples
                item1 = self._veclist[index1]
                index2 = index1 + 1
                index1 += 1
                while index2 < len(self._veclist):
                    item2 = self._veclist[index2]
                    index2 += 1
                    new_item = [None] * len(item1)
                    nb_diff = 0
                    # compare 2 rangeset vector, item by item, the idea being
                    # to merge vectors if they differ only by one item
                    for pos, (rg1, rg2) in enumerate(zip(item1, item2)):
                        if rg1 == rg2:
                            new_item[pos] = rg1
                        elif not rg1 & rg2: # merge on disjoint ranges
                            nb_diff += 1
                            if nb_diff > 1:
                                break
                            new_item[pos] = rg1 | rg2
                        # if fully contained, keep the largest one
                        elif (rg1 > rg2 or rg1 < rg2): # and nb_diff == 0:
                            nb_diff += 1
                            if nb_diff > 1:
                                break
                            new_item[pos] = max(rg1, rg2)
                        # otherwise, compute rangeset intersection and
                        # keep the two disjoint part to be handled
                        # later...
                        else:
                            # intersection but do nothing
                            nb_diff = 2
                            break
                    # one change has been done: use this new item to compare
                    # with other
                    if nb_diff <= 1:
                        chg = True
                        item1 = self._veclist[index1 - 1] = new_item
                        index2 -= 1
                        self._veclist.pop(index2)
                    elif not full:
                        # easy pass so break to avoid scanning all
                        # index2; advance with next index1 for now
                        break
            if not chg and not full:
                # if no change was done during the last normal pass, we do a
                # full O(n^2) pass. This pass is done only at the end in the
                # hope that most vectors have already been merged by easy
                # O(n) passes.
                chg = full = True

    def __or__(self, other):
        """Return the union of two RangeSetNDs as a new RangeSetND.

        (I.e. all elements that are in either set.)
        """
        if not isinstance(other, RangeSetND):
            return NotImplemented
        return self.union(other)

    def union(self, other):
        """Return the union of two RangeSetNDs as a new RangeSetND.

        (I.e. all elements that are in either set.)
        """
        rgnd_copy = self.copy()
        rgnd_copy.update(other)
        return rgnd_copy

    def update(self, other):
        """Add all RangeSetND elements to this RangeSetND."""
        if isinstance(other, RangeSetND):
            iterable = other._veclist
        else:
            iterable = other
        for vec in iterable:
            # copy rangesets and set custom autostep
            assert isinstance(vec[0], RangeSet)
            cpyvec = []
            for rg in vec:
                cpyrg = rg.copy()
                cpyrg.autostep = self.autostep
                cpyvec.append(cpyrg)
            self._veclist.append(cpyvec)
        self._dirty = True
        if not self._multivar_hint:
            self._fold_univariate()

    union_update = update

    def __ior__(self, other):
        """Update a RangeSetND with the union of itself and another."""
        self._binary_sanity_check(other)
        self.update(other)
        return self

    def __isub__(self, other):
        """Remove all elements of another set from this RangeSetND."""
        self._binary_sanity_check(other)
        self.difference_update(other)
        return self

    def difference_update(self, other, strict=False):
        """Remove all elements of another set from this RangeSetND.

        If strict is True, raise KeyError if an element cannot be removed
        (strict is a RangeSet addition)"""
        if strict and not other in self:
            raise KeyError(other.difference(self)[0])

        ergvx = other._veclist # read only
        rgnd_new = []
        index1 = 0
        while index1 < len(self._veclist):
            rgvec1 = self._veclist[index1]
            procvx1 = [ rgvec1 ]
            nextvx1 = []
            index2 = 0
            while index2 < len(ergvx):
                rgvec2 = ergvx[index2]
                while len(procvx1) > 0: # refine diff for each resulting vector
                    rgproc1 = procvx1.pop(0)
                    tmpvx = []
                    for pos, (rg1, rg2) in enumerate(zip(rgproc1, rgvec2)):
                        if rg1 == rg2 or rg1 < rg2: # issubset
                            pass
                        elif rg1 & rg2:             # intersect
                            tmpvec = list(rgproc1)
                            tmpvec[pos] = rg1.difference(rg2)
                            tmpvx.append(tmpvec)
                        else:                       # disjoint
                            tmpvx = [ rgproc1 ]     # reset previous work
                            break
                    if tmpvx:
                        nextvx1 += tmpvx
                if nextvx1:
                    procvx1 = nextvx1
                    nextvx1 = []
                index2 += 1
            if procvx1:
                rgnd_new += procvx1
            index1 += 1
        self.veclist = rgnd_new

    def __sub__(self, other):
        """Return the difference of two RangeSetNDs as a new RangeSetND.

        (I.e. all elements that are in this set and not in the other.)
        """
        if not isinstance(other, RangeSetND):
            return NotImplemented
        return self.difference(other)

    def difference(self, other):
        """
        ``s.difference(t)`` returns a new object with elements in s
        but not in t.
        """
        self_copy = self.copy()
        self_copy.difference_update(other)
        return self_copy

    def intersection(self, other):
        """
        ``s.intersection(t)`` returns a new object with elements common
        to s and t.
        """
        self_copy = self.copy()
        self_copy.intersection_update(other)
        return self_copy

    def __and__(self, other):
        """
        Implements the & operator. So ``s & t`` returns a new object
        with elements common to s and t.
        """
        if not isinstance(other, RangeSetND):
            return NotImplemented
        return self.intersection(other)

    def intersection_update(self, other):
        """
        ``s.intersection_update(t)`` returns nodeset s keeping only
        elements also found in t.
        """
        if other is self:
            return

        tmp_rnd = RangeSetND()

        empty_rset = RangeSet()

        for rgvec in self._veclist:
            for ergvec in other._veclist:
                irgvec = [rg.intersection(erg) \
                            for rg, erg in zip(rgvec, ergvec)]
                if not empty_rset in irgvec:
                    tmp_rnd.update([irgvec])
        # substitute
        self.veclist = tmp_rnd.veclist

    def __iand__(self, other):
        """
        Implements the &= operator. So ``s &= t`` returns object s
        keeping only elements also found in t (Python 2.5+ required).
        """
        self._binary_sanity_check(other)
        self.intersection_update(other)
        return self

    def symmetric_difference(self, other):
        """
        ``s.symmetric_difference(t)`` returns the symmetric difference
        of two objects as a new RangeSetND.

        (ie. all items that are in exactly one of the RangeSetND.)
        """
        self_copy = self.copy()
        self_copy.symmetric_difference_update(other)
        return self_copy

    def __xor__(self, other):
        """
        Implement the ^ operator. So ``s ^ t`` returns a new RangeSetND
        with nodes that are in exactly one of the RangeSetND.
        """
        if not isinstance(other, RangeSetND):
            return NotImplemented
        return self.symmetric_difference(other)

    def symmetric_difference_update(self, other):
        """
        ``s.symmetric_difference_update(t)`` returns RangeSetND s
        keeping all nodes that are in exactly one of the objects.
        """
        diff2 = other.difference(self)
        self.difference_update(other)
        self.update(diff2)

    def __ixor__(self, other):
        """
        Implement the ^= operator. So ``s ^= t`` returns object s after
        keeping all items that are in exactly one of the RangeSetND
        (Python 2.5+ required).
        """
        self._binary_sanity_check(other)
        self.symmetric_difference_update(other)
        return self

