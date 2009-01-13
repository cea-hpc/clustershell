# NodeSet.py -- Cluster shell nodeset representation
# Copyright (C) 2007, 2008 CEA
# Author: S. Thiell
#
# This file is part of shine
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
# $Id: NodeSet.py 26 2008-03-26 09:40:38Z st-cea $

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
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message

class RangeSetParseError(RangeSetException):
    """used by RangeSet when a parse cannot be done"""
    def __init__(self, subrange, message):
        # faulty subrange; this allows you to target the error
        self.message = "%s : \"%s\"" % (message, subrange)


class NodeSetException(Exception):
    """used by NodeSet"""
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message

class NodeSetParseError(NodeSetException):
    """used by NodeSet when a parse cannot be done"""
    def __init__(self, part, message):
        # faulty part; this allows you to target the error
        self.part = part
        self.message = message

class NodeSetParseRangeError(NodeSetParseError):
    """used by NodeSet when bad range is encountered during a a parse"""
    def __init__(self, rset_exc):
        # faulty part; this allows you to target the error
        self.message = rset_exc.message


class RangeSet:
    """
    Advanced range sets.

    RangeSet creation examples:
        rset = RangeSet()            # empty RangeSet
        rset = RangeSet("5,10-42")   # contains 5, 10 to 42
        rset = RangeSet("0-10/2")    # contains 0, 2, 4, 6, 8, 10
     
    Also, RangeSet provides update(), intersection_update() and
    difference_update() (exclusion) methods.
    """
    def __init__(self, pattern=None, autostep=None):
        """
        Initialize RangeSet with optional pdsh-like string pattern and
        autostep threshold.
        """
        if autostep is None:
            # disabled by default for pdsh compat (+inf)
            self._autostep = 1E400
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
                    if int(begin) != 0:
                        begins = begin.lstrip("0")
                    else:
                        begins = begin
                    if len(begin) - len(begins) > 0:
                        pad = len(begin)
                    else:
                        pad = 0
                    start = int(begins)
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
                            for j in range(istart, k + m, m):
                                rg.append((j, j, 1, pad))
                            istart = k = i
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

    def update(self, rangeset):
        """
        Add provided RangeSet.
        """
        for start, stop, step, pad in rangeset._ranges:
            self.add_range(start, stop, step, pad)

    def difference_update(self, rangeset):
        """
        Sub (exclude) provided RangeSet.
        """
        self._ranges, self._length = self._sub_exfold(rangeset)

    def _sub_exfold(self, rangeset):
        """
        Calc sub/exclusion with the expand/fold method.
        """
        # expand both rangesets
        items1, pad1 = self._expand()
        items2, pad2 = rangeset._expand()

        # create a temporary dict with keys from items2
        iset = dict.fromkeys(items2)

        # fold items that are in both sets
        return self._fold([e for e in items1 if e not in iset], pad1 or pad2)

    def intersection_update(self, rangeset):
        """
        Intersection with provided RangeSet.
        """
        self._ranges, self._length = self._intersect_exfold(rangeset)

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

                if len(node) == 0:
                    raise NodeSetParseError(pat, "empty node name")

                # single node parsing
                if single_node_re is None:
                    single_node_re = re.compile("(\D+)*(\d+)*(\S+)*")

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

    Also, NodeSet provides update(), intersection_update() and
    difference_update() (exclusion) methods. 
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
            self._patterns[pat] = rangeset

    def union(self, other):
        """
        s.union(t) returns a new set with elements from both s and t.
        """
        self_copy = copy.deepcopy(self)
        self_copy.update(other)
        return self_copy

    def __or__(self, other):
        """
        Implements the | operator. So s | t returns a new set with
        elements from both s and t.
        """
        if not isinstance(other, self.__class__):
            return NotImplemented
        return self.union(other)

    def update(self, other):
        """
        s.update(t) returns nodeset s with elements added from t.
        """
        for pat, rangeset in _NodeSetParse(other, self._autostep):
            self._add_rangeset(pat, rangeset)

    def __ior__(self, other):
        """
        Implements the |= operator. So s |= t returns nodeset s with
        elements added from t.
        """
        if not isinstance(other, self.__class__):
            return NotImplemented
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
        Implements the & operator. So s & t returns a new set with
        elements common to s and t.
        """
        if not isinstance(other, self.__class__):
            return NotImplemented
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
        only elements also found in t.
        """
        if not isinstance(other, self.__class__):
            return NotImplemented
        return self.intersection_update(other)

    def difference(self, other):
        """
        s.difference(t) returns a new set with elements in s but not in
        t.
        """
        self_copy = copy.deepcopy(self)
        self_copy.difference_update(other)
        return self_copy

    def __sub__(self, other):
        """
        Implement the - operator. So s - t returns a new set with
        elements in s but not in t.
        """
        if not isinstance(other, self.__class__):
            return NotImplemented
        return self.difference(other)

    def difference_update(self, other):
        """
        s.difference_update(t) returns nodeset s after removing
        elements found in t.
        """
        # the purge of each empty pattern is done afterward to allow self = ns
        purge_patterns = []

        # iterate first over exclude nodeset rangesets which is usually smaller
        for pat, erangeset in _NodeSetParse(other, self._autostep):
            # if pattern is found, deal with it
            rangeset = self._patterns.get(pat)
            if rangeset:
                # sub rangeset
                rangeset.difference_update(erangeset)
                # check if no range left and add pattern to purge list
                if len(rangeset) == 0:
                    purge_patterns.append(pat)
            else:
                # unnumbered node exclusion
                if self._patterns.has_key(pat):
                    purge_patterns.append(pat)

        for pat in purge_patterns:
            del self._patterns[pat]

    def __isub__(self, other):
        """
        Implement the -= operator. So s -= t returns nodeset s after
        removing elements found in t.
        """
        if not isinstance(other, self.__class__):
            return NotImplemented
        return self.difference_update(other)


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

