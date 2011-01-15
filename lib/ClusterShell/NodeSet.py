#
# Copyright CEA/DAM/DIF (2007, 2008, 2009, 2010)
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
#
# $Id$

"""
Cluster node set module.

A module to deal efficiently with 1D rangesets and nodesets (pdsh-like).
Instances of RangeSet and NodeSet both provide similar operations than
the builtin set() type and Set object.
See http://www.python.org/doc/lib/set-objects.html

Usage example
=============
  >>> # Import NodeSet class
  ... from ClusterShell.NodeSet import NodeSet
  >>>
  >>> # Create a new nodeset from string
  ... nodeset = NodeSet("cluster[1-30]")
  >>> # Add cluster32 to nodeset
  ... nodeset.update("cluster32")
  >>> # Remove from nodeset
  ... nodeset.difference_update("cluster[2-5]")
  >>> # Print nodeset as a pdsh-like pattern
  ... print nodeset
  cluster[1,6-30,32]
  >>> # Iterate over node names in nodeset
  ... for node in nodeset:
  ...     print node
  [...]
"""

import copy
import re
import sys

import ClusterShell.NodeUtils as NodeUtils


# Define default GroupResolver object used by NodeSet
DEF_GROUPS_CONFIG = "/etc/clustershell/groups.conf"
DEF_STD_GROUP_RESOLVER = NodeUtils.GroupResolverConfig(DEF_GROUPS_CONFIG)
STD_GROUP_RESOLVER = DEF_STD_GROUP_RESOLVER


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


class NodeSetException(Exception):
    """Base NodeSet exception class."""

class NodeSetParseError(NodeSetException):
    """Raised when NodeSet parsing cannot be done properly."""
    def __init__(self, part, msg):
        if part:
            msg = "%s : \"%s\"" % (msg, part)
        NodeSetException.__init__(self, msg)
        # faulty part; this allows you to target the error
        self.part = part

class NodeSetParseRangeError(NodeSetParseError):
    """Raised when bad range is encountered during NodeSet parsing."""
    def __init__(self, rset_exc):
        NodeSetParseError.__init__(self, str(rset_exc), "bad range")

class NodeSetExternalError(NodeSetException):
    """Raised when an external error is encountered."""


class RangeSet:
    """
    Advanced range sets.

    RangeSet creation examples:
       >>> rset = RangeSet()            # empty RangeSet
       >>> rset = RangeSet("5,10-42")   # contains 5, 10 to 42
       >>> rset = RangeSet("0-10/2")    # contains 0, 2, 4, 6, 8, 10
     
    Also, RangeSet provides methods like update(), intersection_update()
    or difference_update(), which conform to the Python Set API.
    """
    def __init__(self, pattern=None, autostep=None):
        """
        Initialize RangeSet with optional pdsh-like string pattern and
        autostep threshold.
        """
        if autostep is None:
            # disabled by default for pdsh compat (+inf is 1E400, but a bug in
            # python 2.4 makes it impossible to be pickled, so we use less).
            # NOTE: Later, we could consider sys.maxint here.
            self._autostep = 1E100
        else:
            # - 1 because user means node count, but we means
            # real steps.
            self._autostep = int(autostep) - 1

        self._length = 0
        self._ranges = []

        if pattern is not None:

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
                if start > stop or step < 1:
                    raise RangeSetParseError(subrange,
                            "invalid values in range")

                self.add_range(start, stop, step, pad)
        
    @classmethod
    def fromlist(cls, rnglist, autostep=None):
        """
        Class method that returns a new RangeSet with ranges from
        provided list.
        """
        inst = RangeSet(autostep=autostep)
        for rng in rnglist:
            if isinstance(rng, RangeSet):
                inst.update(rng)
            else:
                inst.update(RangeSet(rng))
        return inst

    @classmethod
    def fromone(cls, index, pad=0, autostep=None):
        """
        Class method that returns a new RangeSet of one single item.
        """
        inst = RangeSet(autostep=autostep)
        inst.add(index, pad)
        return inst

    def __iter__(self):
        """
        Iterate over each item in RangeSet.
        """
        for start, stop, step, pad in self._ranges:
            for i in range(start, stop + 1, step):
                yield "%*d" % (pad, i)

    def __len__(self):
        """
        Get the number of items in RangeSet.
        """
        return self._length

    def __str__(self):
        """
        Get range-based string.
        """
        cnt = 0
        res = ""
        for start, stop, step, pad in self._ranges:
            assert pad != None
            if cnt > 0:
                res += ","
            if start == stop:
                res += "%0*d" % (pad, start)
            else:
                assert step >= 0, "Internal error: step < 0"
                if step == 1:
                    res += "%0*d-%0*d" % (pad, start, pad, stop)
                else:
                    res += "%0*d-%0*d/%d" % (pad, start, pad, stop, step)
            cnt += stop - start + 1
        return res

    # __repr__ is the same as __str__ as it is a valid expression that
    # could be used to recreate a RangeSet with the same value
    __repr__ = __str__

    def __contains__(self, elem):
        """
        Is element contained in RangeSet? Element can be either a
        string with optional padding (eg. "002") or an integer
        (obviously, no padding check is performed for integer).
        """
        # support str type with padding support, eg. `"003" in rangeset'
        if type(elem) is str:
            pad = 0
            if int(elem) != 0:
                selem = elem.lstrip("0")
                if len(elem) - len(selem) > 0:
                    pad = len(elem)
                ielem = int(selem)
            else:
                if len(elem) > 1:
                    pad = len(elem)
                ielem = 0
            return self._contains_with_padding(ielem, pad)
        
        # the following cast raises TypeError if elem is not an integer
        return self._contains(int(elem))
    
    def _contains(self, ielem):
        """
        Contains subroutine that takes an integer.
        """
        for rgstart, rgstop, rgstep, rgpad in self._ranges:
            if ielem >= rgstart and ielem <= rgstop and \
                (ielem - rgstart) % rgstep == 0:
                return True
        return False

    def _contains_with_padding(self, ielem, pad):
        """
        Contains subroutine that takes an integer and a padding value.
        """
        for rgstart, rgstop, rgstep, rgpad in self._ranges:
            # for each ranges, check for inclusion + padding matching
            # + step matching
            if ielem >= rgstart and ielem <= rgstop and \
                (pad == rgpad or (pad == 0 and len(str(ielem)) >= rgpad)) and \
                (ielem - rgstart) % rgstep == 0:
                return True
        return False

    def _binary_sanity_check(self, other):
        # check that the other argument to a binary operation is also
        # a RangeSet, raising a TypeError otherwise.
        if not isinstance(other, RangeSet):
            raise TypeError, "Binary operation only permitted between RangeSets"

    def issubset(self, rangeset):
        """
        Report whether another rangeset contains this rangeset.
        """
        self._binary_sanity_check(rangeset)
        for start, stop, step, pad in self._ranges:
            for i in range(start, stop + 1, step):
                if not rangeset._contains_with_padding(i, pad):
                    return False
        return True

    def issuperset(self, rangeset):
        """
        Report whether this rangeset contains another rangeset.
        """
        self._binary_sanity_check(rangeset)
        return rangeset.issubset(self)

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
        
    # inequality comparisons using the is-subset relation
    __le__ = issubset
    __ge__ = issuperset

    def __lt__(self, other):
        """
        x.__lt__(y) <==> x<y
        """
        self._binary_sanity_check(other)
        return len(self) < len(other) and self.issubset(other)

    def __gt__(self, other):
        """
        x.__gt__(y) <==> x>y
        """
        self._binary_sanity_check(other)
        return len(self) > len(other) and self.issuperset(other)

    def __getitem__(self, index):
        """
        Return the element at index or a subrange when a slice is specified.
        """
        if isinstance(index, slice):
            inst = RangeSet(autostep=self._autostep)
            sl_start = sl_next = index.start or 0
            sl_stop = index.stop or sys.maxint
            sl_step = index.step or 1
            if not isinstance(sl_next, int) or not isinstance(sl_stop, int) \
                or not isinstance(sl_step, int):
                raise TypeError, "RangeSet slice indices must be integers"
            if sl_stop <= sl_next:
                return inst
            # get items from slice, O(n) algorithm for n = number of ranges
            length = 0
            for start, stop, step, pad in self._ranges:
                cnt =  (stop - start) / step + 1
                offset = sl_next - length
                if offset < cnt:
                    num = min(sl_stop - sl_next, cnt - offset)
                    inst.add_range(start + offset * step,
                                   start + (offset + num - 1) * step,
                                   sl_step * step,  # slice_step * range_step
                                   pad)
                    # adjust sl_next...
                    sl_next += num
                    if (sl_next - sl_start) % sl_step:
                        sl_next = sl_start + \
                            ((sl_next - sl_start)/sl_step + 1) * sl_step
                    if sl_next >= sl_stop:
                        return inst
                # else: skip until sl_next is reached
                length += cnt
            return inst
        elif isinstance(index, int):
            length = 0
            for start, stop, step, pad in self._ranges:
                cnt =  (stop - start) / step + 1
                if index < length + cnt:
                    return start + (index - length) * step
                length += cnt
            raise IndexError, "%d out of range" % index
        else:
            raise TypeError, "RangeSet indices must be integers"

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

    def _expand(self):
        """
        Expand all items. Internal use.
        """
        items = []
        pad = 0
        for rgstart, rgstop, rgstep, rgpad in self._ranges:
            items += range(rgstart, rgstop + 1, rgstep)
            pad = pad or rgpad
        return items, pad

    def _fold(self, items, pad):
        """
        Fold items as ranges and group them by step.
        Return: (ranges, total_length)
        """
        cnt, k, m, istart, rng = 0, -1, 0, None, []

        # iterate over items and regroup them using steps
        for i in items:
            if i > k:
                cnt += 1
                if istart is None:
                    istart = k = i
                elif m > 0: # check step length (m)
                    if m != i - k:
                        if m == 1 or k - istart >= self._autostep * m:
                            # add one range with possible autostep
                            rng.append((istart, k, m, pad))
                            istart = k = i
                        elif k - istart > m:
                            # stepped without autostep
                            # be careful to let the last one "pending"
                            for j in range(istart, k, m):
                                rng.append((j, j, 1, pad))
                            istart = k
                        else:
                            rng.append((istart, istart, 1, pad))
                            istart = k
                m = i - k
                k = i

        # finishing
        if istart is not None: # istart might be 0
            if m > 0:
                if m == 1 or k - istart >= self._autostep * m:
                    # add one range with possible autostep
                    rng.append((istart, k, m, pad))
                elif k - istart > m:
                    # stepped without autostep
                    for j in range(istart, k + m, m):
                        rng.append((j, j, 1, pad))
                else:
                    rng.append((istart, istart, 1, pad))
                    rng.append((k, k, 1, pad))
            else:
                rng.append((istart, istart, 1, pad))

        return rng, cnt

    def add_range(self, start, stop, step=1, pad=0):
        """
        Add a range (start, stop, step and padding length) to RangeSet.
        """
        assert start <= stop, "please provide ordered node index ranges"
        assert step > 0
        assert pad >= 0
        assert stop - start < 1e9, "range too large"

        if self._length == 0: # first-add switch
            stop_adjust = stop - (stop - start) % step
            if step == 1 or stop_adjust - start >= self._autostep * step:
                self._ranges = [ (start, stop_adjust, step, pad) ]
            else:
                # case: step > 1 and no proper autostep
                for j in range(start, stop_adjust + step, step):
                    self._ranges.append((j, j, step, pad))
            self._length = (stop_adjust - start) / step + 1
        elif step > 1:
            # use generic expand/fold method in that case
            self._add_range_exfold(start, stop, step, pad)
        else:
            # step == 1 specific method (no expand/folding if possible)
            self._add_range_inline(start, stop, step, pad)

    def _add_range_inline(self, start, stop, step, pad):
        """
        Add range without expanding then folding all items.
        """
        assert start <= stop, "please provide ordered node index ranges"
        assert step > 0
        assert pad >= 0

        new_ranges = []
        new_length = 0
        pstart = pstop = -1  # pending start and stop range
        included = False
        rgpad = 0

        # iterate over existing ranges
        for rgstart, rgstop, rgstep, rgpad in self._ranges:
            if rgstep > 1:
                # failback to generic method when step > 1 is found
                self._add_range_exfold(start, stop, step, pad)
                return
            # handle pending range...
            if rgstop <= pstop:
                # just gobble up smaller ranges
                continue
            if pstart >= 0:
                if pstop + 1 < rgstart:
                    # out of range: add pending range
                    new_ranges.append((pstart, pstop, 1, rgpad or pad))
                    new_length += pstop - pstart + 1
                else:
                    # in range: merge left by modifying rgstart
                    rgstart = pstart
                # invalidate pending range
                pstart = -1
            # out of range checks...
            if included or start > rgstop + 1:
                # simple case: just copy this range "as it"
                new_ranges.append((rgstart, rgstop, 1, rgpad or pad))
                new_length += rgstop - rgstart + 1
                continue
            elif stop + 1 < rgstart:
                # this range is greater than us and not mergeable:
                # add specified range and also this range "as it"
                new_ranges.append((start, stop, 1, rgpad or pad))
                new_ranges.append((rgstart, rgstop, 1, rgpad or pad))
                new_length += stop - start + rgstop - rgstart + 2
                included = True
                continue
            # we are "in range", set pending range
            pstart, pstop = min(rgstart, start), max(rgstop, stop)
            included = True

        # finish
        if not included:
            # specified range is greater that all ranges
            assert new_length == self._length
            new_ranges.append((start, stop, 1, rgpad or pad))
            new_length += stop - start + 1
        elif pstart >= 0:
            # do not forget pending range
            new_ranges.append((pstart, pstop, 1, rgpad or pad))
            new_length += pstop - pstart + 1

        # assign new values
        self._ranges = new_ranges
        self._length = new_length

    def _add_range_exfold(self, start, stop, step, pad):
        """
        Add range expanding then folding all items.
        """
        assert start <= stop, "please provide ordered node index ranges"
        assert step > 0
        assert pad >= 0

        items, rgpad = self._expand()
        items += range(start, stop + 1, step)
        items.sort()
        self._ranges, self._length = self._fold(items, pad or rgpad)

    def union(self, other):
        """
        s.union(t) returns a new rangeset with elements from both s and t.
        """
        self_copy = copy.deepcopy(self)
        self_copy.update(other)
        return self_copy

    def __or__(self, other):
        """
        Implements the | operator. So s | t returns a new rangeset with
        elements from both s and t.
        """
        if not isinstance(other, RangeSet):
            return NotImplemented
        return self.union(other)

    def add(self, elem, pad=0):
        """
        Add element to RangeSet.
        """
        self.add_range(elem, elem, step=1, pad=pad)

    def update(self, rangeset):
        """
        Update a rangeset with the union of itself and another.
        """
        for start, stop, step, pad in rangeset._ranges:
            self.add_range(start, stop, step, pad)

    def clear(self):
        """
        Remove all ranges from this rangeset.
        """
        self._ranges = []
        self._length = 0

    def __ior__(self, other):
        """
        Implements the |= operator. So s |= t returns rangeset s with
        elements added from t. (Python version 2.5+ required)
        """
        self._binary_sanity_check(other)
        return self.update(other)

    def intersection(self, rangeset):
        """
        s.intersection(t) returns a new rangeset with elements common
        to s and t.
        """
        self_copy = copy.deepcopy(self)
        self_copy.intersection_update(rangeset)
        return self_copy

    def __and__(self, other):
        """
        Implements the & operator. So s & t returns a new rangeset with
        elements common to s and t.
        """
        if not isinstance(other, RangeSet):
            return NotImplemented
        return self.intersection(other)

    def intersection_update(self, rangeset):
        """
        Intersection with provided RangeSet.
        """
        self._ranges, self._length = self._intersect_exfold(rangeset)

    def __iand__(self, other):
        """
        Implements the &= operator. So s &= t returns rangeset s keeping
        only elements also found in t. (Python version 2.5+ required)
        """
        self._binary_sanity_check(other)
        return self.intersection_update(other)

    def _intersect_exfold(self, rangeset):
        """
        Calc intersection with the expand/fold method.
        """
        # expand both rangesets
        items1, pad1 = self._expand()
        items2, pad2 = rangeset._expand()

        # create a temporary dict with keys from items2
        iset = dict.fromkeys(items2)

        # fold items that are in both sets
        return self._fold([e for e in items1 if e in iset], pad1 or pad2)

    def difference(self, rangeset):
        """
        s.difference(t) returns a new rangeset with elements in s but
        not in t.
        in t.
        """
        self_copy = copy.deepcopy(self)
        self_copy.difference_update(rangeset)
        return self_copy

    def __sub__(self, other):
        """
        Implement the - operator. So s - t returns a new rangeset with
        elements in s but not in t.
        """
        if not isinstance(other, RangeSet):
            return NotImplemented
        return self.difference(other)

    def difference_update(self, rangeset, strict=False):
        """
        s.difference_update(t) returns rangeset s after removing
        elements found in t. If strict is True, raise KeyError
        if an element cannot be removed.
        """
        self._ranges, self._length = self._sub_exfold(rangeset, strict)

    def __isub__(self, other):
        """
        Implement the -= operator. So s -= t returns rangeset s after
        removing elements found in t. (Python version 2.5+ required)
        """
        self._binary_sanity_check(other)
        return self.difference_update(other)

    def remove(self, elem):
        """
        Remove element elem from the RangeSet. Raise KeyError if elem
        is not contained in the RangeSet.
        """
        items1, pad1 = self._expand()

        try:
            items1.remove(elem)
        except ValueError:
            raise KeyError, elem

        self._ranges, self._length = self._fold(items1, pad1)

    def _sub_exfold(self, rangeset, strict):
        """
        Calc sub/exclusion with the expand/fold method. If strict is
        True, raise KeyError if the rangeset is not included.
        """
        # expand both rangesets
        items1, pad1 = self._expand()
        items2, pad2 = rangeset._expand()

        # create a temporary dict with keys from items2
        iset = dict.fromkeys(items2)

        if strict:
            # create a list of remaining items (lst) and update iset
            lst = []
            for e in items1:
                if e not in iset:
                    lst.append(e)
                else:
                    del iset[e]

            # if iset is not empty, some elements were not removed
            if len(iset) > 0:
                # give the user an indication of the range that cannot
                # be removed
                missing = RangeSet()
                missing._ranges, missing._length = self._fold(iset.keys(), pad2)
                # repr(missing) is implicit here
                raise KeyError, missing

            return self._fold(lst, pad1 or pad2)
        else:
            # fold items that are in set 1 and not in set 2
            return self._fold([e for e in items1 if e not in iset],
                              pad1 or pad2)

    def symmetric_difference(self, other):
        """
        s.symmetric_difference(t) returns the symmetric difference of
        two rangesets as a new RangeSet.
        
        (ie. all elements that are in exactly one of the rangesets.)
        """
        self_copy = copy.deepcopy(self)
        self_copy.symmetric_difference_update(other)
        return self_copy

    def __xor__(self, other):
        """
        Implement the ^ operator. So s ^ t returns a new rangeset with
        elements that are in exactly one of the rangesets.
        """
        if not isinstance(other, RangeSet):
            return NotImplemented
        return self.symmetric_difference(other)

    def symmetric_difference_update(self, rangeset):
        """
        s.symmetric_difference_update(t) returns rangeset s keeping all
        elements that are in exactly one of the rangesets.
        """
        self._ranges, self._length = self._xor_exfold(rangeset)

    def __ixor__(self, other):
        """
        Implement the ^= operator. So s ^= t returns rangeset s after
        keeping all elements that are in exactly one of the rangesets.
        (Python version 2.5+ required)
        """
        self._binary_sanity_check(other)
        return self.symmetric_difference_update(other)

    def _xor_exfold(self, rangeset):
        """
        Calc symmetric difference (xor).
        """
        # expand both rangesets
        items1, pad1 = self._expand()
        items2, pad2 = rangeset._expand()

        if pad1 != pad2:
            raise RangeSetPaddingError('', "%s != %s" % (pad1, pad2))
        # same padding, we're clean...

        # create a temporary dicts
        iset1 = dict.fromkeys(items1)
        iset2 = dict.fromkeys(items2)

        # keep items that are in one list only
        allitems = items1 + items2
        lst = [e for e in allitems if not e in iset1 or not e in iset2]
        lst.sort()

        return self._fold(lst, pad1)


class NodeSetBase(object):
    """
    Base class for NodeSet.
    """
    def __init__(self, pattern=None, rangeset=None):
        """
        Initialize an empty NodeSetBase.
        """
        self._length = 0
        self._patterns = {}
        if pattern:
            self._add(pattern, rangeset)
        elif rangeset:
            raise ValueError("missing pattern")

    def _iter(self):
        """
        Iterator on internal item tuples (pattern, index, padding).
        """
        for pat, rangeset in sorted(self._patterns.iteritems()):
            if rangeset:
                for start, stop, step, pad in rangeset._ranges:
                    for idx in xrange(start, stop + 1, step):
                        yield pat, idx, pad
            else:
                yield pat, None, None

    def _iterbase(self):
        """
        Iterator on single, one-item NodeSetBase objects.
        """
        for pat, start, pad in self._iter():
            if start is not None:
                yield NodeSetBase(pat, RangeSet.fromone(start, pad))
            else:
                yield NodeSetBase(pat) # no node index

    def __iter__(self):
        """
        Iterator on single nodes as string.
        """
        # Does not call self._iterbase() + str() for better performance.
        for pat, start, pad in self._iter():
            if start is not None:
                yield pat % ("%0*d" % (pad, start))
            else:
                yield pat

    def __len__(self):
        """
        Get the number of nodes in NodeSet.
        """
        cnt = 0
        for  rangeset in self._patterns.itervalues():
            if rangeset:
                cnt += len(rangeset)
            else:
                cnt += 1
        return cnt

    def __str__(self):
        """
        Get ranges-based pattern of node list.
        """
        result = ""
        for pat, rangeset in sorted(self._patterns.iteritems()):
            if rangeset:
                s = str(rangeset)
                cnt = len(rangeset)
                if cnt > 1:
                    s = "[" + s + "]"
                result += pat % s
            else:
                result += pat
            result += ","
        return result[:-1]

    def __contains__(self, other):
        """
        Is node contained in NodeSet ?
        """
        return self.issuperset(other)

    def _binary_sanity_check(self, other):
        # check that the other argument to a binary operation is also
        # a NodeSet, raising a TypeError otherwise.
        if not isinstance(other, NodeSetBase):
            raise TypeError, \
                "Binary operation only permitted between NodeSetBase"

    def issubset(self, other):
        """
        Report whether another nodeset contains this nodeset.
        """
        self._binary_sanity_check(other)
        return other.issuperset(self)

    def issuperset(self, other):
        """
        Report whether this nodeset contains another nodeset.
        """
        self._binary_sanity_check(other)
        status = True
        for pat, erangeset in other._patterns.iteritems():
            rangeset = self._patterns.get(pat)
            if rangeset:
                status = rangeset.issuperset(erangeset)
            else:
                # might be an unnumbered node (key in dict but no value)
                status = self._patterns.has_key(pat)
            if not status:
                break
        return status

    def __eq__(self, other):
        """
        NodeSet equality comparison.
        """
        # See comment for for RangeSet.__eq__()
        if not isinstance(other, NodeSetBase):
            return NotImplemented
        return len(self) == len(other) and self.issuperset(other)

    # inequality comparisons using the is-subset relation
    __le__ = issubset
    __ge__ = issuperset

    def __lt__(self, other):
        """
        x.__lt__(y) <==> x<y
        """
        self._binary_sanity_check(other)
        return len(self) < len(other) and self.issubset(other)

    def __gt__(self, other):
        """
        x.__gt__(y) <==> x>y
        """
        self._binary_sanity_check(other)
        return len(self) > len(other) and self.issuperset(other)

    def __getitem__(self, index):
        """
        Return the node at specified index or a subnodeset when a slice is
        specified.
        """
        if isinstance(index, slice):
            inst = NodeSetBase()
            sl_start = sl_next = index.start or 0
            sl_stop = index.stop or sys.maxint
            sl_step = index.step or 1
            if not isinstance(sl_next, int) or not isinstance(sl_stop, int) \
                or not isinstance(sl_step, int):
                raise TypeError, "NodeSet slice indices must be integers"
            if sl_stop <= sl_next:
                return inst
            length = 0
            for pat, rangeset in sorted(self._patterns.iteritems()):
                if rangeset:
                    cnt = len(rangeset)
                    offset = sl_next - length
                    if offset < cnt:
                        num = min(sl_stop - sl_next, cnt - offset)
                        inst._add(pat, rangeset[offset:offset + num:sl_step])
                    else:
                        #skip until sl_next is reached
                        length += cnt
                        continue
                else:
                    cnt = num = 1
                    if sl_next > length:
                        length += cnt
                        continue
                    inst._add(pat, None)
                # adjust sl_next...
                sl_next += num
                if (sl_next - sl_start) % sl_step:
                    sl_next = sl_start + \
                        ((sl_next - sl_start)/sl_step + 1) * sl_step
                if sl_next >= sl_stop:
                    break
                length += cnt
            return inst
        else:
            length = 0
            for pat, rangeset in sorted(self._patterns.iteritems()):
                if rangeset:
                    cnt = len(rangeset)
                    if index < length + cnt:
                        # return a subrangeset of size 1 to manage padding
                        return pat % rangeset[index - length:index - length + 1]
                else:
                    cnt = 1
                    if index == length:
                        return pat
                length += cnt
            raise IndexError, "%d out of range" % index

    def _add(self, pat, rangeset):
        """
        Add nodes from a (pat, rangeset) tuple. `pat' may be an existing
        pattern and `rangeset' may be None.
        """
        # get patterns dict entry
        pat_e = self._patterns.get(pat)

        if pat_e:
            # don't play with prefix: if there is a value, there is a
            # rangeset.
            assert rangeset != None

            # add rangeset in corresponding pattern rangeset
            pat_e.update(rangeset)
        else:
            # create new pattern (with possibly rangeset=None)
            self._patterns[pat] = copy.copy(rangeset)

    def union(self, other):
        """
        s.union(t) returns a new set with elements from both s and t.
        """
        self_copy = copy.deepcopy(self)
        self_copy.update(other)
        return self_copy

    def __or__(self, other):
        """
        Implements the | operator. So s | t returns a new nodeset with
        elements from both s and t.
        """
        if not isinstance(other, NodeSetBase):
            return NotImplemented
        return self.union(other)

    def add(self, other):
        """
        Add node to NodeSet.
        """
        self.update(other)

    def update(self, other):
        """
        s.update(t) returns nodeset s with elements added from t.
        """
        self._binary_sanity_check(other)

        for pat, rangeset in other._patterns.iteritems():
            self._add(pat, rangeset)

    def clear(self):
        """
        Remove all nodes from this nodeset.
        """
        self._patterns.clear()
        self._length = 0

    def __ior__(self, other):
        """
        Implements the |= operator. So s |= t returns nodeset s with
        elements added from t. (Python version 2.5+ required)
        """
        self._binary_sanity_check(other)
        return self.update(other)

    def intersection(self, other):
        """
        s.intersection(t) returns a new set with elements common to s
        and t.
        """
        self_copy = copy.deepcopy(self)
        self_copy.intersection_update(other)
        return self_copy

    def __and__(self, other):
        """
        Implements the & operator. So s & t returns a new nodeset with
        elements common to s and t.
        """
        if not isinstance(other, NodeSet):
            return NotImplemented
        return self.intersection(other)

    def intersection_update(self, other):
        """
        s.intersection_update(t) returns nodeset s keeping only
        elements also found in t.
        """
        self._binary_sanity_check(other)

        if other is self:
            return

        tmp_ns = NodeSetBase()

        for pat, irangeset in other._patterns.iteritems():
            rangeset = self._patterns.get(pat)
            if rangeset:
                rs = copy.copy(rangeset)
                rs.intersection_update(irangeset)
                # ignore pattern if empty rangeset
                if len(rs) > 0:
                    tmp_ns._add(pat, rs)
            elif not irangeset and pat in self._patterns:
                # intersect two nodes with no rangeset
                tmp_ns._add(pat, None)
            elif not irangeset and pat in self._patterns:
                # intersect two nodes with no rangeset
                tmp_ns._add(pat, None)

        # Substitute 
        self._patterns = tmp_ns._patterns

    def __iand__(self, other):
        """
        Implements the &= operator. So s &= t returns nodeset s keeping
        only elements also found in t. (Python version 2.5+ required)
        """
        self._binary_sanity_check(other)
        return self.intersection_update(other)

    def difference(self, other):
        """
        s.difference(t) returns a new NodeSet with elements in s but not
        in t.
        """
        self_copy = copy.deepcopy(self)
        self_copy.difference_update(other)
        return self_copy

    def __sub__(self, other):
        """
        Implement the - operator. So s - t returns a new nodeset with
        elements in s but not in t.
        """
        if not isinstance(other, NodeSetBase):
            return NotImplemented
        return self.difference(other)

    def difference_update(self, other, strict=False):
        """
        s.difference_update(t) returns nodeset s after removing
        elements found in t. If strict is True, raise KeyError
        if an element cannot be removed.
        """
        self._binary_sanity_check(other)
        # the purge of each empty pattern is done afterward to allow self = ns
        purge_patterns = []

        # iterate first over exclude nodeset rangesets which is usually smaller
        for pat, erangeset in other._patterns.iteritems():
            # if pattern is found, deal with it
            rangeset = self._patterns.get(pat)
            if rangeset:
                # sub rangeset, raise KeyError if not found
                rangeset.difference_update(erangeset, strict)

                # check if no range left and add pattern to purge list
                if len(rangeset) == 0:
                    purge_patterns.append(pat)
            else:
                # unnumbered node exclusion
                if self._patterns.has_key(pat):
                    purge_patterns.append(pat)
                elif strict:
                    raise KeyError, pat

        for pat in purge_patterns:
            del self._patterns[pat]

    def __isub__(self, other):
        """
        Implement the -= operator. So s -= t returns nodeset s after
        removing elements found in t. (Python version 2.5+ required)
        """
        self._binary_sanity_check(other)
        return self.difference_update(other)

    def remove(self, elem):
        """
        Remove element elem from the nodeset. Raise KeyError if elem
        is not contained in the nodeset.
        """
        self.difference_update(elem, True)

    def symmetric_difference(self, other):
        """
        s.symmetric_difference(t) returns the symmetric difference of
        two nodesets as a new NodeSet.
        
        (ie. all nodes that are in exactly one of the nodesets.)
        """
        self_copy = copy.deepcopy(self)
        self_copy.symmetric_difference_update(other)
        return self_copy

    def __xor__(self, other):
        """
        Implement the ^ operator. So s ^ t returns a new NodeSet with
        nodes that are in exactly one of the nodesets.
        """
        if not isinstance(other, NodeSet):
            return NotImplemented
        return self.symmetric_difference(other)

    def symmetric_difference_update(self, other):
        """
        s.symmetric_difference_update(t) returns nodeset s keeping all
        nodes that are in exactly one of the nodesets.
        """
        self._binary_sanity_check(other)
        purge_patterns = []

        # iterate over our rangesets
        for pat, rangeset in self._patterns.iteritems():
            brangeset = other._patterns.get(pat)
            if brangeset:
                rangeset.symmetric_difference_update(brangeset)
            else:
                if other._patterns.has_key(pat):
                    purge_patterns.append(pat)

        # iterate over other's rangesets
        for pat, brangeset in other._patterns.iteritems():
            rangeset = self._patterns.get(pat)
            if not rangeset and not self._patterns.has_key(pat):
                self._add(pat, brangeset)

        # check for patterns cleanup
        for pat, rangeset in self._patterns.iteritems():
            if rangeset is not None and len(rangeset) == 0:
                purge_patterns.append(pat)

        # cleanup
        for pat in purge_patterns:
            del self._patterns[pat]

    def __ixor__(self, other):
        """
        Implement the ^= operator. So s ^= t returns nodeset s after
        keeping all nodes that are in exactly one of the nodesets.
        (Python version 2.5+ required)
        """
        self._binary_sanity_check(other)
        return self.symmetric_difference_update(other)


class NodeGroupBase(NodeSetBase):
    """
    """
    def _add(self, pat, rangeset):
        """
        Add groups from a (pat, rangeset) tuple. `pat' may be an existing
        pattern and `rangeset' may be None.
        """
        if pat and pat[0] != '@':
            raise ValueError("NodeGroup name must begin with character '@'")
        NodeSetBase._add(self, pat, rangeset)


class ParsingEngine(object):
    """
    Class that is able to transform a source into a NodeSetBase.
    """
    OP_CODES = { 'update': ',',
                 'difference_update': '!',
                 'intersection_update': '&',
                 'symmetric_difference_update': '^' }

    def __init__(self, group_resolver):
        """
        Initialize Parsing Engine.
        """
        self.group_resolver = group_resolver
        self.single_node_re = re.compile("(\D*)(\d*)(.*)")

    def parse(self, nsobj, autostep):
        """
        Parse provided object if possible and return a NodeSetBase object.
        """
        # passing None is supported
        if nsobj is None:
            return NodeSetBase()

        # is nsobj a NodeSetBase instance?
        if isinstance(nsobj, NodeSetBase):
            return nsobj

        # or is nsobj a string?
        if type(nsobj) is str:
            try:
                return self.parse_string(str(nsobj), autostep)
            except NodeUtils.GroupSourceQueryFailed, exc:
                raise NodeSetParseError(nsobj, str(exc))

        raise TypeError("Unsupported NodeSet input %s" % type(nsobj))
        
    def parse_string(self, nsstr, autostep):
        """
        Parse provided string and return a NodeSetBase object.
        """
        nodeset = NodeSetBase()

        for opc, pat, rangeset in self._scan_string(nsstr, autostep):
            # Parser main debugging:
            #print "OPC %s PAT %s RANGESET %s" % (opc, pat, rangeset)
            if self.group_resolver and pat[0] == '@':
                ns_group = NodeSetBase()
                for nodegroup in NodeGroupBase(pat, rangeset):
                    # parse/expand nodes group
                    ns_string_ext = self.parse_group_string(nodegroup)
                    if ns_string_ext:
                        # convert result and apply operation
                        ns_group.update(self.parse(ns_string_ext, autostep))
                # perform operation
                getattr(nodeset, opc)(ns_group)
            else:
                getattr(nodeset, opc)(NodeSetBase(pat, rangeset))

        return nodeset
        
    def parse_group(self, group, namespace=None, autostep=None):
        """Parse provided single group name (without @ prefix)."""
        assert self.group_resolver is not None
        nodestr = self.group_resolver.group_nodes(group, namespace)
        return self.parse(",".join(nodestr), autostep)
        
    def parse_group_string(self, nodegroup):
        """Parse provided group string and return a string."""
        assert nodegroup[0] == '@'
        assert self.group_resolver is not None
        grpstr = nodegroup[1:]
        if grpstr.find(':') < 0:
            # default namespace
            return ",".join(self.group_resolver.group_nodes(grpstr))
        else:
            # specified namespace
            namespace, group = grpstr.split(':', 1)
            return ",".join(self.group_resolver.group_nodes(group, namespace))

    def _next_op(self, pat):
        """Opcode parsing subroutine."""
        op_idx = -1
        next_op_code = None
        for opc, idx in [(k, pat.find(v)) \
                            for k, v in ParsingEngine.OP_CODES.iteritems()]:
            if idx >= 0 and (op_idx < 0 or idx <= op_idx):
                next_op_code = opc
                op_idx = idx
        return op_idx, next_op_code

    def _scan_string(self, nsstr, autostep):
        """
        Parsing engine's string scanner method.
        """
        pat = nsstr.strip()
        # avoid misformatting
        if pat.find('%') >= 0:
            pat = pat.replace('%', '%%')
        next_op_code = 'update'
        while pat is not None:
            # Ignore whitespace(s) for convenience
            pat = pat.lstrip()

            op_code, next_op_code = next_op_code, None
            op_idx = -1
            op_idx, next_op_code = self._next_op(pat)
            bracket_idx = pat.find('[')

            # Check if the operator is after the bracket, or if there
            # is no operator at all but some brackets.
            if bracket_idx >= 0 and (op_idx > bracket_idx or op_idx < 0):
                # In this case, we have a pattern of potentially several
                # nodes.
                # Fill prefix, range and suffix from pattern
                # eg. "forbin[3,4-10]-ilo" -> "forbin", "3,4-10", "-ilo"
                pfx, sfx = pat.split('[', 1)
                try:
                    rng, sfx = sfx.split(']', 1)
                except ValueError:
                    raise NodeSetParseError(pat, "missing bracket")

                # Check if we have a next op-separated node or pattern
                op_idx, next_op_code = self._next_op(sfx)
                if op_idx < 0:
                    pat = None
                else:
                    sfx, pat = sfx.split(self.OP_CODES[next_op_code], 1)

                # Ignore whitespace(s)
                sfx = sfx.rstrip()

                # pfx + sfx cannot be empty
                if len(pfx) + len(sfx) == 0:
                    raise NodeSetParseError(pat, "empty node name")

                # Process comma-separated ranges
                try:
                    rset = RangeSet(rng, autostep)
                except RangeSetParseError, e:
                    raise NodeSetParseRangeError(e)

                yield op_code, "%s%%s%s" % (pfx, sfx), rset
            else:
                # In this case, either there is no comma and no bracket,
                # or the bracket is after the comma, then just return
                # the node.
                if op_idx < 0:
                    node = pat
                    pat = None # break next time
                else:
                    node, pat = pat.split(self.OP_CODES[next_op_code], 1)
                # Ignore whitespace(s)
                node = node.strip()

                if len(node) == 0:
                    raise NodeSetParseError(pat, "empty node name")

                # single node parsing
                mo = self.single_node_re.match(node)
                if not mo:
                    raise NodeSetParseError(pat, "parse error")
                pfx, idx, sfx = mo.groups()
                pfx, sfx = pfx or "", sfx or ""

                # pfx+sfx cannot be empty
                if len(pfx) + len(sfx) == 0:
                    raise NodeSetParseError(pat, "empty node name")

                if idx:
                    try:
                        rset = RangeSet(idx, autostep)
                    except RangeSetParseError, e:
                        raise NodeSetParseRangeError(e)
                    p = "%s%%s%s" % (pfx, sfx)
                    yield op_code, p, rset
                else:
                    # undefined pad means no node index
                    yield op_code, pfx, None


# Special constant for NodeSet's resolver parameter to avoid any group
# resolution at all.
NOGROUP_RESOLVER = -1


class NodeSet(NodeSetBase):
    """
    Iterable class of nodes with node ranges support.

    NodeSet creation examples:
       >>> nodeset = NodeSet()               # empty NodeSet
       >>> nodeset = NodeSet("cluster3")     # contains only cluster3
       >>> nodeset = NodeSet("cluster[5,10-42]")
       >>> nodeset = NodeSet("cluster[0-10/2]")
       >>> nodeset = NodeSet("cluster[0-10/2],othername[7-9,120-300]")

    NodeSet provides methods like update(), intersection_update() or
    difference_update() methods, which conform to the Python Set API.
    However, unlike RangeSet or standard Set, NodeSet is somewhat not
    so strict for convenience, and understands NodeSet instance or
    NodeSet string as argument. Also, there is no strict definition of
    one element, for example, it IS allowed to do:
        >>> nodeset.remove("blue[36-40]")

    Additionally, the NodeSet class recognizes the "extended string
    pattern" which adds support for union (special character ","),
    difference ("!"), intersection ("&") and symmetric difference ("^")
    operations. String patterns are read from left to right, by
    proceeding any character operators accordinately.

    Extended string pattern usage examples:
        >>> nodeset = NodeSet("node[0-10],node[14-16]") # union
        >>> nodeset = NodeSet("node[0-10]!node[8-10]")  # difference
        >>> nodeset = NodeSet("node[0-10]&node[5-13]")  # intersection
        >>> nodeset = NodeSet("node[0-10]^node[5-13]")  # xor
    """
    def __init__(self, nodes=None, autostep=None, resolver=None):
        """
        Initialize a NodeSet.
        The `nodes' argument may be a valid nodeset string or a NodeSet
        object. If no nodes are specified, an empty NodeSet is created.
        """
        NodeSetBase.__init__(self)

        self._autostep = autostep

        # Set group resolver.
        self._resolver = None
        if resolver != NOGROUP_RESOLVER:
            self._resolver = resolver or STD_GROUP_RESOLVER

        # Initialize default parser.
        self._parser = ParsingEngine(self._resolver)

        self.update(nodes)

    @classmethod
    def fromlist(cls, nodelist, autostep=None, resolver=None):
        """
        Class method that returns a new NodeSet with nodes from
        provided list.
        """
        inst = NodeSet(autostep=autostep, resolver=resolver)
        for node in nodelist:
            inst.update(node)
        return inst

    @classmethod
    def fromall(cls, groupsource=None, autostep=None, resolver=None):
        """
        Class method that returns a new NodeSet with all nodes from
        optional groupsource.
        """
        inst = NodeSet(autostep=autostep, resolver=resolver)
        if not inst._resolver:
            raise NodeSetExternalError("No node group resolver")
        try:
            # Ask resolver to provide all nodes.
            for nodes in inst._resolver.all_nodes(groupsource):
                inst.update(nodes)
        except NodeUtils.GroupSourceNoUpcall:
            # As the resolver is not able to provide all nodes directly,
            # failback to list + map(s) method:
            try:
                # Like in regroup(), we get a NodeSet of all groups in
                # specified group source.
                allgrpns = NodeSet.fromlist( \
                                inst._resolver.grouplist(groupsource),
                                resolver=NOGROUP_RESOLVER)
                # For each individual group, resolve it to node and accumulate.
                for grp in allgrpns:
                    inst.update(NodeSet.fromlist( \
                                inst._resolver.group_nodes(grp, groupsource)))
            except NodeUtils.GroupSourceNoUpcall:
                # We are not able to find "all" nodes, definitely.
                raise NodeSetExternalError("Not enough working external " \
                    "calls (all, or map + list) defined to get all nodes")
        except NodeUtils.GroupSourceQueryFailed, exc:
            raise NodeSetExternalError("Unable to get all nodes due to the " \
                "following external failure:\n\t%s" % exc)
        return inst

    def __getstate__(self):
        """Called when pickling: remove references to group resolver."""
        odict = self.__dict__.copy()
        del odict['_resolver']
        del odict['_parser']
        return odict

    def __setstate__(self, dic):
        """Called when unpickling: restore parser using non group
        resolver."""
        self.__dict__.update(dic)
        self._resolver = None
        self._parser = ParsingEngine(None)

    def _find_groups(self, node, namespace, allgroups):
        """Find groups of node by namespace."""
        if allgroups:
            # find node groups using in-memory allgroups
            for grp, nodeset in allgroups.iteritems():
                if node in nodeset:
                    yield grp
        else:
            # find node groups using resolver
            for group in self._resolver.node_groups(node, namespace):
                yield group

    def regroup(self, groupsource=None, autostep=None, overlap=False,
                noprefix=False):
        """
        Regroup nodeset using groups.
        """
        groups = {}
        rest = NodeSet(self, resolver=NOGROUP_RESOLVER)

        try:
            # Get a NodeSet of all groups in specified group source.
            allgrpns = NodeSet.fromlist(self._resolver.grouplist(groupsource),
                                        resolver=NOGROUP_RESOLVER)
        except NodeUtils.GroupSourceException:
            # If list query failed, we still might be able to regroup
            # using reverse.
            allgrpns = None

        allgroups = {}

        # Check for external reverse presence, and also use the
        # following heuristic: external reverse is used only when number
        # of groups is greater than the NodeSet size.
        if self._resolver.has_node_groups(groupsource) and \
            (not allgrpns or len(allgrpns) >= len(self)):
            # use external reverse
            pass
        else:
            if not allgrpns: # list query failed and no way to reverse!
                return str(rest)
            try:
                # use internal reverse: populate allgroups
                for grp in allgrpns:
                    nodelist = self._resolver.group_nodes(grp, groupsource)
                    allgroups[grp] = NodeSet(",".join(nodelist))
            except NodeUtils.GroupSourceQueryFailed, exc:
                # External result inconsistency
                raise NodeSetExternalError("Unable to map a group " \
                        "previously listed\n\tFailed command: %s" % exc)

        # For each NodeSetBase in self, finds its groups.
        for node in self._iterbase():
            for grp in self._find_groups(node, groupsource, allgroups):
                if grp not in groups:
                    nodes = self._parser.parse_group(grp, groupsource, autostep)
                    groups[grp] = (0, nodes)
                i, nodes = groups[grp]
                groups[grp] = (i + 1, nodes)
                
        # Keep only groups that are full.
        fulls = []
        for k, (i, nodes) in groups.iteritems():
            assert i <= len(nodes)
            if i == len(nodes):
                fulls.append((i, k))

        regrouped = NodeSet(resolver=NOGROUP_RESOLVER)

        bigalpha = lambda x, y: cmp(y[0], x[0]) or cmp(x[1], y[1])

        # Build regrouped NodeSet by selecting largest groups first.
        for num, grp in sorted(fulls, cmp=bigalpha):
            if not overlap and groups[grp][1] not in rest:
                continue
            if groupsource and not noprefix:
                regrouped.update("@%s:%s" % (groupsource, grp))
            else:
                regrouped.update("@" + grp)
            rest.difference_update(groups[grp][1])
            if not rest:
                return str(regrouped)

        if regrouped:
            return "%s,%s" % (regrouped, rest)

        return str(rest)

    def issubset(self, other):
        """
        Report whether another nodeset contains this nodeset.
        """
        nodeset = self._parser.parse(other, self._autostep)
        return NodeSetBase.issuperset(nodeset, self)

    def issuperset(self, other):
        """
        Report whether this nodeset contains another nodeset.
        """
        nodeset = self._parser.parse(other, self._autostep)
        return NodeSetBase.issuperset(self, nodeset)

    def __getitem__(self, index):
        """
        Return the node at specified index or a subnodeset when a slice
        is specified.
        """
        base = NodeSetBase.__getitem__(self, index)
        if not isinstance(base, NodeSetBase):
            return base
        # return a real NodeSet
        inst = NodeSet(autostep=self._autostep, resolver=self._resolver)
        inst._length = base._length
        inst._patterns = base._patterns
        return inst

    def split(self, nbr):
        """
        Split the nodeset into nbr sub-nodesets (at most). Each
        sub-nodeset will have the same number of elements more or
        less 1. Current nodeset remains unmodified.

        >>> NodeSet("foo[1-5]").split(3) 
        NodeSet("foo[1-2]")
        NodeSet("foo[3-4]")
        NodeSet("foo5")
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

    def update(self, other):
        """
        s.update(t) returns nodeset s with elements added from t.
        """
        nodeset = self._parser.parse(other, self._autostep)
        NodeSetBase.update(self, nodeset)

    def intersection_update(self, other):
        """
        s.intersection_update(t) returns nodeset s keeping only
        elements also found in t.
        """
        nodeset = self._parser.parse(other, self._autostep)
        NodeSetBase.intersection_update(self, nodeset)

    def difference_update(self, other, strict=False):
        """
        s.difference_update(t) returns nodeset s after removing
        elements found in t. If strict is True, raise KeyError
        if an element cannot be removed.
        """
        nodeset = self._parser.parse(other, self._autostep)
        NodeSetBase.difference_update(self, nodeset, strict)

    def symmetric_difference_update(self, other):
        """
        s.symmetric_difference_update(t) returns nodeset s keeping all
        nodes that are in exactly one of the nodesets.
        """
        nodeset = self._parser.parse(other, self._autostep)
        NodeSetBase.symmetric_difference_update(self, nodeset)


def expand(pat):
    """
    Commodity function that expands a pdsh-like pattern into a list of
    nodes.
    """
    return list(NodeSet(pat))

def fold(pat):
    """
    Commodity function that clean dups and fold provided pattern with
    ranges and "/step" support.
    """
    return str(NodeSet(pat))

def grouplist(namespace=None):
    """
    Commodity function that retrieves the list of groups for a specified
    group namespace (or use default namespace).
    """
    return STD_GROUP_RESOLVER.grouplist(namespace)


# doctest

def _test():
    import doctest
    doctest.testmod()

if __name__ == '__main__':
    _test()

