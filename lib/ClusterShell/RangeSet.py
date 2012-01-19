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
#
# $Id$

"""
Cluster range set module.

Instances of RangeSet provide similar operations than the builtin set()
type and Set object.
See http://www.python.org/doc/lib/set-objects.html
"""


from array import array
from itertools import imap
from operator import itemgetter
import sys

__all__ = ['RangeSetException',
           'RangeSetParseError',
           'RangeSetPaddingError',
           'RangeSet']


def extractslice(index, length):
    """RangeSet/NodeSet private utility function: extract slice parameters
    from slice object `index` for an list-like object of size `length`."""
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


class AVLRangeTreeNode(object):
    """Internal object, represents a tree node.
    ------------------------------------------------------------------------
    Derivated AVLTree's Node class
    Author:  mozman (python version)
    Purpose: avl tree module (Julienne Walker's unbounded none recursive
             algorithm)
    Source: http://eternallyconfuzzled.com/tuts/datastructures/jsw_tut_avl.aspx
    Copyright (C) 2010, 2011 by Manfred Moitzi
    License: LGPLv3
    ------------------------------------------------------------------------
    Adapted version to support range of integers with optional padding value,
    instead of key/value pair in the original version.
    """
    __slots__ = ['left', 'right', 'balance', 'start', 'stop', 'pad']

    def __init__(self, start, stop, pad=0):
        self.left = None
        self.right = None
        self.balance = 0
        self.start = start
        self.stop = stop
        self.pad = pad

    def __eq__(self, other):
        return self.start == other.start and self.stop == other.stop

    def __getitem__(self, key):
        """ x.__getitem__(key) <==> x[key],
            where key is 0 (left) or 1 (right) """
        if key == 0:
            return self.left
        else:
            return self.right
        # NOTE: can be shorten in py2.5+ by:
        #return self.left if key == 0 else self.right

    def __setitem__(self, key, value):
        """ x.__setitem__(key, value) <==> x[key]=value,
            where key is 0 (left) or 1 (right) """
        if key == 0:
            self.left = value
        else:
            self.right = value

    def free(self):
        """Remove all references."""
        self.left = None
        self.right = None


class AVLRangeTreeWalker(object):
    """Tree walker (helper class)"""
    def __init__(self, tree):
        self._tree = tree
        self._node = tree.root
        self._stack = []

    def reset(self):
        self._stack = []
        self._node = self._tree.root

    @property
    def start(self):
        return self._node.start

    @property
    def stop(self):
        return self._node.stop

    @property
    def pad(self):
        return self._node.pad

    @property
    def node(self):
        return self._node

    @property
    def is_valid(self):
        return self._node is not None

    def push(self):
        self._stack.append(self._node)

    def pop(self):
        self._node = self._stack.pop()

    def stack_is_empty(self):
        return (self._stack is None) or (len(self._stack) == 0)

    def has_child(self, direction):
        if direction == 0:
            return self._node.left is not None
        else:
            return self._node.right is not None

    def down(self, direction):
        if direction == 0:
            self._node = self._node.left
        else:
            self._node = self._node.right

    def has_left(self):
        return self._node.left is not None

    def has_right(self):
        return self._node.right is not None


# AVL-tree useful functions
#
def height(node):
    if node is not None:
        return node.balance
    else:
        return -1

def jsw_single(root, direction):
    other_side = 1 - direction
    save = root[other_side]
    root[other_side] = save[direction]
    save[direction] = root
    rlh = height(root.left)
    rrh = height(root.right)
    slh = height(save[other_side])
    root.balance = max(rlh, rrh) + 1
    save.balance = max(slh, root.balance) + 1
    return save

def jsw_double(root, direction):
    other_side = 1 - direction
    root[other_side] = jsw_single(root[other_side], other_side)
    return jsw_single(root, direction)


class AVLRangeTree(object):
    """
    AVLRangeTree implements a special balanced binary tree of contiguous
    ranges (data structure to manage cluster node ranges).

    In computer science, an AVL tree is a self-balancing binary search tree, and
    it is the first such data structure to be invented. In an AVL tree, the
    heights of the two child subtrees of any node differ by at most one;
    therefore, it is also said to be height-balanced. Lookup, insertion, and
    deletion all take O(log n) time in both the average and worst cases, where n
    is the number of nodes in the tree prior to the operation. Insertions and
    deletions may require the tree to be rebalanced by one or more tree rotations.

    The AVL tree is named after its two inventors, G.M. Adelson-Velskii and E.M.
    Landis, who published it in their 1962 paper "An algorithm for the
    organization of information."

    AVLRangeTree() -> new empty tree.
    """
    # maxheight of 32 represents more than 10^6 tree nodes
    MAXSTACK = 32

    def __init__(self):
        """ x.__init__(...) initializes x; see x.__class__.__doc__ """
        self._root = None       # root AVLRangeTreeNode instance of the tree
        self._count = 0         # size of tree
        self._length = 0        # sum of all ranges

    def __repr__(self):
        """ x.__repr__(...) <==> repr(x) """
        # FIXME
        tpl = "%s({%s})" % (self.__class__.__name__ , '%s')
        return tpl % ", ".join( ("%d-%d" % (start, stop-1) \
            for start, stop, pad in self.ranges()) )

    def __len__(self):
        """ x.__len__() <==> len(x) """
        return self._length

    def copy(self):
        """Return a copy of an AVLRangeTree"""
        cpy = self.__class__()
        # NOTE: cpy.update() is faster than deepcopy (Python2.6)
        cpy.update(self)
        return cpy

    __copy__ = copy # For the copy module

    def nodes(self, reverse=False):
        """ T.nodes([reverse]) -> an iterator over AVLRangeTreeNode instances
        of T, in ascending order if reverse is True, iterate in descending
        order, reverse defaults to False
        """
        if self._count > 0:
            walk = AVLRangeTreeWalker(self)
            if reverse:
                direction = 1
            else:
                direction = 0
            other = 1 - direction
            go_down = True
            while True:
                if walk.has_child(direction) and go_down:
                    walk.push()
                    walk.down(direction)
                else:
                    yield walk.node
                    if walk.has_child(other):
                        walk.down(other)
                        go_down = True
                    else:
                        if walk.stack_is_empty():
                            return # all done
                        walk.pop()
                        go_down = False

    def ranges(self, reverse=False):
        """ T.ranges([reverse]) -> an iterator over the range tuples (start,
        stop, pad) of T, in ascending order if reverse is True, iterate in
        descending order, reverse defaults to False
        """
        for node in self.nodes(reverse):
            yield node.start, node.stop, node.pad

    def __getstate__(self):
        """ T.__getstate__() -> used for pickling """
        # Pickle ranges as a list
        state = { '_count': self._count,
                  '_length': self._length,
                  '_ranges': list(self.ranges()) }
        return state

    def __setstate__(self, state):
        """ T.__setstate__() -> used for pickling """
        self._root = None
        self._count = 0
        self._length = 0
        for start, stop, pad in state['_ranges']:
            self.insert_range(start, stop, pad)
        # sanity check
        assert self._count == state['_count'], "__setstate__ failed"
        assert self._length == state['_length'], "__setstate__ failed"

    def __getitem__(self, index):
        """
        Return the element at index or a subtree when a slice is specified.
        For example, the element of index 2 of range tree "1-2,5-7" is 5.
        """
        if isinstance(index, slice):
            inst = self.__class__()
            sl_start, sl_stop, sl_step = extractslice(index, self._length)
            if sl_stop <= sl_start:
                return inst
            if sl_step == 1:
                # Use case: range[x:y]
                offset, slice_offset = 0, 0
                for start, stop, pad in self.ranges():
                    cnt = stop - start
                    if sl_start < offset + cnt:
                        # once sl_start reached, adjust new range boundaries
                        maxstart = max(0, sl_start - offset)
                        minstop = min(maxstart + sl_stop - sl_start - \
                                      slice_offset, cnt)
                        inst.insert_range(start + maxstart, start + minstop,
                                          pad)
                        # adjust cursor on slice and give up when slice when
                        # its size is reached
                        slice_offset += minstop - maxstart
                        if slice_offset >= sl_stop - sl_start:
                            break
                    offset += cnt
            else:
                # Python slicing with step > 0. We use a generator over ranges
                # that should never raise StopIteration here, as we perform
                # bound checking.
                rgen = self.ranges()
                offset = 0
                for i in range(sl_start, min(sl_stop, self._length), sl_step):
                    while i >= offset:
                        start, stop, pad = rgen.next()
                        offset += stop - start
                    # i < offset ==> item found
                    inst.insert_range(stop - offset + i, \
                                      stop - offset + i + 1, pad)
            return inst
        else:
            # index is an integer (or TypeError will be raised)
            length = self._length
            if index < 0:
                if index >= -length:
                    index = length - -index
                else:
                    raise IndexError, "%d out of range" % index
            elif index >= length:
                raise IndexError, "%d out of range" % index
            offset = 0
            if index <= length/2:
                for start, stop, pad in self.ranges(reverse=False):
                    offset += stop - start
                    if index < offset:
                        return stop - offset + index
            else:
                # use reverse tree traversal for last items
                for start, stop, pad in self.ranges(reverse=True):
                    offset += stop - start
                    if length - index <= offset:
                        return start + offset - length + index

    def clear(self):
        """ T.clear() -> None.  Remove all items from T. """
        def _clear(node):
            if node is not None:
                _clear(node.left)
                _clear(node.right)
                self._free_node(node)
        _clear(self._root)
        assert self._count == 0
        assert self._length == 0
        self._root = None

    @property
    def count(self):
        """ count of node items """
        return self._count

    @property
    def root(self):
        """ root node of T """
        return self._root

    def _new_node(self, start, stop, pad):
        """ Create a new treenode """
        node = AVLRangeTreeNode(start, stop, pad)
        self._count += 1
        self._length += node.stop - node.start
        assert self._length > 0
        return node

    def _free_node(self, node):
        """ Free a new treenode """
        # update live counters
        self._count -= 1
        self._length -= node.stop - node.start
        node.free()

    def insert_range(self, start, stop, pad=0):
        """ T.insert(start, stop) insert range (start, stop) into RangeTree """
        #print "INSERT_RANGE start=%d stop=%d pad=%d" % (start, stop, pad)
        node_stack = [] # node stack
        dir_stack = array('I') # direction stack
        done = False
        top = 0
        merge_direction = None
        merge_node = None
        node = self._root
        while True:
            if node is None:
                assert self._root is None
                self._root = self._new_node(start, stop, pad)
                return
            if start >= node.start and stop <= node.stop:
                return # already in
            if start <= node.start and stop >= node.stop:
                self.remove(node)
                node = self._root
                continue
            if start < node.start:
                direction = 0
            else:
                assert stop > node.stop
                direction = 1
            if start <= node.stop and stop >= node.start:
                if merge_node is not None:
                    if merge_direction:
                        assert stop >= node.start
                        orig_stop = node.stop
                        self.remove(node)
                        self._length += orig_stop - merge_node.stop
                        merge_node.stop = orig_stop
                    else:
                        assert start <= node.stop
                        orig_start = node.start
                        self.remove(node)
                        self._length += merge_node.start - orig_start
                        merge_node.start = orig_start
                    return
                # merge
                merge_direction = direction
                merge_node = node
            dir_stack.append(direction)
            node_stack.append(node)
            if node[direction] is None:
                break
            node = node[direction]

        if merge_node is not None:
            if merge_direction:
                self._length += stop - merge_node.stop
                merge_node.stop = stop
            else:
                self._length += merge_node.start - start
                merge_node.start = start
            return

        # Insert a new node at the bottom of the tree
        node[direction] = self._new_node(start, stop, pad)

        # Walk back up the search path
        top = len(node_stack) - 1
        while (top >= 0) and not done:
            direction = dir_stack[top]
            other_side = 1 - direction
            topnode = node_stack[top]
            left_height = height(topnode[direction])
            right_height = height(topnode[other_side])

            # Terminate or rebalance as necessary */
            if (left_height-right_height == 0):
                done = True
            if (left_height-right_height >= 2):
                a = topnode[direction][direction]
                b = topnode[direction][other_side]

                if height(a) >= height(b):
                    node_stack[top] = jsw_single(topnode, other_side)
                else:
                    node_stack[top] = jsw_double(topnode, other_side)

                # Fix parent
                if top != 0:
                    node_stack[top-1][dir_stack[top-1]] = node_stack[top]
                else:
                    self._root = node_stack[0]
                done = True

            # Update balance factors
            topnode = node_stack[top]
            left_height = height(topnode[direction])
            right_height = height(topnode[other_side])

            topnode.balance = max(left_height, right_height) + 1
            top -= 1
            
    def remove(self, n):
        """ T.remove(key) <==> del T[key], remove item <key> from tree """
        if self._root is None:
            raise KeyError(node)
        else:
            node_stack = [None] * AVLRangeTree.MAXSTACK # node stack
            dir_stack = array('I', [0] * AVLRangeTree.MAXSTACK) # dir stack
            top = 0
            node = self._root

            while True:
                # Terminate if not found
                if node is None:
                    raise KeyError(n)
                elif node is n:
                    break

                # Push direction and node onto stack
                #direction = 0 if n.start < node.start else 1   # py2.5+
                if n.start < node.start:
                    direction = 0
                else:
                    direction = 1
                #direction = 1 if n.start >= node.stop else 0
                dir_stack[top] = direction

                node_stack[top] = node
                node = node[direction]
                top += 1

            # Remove tree node
            if (node.left is None) or (node.right is None):
                # Which child is not null?
                #direction = 1 if node.left is None else 0  # py2.5+
                if node.left is None:
                    direction = 1
                else:
                    direction = 0

                # Fix parent
                if top != 0:
                    node_stack[top-1][dir_stack[top-1]] = node[direction]
                else:
                    self._root = node[direction]
                self._free_node(node)
            else:
                # Find the inorder successor
                heir = node.right

                # Save the path
                dir_stack[top] = 1
                node_stack[top] = node
                top += 1

                while (heir.left is not None):
                    dir_stack[top] = 0
                    node_stack[top] = heir
                    top += 1
                    heir = heir.left

                # Swap data
                rmlen = node.stop - node.start
                node.start = heir.start
                node.stop = heir.stop

                # Unlink successor and fix parent
                #xdir = 1 if (node_stack[top-1] == node) else 0     #py2.5+
                if node_stack[top-1] == node:
                    xdir = 1
                else:
                    xdir = 0
                node_stack[top-1][xdir] = heir.right
                heir.free()
                self._length -= rmlen
                self._count -= 1

            # Walk back up the search path
            top -= 1
            while top >= 0:
                direction = dir_stack[top]
                other_side = 1 - direction
                topnode = node_stack[top]
                left_height = height(topnode[direction])
                right_height = height(topnode[other_side])
                b_max = max(left_height, right_height)

                # Update balance factors
                topnode.balance = b_max + 1

                # Terminate or rebalance as necessary
                if (left_height - right_height) == -1:
                    break
                if (left_height - right_height) <= -2:
                    a = topnode[other_side][direction]
                    b = topnode[other_side][other_side]
                    if height(a) <= height(b):
                        node_stack[top] = jsw_single(topnode, direction)
                    else:
                        node_stack[top] = jsw_double(topnode, direction)
                    # Fix parent
                    if top != 0:
                        node_stack[top-1][dir_stack[top-1]] = node_stack[top]
                    else:
                        self._root = node_stack[0]
                top -= 1
    
    def remove_range(self, start, stop, strict=True):
        """ T.remove(key) <==> del T[key], remove item <key> from tree """
        if self._root is None:
            if strict:
                raise KeyError(start)
        else:
            node_stack = [None] * AVLRangeTree.MAXSTACK # node stack
            dir_stack = array('I', [0] * AVLRangeTree.MAXSTACK) # dir stack
            top = 0
            node = self._root
            restore_ranges = [] # if strict is True, this method restores
                                # removed ranges in case of KeyError
            while True:
                if node is None:    # terminate if not found
                    if strict:
                        # restore previously removed ranges
                        for start, stop, pad in restore_ranges:
                            self.insert_range(start, stop, pad)
                        raise KeyError
                    else:
                        return
                if start >= node.start and stop <= node.stop:
                    break
                if start <= node.start and stop >= node.stop:
                    if strict:
                        restore_ranges.append((node.start, node.stop, node.pad))
                    self.remove(node)
                    node = self._root
                    continue
                # Get direction and truncate current node if needed
                elif start < node.start:
                    direction = 0
                    if stop > node.start:
                        if strict:
                            restore_ranges.append((stop, node.stop, node.pad))
                        self._length -= node.stop - stop - 1
                        node.start = stop
                else:
                    assert stop > node.stop
                    direction = 1
                    if start < node.stop:
                        if strict:
                            restore_ranges.append((start, node.stop, node.pad))
                        self._length -= node.stop - start
                        node.stop = start

                # Push direction and node onto stack
                dir_stack[top] = direction
                node_stack[top] = node
                node = node[direction]
                top += 1

            # bounds checking
            if node.start == start:
                self._length -= stop - node.start
                node.start = stop
                if node.start < node.stop:
                    return
            elif node.stop == stop:
                assert node.stop >= start
                self._length -= node.stop - start
                node.stop = start
                if node.start < node.stop:
                    return
            else:
                # split by reducing first node range and inserting a second one
                orig_stop = node.stop
                self._length -= node.stop - start
                node.stop = start
                self.insert_range(stop, orig_stop, node.pad)
                return

            # Emptied tree node range: remove it
            if (node.left is None) or (node.right is None):
                # Which child is not null?
                #direction = 1 if node.left is None else 0  #py2.5+
                if node.left is None:
                    direction = 1
                else:
                    direction = 0

                # Fix parent
                if top != 0:
                    node_stack[top-1][dir_stack[top-1]] = node[direction]
                else:
                    self._root = node[direction]
                self._free_node(node)
            else:
                # Find the inorder successor
                heir = node.right

                # Save the path
                dir_stack[top] = 1
                node_stack[top] = node
                top += 1

                while (heir.left is not None):
                    dir_stack[top] = 0
                    node_stack[top] = heir
                    top += 1
                    heir = heir.left

                # Swap data
                rmlen = node.stop - node.start
                node.start = heir.start
                node.stop = heir.stop

                # Unlink successor and fix parent
                #xdir = 1 if (node_stack[top-1] == node) else 0     #py2.5+
                if node_stack[top-1] == node:
                    xdir = 1
                else:
                    xdir = 0
                node_stack[top-1][xdir] = heir.right
                heir.free()
                self._length -= rmlen
                self._count -= 1

            # Walk back up the search path
            top -= 1
            while top >= 0:
                direction = dir_stack[top]
                other_side = 1 - direction
                topnode = node_stack[top]
                left_height = height(topnode[direction])
                right_height = height(topnode[other_side])
                b_max = max(left_height, right_height)

                # Update balance factors
                topnode.balance = b_max + 1

                # Terminate or rebalance as necessary
                if (left_height - right_height) == -1:
                    break
                if (left_height - right_height) <= -2:
                    a = topnode[other_side][direction]
                    b = topnode[other_side][other_side]
                    if height(a) <= height(b):
                        node_stack[top] = jsw_single(topnode, direction)
                    else:
                        node_stack[top] = jsw_double(topnode, direction)
                    # Fix parent
                    if top != 0:
                        node_stack[top-1][dir_stack[top-1]] = node_stack[top]
                    else:
                        self._root = node_stack[0]
                top -= 1

    def intersection_update(self, other):
        """ AVLRangeTree intersection (in-place)"""
        if self._root is None:
            return self

        rm_ranges = []
        new_ranges = []
        mine = self.nodes()
        their = other.ranges()
        node = None
        try:
            # walk around both tree nodes
            node = mine.next()
            start, stop, pad = node.start, node.stop, node.pad
            istart, istop, ipad = their.next()
            while True:
                if istop <= start:
                    istart, istop, ipad = their.next()
                    continue
                elif istart >= stop:
                    if node:
                        rm_ranges.append((node.start, node.stop))
                    node = None
                    node = mine.next()
                    start, stop, pad = node.start, node.stop, node.pad
                    continue
                if node:
                    if istart > start:
                        self._length -= istart - start
                    if stop > istop:
                        self._length -= stop - istop
                    node.start = max(start, istart)
                    node.stop = min(stop, istop)
                    node = None
                else:
                    new_ranges.append((max(start, istart), min(stop, istop), \
                                      pad or ipad))
                if stop > istop:
                    start = istop
                    istart, istop, ipad = their.next()
                else:
                    node = None
                    node = mine.next() 
                    start, stop, pad = node.start, node.stop, node.pad
        except StopIteration:
            pass

        # if ranges are remaining in ...
        try:
            if node is None:
                node = mine.next()
                start, stop = node.start, node.stop
            while True:
                rm_ranges.append((node.start, node.stop))
                node = mine.next()
                start, stop = node.start, node.stop
        except StopIteration:
            pass

        for start, stop in rm_ranges:
            self.remove_range(start, stop)

        for start, stop, pad in new_ranges:
            self.insert_range(start, stop, pad)

        return self

    def dot(self):
        def rfmt(x, y):
            if y - x == 1:
                return "%s" % x
            else:
                return "%s-%s" % (x, y - 1)
        rstr = ""
        if self._count == 0:
            return
        walk = AVLRangeTreeWalker(self)
        direction = 0
        other = 1 - direction
        go_down = True
        while True:
            if walk.has_child(direction) and go_down:
                walk.push()
                walk.down(direction)
            else:
                if walk.has_left():
                    rstr += "\"%s\" -> \"%s\";\n" % \
                        (rfmt(walk.node.start, walk.stop), \
                         rfmt(walk._node[0].start, walk._node[0].stop))
                if walk.has_right():
                    rstr += "\"%s\" -> \"%s\";\n" % \
                        (rfmt(walk.start, walk.stop), \
                         rfmt(walk._node[1].start, walk._node[1].stop))

                if walk.has_child(other):
                    walk.down(other)
                    go_down = True
                else:
                    if walk.stack_is_empty():
                        return rstr # all done
                    walk.pop()
                    go_down = False

    def __contains__(self, elem):
        """ Is element contained in any ranges? Allowed types for elem are
        integer (no padding check) or string (padding check), otherwise
        TypeError is raised.
        Complexity: O(log n)"""
        if type(elem) is str:
            pad = 0
            # support str type with padding support, eg. `"003" in rangeset'
            if int(elem) != 0:
                selem = elem.lstrip("0")
                if len(elem) - len(selem) > 0:
                    pad = len(elem)
                ielem = int(selem)
            else:
                if len(elem) > 1:
                    pad = len(elem)
                ielem = 0
        else:
            pad = -1
            ielem = int(elem)
        # perform AVL-tree item lookup in O(log n)
        node = self._root
        while node:
            if node.start <= ielem < node.stop:
                # element found: perform padding check if needed
                return (pad == -1 or pad == node.pad or \
                    (pad == 0 and len(str(elem)) >= node.pad))
            node = node[1 - int(ielem < node.start)]
            # py2.5+ -> node = node[0 if ielem < node.start else 1]
        return False

    def issubset(self, other):
        """Report whether another AVLRangeTree contains this tree."""
        try:
            mine = self.ranges()
            their = other.ranges()
            # walk around both tree nodes
            start, stop, pad = mine.next()
            istart, istop, ipad = their.next()
            while True:
                try:
                    # when disjoint, skip needed loop
                    if istop <= start:
                        istart, istop, ipad = their.next()
                        continue
                    elif istart >= stop:
                        return False
                    elif start < istart or stop > istop:
                        return False
                    elif pad != ipad:
                        return False    # padding do not match
                except StopIteration:
                    return False # we have more range => not a subset
                start, stop, pad = mine.next()
        except StopIteration:
            return True
        
    def issuperset(self, other):
        """Report whether this AVLRangeTree contains another tree."""
        return other.issubset(self)

    def update(self, other):
        """Update an AVLRangeTree (in-place union)"""
        if self is not other:
            for start, stop, pad in other.ranges():
                self.insert_range(start, stop, pad)
        
    def difference_update(self, other, strict=False):
        """Remove ranges found in other AVLRangeTree. If strict is True, raise
        KeyError if an element cannot be removed."""
        if self is other:
            self.clear()
        elif strict:
            # self copy needed for strict difference_update() because we don't
            # want self to be modified at all if KeyError is raised
            cpy = self.copy()
            for start, stop, pad in other.ranges():
                cpy.remove_range(start, stop, strict)
            self._root = cpy._root
            self._length = cpy._length
            self._count = cpy._count
        else:
            for start, stop, pad in other.ranges():
                self.remove_range(start, stop, strict)
        
    def symmetric_difference(self, other):
        """Return the symmetric difference of two AVLRangeTree as a new
        AVLRangeTree (not in-place)."""
        xtree = self.__class__()
        try:
            mine = self.ranges()
            their = other.ranges()
            # walk around both tree nodes
            start, stop, pad = mine.next()
            istart, istop, ipad = their.next()
            cursor = min(start, istart)
            while True:
                try:
                    if istop <= start:
                        if cursor < istop:
                            xtree.insert_range(cursor, istop, ipad)
                        cursor = max(start, istop)
                        istart, istop, ipad = their.next()
                        cursor = min(istart, max(cursor, start))
                        continue
                    elif istart >= stop:
                        if cursor < stop:
                            xtree.insert_range(cursor, stop, pad)
                    else:
                        maxstart = max(istart, start)
                        if cursor < maxstart:
                            xtree.insert_range(cursor, maxstart, pad)
                        if stop < istop:
                            cursor = stop
                        else:
                            cursor = istop
                            istart, istop, ipad = their.next()
                            if stop == cursor:
                                cursor = istart
                            continue
                except StopIteration:
                    # their stops
                    try:
                        while True:
                            if stop > cursor:
                                xtree.insert_range(cursor, stop, pad)
                            cursor, stop, pad = mine.next()
                    except StopIteration:
                        return xtree
                start, stop, pad = mine.next()
                cursor = min(start, max(cursor, istart))
                if cursor < min(start, istop):
                    xtree.insert_range(cursor, min(start, istop), pad)
                    cursor = min(start, istop)
        except StopIteration:
            # mine stops
            try:
                while True:
                    if istop > cursor:
                        xtree.insert_range(cursor, istop, ipad)
                    cursor, istop, ipad = their.next()
            except StopIteration:
                pass
            return xtree
        
        

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


class RangeSet(object):
    """
    Advanced range sets.

    RangeSet creation examples:
       >>> rset = RangeSet()            # empty RangeSet
       >>> rset = RangeSet("5,10-42")   # contains 5, 10 to 42
       >>> rset = RangeSet("0-10/2")    # contains 0, 2, 4, 6, 8, 10
     
    Also, RangeSet provides methods like update(), intersection_update()
    or difference_update(), which conform to the Python Set API.

    Latest version of this class uses an AVL self-balancing binary search tree
    to manage internal ranges (instead of a sorted list in ClusterShell 1.5 or
    less).  Thus, basic lookup, add and remove operations have a worst case
    time complexity of O(log k) with k = number of internal ranges.
    """
    _VERSION = 3    # serial version number

    def __init__(self, pattern=None, autostep=None):
        """
        Initialize RangeSet with optional string pattern and autostep
        threshold.
        """
        self._autostep = None
        self.autostep = autostep
        self._rngtree = AVLRangeTree()

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

                self.add_range(start, stop + 1, step, pad)
        
    @classmethod
    def fromlist(cls, rnglist, autostep=None):
        """
        Class method that returns a new RangeSet with ranges from
        provided list.
        """
        inst = RangeSet(autostep=autostep)
        inst.updaten(rnglist)
        return inst

    @classmethod
    def fromone(cls, index, pad=0, autostep=None):
        """
        Class method that returns a new RangeSet of one single item.
        """
        inst = RangeSet(autostep=autostep)
        inst.add(index, pad)
        return inst

    def get_autostep(self):
        if self._autostep >= 1E100:
            return None
        else:
            return self._autostep + 1

    def set_autostep(self, val):
        if val is None:
            # disabled by default for pdsh compat (+inf is 1E400, but a bug in
            # python 2.4 makes it impossible to be pickled, so we use less)
            # NOTE: Later, we could consider sys.maxint here
            self._autostep = 1E100
        else:
            # - 1 because user means node count, but we means real steps
            self._autostep = int(val) - 1

    autostep = property(get_autostep, set_autostep)

    def __iter__(self):
        """
        Iterate over each item in RangeSet.
        """
        for start, stop, pad in self._rngtree.ranges():
            for i in range(start, stop):
                yield "%0*d" % (pad, i)

    def __getstate__(self):
        """called upon pickling"""
        odict = self.__dict__.copy()
        # pickle includes current serial version
        odict['_version'] = RangeSet._VERSION
        # workaround for pickling object from Python < 2.5
        if sys.version_info < (2, 5, 0):
            # Python 2.4 can't pickle slice objects
            odict['_length'] = len(self)
            odict['_ranges'] = [((sli.start, sli.stop, sli.step), pad) \
                                    for sli, pad in self.slices()]
        return odict

    def __setstate__(self, dic):
        """called upon unpickling"""
        self.__dict__.update(dic)
        # unpickle from old version?
        if getattr(self, '_version', 0) < RangeSet._VERSION:
            self._ranges = [(slice(start, stop + 1, step), pad) \
                                for start, stop, step, pad in self._ranges]
        elif hasattr(self, '_ranges'):
            if self._ranges and type(self._ranges[0][0]) is not slice:
                # workaround for object pickled from Python < 2.5
                self._ranges = [(slice(start, stop, step), pad) \
                                for (start, stop, step), pad in self._ranges]
            # convert to v3
            self._rngtree = AVLRangeTree()
            for sli, pad in self._ranges:
                self.add_range(sli.start, sli.stop, sli.step, pad)
            delattr(self, '_ranges')
            delattr(self, '_length')
        else:
            # version 3+
            assert getattr(self, '_version', 0) >= RangeSet._VERSION
            assert hasattr(self, '_rngtree')

    def __len__(self):
        """
        Get the number of items in RangeSet.
        """
        return len(self._rngtree)

    @property
    def rangecount(self):
        """Get the number of integer ranges in RangeSet (O(1))"""
        return self._rngtree.count

    def _str_step(self, ranges):
        """Stringify list `ranges' with x-y/step format support"""
        cnt = 0
        res = ""
        for sli, pad in ranges: 
            if cnt > 0:
                res += ","
            if sli.start + 1 == sli.stop:
                res += "%0*d" % (pad, sli.start)
            else:
                assert sli.step >= 0, "Internal error: sli.step < 0"
                if sli.step == 1:
                    res += "%0*d-%0*d" % (pad, sli.start, pad, sli.stop - 1)
                else:
                    res += "%0*d-%0*d/%d" % (pad, sli.start, pad,
                                             sli.stop - 1, sli.step)
            cnt += sli.stop - sli.start
        return res
        
    def __str__(self):
        """
        Get range-based string.
        """
        # TODO: combine with slices()
        if self._autostep < 1E100:
            return self._str_step(self._folded_slices())
        else:
            res = []
            for start, stop, pad in self._rngtree.ranges():
                if start + 1 == stop:
                    res.append("%0*d" % (pad, start))
                else:
                    res.append("%0*d-%0*d" % (pad, start, pad, stop - 1))
            return ",".join(res)

    # __repr__ is the same as __str__ as it is a valid expression that
    # could be used to recreate a RangeSet with the same value
    __repr__ = __str__

    def copy(self):
        """Return a copy of a RangeSet."""
        cpy = self.__class__()
        cpy._autostep = self._autostep
        cpy._rngtree = self._rngtree.copy()
        return cpy

    __copy__ = copy # For the copy module

    def __contains__(self, obj):
        """
        Is object contained in RangeSet? Object can be either another
        RangeSet object, a string with optional padding (eg. "002") or an
        integer (obviously, no padding check is performed for integer).
        """
        if isinstance(obj, self.__class__):
            return obj._rngtree.issubset(self._rngtree)

        return obj in self._rngtree

    def _folded_slices(self):
        """
        Internal generator that is able to retrieve ranges organized by step.
        Complexity: O(n) with n = number of ranges in tree.
        """
        if self._rngtree.count == 0:
            return

        prng = None         # pending range
        istart = None       # processing starting indice
        m = 0               # processing step
        for start, stop, pad in self._rngtree.ranges():
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
                        yield slice(*prng), pad
                    else:
                        yield slice(istart, istart + 1, 1), pad
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
                        yield slice(*prng), pad
                        prng = None
                if m != i - k:
                    # case: step value has changed
                    if stepped:
                        yield slice(istart, k + 1, m), pad
                    else:
                        for j in range(istart, k - m + 1, m):
                            yield slice(j, j + 1, 1), pad
                        if not unitary:
                            yield slice(k, k + 1, 1), pad
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
                        yield slice(istart, i + 1, m), pad
                        i += 1
                    else:
                        # autostep setting does not apply in that case
                        for j in range(istart, i - m + 1, m):
                            yield slice(j, j + 1, 1), pad
                    if stop > i + 1:    # current->pending only if not unitary
                        prng = [i, stop, 1]
                    istart = i = k = stop - 1
            m = i - k   # compute step
            k = i
        # exited loop, process pending range or indice...
        if m == 0:
            if prng:
                yield slice(*prng), pad
            else:
                yield slice(istart, istart + 1, 1), pad
        else:
            assert m > 0
            stepped = (k - istart >= self._autostep * m)
            if prng:
                if stepped:
                    prng[1] -= 1
                else:
                    istart += m
                yield slice(*prng), pad
                prng = None
            if stepped:
                yield slice(istart, i + 1, m), pad
            else:
                for j in range(istart, i + 1, m):
                    yield slice(j, j + 1, 1), pad

    def _native_slices(self):
        """Get slices without step conversion feature."""
        for start, stop, pad in self._rngtree.ranges():
            yield slice(start, stop, 1), pad

    def slices(self, padding=True):
        """
        Iterate over RangeSet ranges as Python slice objects.

        If padding is True, make an interator that returns 2-length
        tuples, the first argument being a Python slice object
        corresponding to the range and the second being the range's
        padding length information.
        If padding is False, make an iterator that returns Python slice
        objects without padding information, which can be convenient
        for numerical manipulation.
        """
        # return an iterator
        if self._autostep >= 1E100:
            slices_func = self._native_slices
        else:
            slices_func = self._folded_slices

        if padding:
            return slices_func()
        else:
            return imap(itemgetter(0), slices_func())

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
        return self._rngtree.issubset(rangeset._rngtree)

    def issuperset(self, rangeset):
        """
        Report whether this rangeset contains another rangeset.
        """
        self._binary_sanity_check(rangeset)
        return self._rngtree.issuperset(rangeset._rngtree)

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
            inst = RangeSet(autostep=self._autostep + 1)
            inst._rngtree = self._rngtree[index]
            return inst
        elif isinstance(index, int):
            return self._rngtree.__getitem__(index)
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

        if step > 1:
            for i in range(start, stop, step):
                self._rngtree.insert_range(i, i+1, pad)
        else:
            self._rngtree.insert_range(start, stop, pad)

    def union(self, other):
        """
        s.union(t) returns a new rangeset with elements from both s and t.
        """
        self_copy = self.copy()
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
        self.add_range(elem, elem + 1, 1, pad)

    def update(self, rangeset):
        """
        Update a rangeset with the union of itself and another.
        """
        # XXX test if rangeset is a list?
        self._rngtree.update(rangeset._rngtree)

    def updaten(self, rangesets):
        """
        Update a rangeset with the union of itself and several others.
        """
        # XXX deprecated?
        for rng in rangesets:
            if isinstance(rng, RangeSet):
                self.update(rng)
            else:
                self.update(RangeSet(rng))
            # py2.5+
            #self.update(rng if isinstance(rng, RangeSet) else RangeSet(rng))

    def clear(self):
        """
        Remove all ranges from this rangeset.
        """
        self._rngtree.clear()

    def __ior__(self, other):
        """
        Implements the |= operator. So s |= t returns rangeset s with
        elements added from t. (Python version 2.5+ required)
        """
        self._binary_sanity_check(other)
        self.update(other)
        return self

    def intersection(self, rangeset):
        """
        s.intersection(t) returns a new rangeset with elements common
        to s and t.
        """
        self_copy = self.copy()
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
        self._rngtree.intersection_update(rangeset._rngtree)

    def __iand__(self, other):
        """
        Implements the &= operator. So s &= t returns rangeset s keeping
        only elements also found in t. (Python version 2.5+ required)
        """
        self._binary_sanity_check(other)
        self.intersection_update(other)
        return self

    def difference(self, rangeset):
        """
        s.difference(t) returns a new rangeset with elements in s but
        not in t.
        in t.
        """
        self_copy = self.copy()
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
        self._rngtree.difference_update(rangeset._rngtree, strict)

    def __isub__(self, other):
        """
        Implement the -= operator. So s -= t returns rangeset s after
        removing elements found in t. (Python version 2.5+ required)
        """
        self._binary_sanity_check(other)
        self.difference_update(other)
        return self

    def remove(self, elem):
        """
        Remove element elem from the RangeSet. Raise KeyError if elem
        is not contained in the RangeSet.
        """
        try:
            i = int(elem)
            self._rngtree.remove_range(i, i + 1)
        except ValueError:
            raise KeyError, elem

    def discard(self, elem):
        """
        Remove element elem from the RangeSet. Raise KeyError if elem
        is not contained in the RangeSet.
        """
        try:
            i = int(elem)
            self._rngtree.remove_range(i, i + 1)
        except (KeyError, ValueError):
            pass

    def symmetric_difference(self, other):
        """
        s.symmetric_difference(t) returns the symmetric difference of
        two rangesets as a new RangeSet.
        
        (ie. all elements that are in exactly one of the rangesets.)
        """
        inst = RangeSet(autostep=self._autostep + 1)
        inst._rngtree = self._rngtree.symmetric_difference(other._rngtree)
        return inst

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
        self._rngtree = self._rngtree.symmetric_difference(rangeset._rngtree)

    def __ixor__(self, other):
        """
        Implement the ^= operator. So s ^= t returns rangeset s after
        keeping all elements that are in exactly one of the rangesets.
        (Python version 2.5+ required)
        """
        self._binary_sanity_check(other)
        self.symmetric_difference_update(other)
        return self

