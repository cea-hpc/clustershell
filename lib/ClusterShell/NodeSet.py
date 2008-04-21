# NodeSet.py -- Cluster shell nodeset representation
# Copyright (C) 2007, 2008 CEA
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

import copy
import re

class _NodeSetPatternIterator:
    """
    NodeSet helper iterator class.
    """
    def __init__(self, pattern):
        self.single_node_re = re.compile("(\D+)(\d+)*(\S+)*")
        self.pat = pattern

    def __iter__(self):
        """
        Iterate over node rangesets.
        """
        while self.pat:

            # What's first: a simple node or a pattern of nodes?
            comma_idx = self.pat.find(',')
            bracket_idx = self.pat.find('[')

            # Check if the comma is after the bracket, or if there
            # is no comma at all but some brackets.
            if bracket_idx >= 0 and (comma_idx > bracket_idx or comma_idx < 0):

                # In this case, we have a pattern of potentially several nodes.

                # Fill prefix, range and suffix from pattern
                # eg. "forbin[3,4-10]-ilo" -> "forbin", "3,4-10", "-ilo"
                pfx, sfx = self.pat.split('[', 1)
                rg, sfx = sfx.split(']', 1)

                # Check if we have a next comma-separated node or pattern
                if sfx.find(',') < 0:
                    self.pat = None
                else:
                    sfx, self.pat = sfx.split(',', 1)

                # Process comma-separated ranges
                if rg.find(',') < 0:
                    subranges = [rg]
                else:
                    subranges = rg.split(',')

                for subrange in subranges:
                    if subrange.find('-') < 0:
                        begin = end = subrange
                    else:
                        begin, end = subrange.split('-', 1)

                    # Compute padding and return node range info tuple
                    begins = begin.lstrip("0")
                    if len(begin) - len(begins) > 0:
                        pad = len(begin)
                    else:
                        pad = 0
                    begin = int(begin)
                    end = int(end)
                    yield "%s%%s%s" % (pfx, sfx), pad, begin, end
            else:
                # In this case, either there is no comma and no bracket, or the
                # bracket is after the comma, then just return the node.
                if comma_idx < 0:
                    node = self.pat
                    self.pat = None # break next time
                else:
                    node, self.pat = self.pat.split(',', 1)
                #
                # single node parsing
                #
                mo = self.single_node_re.match(node)
                pfx, idx, sfx = mo.groups()
                sfx = sfx or ""
                if idx:
                    pat = "%s%%s%s" % (pfx, sfx)
                    idxs = idx.lstrip("0")
                    begin = int(idx)
                    if len(idx) - len(idxs) > 0:
                        pad = len(idx)
                    else:
                        pad = 0
                else:
                    # undefined pad means no node index
                    pat, begin, pad = pfx, 0, None
                end = begin # single node
                yield pat, pad, begin, end



class _NodeRangeSet:
    """
    Helper class to efficiently deal with range sets.
    """
    def __init__(self):
        self.ranges = []

    def __iter__(self):
        for start, stop, pad in self.ranges:
            yield start, stop, pad

    def __str__(self):
        return str(self.ranges)

    def add(self, start, stop, pad):
        assert start <= stop, "Confused: please provide ordered node index ranges"
        new_ranges = []
        rgpad = pad
        for rgstart, rgstop, rgpad in self.ranges:
            # Concatenate ranges...
            if start > rgstop + 1 or stop < rgstart - 1:
                # out of range, no change
                new_ranges.append((rgstart, rgstop, rgpad))
            elif start < rgstart:
                if stop < rgstop:
                    stop = rgstop
            elif stop > rgstop:
                start = rgstart
            else:
                # Already in, nothing to do!
                return
        # Add (possibly modified) new ranges
        new_ranges.append((start, stop, pad or rgpad))
        new_ranges.sort()
        self.ranges = new_ranges


class NodeSet:
    """
    Public iterable class of nodes with node ranges support.
    """
    def __init__(self, pattern=None):
        self.patterns = {}
        if pattern:
            self.add(pattern)

    def fromlist(cls, l):
        inst = NodeSet()
        for pat in l:
            inst.add(pat)
        return inst
    fromlist = classmethod(fromlist)

    def __iter__(self):
        """
        Iterate over concret nodes.
        """
        for pat, rangesets in self.patterns.iteritems():
            for start, stop, pad in rangesets:
                if pad is not None:
                    while start <= stop:
                        yield pat % ("%0*d" % (pad, start))
                        start += 1
                else:
                    yield pat

    def __len__(self):
        cnt = 0
        for pat, rangesets in self.patterns.iteritems():
            for start, stop, pad in rangesets:
                if pad is not None:
                    cnt += stop - start
                cnt += 1
        return cnt

    # Get range-based pattern
    def as_ranges(self):
        """
        Get pdsh-like, ranges-based pattern of node list.
        """
        result = ""
        for pat, rangesets in self.patterns.iteritems():
            cnt = 0
            s = ""
            for start, stop, pad in rangesets:
                if pad is not None:
                    if cnt > 0:
                        s += ","
                    if start == stop:
                        s += "%0*d" % (pad, start)
                    else:
                        s += "%0*d-%0*d" % (pad, start, pad, stop)
                    cnt += stop - start + 1
            if cnt > 1:
                s = "[" + s + "]"
            if cnt > 0:
                result += pat % s
            else:
                result += pat
            result += ","
        return result[:-1]
        
    def as_list(self):
        "Provided for completeness."
        return list(self)

    def add(self, other):
        """
        Add new pattern string : node, comma separated nodes, or pdsh-like pattern.
        """
        if isinstance(other, NodeSet):
            pattern = other.as_ranges()
        elif type(other) is str:
            pattern = str(other)

        for pat, pad, start, stop in _NodeSetPatternIterator(pattern):

            # Get dict entry or create a new one if needed.
            s = self.patterns.setdefault(pat, _NodeRangeSet())

            # Add new range in corresponding range set.
            s.add(start, stop, pad)

    def __add__(self, other):
        self_copy = copy.deepcopy(self)
        self_copy.add(other)
        return self_copy


def expand_nodes(pat):
    return list(NodeSet(pat))


# Sand box


"""

if __name__ == '__main__':

    nl = NodeSet("cors115,cors[116-119]")
    print nl.as_ranges()
    print nl.as_list()

    print list(nl)

    print expand_nodes("cors007,cors[001-002]")

    nl = NodeSet()
    nl.add("cws-cors")
    nl.add("cors007,cors[001-002]")
    nl2 = nl + "cors008"
    nl.add("cors007-ipmi")
    nl.add("cors007-ib0")
    nl.add("cors117")
    nl.add("cors117-ipmi")
    nl.add("cors34-ib0")
    nl.add("cors117-ib0")
    nl.add("cors116-ib0")
    nl.add("cors0113-ib0")
    nl.add("cors114-ib0")
    nl.add("cors1")
    nl.add("cors5")
    nl.add("cors[3-8]")
    nl.add("cors[9-80]")
    nl.add("cors[034-234]")
    nl.add("cors[3-8]-ipmi")
    nl.add("cors[9-80]-ipmi")
    nl.add("cors[032-134]")
    nl.add("cors[135-140]")

    print nl.as_ranges()
    print list(nl)

    print "---"
    print nl2.as_ranges()
    print list(nl2)


    for n in NodeSet("cors-mgr,cors[1-1000000]"):
        print n
"""


