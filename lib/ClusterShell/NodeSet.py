# NodeSet.py -- Cluster shell nodeset representation
# Copyright (C) 2007, 2008, 2009 CEA
# Written by S. Thiell
#
# This file is part of ClusterShell
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
# $Id$

"""
Cluster node set.

A module to deal efficiently with pdsh-like rangesets and nodesets.
Instances of RangeSet and NodeSet both provide similar operations than
the builtin set() type and Set object.
   [ See http://www.python.org/doc/lib/set-objects.html ]

Usage example:

    # Import NodeSet class
    from ClusterShell.NodeSet import NodeSet

    # Create a new nodeset from pdsh-like pattern
    nodeset = NodeSet("cluster[1-30]")

    # Add cluster32 to nodeset
    nodeset.update("cluster32")

    # Remove from nodeset
    nodeset.difference_update("cluster[2-5]")

    # Print nodeset as a pdsh-like pattern
    print nodeset

    # Iterate over node names in nodeset
    for node in nodeset:
        print node
"""

import copy
import re

class RangeSetException(Exception):
    """used by RangeSet"""
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return self.msg

class RangeSetParseError(RangeSetException):
    """used by RangeSet when a parse cannot be done"""
    def __init__(self, subrange, msg):
        # faulty subrange; this allows you to target the error
        self.msg = "%s : \"%s\"" % (msg, subrange)

class RangeSetPaddingError(RangeSetException):
    """used by RangeSet when a fatal padding incoherency occurs"""


class NodeSetException(Exception):
    """used by NodeSet"""
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return self.msg

class NodeSetParseError(NodeSetException):
    """used by NodeSet when a parse cannot be done"""
    def __init__(self, part, msg):
        # faulty part; this allows you to target the error
        self.part = part
        self.msg = msg

class NodeSetParseRangeError(NodeSetParseError):
    """used by NodeSet when bad range is encountered during a a parse"""
    def __init__(self, rset_exc):
        # faulty part; this allows you to target the error
        self.msg = rset_exc.msg


class RangeSet:
    """
    Advanced range sets.

    RangeSet creation examples:
        rset = RangeSet()            # empty RangeSet
        rset = RangeSet("5,10-42")   # contains 5, 10 to 42
        rset = RangeSet("0-10/2")    # contains 0, 2, 4, 6, 8, 10
     
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
        
    def fromlist(cls, l, autostep=None):
        """
        Class method that returns a new RangeSet with ranges from
        provided list.
        """
        inst = RangeSet(autostep=autostep)
        for rg in l:
            if isinstance(rg, RangeSet):
                inst.update(rg)
            else:
                inst.update(RangeSet(rg))
        return inst
    fromlist = classmethod(fromlist)

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
        s = ""
        for start, stop, step, pad in self._ranges:
            assert pad != None
            if cnt > 0:
                s += ","
            if start == stop:
                s += "%0*d" % (pad, start)
            else:
                assert step >= 0, "Internal error: step < 0"
                if step == 1:
                    s += "%0*d-%0*d" % (pad, start, pad, stop)
                else:
                    s += "%0*d-%0*d/%d" % (pad, start, pad, stop, step)
            cnt += stop - start + 1
        return s

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

    def __getitem__(self, i):
        """
        Return the element at index i.
        """
        length = 0
        for start, stop, step, pad in self._ranges:
            cnt =  (stop - start) / step + 1
            if i < length + cnt:
                return start + (i - length) * step
            length += cnt

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
        cnt, k, m, istart, rg = 0, -1, 0, None, []

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
                            rg.append((istart, k, m, pad))
                            istart = k = i
                        elif k - istart > m:
                            # stepped without autostep
                            # be careful to let the last one "pending"
                            for j in range(istart, k, m):
                                rg.append((j, j, 1, pad))
                            istart = k
                        else:
                            rg.append((istart, istart, 1, pad))
                            istart = k
                m = i - k
                k = i

        # finishing
        if istart is not None: # istart might be 0
            if m > 0:
                if m == 1 or k - istart >= self._autostep * m:
                    # add one range with possible autostep
                    rg.append((istart, k, m, pad))
                elif k - istart > m:
                    # stepped without autostep
                    for j in range(istart, k + m, m):
                        rg.append((j, j, 1, pad))
                else:
                    rg.append((istart, istart, 1, pad))
                    rg.append((k, k, 1, pad))
            else:
                rg.append((istart, istart, 1, pad))

        return rg, cnt

    def add_range(self, start, stop, step=1, pad=0):
        """
        Add a range (start, stop, step and padding length) to RangeSet.
        """
        assert start <= stop, "please provide ordered node index ranges"
        assert step != None
        assert step > 0
        assert pad != None
        assert pad >= 0
        assert stop - start < 1e9, "range too large"

        if self._length == 0:
            # first add optimization
            stop_adjust = stop - (stop - start) % step
            if step == 1 or stop_adjust - start >= self._autostep * step:
                self._ranges = [ (start, stop_adjust, step, pad) ]
            else:
                for j in range(start, stop_adjust + step, step):
                    self._ranges.append((j, j, step, pad))
            self._length = (stop_adjust - start) / step + 1
        else:
            self._ranges, self._length = self._add_range_exfold(start, stop, \
                    step, pad)

    def _add_range_exfold(self, start, stop, step, pad):
        """
        Add range expanding then folding all items.
        """
        assert start <= stop, "please provide ordered node index ranges"
        assert step > 0
        assert pad != None
        assert pad >= 0

        items, rgpad = self._expand()
        items += range(start, stop + 1, step)
        items.sort()

        return self._fold(items, pad or rgpad)

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
        self._binary_sanity_check(other)
        return self.union(other)

    def add(self, elem):
        """
        Add element to RangeSet.
        """
        self.add_range(elem, elem, step=1, pad=0)

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
        self_copy.intersection_update(other)
        return self_copy

    def __and__(self, other):
        """
        Implements the & operator. So s & t returns a new rangeset with
        elements common to s and t.
        """
        self._binary_sanity_check(other)
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
        self_copy.difference_update(other)
        return self_copy

    def __sub__(self, other):
        """
        Implement the - operator. So s - t returns a new rangeset with
        elements in s but not in t.
        """
        self._binary_sanity_check(other)
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
        except ValueError, e:
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
                # give the user an indication of the range that cannot be removed
                missing = RangeSet()
                missing._ranges, missing._length = self._fold(iset.keys(), pad2)
                # repr(missing) is implicit here
                raise KeyError, missing

            return self._fold(lst, pad1 or pad2)
        else:
            # fold items that are in set 1 and not in set 2
            return self._fold([e for e in items1 if e not in iset], pad1 or pad2)

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
        self._binary_sanity_check(other)
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
            raise RangeSetPaddingError()
        # same padding, we're clean...

        # create a temporary dicts
        iset1 = dict.fromkeys(items1)
        iset2 = dict.fromkeys(items2)

        # keep items that are in one list only
        allitems = items1 + items2
        lst = [e for e in allitems if not e in iset1 or not e in iset2]
        lst.sort()

        return self._fold(lst, pad1)


def _NodeSetParse(ns, autostep):
    """
    Internal RangeSet generator for NodeSet or nodeset string pattern
    parsing.
    """
    # is ns a NodeSet instance?
    if isinstance(ns, NodeSet):
        for pat, rangeset in ns._patterns.iteritems():
            yield pat, rangeset
    # or is ns a string?
    elif type(ns) is str:
        single_node_re = None
        pat = str(ns)
        # avoid misformatting
        if pat.find('%') >= 0:
            pat = pat.replace('%', '%%')
        while pat is not None:
            # Ignore whitespace(s) for convenience
            pat = pat.lstrip()

            # What's first: a simple node or a pattern of nodes?
            comma_idx = pat.find(',')
            bracket_idx = pat.find('[')

            # Check if the comma is after the bracket, or if there
            # is no comma at all but some brackets.
            if bracket_idx >= 0 and (comma_idx > bracket_idx or comma_idx < 0):

                # In this case, we have a pattern of potentially several
                # nodes.

                # Fill prefix, range and suffix from pattern
                # eg. "forbin[3,4-10]-ilo" -> "forbin", "3,4-10", "-ilo"
                pfx, sfx = pat.split('[', 1)

                try:
                    rg, sfx = sfx.split(']', 1)
                except ValueError:
                    raise NodeSetParseError(pat, "missing bracket")

                # Check if we have a next comma-separated node or pattern
                if sfx.find(',') < 0:
                    pat = None
                else:
                    sfx, pat = sfx.split(',', 1)

                # Ignore whitespace(s)
                sfx = sfx.rstrip()

                # pfx + sfx cannot be empty
                if len(pfx) + len(sfx) == 0:
                    raise NodeSetParseError(pat, "empty node name")

                # Process comma-separated ranges
                try:
                    rset = RangeSet(rg, autostep)
                except RangeSetParseError, e:
                    raise NodeSetParseRangeError(e)

                yield "%s%%s%s" % (pfx, sfx), rset
            else:
                # In this case, either there is no comma and no bracket,
                # or the bracket is after the comma, then just return
                # the node.
                if comma_idx < 0:
                    node = pat
                    pat = None # break next time
                else:
                    node, pat = pat.split(',', 1)
                # Ignore whitespace(s)
                node = node.strip()

                if len(node) == 0:
                    raise NodeSetParseError(pat, "empty node name")

                # single node parsing
                if single_node_re is None:
                    single_node_re = re.compile("(\D*)(\d*)(.*)")

                mo = single_node_re.match(node)
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
                    yield p, rset
                else:
                    # undefined pad means no node index
                    yield pfx, None


class NodeSet(object):
    """
    Iterable class of nodes with node ranges support.

    NodeSet creation examples:
        nodeset = NodeSet()                   # empty NodeSet
        nodeset = NodeSet("clustername3")     # contains only clustername3
        nodeset = NodeSet("clustername[5,10-42]")
        nodeset = NodeSet("clustername[0-10/2]")
        nodeset = NodeSet("clustername[0-10/2],othername[7-9,120-300]")

    NodeSet provides methods like update(), intersection_update() or
    difference_update() methods, which conform to the Python Set API.
    However, unlike RangeSet or standard Set, NodeSet is somewhat not
    so strict for convenience, and understands NodeSet instance or
    NodeSet string as argument. Also, there is no strict definition of
    one element, for example, it IS allowed to do:
        nodeset.remove("blue[36-40]").
    """
    def __init__(self, pattern=None, autostep=None):
        """
        Initialize a NodeSet. If no pattern is specified, an empty
        NodeSet is created.
        """
        self._autostep = autostep
        self._length = 0
        self._patterns = {}
        if pattern is not None:
            self.update(pattern)

    def fromlist(cls, l, autostep=None):
        """
        Class method that returns a new NodeSet with nodes from
        provided list.
        """
        inst = NodeSet(autostep=autostep)
        for pat in l:
            inst.update(pat)
        return inst
    fromlist = classmethod(fromlist)

    def __iter__(self):
        """
        Iterate over concret nodes.
        """
        for pat, rangeset in self._patterns.iteritems():
            if rangeset:
                for start, stop, step, pad in rangeset._ranges:
                    while start <= stop:
                        yield pat % ("%0*d" % (pad, start))
                        start += step
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
        Get pdsh-like, ranges-based pattern of node list.
        """
        result = ""
        for pat, rangeset in self._patterns.iteritems():
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
        if not isinstance(other, NodeSet):
            raise TypeError, "Binary operation only permitted between NodeSets"

    def issubset(self, other):
        """
        Report whether another nodeset contains this nodeset.
        """
        binary = None

        # type check is needed for this case...
        if isinstance(other, NodeSet):
            binary = other
        elif type(other) is str:
            binary = NodeSet(other)
        else:
            raise TypeError, "Binary operation only permitted between NodeSets or string"

        return binary.issuperset(self)
        
    def issuperset(self, other):
        """
        Report whether this nodeset contains another nodeset.
        """
        status = False
        for pat, erangeset in _NodeSetParse(other, self._autostep):
            rangeset = self._patterns.get(pat)
            if rangeset:
                status = rangeset.issuperset(erangeset)
            else:
                # might be an unnumbered node (key in dict but no value)
                status = self._patterns.has_key(pat)
        return status

    # inequality comparisons using the is-subset relation
    __le__ = issubset
    __ge__ = issuperset

    def __lt__(self, other):
        """
        x.__lt__(y) <==> x<y
        """
        return len(self) < len(other) and self.issubset(other)

    def __gt__(self, other):
        """
        x.__gt__(y) <==> x>y
        """
        return len(self) > len(other) and self.issuperset(other)

    def __getitem__(self, i):
        """
        Return the node at index i. For convenience only, not
        optimized as of version 1.0.
        """
        return list(self)[i]

    def __getslice__(self, i, j):
        """
        Return the slice from index i to index j-1. For convenience
        only, not optimized as of version 1.0.
        """
        return NodeSet.fromlist(list(self)[i:j])

    def _add_rangeset(self, pat, rangeset):
        """
        Add a rangeset to a new or existing pattern.
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
        self._binary_sanity_check(other)
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
        for pat, rangeset in _NodeSetParse(other, self._autostep):
            self._add_rangeset(pat, rangeset)

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
        self._binary_sanity_check(other)
        return self.intersection(other)

    def intersection_update(self, other):
        """
        s.intersection_update(t) returns nodeset s keeping only
        elements also found in t.
        """
        if other is self:
            return

        tmp_ns = NodeSet()

        for pat, irangeset in _NodeSetParse(other, self._autostep):
            rangeset = self._patterns.get(pat)
            if rangeset:
                rs = copy.copy(rangeset)
                rs.intersection_update(irangeset)
                # ignore pattern if empty rangeset
                if len(rs) > 0:
                    tmp_ns._add_rangeset(pat, rs)

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
        self._binary_sanity_check(other)
        return self.difference(other)

    def difference_update(self, other, strict=False):
        """
        s.difference_update(t) returns nodeset s after removing
        elements found in t. If strict is True, raise KeyError
        if an element cannot be removed.
        """
        # the purge of each empty pattern is done afterward to allow self = ns
        purge_patterns = []

        # iterate first over exclude nodeset rangesets which is usually smaller
        for pat, erangeset in _NodeSetParse(other, self._autostep):
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
        self._binary_sanity_check(other)
        return self.symmetric_difference(other)

    def symmetric_difference_update(self, other):
        """
        s.symmetric_difference_update(t) returns nodeset s keeping all
        nodes that are in exactly one of the nodesets.
        """
        binary = None

        # type check is needed for this case...
        if isinstance(other, NodeSet):
            binary = other
        elif type(other) is str:
            binary = NodeSet(other)
        else:
            raise TypeError, "Binary operation only permitted between NodeSets or string"

        purge_patterns = []

        # iterate over our rangesets
        for pat, rangeset in self._patterns.iteritems():
            brangeset = binary._patterns.get(pat)
            if brangeset:
                rangeset.symmetric_difference_update(brangeset)
            else:
                if binary._patterns.has_key(pat):
                    purge_patterns.append(pat)

        # iterate over binary's rangesets
        for pat, brangeset in binary._patterns.iteritems():
            rangeset = self._patterns.get(pat)
            if not rangeset and not self._patterns.has_key(pat):
                self._add_rangeset(pat, brangeset)

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


# doctest

def _test():
    import doctest
    doctest.testmod()

if __name__ == '__main__':
    _test()

