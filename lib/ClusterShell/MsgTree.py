#
# Copyright CEA/DAM/DIF (2007, 2008, 2009)
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
MsgTree

ClusterShell message tree module. The purpose of MsgTree is to
provide a shared message tree for storing message lines received
from ClusterShell Workers (for example, from remote cluster
commands). It should be efficient, in term of compute power and memory
consumption, especially when remote messages are the same.
"""

from itertools import imap
from operator import itemgetter


class MsgTreeElem(object):
    """
    Class representing an element of the MsgTree and its associated
    message. Object of this class are returned by the various MsgTree
    methods like messages() or walk(). The object can then be used as
    an iterator over the message lines or casted into a string.
    """
    def __init__(self, msgline=None, parent=None):
        """
        Initialize message tree element.
        """
        # structure
        self.parent = parent
        self.children = {}
        # content
        self.msgline = msgline
        self.keys = None
   
    def __len__(self):
        """Length of whole message string."""
        return len(str(self))

    def __eq__(self, other):
        """Comparison method compares whole message strings."""
        return str(self) == str(other)

    def _shift(self, key, target_elem):
        """Shift one of our key to specified target element."""
        if self.keys and len(self.keys) == 1:
            shifting = self.keys
            self.keys = None
        else:
            shifting = set([ key ])
            if self.keys:
                self.keys.difference_update(shifting)

        if not target_elem.keys:
            target_elem.keys = shifting
        else:
            target_elem.keys.update(shifting)

        return target_elem

    def __getitem__(self, i):
        return list(self.lines())[i]

    def __iter__(self):
        """Iterate over message lines starting from this tree element."""
        # no msgline in root element
        if self.msgline is None:
            return
        # trace the message path
        path = [self.msgline]
        parent = self.parent
        while parent.msgline is not None:
            path.append(parent.msgline)
            parent = parent.parent
        # rewind path
        while path:
            yield path.pop()

    def lines(self):
        """
        Get the whole message lines iterator from this tree element.
        """
        return iter(self)

    splitlines = lines

    def message(self):
        """
        Get the whole message buffer from this tree element.
        """
        # concat buffers
        return '\n'.join(self.lines())

    __str__ = message

    def append(self, key, msgline):
        """
        A new message line is coming, append it to the tree element
        with associated source key. Called by MsgTree.add().
        Return corresponding newly created MsgTreeElem.
        """
        # create new child element and shift down the key
        return self._shift(key, self.children.setdefault(msgline, \
                                        self.__class__(msgline, self)))


class MsgTree(object):
    """
    A MsgTree object maps key objects to multi-lines messages.
    MsgTree's are mutable objects. Keys are almost arbitrary values
    (must be hashable). Message lines are organized as a tree
    internally. MsgTree provides low memory consumption especially
    on a cluster when all nodes return similar messages. Also,
    the gathering of messages is done automatically.
    """

    def __init__(self):
        # root element of MsgTree
        self._root = MsgTreeElem()
        # dict of keys to MsgTreeElem
        self._keys = {}

    def clear(self):
        """Remove all items from the MsgTree."""
        self._root = MsgTreeElem()
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
        Add a message line associated with the given key to the MsgTree.
        """
        # try to get current element in MsgTree for the given key,
        # defaulting to the root element
        e_msg = self._keys.get(key, self._root)

        # add child msg and update keys dict
        self._keys[key] = e_msg.append(key, msgline)

    def keys(self):
        """Return an iterator over MsgTree's keys."""
        return self._keys.iterkeys()

    __iter__ = keys
    
    def messages(self, match=None):
        """Return an iterator over MsgTree's messages."""
        return imap(itemgetter(0), self.walk(match))
    
    def items(self, match=None, mapper=None):
        """
        Return (key, message) for each key of the MsgTree.
        """
        if mapper is None:
            mapper = lambda k: k
        for key, elem in self._keys.iteritems():
            if match is None or match(key):
                yield mapper(key), elem

    def _depth(self):
        """
        Return the depth of the MsgTree, ie. the max number of lines
        per message. Added for debugging.
        """
        depth = 0
        # stack of (element, depth) tuples used to walk the tree
        estack = [ (self._root, depth) ]

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
        Return an iterator of (message, keys) tuples for each
        different message in the tree.
        """
        # stack of elements used to walk the tree (depth-first)
        estack = [ self._root ]

        while estack:
            elem = estack.pop()
            if len(elem.children) > 0:
                estack += elem.children.values()
            if elem.keys: # has some keys
                mkeys = filter(match, elem.keys)
                if len(mkeys):
                    yield elem, map(mapper, mkeys)

