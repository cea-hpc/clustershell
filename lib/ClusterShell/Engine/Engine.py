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

"""
Interface of underlying Task's engine.
"""

from sets import Set

import heapq
import thread
import time

class EngineException(Exception):
    """
    Base engine exception.
    """

class EngineAbortException(EngineException):
    """
    Raised on user abort.
    """

class EngineTimeoutException(EngineException):
    """
    Raised when a timeout is encountered.
    """

class EngineAlreadyRunningError(EngineException):
    """
    Error raised when the engine is already running.
    """


class _MsgTreeElem:
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


class _WorkerTimerQ:

    class _WorkerTimer:
        """
        Helper class to represent a fire time. Allow to be used in an
        heapq.
        """
        def __init__(self, worker):
            self.worker = worker
            self.fire_date = float(worker.timeout) + time.time()

        def __cmp__(self, other):
            if self.fire_date < other.fire_date:
                return -1
            elif self.fire_date > other.fire_date:
                return 1
            else:
                return 0

    def __init__(self):
        """
        Initializer.
        """
        self.timers = []

    def __len__(self):
        """
        Return the number of active timers.
        """
        return len(self.timers)

    def push(self, worker):
        """
        Add and arm a worker's timer.
        """
        # arm only if timeout is set
        if worker.timeout > 0:
            heapq.heappush(self.timers, _WorkerTimerQ._WorkerTimer(worker))

    def pop(self):
        """
        Remove one timer in the queue and return its associated worker.
        """
        return heapq.heappop(self.timers).worker

    def expire_relative(self):
        """
        Return next timer fire delay (relative time).
        """

        if len(self.timers) > 0:
            return max(0., self.timers[0].fire_date - time.time())

        return -1

    def expired(self):
        """
        Has a timer expired?
        """
        return len(self.timers) > 0 and \
            (self.timers[0].fire_date - time.time()) <= 1e-2

    def clear(self):
        """
        Stop and clear all timers.
        """
        del self.timers
        self.timers = []

class Engine:
    """
    Interface for ClusterShell engine. Subclass must implement a runloop
    listening for workers events.
    """

    def __init__(self, info):
        """
        Initialize base class.
        """
        # take a reference on info dict
        self.info = info

        # keep track of all workers
        self._workers = Set()

        # keep track of registered workers in a dict where keys are fileno
        self.reg_workers = {}

        # timer queue to handle workers timeout
        self.timerq = _WorkerTimerQ()

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

        # thread stuffs
        self.run_lock = thread.allocate_lock()
        self.start_lock = thread.allocate_lock()
        self.start_lock.acquire()

    def _reset(self):
        """
        Reset buffers and retcodes managment variables.
        """
        self._msg_root = _MsgTreeElem()
        self._d_source_msg = {}
        self._d_source_rc = {}
        self._d_rc_sources = {}
        self._max_rc = 0
 
    def workers(self):
        """
        Get a copy of workers set.
        """
        return self._workers.copy()

    def add(self, worker):
        """
        Add a worker to engine. Subclasses that override this method
        should call base class method.
        """
        # bind to engine
        worker._set_engine(self)

        # add to workers set
        self._workers.add(worker)

        if self.run_lock.locked():
            # in-fly add if running
            self.register(worker._start())

    def remove(self, worker, did_timeout=False):
        """
        Remove a worker from engine. Subclasses that override this
        method should call base class method.
        """
        self._workers.remove(worker)
        if worker.registered:
            self.unregister(worker)
            worker._close(force=False, timeout=did_timeout)

    def clear(self, did_timeout=False):
        """
        Remove all workers. Subclasses that override this method should
        call base class method.
        """
        while len(self._workers) > 0:
            worker = self._workers.pop()
            if worker.registered:
                self.unregister(worker)
                worker._close(force=True, timeout=did_timeout)

    def register(self, worker):
        """
        Register a worker. Subclasses that override this method should
        call base class method.
        """
        assert worker in self._workers
        assert worker.registered == False

        self.reg_workers[worker.fileno()] = worker
        worker.registered = True

    def unregister(self, worker):
        """
        Unregister a worker. Subclasses that override this method should
        call base class method.
        """
        assert worker.registered == True

        del self.reg_workers[worker.fileno()]
        worker.registered = False

    def start_all(self):
        """
        Start and register all stopped workers.
        """
        for worker in self._workers:
            if not worker.registered:
                self.register(worker._start())
    
    def run(self, timeout):
        """
        Run engine in calling thread.
        """
        # change to running state
        if not self.run_lock.acquire(0):
            raise EngineAlreadyRunningError()

        # arm worker timers
        for worker in self._workers:
            self.timerq.push(worker)

        # start workers now
        self.start_all()

        # we're started
        self.start_lock.release()

        # prepare msg and rc handling
        self._reset()

        # note: try-except-finally not supported before python 2.5
        try:
            try:
                self.runloop(timeout)
            except Exception, e:
                # any exceptions invalidate workers
                self.clear(isinstance(e, EngineTimeoutException))
                raise
        finally:
            # cleanup
            self.timerq.clear()

            # change to idle state
            self.start_lock.acquire()
            self.run_lock.release()

    def runloop(self, timeout):
        """
        Engine specific run loop. Derived classes must implement.
        """
        raise NotImplementedError("Derived classes must implement.")

    def abort(self):
        """
        Abort task's running loop.
        """
        raise EngineAbortException()

    def exited(self):
        """
        Return True if the engine has exited the runloop once.
        """
        raise NotImplementedError("Derived classes must implement.")

    def join(self):
        """
        Block calling thread until runloop has finished.
        """
        # make sure engine has started first
        self.start_lock.acquire()
        self.start_lock.release()
        # joined once run_lock is available
        self.run_lock.acquire()
        self.run_lock.release()

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

        if e_msg is None:
            return None

        return e_msg.message()

    def iter_messages(self):
        """
        Return an iterator over all messages and keys list.
        """
        for e in self._msg_root:
            yield e.message(), [t[1] for t in e.sources]

    def iter_messages_by_key(self, key):
        """
        Return an iterator over stored messages for the given key.
        """
        for (w, k), e in self._d_source_msg.iteritems():
            if k == key:
                yield e.message()

    def iter_messages_by_worker(self, worker):
        """
        Return an iterator over messages and keys list for a specific
        worker.
        """
        for e in self._msg_root:
            keys = [t[1] for t in e.sources if t[0] is worker]
            if len(keys) > 0:
                yield e.message(), keys

    def iter_key_messages_by_worker(self, worker):
        """
        Return an iterator over key, message for a specific worker.
        """
        for (w, k), e in self._d_source_msg.iteritems():
            if w is worker:
                yield k, e.message()
 
    def retcode_by_source(self, source):
        """
        Get a return code by its source (worker, key).
        """
        return self._d_source_msg.get(source, 0)
   
    def iter_retcodes(self):
        """
        Return an iterator over return codes and keys list.
        """
        # Use the items iterator for the underlying dict.
        for rc, src in self._d_rc_sources.iteritems():
            yield rc, [t[1] for t in src]

    def iter_retcodes_by_key(self, key):
        """
        Return an iterator over return codes for the given key.
        """
        for (w, k), rc in self._d_source_rc.iteritems():
            if k == key:
                yield rc

    def iter_retcodes_by_worker(self, worker):
        """
        Return an iterator over return codes and keys list for a
        specific worker.
        """
        # Use the items iterator for the underlying dict.
        for rc, src in self._d_rc_sources.iteritems():
            keys = [t[1] for t in src if t[0] is worker]
            if len(keys) > 0:
                yield rc, keys

    def max_retcode(self):
        """
        Get max return code encountered during last run.
        """
        return self._max_rc

