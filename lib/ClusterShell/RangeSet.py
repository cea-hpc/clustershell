#
# Copyright CEA/DAM/DIF (2012)
#  Contributor: Stephane THIELL <stephane.thiell@cea.fr>
#
# This file is part of the ClusterShell library.
#
# This software is governed by the CeCILL-C license under French law and
# abiding by the rules of distribution of free software.  You can  use,
# modify and/ or redistribute the software under the terms of the CeCILL-C
# license as circulated by CEA, CNRS and INRIA at the following URL
# "http://www.cecill.info".
#
# As a counterpart to the access to the source code and  rights to copy,
# modify and redistribute granted by the license, users are provided only
# with a limited warranty  and the software's author,  the holder of the
# economic rights,  and the successive licensors  have only  limited
# liability.
#
# In this respect, the user's attention is drawn to the risks associated
# with loading,  using,  modifying and/or developing or reproducing the
# software by the user in light of its specific status of free software,
# that may mean  that it is complicated to manipulate,  and  that  also
# therefore means  that it is reserved for developers  and  experienced
# professionals having in-depth computer knowledge. Users are therefore
# encouraged to load and test the software's suitability as regards their
# requirements in conditions enabling the security of their systems and/or
# data to be ensured and,  more generally, to use and operate it in the
# same conditions as regards security.
#
# The fact that you are presently reading this means that you have had
# knowledge of the CeCILL-C license and that you accept its terms.

"""
Cluster range set module.

Instances of RangeSet provide similar operations than the builtin set type,
extended to support cluster ranges-like format and stepping support ("0-8/2").
"""

__all__ = ['RangeSetException',
           'RangeSetParseError',
           'RangeSetPaddingError',
           'RangeSet']


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
    sets and is used by the NodeSet class.

    RangeSet basic constructors:
       >>> rset = RangeSet()            # empty RangeSet
       >>> rset = RangeSet("5,10-42")   # contains 5, 10 to 42
       >>> rset = RangeSet("0-10/2")    # contains 0, 2, 4, 6, 8, 10

    Since v1.6, any iterable of integers can be specified as first argument:
       >>> RangeSet([3, 6, 8, 7, 1])
       1,3,6-8
       >>> rset2 = RangeSet(rset)

    Padding of ranges (eg. "003-009") can be managed through a public RangeSet
    instance variable named padding. It may be changed at any time. Since v1.6,
    padding is a simple display feature per RangeSet object, thus current
    padding value is not taken into account when computing set operations.
    Since v1.6, RangeSet is itself an iterator over its items as integers
    (instead of strings). To iterate over string items as before (with
    optional padding), you can now use the RangeSet.striter() method.

    RangeSet provides methods like union(), intersection(), difference(),
    symmetric_difference() and their in-place versions update(),
    intersection_update(), difference_update(),
    symmetric_difference_update() which conform to the Python Set API.
    """
    _VERSION = 3    # serial version number

    # define __new__() to workaround built-in set subclassing with Python 2.4
    def __new__(cls, pattern=None, autostep=None):
        """Object constructor"""
        return set.__new__(cls)
        
    def __init__(self, pattern=None, autostep=None):
        """Initialize RangeSet with optional string pattern and autostep
        threshold.
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
        self.autostep = autostep

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
                raise RangeSetParseError(subrange,
                        "cannot convert string to integer")

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
        if self._autostep >= 1E100:
            return None
        else:
            return self._autostep + 1

    def set_autostep(self, val):
        """Set autostep value (property)"""
        if val is None:
            # disabled by default for pdsh compat (+inf is 1E400, but a bug in
            # python 2.4 makes it impossible to be pickled, so we use less)
            # NOTE: Later, we could consider sys.maxint here
            self._autostep = 1E100
        else:
            # - 1 because user means node count, but we means real steps
            self._autostep = int(val) - 1

    autostep = property(get_autostep, set_autostep)
    
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
        """Internal generator that is able to retrieve ranges organized by step.
        Complexity: O(n) with n = number of ranges in tree."""
        if len(self) == 0:
            return

        prng = None         # pending range
        istart = None       # processing starting indice
        m = 0               # processing step
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
            elif m == 0:        # istart is set but step is unknown
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
            else:               # step m > 0
                assert m > 0
                i = start
                # does current range lead to broken step?
                if m != i - k or not unitary:
                    #j = i if m == i - k else k
                    if m == i - k: j = i
                    else: j = k
                    # stepped is True when autostep setting does apply
                    stepped = (j - istart >= self._autostep * m)
                    if prng:    # yield pending range?
                        if stepped:
                            prng[1] -= 1
                        else:
                            istart += m
                        yield slice(*prng)
                        prng = None
                if m != i - k:
                    # case: step value has changed
                    if stepped:
                        yield slice(istart, k + 1, m)
                    else:
                        for j in range(istart, k - m + 1, m):
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
                        # yield 'range/m' by taking first indice of new range
                        yield slice(istart, i + 1, m)
                        i += 1
                    else:
                        # autostep setting does not apply in that case
                        for j in range(istart, i - m + 1, m):
                            yield slice(j, j + 1, 1)
                    if stop > i + 1:    # current->pending only if not unitary
                        prng = [i, stop, 1]
                    istart = i = k = stop - 1
            m = i - k   # compute step
            k = i
        # exited loop, process pending range or indice...
        if m == 0:
            if prng:
                yield slice(*prng)
            else:
                yield slice(istart, istart + 1, 1)
        else:
            assert m > 0
            stepped = (k - istart >= self._autostep * m)
            if prng:
                if stepped:
                    prng[1] -= 1
                else:
                    istart += m
                yield slice(*prng)
                prng = None
            if stepped:
                yield slice(istart, i + 1, m)
            else:
                for j in range(istart, i + 1, m):
                    yield slice(j, j + 1, 1)

    def slices(self):
        """
        Iterate over RangeSet ranges as Python slice objects.
        """
        # return an iterator
        if self._autostep >= 1E100:
            return self._contiguous_slices()
        else:
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
        Like the Python built-in function range(), the last element is
        the largest start + i * step less than stop.
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

    def  __sub__(self, other):
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

        (Called in response to the expression `element in self'.)
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
            # keep padding unless is has not been defined yet
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
        
        Raise KeyError if element is not contained in RangeSet.
        Raise ValueError if element is not castable to integer.
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

