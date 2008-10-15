# Engine.py -- Base class for ClusterShell engine
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
# $Id: Engine.py 7 2007-12-20 14:52:31Z st-cea $


from sets import Set

class EngineError(Exception):
    """
    Base engine error exception.
    """
    pass

class EngineTimeoutError(EngineError):
    """
    Raised when a timeout is encountered.
    """
    pass

class EngineInProgressError(EngineError):
    """
    Raised on operation in progress, for example the results are
    not available yet.
    """
    pass

class _MsgTreeElem:
    """
    Helper class used to build a messages tree. Advantages are:
    (1) low memory consumption especially on a cluster when all nodes return similar messages,
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
            self.sources.union_update(source)
    
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
            src = Set([ source ])
            self._remove_source(src)

        # add msg elem to child
        elem = self.children.setdefault(msg, _MsgTreeElem(msg, self))
        # add source to elem
        elem._add_source(src)
        return elem

    def message(self):
        """
        Get the whole message buffer from this tree element.
        """
        msg = ""

        # no msg in root element
        if not self.msg:
            return msg
        
        # build list of msg (reversed by design)
        rmsgs = [self.msg]
        parent = self.parent
        while parent and parent.msg:
            rmsgs.append(parent.msg)
            parent = parent.parent

        # reverse the list
        rmsgs.reverse()

        # concat buffers
        return ''.join(rmsgs)


class Engine:
    """
    Interface for ClusterShell engine. Subclass must implement a runloop listening
    for workers events.
    """

    def __init__(self, info):
        """
        Initialize base class.
        """
        self.info = info
        self.worker_list = []

        # root of msg tree
        self._msg_root = _MsgTreeElem()

        # dict of sources to msg tree elements
        self._d_source_msg = {}

        # dict of sources to return codes
        self._d_source_rc = {}

        # dict of return codes to sources
        self._d_rc_sources = {}

        # keep max rc
        self._max_rc = 0

    def add(self, worker):
        """
        Add worker to engine.
        """
        worker._set_engine(self)
        self.worker_list.append(worker)

    def run(self, timeout):
        """
        Run engine in calling thread."
        """
        self._runloop(timeout)

        # clear engine worker list
        self.worker_list = []

    def _runloop(self, timeout):
        """
        Run engine in calling thread.
        """
        raise NotImplementedError("Derived classes must implement.")

    def exited(self):
        """
        Returns True if the engine has exited the runloop once.
        """
        raise NotImplementedError("Derived classes must implement.")

    def join(self):
        """
        Block calling thread until engine terminates.
        """
        raise NotImplementedError("Derived classes must implement.")

    def add_msg(self, source, msg):
        """
        Add a worker message associated with a source.
        """
        # try first to get current element in msgs tree
        e_msg = self._d_source_msg.get(source)
        if not e_msg:
            # key not found (first msg from it)
            e_msg = self._msg_root

        # add child msg and update dict
        self._d_source_msg[source] = e_msg.add_msg(source, msg)

    def set_rc(self, source, rc, override=True):
        """
        Add a worker return code associated with a source.
        """
        if not override and self._d_source_rc.has_key(source):
            return

        # store rc by source
        self._d_source_rc[source] = rc

        # store source by rc
        e = self._d_rc_sources.get(rc)
        if e is None:
            self._d_rc_sources[rc] = Set([source])
        else:
            self._d_rc_sources[rc].add(source)
        
        # update max rc
        if rc > self._max_rc:
            self._max_rc = rc

    def message_by_source(self, source):
        """
        Get a message by its source (worker, key).
        """
        e_msg = self._d_source_msg.get(source)

        if e_msg:
            return e_msg.message()
        else:
            return None

    def iter_messages(self):
        """
        Returns an iterator over all messages and keys list.
        """
        for e in self._msg_root:
            yield e.message(), [t[1] for t in e.sources]

    def iter_messages_by_worker(self, worker):
        """
        Returns an iterator over messages and keys list for a specific worker.
        """
        for e in self._msg_root:
            yield e.message(), [t[1] for t in e.sources if t[0] is worker]

    def iter_key_messages_by_worker(self, worker):
        """
        Returns an iterator over key, message for a specific worker.
        """
        for (w, k), e in self._d_source_msg.iteritems():
            if w is worker:
                yield k, e.message()
 
    def retcode_by_source(self, source):
        """
        Get a return code by its source (worker, key).
        """
        if not self.exited:
            raise EngineInProgressError()

        return self._d_source_msg.get(source, 0)
   
    def iter_retcodes(self):
        """
        Returns an iterator over return codes and keys list.
        """
        if not self.exited:
            raise EngineInProgressError()

        # Use the items iterator for the underlying dict.
        for rc, src in self._d_rc_sources.iteritems():
            yield rc, [t[1] for t in src]

    def iter_retcodes_by_worker(self, worker):
        """
        Returns an iterator over return codes and keys list for a specific worker.
        """
        if not self.exited:
            raise EngineInProgressError()

        # Use the items iterator for the underlying dict.
        for rc, src in self._d_rc_sources.iteritems():
            yield rc, [t[1] for t in src if t[0] is worker]

    def max_retcode(self):
        """
        Get max return code encountered during last run.
        """
        if not self.exited:
            raise EngineInProgressError()

        return self._max_rc

