#
# Copyright (C) 2012-2016 CEA/DAM
# Copyright (C) 2012-2016 Aurelien Degremont <aurelien.degremont@cea.fr>
# Copyright (C) 2015-2016 Stephane Thiell <sthiell@stanford.edu>
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

from operator import mul

try:
    from itertools import product
except:
    # itertools.product : new in Python 2.6
    def product(*args, **kwds):
        """Cartesian product of input iterables."""
        pools = map(tuple, args) * kwds.get('repeat', 1)
        result = [[]]
        for pool in pools:
            result = [x+[y] for x in result for y in pool]
        for prod in result:
            yield tuple(prod)

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
    """Raised when a fatal padding incoherency occurs"""
    def __init__(self, part, msg):
        RangeSetParseError.__init__(self, part, "padding mismatch (%s)" % msg)


class RangeSet(set):
    """
    Mutable set of cluster node indexes featuring a fast range-based API.

    This class aims to ease the management of potentially large cluster range
    sets and is used by the :class:`.NodeSet` class.

    RangeSet basic constructors:

       >>> rset = RangeSet()            # empty RangeSet
       >>> rset = RangeSet("5,10-42")   # contains 5, 10 to 42
       >>> rset = RangeSet("0-10/2")    # contains 0, 2, 4, 6, 8, 10

    Also any iterable of integers can be specified as first argument:

       >>> RangeSet([3, 6, 8, 7, 1])
       1,3,6-8
       >>> rset2 = RangeSet(rset)

    Padding of ranges (eg. "003-009") can be managed through a public RangeSet
    instance variable named padding. It may be changed at any time. Padding is
    a simple display feature per RangeSet object, thus current padding value is
    not taken into account when computing set operations.
    RangeSet is itself an iterator over its items as integers (instead of
    strings). To iterate over string items with optional padding, you can use
    the :meth:`RangeSet.striter`: method.

    RangeSet provides methods like :meth:`RangeSet.union`,
    :meth:`RangeSet.intersection`, :meth:`RangeSet.difference`,
    :meth:`RangeSet.symmetric_difference` and their in-place versions
    :meth:`RangeSet.update`, :meth:`RangeSet.intersection_update`,
    :meth:`RangeSet.difference_update`,
    :meth:`RangeSet.symmetric_difference_update` which conform to the Python
    Set API.
    """
    _VERSION = 3    # serial version number

    # define __new__() to workaround built-in set subclassing with Python 2.4
    def __new__(cls, pattern=None, autostep=None):
        """Object constructor"""
        return set.__new__(cls)

    def __init__(self, pattern=None, autostep=None):
        """Initialize RangeSet object.

        :param pattern: optional string pattern
        :param autostep: optional autostep threshold
        """
        if pattern is None or isinstance(pattern, str):
            set.__init__(self)
        else:
            set.__init__(self, pattern)

        if isinstance(pattern, RangeSet):
            self._autostep = pattern._autostep
            self.padding = pattern.padding
        else:
            self._autostep = None
            self.padding = None
        self.autostep = autostep #: autostep threshold public instance attribute

        if isinstance(pattern, str):
            self._parse(pattern)

    def _parse(self, pattern):
        """Parse string of comma-separated x-y/step -like ranges"""
        # Comma separated ranges
        if pattern.find(',') < 0:
            subranges = [pattern]
        else:
            subranges = pattern.split(',')

        for subrange in subranges:
            if subrange.find('/') < 0:
                step = 1
                baserange = subrange
            else:
                baserange, step = subrange.split('/', 1)

            try:
                step = int(step)
            except ValueError:
                raise RangeSetParseError(subrange,
                        "cannot convert string to integer")

            if baserange.find('-') < 0:
                if step != 1:
                    raise RangeSetParseError(subrange,
                            "invalid step usage")
                begin = end = baserange
            else:
                begin, end = baserange.split('-', 1)

            # compute padding and return node range info tuple
            try:
                pad = 0
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
                stop = int(ends)
            except ValueError:
                if len(subrange) == 0:
                    msg = "empty range"
                else:
                    msg = "cannot convert string to integer"
                raise RangeSetParseError(subrange, msg)

            # check preconditions
            if stop > 1e100 or start > stop or step < 1:
                raise RangeSetParseError(subrange,
                                         "invalid values in range")

            self.add_range(start, stop + 1, step, pad)

    @classmethod
    def fromlist(cls, rnglist, autostep=None):
        """Class method that returns a new RangeSet with ranges from provided
        list."""
        inst = RangeSet(autostep=autostep)
        inst.updaten(rnglist)
        return inst

    @classmethod
    def fromone(cls, index, pad=0, autostep=None):
        """Class method that returns a new RangeSet of one single item or
        a single range (from integer or slice object)."""
        inst = RangeSet(autostep=autostep)
        # support slice object with duck-typing
        try:
            inst.add(index, pad)
        except TypeError:
            if not index.stop:
                raise ValueError("Invalid range upper limit (%s)" % index.stop)
            inst.add_range(index.start or 0, index.stop, index.step or 1, pad)
        return inst

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
        return sorted(set.__iter__(self))

    def __iter__(self):
        """Iterate over each element in RangeSet."""
        return iter(self._sorted())

    def striter(self):
        """Iterate over each (optionally padded) string element in RangeSet."""
        pad = self.padding or 0
        for i in self._sorted():
            yield "%0*d" % (pad, i)

    def contiguous(self):
        """Object-based iterator over contiguous range sets."""
        pad = self.padding or 0
        for sli in self._contiguous_slices():
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
                if self_ranges and type(self_ranges[0][0]) is not slice:
                    # workaround for object pickled from Python < 2.5
                    setattr(self, '_ranges', [(slice(start, stop, step), pad) \
                        for (start, stop, step), pad in self_ranges])
            # convert to v3
            for sli, pad in getattr(self, '_ranges'):
                self.add_range(sli.start, sli.stop, sli.step, pad)
            delattr(self, '_ranges')
            delattr(self, '_length')

    def _strslices(self):
        """Stringify slices list (x-y/step format)"""
        pad = self.padding or 0
        for sli in self.slices():
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

    def _contiguous_slices(self):
        """Internal iterator over contiguous slices in RangeSet."""
        k = j = None
        for i in self._sorted():
            if k is None:
                k = j = i
            if i - j > 1:
                yield slice(k, j + 1, 1)
                k = i
            j = i
        if k is not None:
            yield slice(k, j + 1, 1)

    def _folded_slices(self):
        """Internal generator that is able to retrieve ranges organized by
        step."""
        if len(self) == 0:
            return

        prng = None         # pending range
        istart = None       # processing starting indice
        step = 0            # processing step
        for sli in self._contiguous_slices():
            start = sli.start
            stop = sli.stop
            unitary = (start + 1 == stop)   # one indice?
            if istart is None:  # first loop
                if unitary:
                    istart = start
                else:
                    prng = [start, stop, 1]
                    istart = stop - 1
                i = k = istart
            elif step == 0:        # istart is set but step is unknown
                if not unitary:
                    if prng is not None:
                        # yield and replace pending range
                        yield slice(*prng)
                    else:
                        yield slice(istart, istart + 1, 1)
                    prng = [start, stop, 1]
                    istart = k = stop - 1
                    continue
                i = start
            else:               # step > 0
                assert step > 0
                i = start
                # does current range lead to broken step?
                if step != i - k or not unitary:
                    #Python2.6+: j = i if step == i - k else k
                    if step == i - k:
                        j = i
                    else:
                        j = k
                    # stepped is True when autostep setting does apply
                    stepped = (j - istart >= self._autostep * step)
                    if prng:    # yield pending range?
                        if stepped:
                            prng[1] -= 1
                        else:
                            istart += step
                        yield slice(*prng)
                        prng = None
                if step != i - k:
                    # case: step value has changed
                    if stepped:
                        yield slice(istart, k + 1, step)
                    else:
                        for j in range(istart, k - step + 1, step):
                            yield slice(j, j + 1, 1)
                        if not unitary:
                            yield slice(k, k + 1, 1)
                    if unitary:
                        if stepped:
                            istart = i = k = start
                        else:
                            istart = k
                    else:
                        prng = [start, stop, 1]
                        istart = i = k = stop - 1
                elif not unitary:
                    # case: broken step by contiguous range
                    if stepped:
                        # yield 'range/step' by taking first indice of new range
                        yield slice(istart, i + 1, step)
                        i += 1
                    else:
                        # autostep setting does not apply in that case
                        for j in range(istart, i - step + 1, step):
                            yield slice(j, j + 1, 1)
                    if stop > i + 1:    # current->pending only if not unitary
                        prng = [i, stop, 1]
                    istart = i = k = stop - 1
            step = i - k
            k = i
        # exited loop, process pending range or indice...
        if step == 0:
            if prng:
                yield slice(*prng)
            else:
                yield slice(istart, istart + 1, 1)
        else:
            assert step > 0
            stepped = (k - istart >= self._autostep * step)
            if prng:
                if stepped:
                    prng[1] -= 1
                else:
                    istart += step
                yield slice(*prng)
                prng = None
            if stepped:
                yield slice(istart, i + 1, step)
            else:
                for j in range(istart, i + 1, step):
                    yield slice(j, j + 1, 1)

    def slices(self):
        """
        Iterate over RangeSet ranges as Python slice objects.
        """
        # return an iterator
        if self._autostep >= AUTOSTEP_DISABLED:
            # autostep disabled: call simpler method to return only a:b slices
            return self._contiguous_slices()
        else:
            # autostep enabled: call generic method to return a:b:step slices
            return self._folded_slices()

    def __getitem__(self, index):
        """
        Return the element at index or a subrange when a slice is specified.
        """
        if isinstance(index, slice):
            inst = RangeSet()
            inst._autostep = self._autostep
            inst.padding = self.padding
            inst.update(self._sorted()[index])
            return inst
        elif isinstance(index, int):
            return self._sorted()[index]
        else:
            raise TypeError, \
                "%s indices must be integers" % self.__class__.__name__

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
        slice_size = len(self) / nbr
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

        if pad > 0 and self.padding is None:
            self.padding = pad
        set.update(self, range(start, stop, step))

    def copy(self):
        """Return a shallow copy of a RangeSet."""
        cpy = self.__class__()
        cpy._autostep = self._autostep
        cpy.padding = self.padding
        cpy.update(self)
        return cpy

    __copy__ = copy # For the copy module

    def __eq__(self, other):
        """
        RangeSet equality comparison.
        """
        # Return NotImplemented instead of raising TypeError, to
        # indicate that the comparison is not implemented with respect
        # to the other type (the other comparand then gets a change to
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

    def _wrap_set_op(self, fun, arg):
        """Wrap built-in set operations for RangeSet to workaround built-in set
        base class issues (RangeSet.__new/init__ not called)"""
        result = fun(self, arg)
        result._autostep = self._autostep
        result.padding = self.padding
        return result

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
        return self._wrap_set_op(set.union, other)

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
        return self._wrap_set_op(set.intersection, other)

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
        return self._wrap_set_op(set.symmetric_difference, other)

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
        return self._wrap_set_op(set.difference, other)

    # Membership test

    def __contains__(self, element):
        """Report whether an element is a member of a RangeSet.
        Element can be either another RangeSet object, a string or an
        integer.

        Called in response to the expression ``element in self``.
        """
        if isinstance(element, set):
            return element.issubset(self)

        return set.__contains__(self, int(element))

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
            raise TypeError, "Binary operation only permitted between sets"

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
            raise KeyError(other.difference(self)[0])
        set.difference_update(self, other)

    # Python dict-like mass mutations: update, clear

    def update(self, iterable):
        """Add all integers from an iterable (such as a list)."""
        if isinstance(iterable, RangeSet):
            # keep padding unless it has not been defined yet
            if self.padding is None and iterable.padding is not None:
                self.padding = iterable.padding
        assert type(iterable) is not str
        set.update(self, iterable)

    def updaten(self, rangesets):
        """
        Update a rangeset with the union of itself and several others.
        """
        for rng in rangesets:
            if isinstance(rng, set):
                self.update(rng)
            else:
                self.update(RangeSet(rng))
            # py2.5+
            #self.update(rng if isinstance(rng, set) else RangeSet(rng))

    def clear(self):
        """Remove all elements from this RangeSet."""
        set.clear(self)
        self.padding = None

    # Single-element mutations: add, remove, discard

    def add(self, element, pad=0):
        """Add an element to a RangeSet.
        This has no effect if the element is already present.
        """
        set.add(self, int(element))
        if pad > 0 and self.padding is None:
            self.padding = pad

    def remove(self, element):
        """Remove an element from a RangeSet; it must be a member.

        :param element: the element to remove
        :raises KeyError: element is not contained in RangeSet
        :raises ValueError: element is not castable to integer
        """
        set.remove(self, int(element))

    def discard(self, element):
        """Remove element from the RangeSet if it is a member.

        If the element is not a member, do nothing.
        """
        try:
            i = int(element)
            set.discard(self, i)
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
                if type(rgvec[0]) is str:
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

    def __nonzero__(self):
        return bool(self._veclist)

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
        """Iterate through individual items as tuples with padding info."""
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
        pad_veclist = ((rg.padding for rg in vec) for vec in self._veclist)
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
            rnd = RangeSetND(iveclist[index],
                             pads=[rg.padding for rg in self._veclist[0]],
                             autostep=self.autostep)
            return rnd

        elif isinstance(index, int):
            # find a tuple of integer (multi-dimensional) at position index
            if index < 0:
                length = len(self)
                if index >= -length:
                    index = length + index
                else:
                    raise IndexError, "%d out of range" % index
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
            raise IndexError, "%d out of range" % index
        else:
            raise TypeError, \
                "%s indices must be integers" % self.__class__.__name__

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
            raise TypeError, \
                "Binary operation only permitted between RangeSetND"

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
        self._sort()
        # PHASE 2: merge
        self._fold_multivariate_merge()
        self._sort()
        self._dirty = False

    def _fold_multivariate_expand(self):
        """Multivariate nD folding: expand [phase 1]"""
        max_length = sum([reduce(mul, [len(rg) for rg in rgvec]) \
                                       for rgvec in self._veclist])
        # Simple heuristic that makes us faster
        if len(self._veclist) * (len(self._veclist) - 1) / 2 > max_length * 10:
            # *** nD full expand is preferred ***
            pads = self.pads()
            self._veclist = [[RangeSet.fromone(i, pad=pads[axis])
                              for axis, i in enumerate(tvec)]
                             for tvec in set(self._iter())]
            return

        # *** nD compare algorithm is preferred ***
        index1, index2 = 0, 1
        while (index1 + 1) < len(self._veclist):
            # use 2 references on iterator to compare items by couples
            item1 = self._veclist[index1]
            index2 = index1 + 1
            index1 += 1
            while index2 < len(self._veclist):
                item2 = self._veclist[index2]
                index2 += 1
                new_item = None
                disjoint = False
                suppl = []
                for pos, (rg1, rg2) in enumerate(zip(item1, item2)):
                    if not rg1 & rg2:
                        disjoint = True
                        break

                    if new_item is None:
                        new_item = [None] * len(item1)

                    if rg1 == rg2:
                        new_item[pos] = rg1
                    else:
                        assert rg1 & rg2
                        # intersection
                        new_item[pos] = rg1 & rg2
                        # create part 1
                        if rg1 - rg2:
                            item1_p = item1[0:pos] + [rg1 - rg2] + item1[pos+1:]
                            suppl.append(item1_p)
                        # create part 2
                        if rg2 - rg1:
                            item2_p = item2[0:pos] + [rg2 - rg1] + item2[pos+1:]
                            suppl.append(item2_p)
                if not disjoint:
                    assert new_item is not None
                    assert suppl is not None
                    item1 = self._veclist[index1 - 1] = new_item
                    index2 -= 1
                    self._veclist.pop(index2)
                    self._veclist += suppl

    def _fold_multivariate_merge(self):
        """Multivariate nD folding: merge [phase 2]"""
        chg = True
        while chg:
            chg = False
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

