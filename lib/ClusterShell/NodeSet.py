#
# Copyright CEA/DAM/DIF (2007, 2008, 2009, 2010, 2011, 2012, 2013, 2014)
#  Contributor: Stephane THIELL <stephane.thiell@cea.fr>
#  Contributor: Aurelien DEGREMONT <aurelien.degremont@cea.fr>
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
Cluster node set module.

A module to efficiently deal with node sets and node groups.
Instances of NodeSet provide similar operations than the builtin set() type,
see http://www.python.org/doc/lib/set-objects.html

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
  ... nodeset.difference_update("cluster[2-5,8-31]")
  >>> # Print nodeset as a pdsh-like pattern
  ... print nodeset
  cluster[1,6-7,32]
  >>> # Iterate over node names in nodeset
  ... for node in nodeset:
  ...     print node
  cluster1
  cluster6
  cluster7
  cluster32
"""

import re
import sys

import ClusterShell.NodeUtils as NodeUtils
from ClusterShell.RangeSet import RangeSet, RangeSetND, RangeSetParseError


# Define default GroupResolver object used by NodeSet
DEF_GROUPS_CONFIG = "/etc/clustershell/groups.conf"
ILLEGAL_GROUP_CHARS = set("@,!&^*")
_DEF_RESOLVER_STD_GROUP = NodeUtils.GroupResolverConfig(DEF_GROUPS_CONFIG, \
                                                        ILLEGAL_GROUP_CHARS)
# Standard group resolver
RESOLVER_STD_GROUP = _DEF_RESOLVER_STD_GROUP
# Special constants for NodeSet's resolver parameter
#   RESOLVER_NOGROUP => avoid any group resolution at all
#   RESOLVER_NOINIT  => reserved use for optimized copy()
RESOLVER_NOGROUP = -1
RESOLVER_NOINIT  = -2
# 1.5 compat (deprecated)
STD_GROUP_RESOLVER = RESOLVER_STD_GROUP
NOGROUP_RESOLVER = RESOLVER_NOGROUP


class NodeSetException(Exception):
    """Base NodeSet exception class."""

class NodeSetError(NodeSetException):
    """Raised when an error is encountered."""

class NodeSetParseError(NodeSetError):
    """Raised when NodeSet parsing cannot be done properly."""
    def __init__(self, part, msg):
        if part:
            msg = "%s : \"%s\"" % (msg, part)
        NodeSetError.__init__(self, msg)
        # faulty part; this allows you to target the error
        self.part = part

class NodeSetParseRangeError(NodeSetParseError):
    """Raised when bad range is encountered during NodeSet parsing."""
    def __init__(self, rset_exc):
        NodeSetParseError.__init__(self, str(rset_exc), "bad range")

class NodeSetExternalError(NodeSetError):
    """Raised when an external error is encountered."""


class NodeSetBase(object):
    """
    Base class for NodeSet.

    This class allows node set base object creation from specified string
    pattern and rangeset object.  If optional copy_rangeset boolean flag is
    set to True (default), provided rangeset object is copied (if needed),
    otherwise it may be referenced (should be seen as an ownership transfer
    upon creation).

    This class implements core node set arithmetics (no string parsing here).

    Example:
       >>> nsb = NodeSetBase('node%s-ipmi', RangeSet('1-5,7'), False)
       >>> str(nsb)
       'node[1-5,7]-ipmi'
       >>> nsb = NodeSetBase('node%s-ib%s', RangeSetND([['1-5,7', '1-2']]), False)
       >>> str(nsb)
       'node[1-5,7]-ib[1-2]'
    """
    def __init__(self, pattern=None, rangeset=None, copy_rangeset=True):
        """New NodeSetBase object initializer"""
        self._length = 0
        self._patterns = {}
        if pattern:
            self._add(pattern, rangeset, copy_rangeset)
        elif rangeset:
            raise ValueError("missing pattern")

    def _iter(self):
        """Iterator on internal item tuples
            (pattern, indexes, padding, autostep)."""
        for pat, rset in sorted(self._patterns.iteritems()):
            if rset:
                autostep = rset.autostep
                if rset.dim() == 1:
                    assert isinstance(rset, RangeSet)
                    padding = rset.padding
                    for idx in rset:
                        yield pat, (idx,), (padding,), autostep
                else:
                    for args, padding in rset.iter_padding():
                        yield pat, args, padding, autostep
            else:
                yield pat, None, None, None

    def _iterbase(self):
        """Iterator on single, one-item NodeSetBase objects."""
        for pat, ivec, pad, autostep in self._iter():
            rset = None     # 'no node index' by default
            if ivec is not None:
                assert len(ivec) > 0
                if len(ivec) == 1:
                    rset = RangeSet.fromone(ivec[0], pad[0] or 0, autostep)
                else:
                    rset = RangeSetND([ivec], pad, autostep)
            yield NodeSetBase(pat, rset)

    def __iter__(self):
        """Iterator on single nodes as string."""
        # Does not call self._iterbase() + str() for better performance.
        for pat, ivec, pads, _ in self._iter():
            if ivec is not None:
                # For performance reasons, add a special case for 1D RangeSet
                if len(ivec) == 1:
                    yield pat % ("%0*d" % (pads[0] or 0, ivec[0]))
                else:
                    yield pat % tuple(["%0*d" % (pad or 0, i) \
                                      for pad, i in zip(pads, ivec)])
            else:
                yield pat

    # define striter() alias for convenience (to match RangeSet.striter())
    striter = __iter__

    # define nsiter() as an object-based iterator that could be used for
    # __iter__() in the future...

    def nsiter(self):
        """Object-based NodeSet iterator on single nodes."""
        for pat, ivec, pad, autostep in self._iter():
            nodeset = self.__class__()
            if ivec is not None:
                if len(ivec) == 1:
                    nodeset._add_new(pat, \
                                     RangeSet.fromone(ivec[0], pad[0] or 0))
                else:
                    nodeset._add_new(pat, RangeSetND([ivec], None, autostep))
            else:
                nodeset._add_new(pat, None)
            yield nodeset

    def contiguous(self):
        """Object-based NodeSet iterator on contiguous node sets.

        Contiguous node set contains nodes with same pattern name and a
        contiguous range of indexes, like foobar[1-100]."""
        for pat, rangeset in sorted(self._patterns.iteritems()):
            if rangeset:
                for cont_rset in rangeset.contiguous():
                    nodeset = self.__class__()
                    nodeset._add_new(pat, cont_rset)
                    yield nodeset
            else:
                nodeset = self.__class__()
                nodeset._add_new(pat, None)
                yield nodeset

    def __len__(self):
        """Get the number of nodes in NodeSet."""
        cnt = 0
        for rangeset in self._patterns.itervalues():
            if rangeset:
                cnt += len(rangeset)
            else:
                cnt += 1
        return cnt

    def __str__(self):
        """Get ranges-based pattern of node list."""
        results = []
        for pat, rset in sorted(self._patterns.iteritems()):
            if rset:
                if rset.dim() > 1:
                    # nD
                    for rgvec in rset.vectors():
                        rgargs = []
                        for rangeset in rgvec:
                            rgs = str(rangeset)
                            cnt = len(rangeset)
                            if cnt > 1:
                                rgs = "[%s]" % rgs
                            rgargs.append(rgs)
                        try:
                            results.append(pat % tuple(rgargs))
                        except TypeError:
                            raise NodeSetParseError(pat, \
                                "node pattern and nD ranges mismatch")
                else:
                    # 1D
                    rgs = str(rset)
                    cnt = len(rset)
                    if cnt > 1:
                        rgs = "[%s]" % rgs
                    results.append(pat % rgs)
            else:
                results.append(pat)
        return ",".join(results)

    def copy(self):
        """Return a shallow copy."""
        cpy = self.__class__()
        cpy._length = self._length
        dic = {}
        for pat, rangeset in self._patterns.iteritems():
            if rangeset is None:
                dic[pat] = None
            else:
                dic[pat] = rangeset.copy()
        cpy._patterns = dic
        return cpy

    def __contains__(self, other):
        """Is node contained in NodeSet ?"""
        return self.issuperset(other)

    def _binary_sanity_check(self, other):
        # check that the other argument to a binary operation is also
        # a NodeSet, raising a TypeError otherwise.
        if not isinstance(other, NodeSetBase):
            raise TypeError, \
                "Binary operation only permitted between NodeSetBase"

    def issubset(self, other):
        """Report whether another nodeset contains this nodeset."""
        self._binary_sanity_check(other)
        return other.issuperset(self)

    def issuperset(self, other):
        """Report whether this nodeset contains another nodeset."""
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
        """NodeSet equality comparison."""
        # See comment for for RangeSet.__eq__()
        if not isinstance(other, NodeSetBase):
            return NotImplemented
        return len(self) == len(other) and self.issuperset(other)

    # inequality comparisons using the is-subset relation
    __le__ = issubset
    __ge__ = issuperset

    def __lt__(self, other):
        """x.__lt__(y) <==> x<y"""
        self._binary_sanity_check(other)
        return len(self) < len(other) and self.issubset(other)

    def __gt__(self, other):
        """x.__gt__(y) <==> x>y"""
        self._binary_sanity_check(other)
        return len(self) > len(other) and self.issuperset(other)

    def _extractslice(self, index):
        """Private utility function: extract slice parameters from slice object
        `index` for an list-like object of size `length`."""
        length = len(self)
        if index.start is None:
            sl_start = 0
        elif index.start < 0:
            sl_start = max(0, length + index.start)
        else:
            sl_start = index.start
        if index.stop is None:
            sl_stop = sys.maxint
        elif index.stop < 0:
            sl_stop = max(0, length + index.stop)
        else:
            sl_stop = index.stop
        if index.step is None:
            sl_step = 1
        elif index.step < 0:
            # We support negative step slicing with no start/stop, ie. r[::-n].
            if index.start is not None or index.stop is not None:
                raise IndexError, \
                    "illegal start and stop when negative step is used"
            # As RangeSet elements are ordered internally, adjust sl_start
            # to fake backward stepping in case of negative slice step.
            stepmod = (length + -index.step - 1) % -index.step
            if stepmod > 0:
                sl_start += stepmod
            sl_step = -index.step
        else:
            sl_step = index.step
        if not isinstance(sl_start, int) or not isinstance(sl_stop, int) \
            or not isinstance(sl_step, int):
            raise TypeError, "slice indices must be integers"
        return sl_start, sl_stop, sl_step

    def __getitem__(self, index):
        """Return the node at specified index or a subnodeset when a slice is
        specified."""
        if isinstance(index, slice):
            inst = NodeSetBase()
            sl_start, sl_stop, sl_step = self._extractslice(index)
            sl_next = sl_start
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
        elif isinstance(index, int):
            if index < 0:
                length = len(self)
                if index >= -length:
                    index = length + index # - -index
                else:
                    raise IndexError, "%d out of range" % index
            length = 0
            for pat, rangeset in sorted(self._patterns.iteritems()):
                if rangeset:
                    cnt = len(rangeset)
                    if index < length + cnt:
                        # return a subrangeset of size 1 to manage padding
                        if rangeset.dim() == 1:
                            return pat % rangeset[index-length:index-length+1]
                        else:
                            sub = rangeset[index-length:index-length+1]
                            for rgvec in sub.vectors():
                                return pat % (tuple(rgvec))
                else:
                    cnt = 1
                    if index == length:
                        return pat
                length += cnt
            raise IndexError, "%d out of range" % index
        else:
            raise TypeError, "NodeSet indices must be integers"

    def _add_new(self, pat, rangeset):
        """Add nodes from a (pat, rangeset) tuple.
        Predicate: pattern does not exist in current set. RangeSet object is
        referenced (not copied)."""
        assert pat not in self._patterns
        self._patterns[pat] = rangeset

    def _add(self, pat, rangeset, copy_rangeset=True):
        """Add nodes from a (pat, rangeset) tuple.
        `pat' may be an existing pattern and `rangeset' may be None.
        RangeSet or RangeSetND objects are copied if re-used internally
        when provided and if copy_rangesets flag is set.
        """
        if pat in self._patterns:
            # existing pattern: get RangeSet or RangeSetND entry...
            pat_e = self._patterns[pat]
            # sanity checks
            if (pat_e is None) is not (rangeset is None):
                raise NodeSetError("Invalid operation")
            # entry may exist but set to None (single node)
            if pat_e:
                pat_e.update(rangeset)
        else:
            # new pattern...
            if rangeset and copy_rangeset:
                rangeset = rangeset.copy()
            self._add_new(pat, rangeset)

    def union(self, other):
        """
        s.union(t) returns a new set with elements from both s and t.
        """
        self_copy = self.copy()
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
        for pat, rangeset in other._patterns.iteritems():
            self._add(pat, rangeset)

    def updaten(self, others):
        """
        s.updaten(list) returns nodeset s with elements added from given list.
        """
        for other in others:
            self.update(other)

    def clear(self):
        """
        Remove all nodes from this nodeset.
        """
        self._patterns.clear()

    def __ior__(self, other):
        """
        Implements the |= operator. So s |= t returns nodeset s with
        elements added from t. (Python version 2.5+ required)
        """
        self._binary_sanity_check(other)
        self.update(other)
        return self

    def intersection(self, other):
        """
        s.intersection(t) returns a new set with elements common to s
        and t.
        """
        self_copy = self.copy()
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
        if other is self:
            return

        tmp_ns = NodeSetBase()

        for pat, irangeset in other._patterns.iteritems():
            rangeset = self._patterns.get(pat)
            if rangeset:
                irset = rangeset.intersection(irangeset)
                # ignore pattern if empty rangeset
                if len(irset) > 0:
                    tmp_ns._add(pat, irset, copy_rangeset=False)
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
        self.intersection_update(other)
        return self

    def difference(self, other):
        """
        s.difference(t) returns a new NodeSet with elements in s but not
        in t.
        """
        self_copy = self.copy()
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
        self.difference_update(other)
        return self

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
        self_copy = self.copy()
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
            if not rangeset and not pat in self._patterns:
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
        self.symmetric_difference_update(other)
        return self


class NodeGroupBase(NodeSetBase):
    """NodeGroupBase aims to ease node group names management."""
    def _add(self, pat, rangeset, copy_rangeset=True):
        """
        Add groups from a (pat, rangeset) tuple. `pat' may be an existing
        pattern and `rangeset' may be None.
        """
        if pat and pat[0] != '@':
            raise ValueError("NodeGroup name must begin with character '@'")
        NodeSetBase._add(self, pat, rangeset, copy_rangeset)


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
        self.base_node_re = re.compile("(\D*)(\d*)")

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

        for opc, pat, rgnd in self._scan_string(nsstr, autostep):
            # Parser main debugging:
            #print "OPC %s PAT %s RANGESETS %s" % (opc, pat, rgnd)
            if self.group_resolver and pat[0] == '@':
                ns_group = NodeSetBase()
                for nodegroup in NodeGroupBase(pat, rgnd):
                    # parse/expand nodes group
                    ns_string_ext = self.parse_group_string(nodegroup)
                    if ns_string_ext:
                        # convert result and apply operation
                        ns_group.update(self.parse(ns_string_ext, autostep))
                # perform operation
                getattr(nodeset, opc)(ns_group)
            else:
                getattr(nodeset, opc)(NodeSetBase(pat, rgnd, False))

        return nodeset
        
    def parse_string_single(self, nsstr, autostep):
        """Parse provided string and return a NodeSetBase object."""
        pat, rangesets = self._scan_string_single(nsstr, autostep)
        if len(rangesets) > 1:
            rgobj = RangeSetND([rangesets], None, autostep, copy_rangeset=False)
        elif len(rangesets) == 1:
            rgobj = rangesets[0]
        else: # non-indexed nodename
            rgobj = None
        return NodeSetBase(pat, rgobj, False)
        
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
            if grpstr == '*':
                return ",".join(self.group_resolver.all_nodes())
            return ",".join(self.group_resolver.group_nodes(grpstr))
        else:
            # specified namespace
            namespace, group = grpstr.split(':', 1)
            if group == '*':
                return ",".join(self.group_resolver.all_nodes(namespace))
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

    def _scan_string_single(self, nsstr, autostep):
        """Single node scan, returns (pat, list of rangesets)"""
        # ignore whitespace(s)
        node = nsstr.strip()
        if len(node) == 0:
            raise NodeSetParseError(nsstr, "empty node name")

        # single node parsing
        pfx_nd = [mobj.groups() for mobj in self.base_node_re.finditer(node)]
        pfx_nd = pfx_nd[:-1]
        if not pfx_nd:
            raise NodeSetParseError(node, "parse error")

        # pfx+sfx cannot be empty
        if len(pfx_nd) == 1 and len(pfx_nd[0][0]) == 0:
            raise NodeSetParseError(node, "empty node name")

        pat = ""
        rangesets = []
        for pfx, idx in pfx_nd:
            if idx:
                # optimization: process single index padding directly
                pad = 0
                if int(idx) != 0:
                    idxs = idx.lstrip("0")
                    if len(idx) - len(idxs) > 0:
                        pad = len(idx)
                    idxint = int(idxs)
                else:
                    if len(idx) > 1:
                        pad = len(idx)
                    idxint = 0
                if idxint > 1e100:
                    raise NodeSetParseRangeError( \
                        RangeSetParseError(idx, "invalid rangeset index"))
                # optimization: use numerical RangeSet constructor
                pat += "%s%%s" % pfx
                rangesets.append(RangeSet.fromone(idxint, pad, autostep))
            else:
                # undefined pad means no node index
                pat += pfx
        return pat, rangesets
    
    def _scan_string(self, nsstr, autostep):
        """Parsing engine's string scanner method (iterator)."""
        pat = nsstr.strip()
        # avoid misformatting
        if pat.find('%') >= 0:
            pat = pat.replace('%', '%%')
        next_op_code = 'update'
        while pat is not None:
            # Ignore whitespace(s) for convenience
            pat = pat.lstrip()

            rsets = []
            op_code = next_op_code

            op_idx, next_op_code = self._next_op(pat)
            bracket_idx = pat.find('[')

            # Check if the operator is after the bracket, or if there
            # is no operator at all but some brackets.
            if bracket_idx >= 0 and (op_idx > bracket_idx or op_idx < 0):
                # In this case, we have a pattern of potentially several
                # nodes.
                # Fill prefix, range and suffix from pattern
                # eg. "forbin[3,4-10]-ilo" -> "forbin", "3,4-10", "-ilo"
                newpat = ""
                sfx = pat
                while bracket_idx >= 0 and (op_idx > bracket_idx or op_idx < 0):
                    pfx, sfx = sfx.split('[', 1)
                    try:
                        rng, sfx = sfx.split(']', 1)
                    except ValueError:
                        raise NodeSetParseError(pat, "missing bracket")

                    # illegal closing bracket checks
                    if pfx.find(']') > -1:
                        raise NodeSetParseError(pfx, "illegal closing bracket")

                    if len(sfx) > 0:
                        bra_end = sfx.find(']')
                        bra_start = sfx.find('[')
                        if bra_start == -1:
                            bra_start = bra_end + 1
                        if bra_end >= 0 and bra_end < bra_start:
                            raise NodeSetParseError(sfx, \
                                                    "illegal closing bracket")
                    pfxlen = len(pfx)

                    # pfx + sfx cannot be empty
                    if pfxlen + len(sfx) == 0:
                        raise NodeSetParseError(pat, "empty node name")

                    # but pfx itself can
                    if pfxlen > 0:
                        pfx, pfxrvec = self._scan_string_single(pfx, autostep)
                        rsets += pfxrvec

                    # readahead for sanity check
                    bracket_idx = sfx.find('[', bracket_idx - pfxlen)
                    op_idx, next_op_code = self._next_op(sfx)

                    # Check for empty component or sequenced ranges
                    if len(pfx) == 0 and op_idx == 0:
                        raise NodeSetParseError(sfx, "empty node name before")\

                    if len(sfx) > 0 and sfx[0] in "0123456789[":
                        raise NodeSetParseError(sfx, \
                                "illegal sequenced numeric ranges")

                    newpat += "%s%%s" % pfx
                    try:
                        rsets.append(RangeSet(rng, autostep))
                    except RangeSetParseError, ex:
                        raise NodeSetParseRangeError(ex)

                # Check if we have a next op-separated node or pattern
                op_idx, next_op_code = self._next_op(sfx)
                if op_idx < 0:
                    pat = None
                else:
                    sfx, pat = sfx.split(self.OP_CODES[next_op_code], 1)

                # Ignore whitespace(s)
                sfx = sfx.rstrip()
                if sfx:
                    sfx, sfxrvec = self._scan_string_single(sfx, autostep)
                    newpat += sfx
                    rsets += sfxrvec

                # pfx + sfx cannot be empty
                if len(newpat) == 0:
                    raise NodeSetParseError(pat, "empty node name")

            else:
                # In this case, either there is no comma and no bracket,
                # or the bracket is after the comma, then just return
                # the node.
                if op_idx < 0:
                    node = pat
                    pat = None # break next time
                else:
                    node, pat = pat.split(self.OP_CODES[next_op_code], 1)
                
                # Check for illegal closing bracket
                if node.find(']') > -1:
                    raise NodeSetParseError(node, "illegal closing bracket")

                newpat, rsets = self._scan_string_single(node, autostep)

            if len(rsets) > 1:
                yield op_code, newpat, RangeSetND([rsets], None, autostep,
                                                  copy_rangeset=False)
            elif len(rsets) == 1:
                yield op_code, newpat, rsets[0]
            else:
                yield op_code, newpat, None


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
        >>> nodeset = NodeSet("blue[1-50]")
        >>> nodeset.remove("blue[36-40]")
        >>> print nodeset
        blue[1-35,41-50]

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

    _VERSION = 2

    def __init__(self, nodes=None, autostep=None, resolver=None):
        """
        Initialize a NodeSet.
        The `nodes' argument may be a valid nodeset string or a NodeSet
        object. If no nodes are specified, an empty NodeSet is created.
        """
        NodeSetBase.__init__(self)

        self._autostep = autostep

        # Set group resolver.
        if resolver in (RESOLVER_NOGROUP, RESOLVER_NOINIT):
            self._resolver = None
        else:
            self._resolver = resolver or RESOLVER_STD_GROUP

        # Initialize default parser.
        if resolver == RESOLVER_NOINIT:
            self._parser = None
        else:
            self._parser = ParsingEngine(self._resolver)
            self.update(nodes)

    @classmethod
    def _fromone(cls, single, autostep=None, resolver=None):
        """Class method that returns a new NodeSet from a single node string
        (optimized constructor)."""
        inst = NodeSet(autostep=autostep, resolver=resolver)
        inst.update(inst._parser.parse_string_single(single, autostep))
        return inst

    @classmethod
    def _fromlist1(cls, nodelist, autostep=None, resolver=None):
        """Class method that returns a new NodeSet with single nodes from
        provided list (optimized constructor)."""
        inst = NodeSet(autostep=autostep, resolver=resolver)
        for single in nodelist:
            inst.update(inst._parser.parse_string_single(single, autostep))
        return inst

    @classmethod
    def fromlist(cls, nodelist, autostep=None, resolver=None):
        """Class method that returns a new NodeSet with nodes from provided
        list."""
        inst = NodeSet(autostep=autostep, resolver=resolver)
        inst.updaten(nodelist)
        return inst

    @classmethod
    def fromall(cls, groupsource=None, autostep=None, resolver=None):
        """Class method that returns a new NodeSet with all nodes from optional
        groupsource."""
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
                                resolver=RESOLVER_NOGROUP)
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
        odict['_version'] = NodeSet._VERSION
        del odict['_resolver']
        del odict['_parser']
        return odict

    def __setstate__(self, dic):
        """Called when unpickling: restore parser using non group
        resolver."""
        self.__dict__.update(dic)
        self._resolver = None
        self._parser = ParsingEngine(None)
        if getattr(self, '_version', 1) <= 1:
            # if setting state from first version, a conversion is needed to
            # support native RangeSetND
            old_patterns = self._patterns
            self._patterns = {}
            for pat, rangeset in sorted(old_patterns.iteritems()):
                if rangeset:
                    assert isinstance(rangeset, RangeSet)
                    rgs = str(rangeset)
                    if len(rangeset) > 1:
                        rgs = "[%s]" % rgs
                    self.update(pat % rgs)
                else:
                    self.update(pat)

    def copy(self):
        """Return a shallow copy of a NodeSet."""
        cpy = self.__class__(resolver=RESOLVER_NOINIT)
        cpy._length = self._length
        dic = {}
        for pat, rangeset in self._patterns.iteritems():
            if rangeset is None:
                dic[pat] = None
            else:
                dic[pat] = rangeset.copy()
        cpy._patterns = dic
        cpy._autostep = self._autostep
        cpy._resolver = self._resolver
        cpy._parser = self._parser
        return cpy

    __copy__ = copy # For the copy module

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

    def _groups2(self, groupsource=None, autostep=None):
        """Find node groups this nodeset belongs to. [private]"""
        if not self._resolver:
            raise NodeSetExternalError("No node group resolver")
        try:
            # Get a NodeSet of all groups in specified group source.
            allgrpns = NodeSet.fromlist(self._resolver.grouplist(groupsource),
                                        resolver=RESOLVER_NOGROUP)
        except NodeUtils.GroupSourceException:
            # If list query failed, we still might be able to regroup
            # using reverse.
            allgrpns = None
        groups_info = {}
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
                return groups_info # empty
            try:
                # use internal reverse: populate allgroups
                for grp in allgrpns:
                    nodelist = self._resolver.group_nodes(grp, groupsource)
                    allgroups[grp] = NodeSet(",".join(nodelist))
            except NodeUtils.GroupSourceQueryFailed, exc:
                # External result inconsistency
                raise NodeSetExternalError("Unable to map a group " \
                        "previously listed\n\tFailed command: %s" % exc)

        # For each NodeSetBase in self, find its groups.
        for node in self._iterbase():
            for grp in self._find_groups(node, groupsource, allgroups):
                if grp not in groups_info:
                    nodes = self._parser.parse_group(grp, groupsource, autostep)
                    groups_info[grp] = (1, nodes)
                else:
                    i, nodes = groups_info[grp]
                    groups_info[grp] = (i + 1, nodes)
        return groups_info

    def groups(self, groupsource=None, noprefix=False):
        """Find node groups this nodeset belongs to.

        Return a dictionary of the form:
            group_name => (group_nodeset, contained_nodeset)

        Group names are always prefixed with "@". If groupsource is provided,
        they are prefixed with "@groupsource:", unless noprefix is True.
        """
        groups = self._groups2(groupsource, self._autostep)
        result = {}
        for grp, (_, nsb) in groups.iteritems():
            if groupsource and not noprefix:
                key = "@%s:%s" % (groupsource, grp)
            else:
                key = "@" + grp
            result[key] = (NodeSet(nsb), self.intersection(nsb))
        return result

    def regroup(self, groupsource=None, autostep=None, overlap=False,
                noprefix=False):
        """Regroup nodeset using node groups.

        Try to find fully matching node groups (within specified groupsource)
        and return a string that represents this node set (containing these
        potential node groups). When no matching node groups are found, this
        method returns the same result as str()."""
        groups = self._groups2(groupsource, autostep)
        if not groups:
            return str(self)

        # Keep only groups that are full.
        fulls = []
        for k, (i, nodes) in groups.iteritems():
            assert i <= len(nodes)
            if i == len(nodes):
                fulls.append((i, k))

        rest = NodeSet(self, resolver=RESOLVER_NOGROUP)
        regrouped = NodeSet(resolver=RESOLVER_NOGROUP)

        bigalpha = lambda x, y: cmp(y[0], x[0]) or cmp(x[1], y[1])

        # Build regrouped NodeSet by selecting largest groups first.
        for _, grp in sorted(fulls, cmp=bigalpha):
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
        inst._patterns = base._patterns
        return inst

    def split(self, nbr):
        """
        Split the nodeset into nbr sub-nodesets (at most). Each
        sub-nodeset will have the same number of elements more or
        less 1. Current nodeset remains unmodified.

        >>> for nodeset in NodeSet("foo[1-5]").split(3):
        ...     print nodeset
        foo[1-2]
        foo[3-4]
        foo5
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
    Commodity function that expands a nodeset pattern into a list of nodes.
    """
    return list(NodeSet(pat))

def fold(pat):
    """
    Commodity function that clean dups and fold provided pattern with ranges
    and "/step" support.
    """
    return str(NodeSet(pat))

def grouplist(namespace=None):
    """
    Commodity function that retrieves the list of raw groups for a specified
    group namespace (or use default namespace).
    Group names are not prefixed with "@".
    """
    return RESOLVER_STD_GROUP.grouplist(namespace)

def std_group_resolver():
    """
    Get the current resolver used for standard "@" group resolution.
    """
    return RESOLVER_STD_GROUP

def set_std_group_resolver(new_resolver):
    """
    Override the resolver used for standard "@" group resolution. The
    new resolver should be either an instance of
    NodeUtils.GroupResolver or None. In the latter case, the group
    resolver is restored to the default one.
    """
    global RESOLVER_STD_GROUP
    RESOLVER_STD_GROUP = new_resolver or _DEF_RESOLVER_STD_GROUP

