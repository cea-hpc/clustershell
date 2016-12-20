#
# Copyright (C) 2007-2016 CEA/DAM
# Copyright (C) 2007-2016 Aurelien Degremont <aurelien.degremont@cea.fr>
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
import string
import sys

from ClusterShell.Defaults import config_paths
import ClusterShell.NodeUtils as NodeUtils

# Import all RangeSet module public objects
from ClusterShell.RangeSet import RangeSet, RangeSetND, AUTOSTEP_DISABLED
from ClusterShell.RangeSet import RangeSetException, RangeSetParseError
from ClusterShell.RangeSet import RangeSetPaddingError


# Define default GroupResolver object used by NodeSet
DEF_GROUPS_CONFIGS = config_paths('groups.conf')
ILLEGAL_GROUP_CHARS = set("@,!&^*")
_DEF_RESOLVER_STD_GROUP = NodeUtils.GroupResolverConfig(DEF_GROUPS_CONFIGS,
                                                        ILLEGAL_GROUP_CHARS)
# Standard group resolver
RESOLVER_STD_GROUP = _DEF_RESOLVER_STD_GROUP
# Special constants for NodeSet's resolver parameter
#   RESOLVER_NOGROUP => avoid any group resolution at all
#   RESOLVER_NOINIT  => reserved use for optimized copy()
RESOLVER_NOGROUP = -1
RESOLVER_NOINIT = -2
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
            msg = "%s: \"%s\"" % (msg, part)
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
    def __init__(self, pattern=None, rangeset=None, copy_rangeset=True,
                 autostep=None, fold_axis=None):
        """New NodeSetBase object initializer"""
        self._autostep = autostep
        self._length = 0
        self._patterns = {}
        self.fold_axis = fold_axis  #: iterable over nD 0-indexed axis
        if pattern:
            self._add(pattern, rangeset, copy_rangeset)
        elif rangeset:
            raise ValueError("missing pattern")

    def get_autostep(self):
        """Get autostep value (property)"""
        return self._autostep

    def set_autostep(self, val):
        """Set autostep value (property)"""
        if val is None:
            self._autostep = None
        else:
            # Work around the pickling issue of sys.maxint (+inf) in py2.4
            self._autostep = min(int(val), AUTOSTEP_DISABLED)

        # Update our RangeSet/RangeSetND objects
        for pat, rset in self._patterns.iteritems():
            if rset:
                rset.autostep = self._autostep

    autostep = property(get_autostep, set_autostep)

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
                yield pat % ()

    # define striter() alias for convenience (to match RangeSet.striter())
    striter = __iter__

    # define nsiter() as an object-based iterator that could be used for
    # __iter__() in the future...

    def nsiter(self):
        """Object-based NodeSet iterator on single nodes."""
        for pat, ivec, pads, autostep in self._iter():
            nodeset = self.__class__()
            if ivec is not None:
                if len(ivec) == 1:
                    pad = pads[0] or 0
                    nodeset._add_new(pat, RangeSet.fromone(ivec[0], pad))
                else:
                    nodeset._add_new(pat, RangeSetND([ivec], pads, autostep))
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

    def _iter_nd_pat(self, pat, rset):
        """
        Take a pattern and a RangeSetND object and iterate over nD computed
        nodeset strings while following fold_axis constraints.
        """
        try:
            dimcnt = rset.dim()
            if self.fold_axis is None:
                # fold along all axis (default)
                fold_axis = range(dimcnt)
            else:
                # set of user-provided fold axis (support negative numbers)
                fold_axis = [int(x) % dimcnt for x in self.fold_axis
                             if -dimcnt <= int(x) < dimcnt]
        except (TypeError, ValueError), exc:
            raise NodeSetParseError("fold_axis=%s" % self.fold_axis, exc)

        for rgvec in rset.vectors():
            rgnargs = []    # list of str rangeset args
            for axis, rangeset in enumerate(rgvec):
                # build an iterator over rangeset strings to add
                if len(rangeset) > 1:
                    if axis not in fold_axis: # expand
                        rgstrit = rangeset.striter()
                    else:
                        rgstrit = ["[%s]" % rangeset]
                else:
                    rgstrit = [str(rangeset)]

                # aggregate/expand along previous computed axis...
                t_rgnargs = []
                for rgstr in rgstrit: # 1-time when not expanding
                    if not rgnargs:
                        t_rgnargs.append([rgstr])
                    else:
                        for rga in rgnargs:
                            t_rgnargs.append(rga + [rgstr])
                rgnargs = t_rgnargs

            # get nodeset patterns formatted with range strings
            for rgargs in rgnargs:
                yield pat % tuple(rgargs)

    def __str__(self):
        """Get ranges-based pattern of node list."""
        results = []
        try:
            for pat, rset in sorted(self._patterns.iteritems()):
                if not rset:
                    results.append(pat % ())
                elif rset.dim() == 1:
                    # check if allowed to fold even for 1D pattern
                    if self.fold_axis is None or \
                            list(x for x in self.fold_axis if -1 <= int(x) < 1):
                        rgs = str(rset)
                        cnt = len(rset)
                        if cnt > 1:
                            rgs = "[%s]" % rgs
                        results.append(pat % rgs)
                    else:
                        results.extend((pat % rgs for rgs in rset.striter()))
                elif rset.dim() > 1:
                    results.extend(self._iter_nd_pat(pat, rset))
        except TypeError:
            raise NodeSetParseError(pat, "Internal error: node pattern and "
                                         "ranges mismatch")
        return ",".join(results)

    def copy(self):
        """Return a shallow copy."""
        cpy = self.__class__()
        cpy.fold_axis = self.fold_axis
        cpy._autostep = self._autostep
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
        when provided and if copy_rangeset flag is set.
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
                # default is to inherit rangeset autostep value
                rangeset = rangeset.copy()
                # but if set, self._autostep does override it
                if self._autostep is not None:
                    # works with rangeset 1D or nD
                    rangeset.autostep = self._autostep
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
        Implements the |= operator. So ``s |= t`` returns nodeset s with
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
        Implements the & operator. So ``s & t`` returns a new nodeset with
        elements common to s and t.
        """
        if not isinstance(other, NodeSet):
            return NotImplemented
        return self.intersection(other)

    def intersection_update(self, other):
        """
        ``s.intersection_update(t)`` returns nodeset s keeping only
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
        Implements the &= operator. So ``s &= t`` returns nodeset s keeping
        only elements also found in t. (Python version 2.5+ required)
        """
        self._binary_sanity_check(other)
        self.intersection_update(other)
        return self

    def difference(self, other):
        """
        ``s.difference(t)`` returns a new NodeSet with elements in s but not
        in t.
        """
        self_copy = self.copy()
        self_copy.difference_update(other)
        return self_copy

    def __sub__(self, other):
        """
        Implement the - operator. So ``s - t`` returns a new nodeset with
        elements in s but not in t.
        """
        if not isinstance(other, NodeSetBase):
            return NotImplemented
        return self.difference(other)

    def difference_update(self, other, strict=False):
        """
        ``s.difference_update(t)`` removes from s all the elements found in t.

        :raises KeyError: an element cannot be removed (only if strict is
            True)
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
        Implement the -= operator. So ``s -= t`` returns nodeset s after
        removing elements found in t. (Python version 2.5+ required)
        """
        self._binary_sanity_check(other)
        self.difference_update(other)
        return self

    def remove(self, elem):
        """
        Remove element elem from the nodeset. Raise KeyError if elem
        is not contained in the nodeset.

        :raises KeyError: elem is not contained in the nodeset
        """
        self.difference_update(elem, True)

    def symmetric_difference(self, other):
        """
        ``s.symmetric_difference(t)`` returns the symmetric difference of
        two nodesets as a new NodeSet.

        (ie. all nodes that are in exactly one of the nodesets.)
        """
        self_copy = self.copy()
        self_copy.symmetric_difference_update(other)
        return self_copy

    def __xor__(self, other):
        """
        Implement the ^ operator. So ``s ^ t`` returns a new NodeSet with
        nodes that are in exactly one of the nodesets.
        """
        if not isinstance(other, NodeSet):
            return NotImplemented
        return self.symmetric_difference(other)

    def symmetric_difference_update(self, other):
        """
        ``s.symmetric_difference_update(t)`` returns nodeset s keeping all
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
        Implement the ^= operator. So ``s ^= t`` returns nodeset s after
        keeping all nodes that are in exactly one of the nodesets.
        (Python version 2.5+ required)
        """
        self._binary_sanity_check(other)
        self.symmetric_difference_update(other)
        return self


def _strip_escape(nsstr):
    """
    Helper to prepare a nodeset string for parsing: trim boundary
    whitespaces and escape special characters.
    """
    return nsstr.strip().replace('%', '%%')


class ParsingEngine(object):
    """
    Class that is able to transform a source into a NodeSetBase.
    """
    OP_CODES = { 'update': ',',
                 'difference_update': '!',
                 'intersection_update': '&',
                 'symmetric_difference_update': '^' }

    BRACKET_OPEN = '['
    BRACKET_CLOSE = ']'

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
        if isinstance(nsobj, basestring):
            try:
                return self.parse_string(str(nsobj), autostep)
            except (NodeUtils.GroupSourceQueryFailed, RuntimeError), exc:
                raise NodeSetParseError(nsobj, str(exc))

        raise TypeError("Unsupported NodeSet input %s" % type(nsobj))

    def parse_string(self, nsstr, autostep, namespace=None):
        """Parse provided string in optional namespace.

        This method parses string, resolves all node groups, and
        computes set operations.

        Return a NodeSetBase object.
        """
        nodeset = NodeSetBase()
        nsstr = _strip_escape(nsstr)

        for opc, pat, rgnd in self._scan_string(nsstr, autostep):
            # Parser main debugging:
            #print "OPC %s PAT %s RANGESETS %s" % (opc, pat, rgnd)
            if self.group_resolver and pat[0] == '@':
                ns_group = NodeSetBase()
                for nodegroup in NodeSetBase(pat, rgnd):
                    # parse/expand nodes group: get group string and namespace
                    ns_str_ext, ns_nsp_ext = self.parse_group_string(nodegroup,
                                                                     namespace)
                    if ns_str_ext: # may still contain groups
                        # recursively parse and aggregate result
                        ns_group.update(self.parse_string(ns_str_ext,
                                                          autostep,
                                                          ns_nsp_ext))
                # perform operation
                getattr(nodeset, opc)(ns_group)
            else:
                getattr(nodeset, opc)(NodeSetBase(pat, rgnd, False))

        return nodeset

    def parse_string_single(self, nsstr, autostep):
        """Parse provided string and return a NodeSetBase object."""
        pat, rangesets = self._scan_string_single(_strip_escape(nsstr),
                                                  autostep)
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

    def parse_group_string(self, nodegroup, namespace=None):
        """Parse provided raw nodegroup string in optional namespace.

        Warning: 1 pass only, may still return groups.

        Return a tuple (grp_resolved_string, namespace).
        """
        assert nodegroup[0] == '@'
        assert self.group_resolver is not None
        grpstr = group = nodegroup[1:]
        if grpstr.find(':') >= 0:
            # specified namespace does always override
            namespace, group = grpstr.split(':', 1)
        if group == '*': # @* or @source:* magic
            reslist = self.all_nodes(namespace)
        else:
            reslist = self.group_resolver.group_nodes(group, namespace)
        return ','.join(reslist), namespace

    def grouplist(self, namespace=None):
        """
        Return a sorted list of groups from current resolver (in optional
        group source / namespace).
        """
        grpset = NodeSetBase()
        for grpstr in self.group_resolver.grouplist(namespace):
            # We scan each group string to expand any range seen...
            grpstr = _strip_escape(grpstr)
            for opc, pat, rgnd in self._scan_string(grpstr, None):
                getattr(grpset, opc)(NodeSetBase(pat, rgnd, False))
        return list(grpset)

    def all_nodes(self, namespace=None):
        """Get all nodes from group resolver as a list of strings."""
        # namespace is the optional group source
        assert self.group_resolver is not None
        alln = []
        try:
            # Ask resolver to provide all nodes.
            alln = self.group_resolver.all_nodes(namespace)
        except NodeUtils.GroupSourceNoUpcall:
            try:
                # As the resolver is not able to provide all nodes directly,
                # failback to list + map(s) method:
                for grp in self.grouplist(namespace):
                    alln += self.group_resolver.group_nodes(grp, namespace)
            except NodeUtils.GroupSourceNoUpcall:
                # We are not able to find "all" nodes, definitely.
                msg = "Not enough working methods (all or map + list) to " \
                      "get all nodes"
                raise NodeSetExternalError(msg)
        except NodeUtils.GroupSourceQueryFailed, exc:
            raise NodeSetExternalError("Failed to get all nodes: %s" % exc)
        return alln

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
        # single node parsing
        pfx_nd = [mobj.groups() for mobj in self.base_node_re.finditer(nsstr)]
        pfx_nd = pfx_nd[:-1]
        if not pfx_nd:
            raise NodeSetParseError(nsstr, "parse error")

        # pfx+sfx cannot be empty
        if len(pfx_nd) == 1 and len(pfx_nd[0][0]) == 0:
            raise NodeSetParseError(nsstr, "empty node name")

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
        next_op_code = 'update'
        while nsstr:
            # Ignore whitespace(s) for convenience
            nsstr = nsstr.lstrip()

            rsets = []
            op_code = next_op_code

            op_idx, next_op_code = self._next_op(nsstr)
            bracket_idx = nsstr.find(self.BRACKET_OPEN)

            # Check if the operator is after the bracket, or if there
            # is no operator at all but some brackets.
            if bracket_idx >= 0 and (op_idx > bracket_idx or op_idx < 0):
                # In this case, we have a pattern of potentially several
                # nodes.
                # Fill prefix, range and suffix from pattern
                # eg. "forbin[3,4-10]-ilo" -> "forbin", "3,4-10", "-ilo"
                newpat = ""
                sfx = nsstr
                while bracket_idx >= 0 and (op_idx > bracket_idx or op_idx < 0):
                    pfx, sfx = sfx.split(self.BRACKET_OPEN, 1)
                    try:
                        rng, sfx = sfx.split(self.BRACKET_CLOSE, 1)
                    except ValueError:
                        raise NodeSetParseError(nsstr, "missing bracket")

                    # illegal closing bracket checks
                    if pfx.find(self.BRACKET_CLOSE) > -1:
                        raise NodeSetParseError(pfx, "illegal closing bracket")

                    if len(sfx) > 0:
                        bra_end = sfx.find(self.BRACKET_CLOSE)
                        bra_start = sfx.find(self.BRACKET_OPEN)
                        if bra_start == -1:
                            bra_start = bra_end + 1
                        if bra_end >= 0 and bra_end < bra_start:
                            msg = "illegal closing bracket"
                            raise NodeSetParseError(sfx, msg)

                    pfxlen, sfxlen = len(pfx), len(sfx)

                    if sfxlen > 0:
                        # amending trailing digits generates /steps
                        sfx, rng = self._amend_trailing_digits(sfx, rng)

                    if pfxlen > 0:
                        # this method supports /steps
                        pfx, rng = self._amend_leading_digits(pfx, rng)
                        if pfx:
                            # scan any nonempty pfx as a single node (no bracket)
                            pfx, pfxrvec = self._scan_string_single(pfx, autostep)
                            rsets += pfxrvec

                    # readahead for sanity check
                    bracket_idx = sfx.find(self.BRACKET_OPEN,
                                           bracket_idx - pfxlen)
                    op_idx, next_op_code = self._next_op(sfx)

                    # Check for empty component or sequenced ranges
                    if len(pfx) == 0 and op_idx == 0:
                        raise NodeSetParseError(sfx, "empty node name before")

                    if len(sfx) > 0 and sfx[0] == '[':
                        msg = "illegal reopening bracket"
                        raise NodeSetParseError(sfx, msg)

                    newpat += "%s%%s" % pfx
                    try:
                        rsets.append(RangeSet(rng, autostep))
                    except RangeSetParseError, ex:
                        raise NodeSetParseRangeError(ex)

                    # the following test forbids fully numeric nodeset
                    if len(pfx) + len(sfx) == 0:
                        msg = "fully numeric nodeset"
                        raise NodeSetParseError(nsstr, msg)

                # Check if we have a next op-separated node or pattern
                op_idx, next_op_code = self._next_op(sfx)
                if op_idx < 0:
                    nsstr = None
                else:
                    opc = self.OP_CODES[next_op_code]
                    sfx, nsstr = sfx.split(opc, 1)
                    # Detected character operator so right operand is mandatory
                    if not nsstr:
                        msg = "missing nodeset operand with '%s' operator" % opc
                        raise NodeSetParseError(None, msg)

                # Ignore whitespace(s)
                sfx = sfx.rstrip()
                if sfx:
                    sfx, sfxrvec = self._scan_string_single(sfx, autostep)
                    newpat += sfx
                    rsets += sfxrvec
            else:
                # In this case, either there is no comma and no bracket,
                # or the bracket is after the comma, then just return
                # the node.
                if op_idx < 0:
                    node = nsstr
                    nsstr = None # break next time
                else:
                    opc = self.OP_CODES[next_op_code]
                    node, nsstr = nsstr.split(opc, 1)
                    # Detected character operator so both operands are mandatory
                    if not node or not nsstr:
                        msg = "missing nodeset operand with '%s' operator" % opc
                        raise NodeSetParseError(node or nsstr, msg)

                # Check for illegal closing bracket
                if node.find(self.BRACKET_CLOSE) > -1:
                    raise NodeSetParseError(node, "illegal closing bracket")

                # Ignore whitespace(s)
                node = node.rstrip()
                newpat, rsets = self._scan_string_single(node, autostep)

            if len(rsets) > 1:
                yield op_code, newpat, RangeSetND([rsets], None, autostep,
                                                  copy_rangeset=False)
            elif len(rsets) == 1:
                yield op_code, newpat, rsets[0]
            else:
                yield op_code, newpat, None

    def _amend_leading_digits(self, outer, inner):
        """Helper to get rid of leading bracket digits.

        Take a bracket outer prefix string and an inner range set string and
        return amended strings.
        """
        outerstrip = outer.rstrip(string.digits)
        outerlen, outerstriplen = len(outer), len(outerstrip)
        if outerstriplen < outerlen:
            # get outer bracket leading digits
            outerdigits = outer[outerstriplen:]
            inner = ','.join(
                '-'.join(outerdigits + bound for bound in elem.split('-'))
                for elem in (str(subrng)
                             for subrng in RangeSet(inner).contiguous()))
        return outerstrip, inner

    def _amend_trailing_digits(self, outer, inner):
        """Helper to get rid of trailing bracket digits.

        Take a bracket outer suffix string and an inner range set string and
        return amended strings.
        """
        outerstrip = outer.lstrip(string.digits)
        outerlen, outerstriplen = len(outer), len(outerstrip)
        if outerstriplen < outerlen:
            # step syntax is not compatible with trailing digits
            if '/' in inner:
                msg = "illegal trailing digits after range with steps"
                raise NodeSetParseError(outer, msg)
            # get outer bracket trailing digits
            outerdigits = outer[0:outerlen-outerstriplen]
            outlen = len(outerdigits)
            def shiftstep(orig, power):
                """Add needed step after shifting range indexes"""
                if '-' in orig:
                    return orig + '/1' + '0' * power
                return orig # do not use /step for single index
            inner = ','.join(shiftstep(s, outlen) for s in
                             ('-'.join(bound + outerdigits
                                       for bound in elem.split('-'))
                              for elem in inner.split(',')))
        return outerstrip, inner

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

    def __init__(self, nodes=None, autostep=None, resolver=None,
                 fold_axis=None):
        """Initialize a NodeSet object.

        The `nodes` argument may be a valid nodeset string or a NodeSet
        object. If no nodes are specified, an empty NodeSet is created.

        The optional `autostep` argument is passed to underlying
        :class:`.RangeSet.RangeSet` objects and aims to enable and make use of
        the range/step syntax (eg. ``node[1-9/2]``) when converting NodeSet to
        string (using folding). To enable this feature, autostep must be set
        there to the min number of indexes that are found at equal distance of
        each other inside a range before NodeSet starts to use this syntax. For
        example, `autostep=3` (or less) will pack ``n[2,4,6]`` into
        ``n[2-6/2]``. Default autostep value is None which means "inherit
        whenever possible", ie. do not enable it unless set in NodeSet objects
        passed as `nodes` here or during arithmetic operations.
        You may however use the special ``AUTOSTEP_DISABLED`` constant to force
        turning off autostep feature.

        The optional `resolver` argument may be used to override the group
        resolving behavior for this NodeSet object. It can either be set to a
        :class:`.NodeUtils.GroupResolver` object, to the ``RESOLVER_NOGROUP``
        constant to disable any group resolution, or to None (default) to use
        standard NodeSet group resolver (see :func:`.set_std_group_resolver()`
        at the module level to change it if needed).

        nD nodeset only: the optional `fold_axis` parameter, if specified, set
        the public instance member `fold_axis` to an iterable over nD 0-indexed
        axis integers. This parameter may be used to disengage some nD folding.
        That may be useful as all cluster tools don't support folded-nD nodeset
        syntax. Pass ``[0]``, for example, to only fold along first axis (that
        is, to fold first dimension using ``[a-b]`` rangeset syntax whenever
        possible). Using `fold_axis` ensures that rangeset won't be folded on
        unspecified axis, but please note however, that using `fold_axis` may
        lead to suboptimial folding, this is because NodeSet algorithms are
        optimized for folding along all axis (default behavior).
        """
        NodeSetBase.__init__(self, autostep=autostep, fold_axis=fold_axis)

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
        try:
            if not inst._resolver:
                raise NodeSetExternalError("Group resolver is not defined")
            else:
                # fill this nodeset with all nodes found by resolver
                inst.updaten(inst._parser.all_nodes(groupsource))
        except NodeUtils.GroupResolverError, exc:
            errmsg = "Group source error (%s: %s)" % (exc.__class__.__name__,
                                                      exc)
            raise NodeSetExternalError(errmsg)
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
            self.fold_axis = None
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
        dic = {}
        for pat, rangeset in self._patterns.iteritems():
            if rangeset is None:
                dic[pat] = None
            else:
                dic[pat] = rangeset.copy()
        cpy._patterns = dic
        cpy.fold_axis = self.fold_axis
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
            try:
                for group in self._resolver.node_groups(node, namespace):
                    yield group
            except NodeUtils.GroupSourceQueryFailed, exc:
                msg = "Group source query failed: %s" % exc
                raise NodeSetExternalError(msg)

    def _groups2(self, groupsource=None, autostep=None):
        """Find node groups this nodeset belongs to. [private]"""
        if not self._resolver:
            raise NodeSetExternalError("No node group resolver")
        try:
            # Get all groups in specified group source.
            allgrplist = self._parser.grouplist(groupsource)
        except NodeUtils.GroupSourceError:
            # If list query failed, we still might be able to regroup
            # using reverse.
            allgrplist = None
        groups_info = {}
        allgroups = {}
        # Check for external reverse presence, and also use the
        # following heuristic: external reverse is used only when number
        # of groups is greater than the NodeSet size.
        if self._resolver.has_node_groups(groupsource) and \
            (not allgrplist or len(allgrplist) >= len(self)):
            # use external reverse
            pass
        else:
            if not allgrplist: # list query failed and no way to reverse!
                return groups_info # empty
            try:
                # use internal reverse: populate allgroups
                for grp in allgrplist:
                    nodelist = self._resolver.group_nodes(grp, groupsource)
                    allgroups[grp] = NodeSet(",".join(nodelist),
                                             resolver=self._resolver)
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
            result[key] = (NodeSet(nsb, resolver=self._resolver),
                           self.intersection(nsb))
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
        s.difference_update(t) removes from s all the elements
        found in t. If strict is True, raise KeyError if an
        element in t cannot be removed from s.
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

def grouplist(namespace=None, resolver=None):
    """
    Commodity function that retrieves the list of raw groups for a specified
    group namespace (or use default namespace).
    Group names are not prefixed with "@".
    """
    return ParsingEngine(resolver or RESOLVER_STD_GROUP).grouplist(namespace)

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

