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

ClusterShell message tree classes.
"""

class _MsgTreeElem:
    """
    Class representing an element of the MsgTree.
    """
    def __init__(self, msg=None, parent=None):
        """
        Initialize message tree element.
        """
        # structure
        self.parent = parent
        self.children = {}
        # content
        self.msg = msg
        self.keys = None
   
    def __len__(self):
        if self.keys:
            return len(self.keys)
        return 0

    def __str__(self):
        return "<MsgTree._MsgTreeElem parent=%s keys=%s msg=%s>" % \
            (self.parent, self.keys, self.msg)

    def _shift(self, key, target_elem):
        """
        Shift one of our key to specified target element.
        """
        if len(self) == 1:
            shifting = self.keys
            self.keys = None
        else:
            shifting = set([ key ])
            if self.keys:
                self.keys.difference_update(shifting)

        if len(target_elem) == 0:
            target_elem.keys = shifting
        else:
            target_elem.keys.update(shifting)

        return target_elem

    def add(self, key, msg):
        """
        A new message line is coming, add it to the tree with
        associated source key.
        """
        # create new child element and shift down the key
        return self._shift(key, self.children.setdefault(msg,
                                        self.__class__(msg, self)))

    def msglist(self):
        """
        Get the whole message list from this tree element.
        """
        msg = ""
        # no msg in root element
        if self.msg is None:
            return msg
        
        # build list of msg (reversed by design)
        rmsgs = [self.msg]
        parent = self.parent
        while parent.msg is not None:
            rmsgs.append(parent.msg)
            parent = parent.parent

        # reverse the list
        rmsgs.reverse()
        return rmsgs

    def message(self):
        """
        Get the whole message buffer from this tree element.
        """
        # concat buffers
        return '\n'.join(self.msglist())


class MsgTreeMsg:
    """
    Class representing a MsgTree message. Object of this class
    are returned by the various MsgTree methods like msg_keys().
    The object can then be used as an iterator over the message
    lines or casted into a string.
    """
    def __init__(self, elem):
        self._elem = elem

    def __len__(self):
        return len(self._elem.message())

    def __eq__(self, other):
        return str(self) == str(other)

    def __iter__(self):
        return iter(self._elem.msglist())

    def __getitem__(self, i):
        return self._elem.msglist()[i]
        
    def __str__(self):
        return self._elem.message()


class MsgTree:
    """
    A MsgTree object maps key objects to multi-lines messages.
    MsgTree's are mutable objects. Keys are almost abritrary values
    (must be hashable). Message lines are organized as a tree
    internally. MsgTree provides low memory consumption especially
    on a cluster when all nodes return similar messages. Also,
    gathering of messages is done automatically.
    """

    def __init__(self):
        """Initialization method."""
        self.clear()

    def clear(self):
        # root element of MsgTree
        self._root = _MsgTreeElem()
        # dict of keys to _MsgTreeElem
        self._keys = {}

    def __len__(self):
        """Return the number of keys contained in the MsgTree."""
        return len(self._keys)

    def __getitem__(self, key):
        """Return the message of MsgTree with specified key. Raises a
        KeyError if key is not in the MsgTree."""
        return MsgTreeMsg(self._keys[key])

    def get(self, key):
        """Return the message of MsgTree with specified key or None
        if not found."""
        e = self._keys.get(key)
        if e is None:
            return None
        return MsgTreeMsg(e)

    def _walktree(self, match=None, mapper=None):
        """Walk the tree. Optionally filter keys on match parameter,
        and optionally map resulting keys with mapper."""
        # stack of elements used to walk the tree
        estack = [ self._root ]

        while len(estack) > 0:
            elem = estack.pop()
            if len(elem.children) > 0:
                estack += elem.children.values()
            if len(elem) > 0: # has key(s)
                mkeys = filter(match, elem.keys)
                if len(mkeys):
                    yield elem, map(mapper, mkeys)

    def keys(self):
        """Return an iterator over MsgTree's keys."""
        return self._keys.iterkeys()

    __iter__ = keys
    
    def msgs(self, match=None):
        """Return an iterator over MsgTree's messages."""
        for elem, keys in self._walktree(match):
            yield MsgTreeMsg(elem)
    
    def items(self, match=None):
        """Return (key, message) for each key of the MsgTree."""
        if not match:
            match = bool
        for key, elem in self._keys.iteritems():
            if match(key):
                yield key, MsgTreeMsg(elem)

    def msg_keys(self, match=None, mapper=None):
        """Return (msg, keys) for each different msg of the MsgTree."""
        for elem, keys in self._walktree(match, mapper):
            yield MsgTreeMsg(elem), keys

    def add(self, key, msg):
        """Add a message associated with the given key to the MsgTree."""
        # try to get current element in MsgTree for the given key,
        # defaulting to the root element
        e_msg = self._keys.get(key) or self._root

        # add child msg and update keys dict
        self._keys[key] = e_msg.add(key, msg)

