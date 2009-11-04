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


class MsgTreeElem:
    """
    Helper class used to build a messages tree. Advantages are:
    (1) low memory consumption especially on a cluster when all nodes
    return similar messages,
    (2) gathering of messages is done (almost) automatically.
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
        self.sources = None
   
    def __iter__(self):
        """
        Iterate over tree key'd elements.
        """
        estack = [ self ]

        while len(estack) > 0:
            elem = estack.pop()
            if len(elem.children) > 0:
                estack += elem.children.values()
            if elem.sources and len(elem.sources) > 0:
                yield elem
    
    def _add_source(self, source):
        """
        Add source tuple (worker, key) to this element.
        """
        if not self.sources:
            self.sources = source.copy()
        else:
            self.sources.update(source)
    
    def _remove_source(self, source):
        """
        Remove a source tuple (worker, key) from this element.
        It's used when moving it to a child.
        """
        if self.sources:
            self.sources.difference_update(source)
        
    def add_msg(self, source, msg):
        """
        A new message line is coming, add it to the tree.
        source is a tuple identifying the message source
        """
        if self.sources and len(self.sources) == 1:
            # do it quick when only one source is attached
            src = self.sources
            self.sources = None
        else:
            # remove source from parent (self)
            src = set([ source ])
            self._remove_source(src)

        # add msg elem to child
        elem = self.children.setdefault(msg, self.__class__(msg, self))
        # add source to elem
        elem._add_source(src)
        return elem

    def message(self):
        """
        Get the whole message buffer from this tree element.
        """
        msg = ""

        # no msg in root element
        if self.msg is None:
            return msg
        
        # build list of msg (reversed by design)
        rmsgs = [self.msg]
        parent = self.parent
        while parent and parent.msg is not None:
            rmsgs.append(parent.msg)
            parent = parent.parent

        # reverse the list
        rmsgs.reverse()

        # concat buffers
        return '\n'.join(rmsgs)

class MsgTree:

    def __init__(self):
        # root of msg tree
        self._root = MsgTreeElem()
        # dict of sources to msg tree elements
        self._d_source_msg = {}

    def reset(self):
        """
        Reset tree buffers.
        """
        self._root = MsgTreeElem()
        self._d_source_msg = {}

    def add(self, source, msg):
        """
        Add a worker message associated with a source.
        """
        # try first to get current element in msgs tree
        e_msg = self._d_source_msg.get(source)
        if not e_msg:
            # key not found (first msg from it)
            e_msg = self._root

        # add child msg and update dict
        self._d_source_msg[source] = e_msg.add_msg(source, msg)

    def iter_buffers(self, match_keys=None):
        """
        Iterate over buffers, returns a tuple (buffer, keys).
        """
        if match_keys:
            for e in self._root:
                keys = [t[1] for t in e.sources if t[1] in match_keys]
                if keys:
                    yield e.message(), keys
        else:
            for e in self._root:
                yield e.message(), [t[1] for t in e.sources]
            
    def get_by_source(self, source):
        """
        Get a message by its source.
        """
        e_msg = self._d_source_msg.get(source)

        if e_msg is None:
            return None

        return e_msg.message()

    def iter_by_key(self, key):
        """
        Return an iterator over stored messages for the given key.
        """
        for (w, k), e in self._d_source_msg.iteritems():
            if k == key:
                yield e.message()

    def iter_by_worker(self, worker, match_keys=None):
        """
        Return an iterator over messages and keys list for a specific
        worker and optional matching keys.
        """
        if match_keys:
            for e in self._root:
                keys = [t[1] for t in e.sources if t[0] is worker and t[1] in match_keys]
                if len(keys) > 0:
                    yield e.message(), keys
        else:
            for e in self._root:
                keys = [t[1] for t in e.sources if t[0] is worker]
                if len(keys) > 0:
                    yield e.message(), keys

    def iterkey_by_worker(self, worker):
        """
        Return an iterator over key, message for a specific worker.
        """
        for (w, k), e in self._d_source_msg.iteritems():
            if w is worker:
                yield k, e.message()
 
