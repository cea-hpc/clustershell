#
# Copyright (C) 2007-2016 CEA/DAM
# Copyright (C) 2016-2017 Stephane Thiell <sthiell@stanford.edu>
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
MsgTree

ClusterShell message tree module. The purpose of MsgTree is to provide a
shared message tree for storing message lines received from ClusterShell
Workers (for example, from remote cluster commands). It should be
efficient, in term of algorithm and memory consumption, especially when
remote messages are the same.
"""

try:
    from itertools import filterfalse
except ImportError:  # Python 2 compat
    from itertools import ifilterfalse as filterfalse

import sys


# MsgTree behavior modes
MODE_DEFER = 0
MODE_SHIFT = 1
MODE_TRACE = 2


class MsgTreeElem(object):
    """
    Class representing an element of the MsgTree and its associated
    message. Object of this class are returned by the various MsgTree
    methods like messages() or walk(). The object can then be used as
    an iterator over the message lines or casted into a bytes buffer.
    """
    def __init__(self, msgline=None, parent=None, trace=False):
        """
        Initialize message tree element.
        """
        # structure
        self.parent = parent
        self.children = {}
        if trace:  # special behavior for trace mode
            self._shift = self._shift_trace
        else:
            self._shift = self._shift_notrace
        # content
        self.msgline = msgline
        self.keys = None

    def __len__(self):
        """Length of whole message buffer."""
        return len(bytes(self))

    def __eq__(self, other):
        """Comparison method compares whole message buffers."""
        return bytes(self) == bytes(other)

    def _add_key(self, key):
        """Add a key to this tree element."""
        if self.keys is None:
            self.keys = set([key])
        else:
            self.keys.add(key)

    def _shift_notrace(self, key, target_elem):
        """Shift one of our key to specified target element."""
        if self.keys and len(self.keys) == 1:
            shifting = self.keys
            self.keys = None
        else:
            shifting = set([key])
            if self.keys:
                self.keys.difference_update(shifting)

        if not target_elem.keys:
            target_elem.keys = shifting
        else:
            target_elem.keys.update(shifting)

        return target_elem

    def _shift_trace(self, key, target_elem):
        """Shift one of our key to specified target element (trace
        mode: keep backtrace of keys)."""
        if not target_elem.keys:
            target_elem.keys = set([key])
        else:
            target_elem.keys.add(key)
        return target_elem

    def __getitem__(self, i):
        return list(self.lines())[i]

    def __iter__(self):
        """Iterate over message lines up to this element."""
        bottomtop = []
        if self.msgline is not None:
            bottomtop.append(self.msgline)
            parent = self.parent
            while parent.msgline is not None:
                bottomtop.append(parent.msgline)
                parent = parent.parent
        return reversed(bottomtop)

    def lines(self):
        """Get an iterator over all message lines up to this element."""
        return iter(self)

    splitlines = lines

    def message(self):
        """
        Get the whole message buffer (from this tree element) as bytes.
        """
        return b'\n'.join(self.lines())

    __bytes__ = message

    def __str__(self):
        """
        Get the whole message buffer (from this tree element) as a string.

        DEPRECATED: use message() or cast to bytes instead.
        """
        if sys.version_info >= (3, 0):
            raise TypeError('cannot get string from %s, use bytes instead' %
                            self.__class__.__name__)
        else:
            # in Python 2, str and bytes are actually the same type
            return self.message()

    def append(self, msgline, key=None):
        """
        A new message is coming, append it to the tree element with
        optional associated source key. Called by MsgTree.add().
        Return corresponding MsgTreeElem (possibly newly created).
        """
        # get/create child element
        elem = self.children.get(msgline)
        if elem is None:
            elem = self.__class__(msgline, self,
                                  self._shift == self._shift_trace)
            self.children[msgline] = elem

        # if no key is given, MsgTree is in MODE_DEFER
        # shift down the given key otherwise
        # Note: replace with ternary operator in py2.5+
        if key is None:
            return elem
        else:
            return self._shift(key, elem)


class MsgTree(object):
    """
    MsgTree maps key objects to multi-lines messages.

    MsgTree is a mutable object. Keys are almost arbitrary values (must
    be hashable). Message lines are organized as a tree internally.
    MsgTree provides low memory consumption especially on a cluster when
    all nodes return similar messages. Also, the gathering of messages is
    done automatically.
    """

    def __init__(self, mode=MODE_DEFER):
        """MsgTree initializer

        The `mode' parameter should be set to one of the following constant:

        MODE_DEFER: all messages are processed immediately, saving memory from
        duplicate message lines, but keys are associated to tree elements
        usually later when tree is first "walked", saving useless state
        updates and CPU time. Once the tree is "walked" for the first time, its
        mode changes to MODE_SHIFT to keep track of further tree updates.
        This is the default mode.

        MODE_SHIFT: all keys and messages are processed immediately, it is more
        CPU time consuming as MsgTree full state is updated at each add() call.

        MODE_TRACE: all keys and messages and processed immediately, and keys
        are kept for each message element of the tree. The special method
        walk_trace() is then available to walk all elements of the tree.
        """
        self.mode = mode
        # root element of MsgTree
        self._root = MsgTreeElem(trace=(mode == MODE_TRACE))
        # dict of keys to MsgTreeElem
        self._keys = {}

    def clear(self):
        """Remove all items from the MsgTree."""
        self._root = MsgTreeElem(trace=(self.mode == MODE_TRACE))
        self._keys.clear()

    def __len__(self):
        """Return the number of keys contained in the MsgTree."""
        return len(self._keys)

    def __getitem__(self, key):
        """Return the message of MsgTree with specified key. Raises a
        KeyError if key is not in the MsgTree."""
        return self._keys[key]

    def get(self, key, default=None):
        """
        Return the message for key if key is in the MsgTree, else default.
        If default is not given, it defaults to None, so that this method
        never raises a KeyError.
        """
        return self._keys.get(key, default)

    def add(self, key, msgline):
        """
        Add a message line (in bytes) associated with the given key to the
        MsgTree.
        """
        # try to get current element in MsgTree for the given key,
        # defaulting to the root element
        e_msg = self._keys.get(key, self._root)
        if self.mode >= MODE_SHIFT:
            key_shift = key
        else:
            key_shift = None
        # add child msg and update keys dict
        self._keys[key] = e_msg.append(msgline, key_shift)

    def _update_keys(self):
        """Update keys associated to tree elements (MODE_DEFER)."""
        for key, e_msg in self._keys.items():
            assert key is not None and e_msg is not None
            e_msg._add_key(key)
        # MODE_DEFER is no longer valid as keys are now assigned to MsgTreeElems
        self.mode = MODE_SHIFT

    def keys(self):
        """Return an iterator over MsgTree's keys."""
        return iter(self._keys.keys())

    __iter__ = keys

    def messages(self, match=None):
        """Return an iterator over MsgTree's messages."""
        return (item[0] for item in self.walk(match))

    def items(self, match=None, mapper=None):
        """
        Return (key, message) for each key of the MsgTree.
        """
        if mapper is None:
            mapper = lambda k: k
        for key, elem in self._keys.items():
            if match is None or match(key):
                yield mapper(key), elem

    def _depth(self):
        """
        Return the depth of the MsgTree, ie. the max number of lines
        per message. Added for debugging.
        """
        depth = 0
        # stack of (element, depth) tuples used to walk the tree
        estack = [(self._root, depth)]

        while estack:
            elem, edepth = estack.pop()
            if len(elem.children) > 0:
                estack += [(v, edepth + 1) for v in elem.children.values()]
            depth = max(depth, edepth)

        return depth

    def walk(self, match=None, mapper=None):
        """
        Walk the tree. Optionally filter keys on match parameter,
        and optionally map resulting keys with mapper function.
        Return an iterator over (message, keys) tuples for each
        different message in the tree.
        """
        if self.mode == MODE_DEFER:
            self._update_keys()
        # stack of elements used to walk the tree (depth-first)
        estack = [self._root]
        while estack:
            elem = estack.pop()
            children = elem.children
            if len(children) > 0:
                estack += children.values()
            if elem.keys: # has some keys
                mkeys = list(filter(match, elem.keys))
                if len(mkeys):
                    if mapper is not None:
                        keys = [mapper(key) for key in mkeys]
                    else:
                        keys = mkeys
                    yield elem, keys

    def walk_trace(self, match=None, mapper=None):
        """
        Walk the tree in trace mode. Optionally filter keys on match
        parameter, and optionally map resulting keys with mapper
        function.
        Return an iterator over 4-length tuples (msgline, keys, depth,
        num_children).
        """
        assert self.mode == MODE_TRACE, \
            "walk_trace() is only callable in trace mode"
        # stack of (element, depth) tuples used to walk the tree
        estack = [(self._root, 0)]
        while estack:
            elem, edepth = estack.pop()
            children = elem.children
            nchildren = len(children)
            if nchildren > 0:
                estack += [(v, edepth + 1) for v in children.values()]
            if elem.keys:
                mkeys = list(filter(match, elem.keys))
                if len(mkeys):
                    if mapper is not None:
                        keys = [mapper(key) for key in mkeys]
                    else:
                        keys = mkeys
                    yield elem.msgline, keys, edepth, nchildren

    def remove(self, match=None):
        """
        Modify the tree by removing any matching key references from the
        messages tree.

        Example of use:
            >>> msgtree.remove(lambda k: k > 3)
        """
        # do not walk tree in MODE_DEFER as no key is associated
        if self.mode != MODE_DEFER:
            estack = [self._root]
            # walk the tree to keep only matching keys
            while estack:
                elem = estack.pop()
                if len(elem.children) > 0:
                    estack += elem.children.values()
                if elem.keys: # has some keys
                    elem.keys = set(filterfalse(match, elem.keys))

        # remove key(s) from known keys dict
        for key in list(filter(match, self._keys.keys())):
            del self._keys[key]
