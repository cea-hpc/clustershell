# Engine.py -- Base class for ClusterShell engine
# Copyright (C) 2007, 2008, 2009 CEA
#
# This file is part of ClusterShell
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
# $Id$

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

class EngineBaseTimer:
    """
    Abstract class for ClusterShell's engine timer. Such a timer requires a
    relative fire time (delay) in second (as float), and supports an optional
    repeating interval in second (as float too).
    """

    def __init__(self, fire_relative, interval=-1.0):
        self.fire_relative = fire_relative
        self.interval = interval
        self.armed = False

    def set_interval(self, interval):
        """
        Set repeating interval (float value in seconds). You may use it safely
        in an event handler (ev_timer).
        """
        self.interval = float(interval)

    def _fire(self):
        raise NotImplementedError("Derived classes must implement.")


class EngineTimer(EngineBaseTimer):
    """
    Concrete class EngineTimer, used by task.timer().
    """

    def __init__(self, fire_relative, interval, handler):
        EngineBaseTimer.__init__(self, fire_relative, interval)
        self.eh = handler
        assert self.eh != None, "An event handler is needed for timer."

    def _fire(self):
        self.eh._invoke("ev_timer", self)

class _EngineTimerQ:

    class _EngineArmedTimer:
        """
        Helper class that allows comparisons of fire times, to be easily used
        in an heapq.
        """
        def __init__(self, client):
            self.client = client
            # arm timer
            self.fire_date = float(client.fire_relative) + time.time()
            self.client.armed = True

        def disarm(self):
            self.client.armed = False

        def rearm(self):
            self.fire_date += float(self.client.interval)
            time_current = time.time()
            if self.fire_date < time_current:
                self.fire_date = time_current
            self.client.armed = True

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
        self.armed_count = 0

    def __len__(self):
        """
        Return the number of active timers.
        """
        return self.armed_count

    def insert(self, client):
        """
        Insert and arm a client's timer.
        """
        # arm only if fire is set
        if client.fire_relative > 0:
            heapq.heappush(self.timers, _EngineTimerQ._EngineArmedTimer(client))
            self.armed_count += 1

    def remove(self, client):
        """
        Disarm client's timer. Current implementation doesn't really remove the
        timer, but simply flags it as disarmed.
        """
        if not client.armed:
            return

        if self.armed_count <= 0:
            raise ValueError, "Engine client timer not found in timer queue"

        client.armed = False
        self.armed_count -= 1

    def _dequeue_disarmed(self):
        """
        Dequeue disarmed timers (garbage collector).
        """
        while len(self.timers) > 0 and not self.timers[0].client.armed:
            heapq.heappop(self.timers)

    def fire(self):
        """
        Remove the smallest timer from the queue and fire its associated client.
        Raise IndexError if the queue is empty.
        """
        self._dequeue_disarmed()

        atimer = heapq.heappop(self.timers)
        atimer.disarm()
        atimer.client._fire()

        if atimer.client.interval > 0.0:
            atimer.rearm()
            heapq.heappush(self.timers, atimer)
        else:
            self.armed_count -= 1

    def expire_relative(self):
        """
        Return next timer fire delay (relative time).
        """
        self._dequeue_disarmed()
        if len(self.timers) > 0:
            return max(0., self.timers[0].fire_date - time.time())

        return -1

    def expired(self):
        """
        Has a timer expired?
        """
        self._dequeue_disarmed()
        return len(self.timers) > 0 and \
            (self.timers[0].fire_date - time.time()) <= 1e-2

    def clear(self):
        """
        Stop and clear all timers.
        """
        self.timers = []


class Engine:
    """
    Interface for ClusterShell engine. Subclasses have to implement a runloop
    listening for client events.
    """

    # Worker's IO state flags. Hopefully, I/O state handling is easy here, as
    # reading and writing are not performed on the same file descriptor.
    IOSTATE_NONE = 0x0
    IOSTATE_READING = 0x1
    IOSTATE_WRITING = 0x2
    IOSTATE_ANY = 0x3

    def __init__(self, info):
        """
        Initialize base class.
        """
        # take a reference on info dict
        self.info = info

        # keep track of all clients
        self._clients = Set()

        # keep track of registered clients in a dict where keys are fileno
        # note: len(self.reg_clients) <= configured fanout
        self.reg_clients = {}

        # timer queue to handle both timers and clients timeout
        self.timerq = _EngineTimerQ()

        # thread stuffs
        self.run_lock = thread.allocate_lock()
        self.start_lock = thread.allocate_lock()
        self.start_lock.acquire()

    def clients(self):
        """
        Get a copy of clients set.
        """
        return self._clients.copy()

    def add(self, client):
        """
        Add a client to engine. Subclasses that override this method
        should call base class method.
        """
        # bind to engine
        client._set_engine(self)

        # add to clients set
        self._clients.add(client)

        if self.run_lock.locked():
            # in-fly add if running
            self.register(client._start())

    def remove(self, client, did_timeout=False):
        """
        Remove a client from engine. Subclasses that override this
        method should call base class method.
        """
        self._clients.discard(client)

        if client.registered:
            self.unregister(client)
            client._close(force=False, timeout=did_timeout)
            self.start_all()

    def clear(self, did_timeout=False):
        """
        Remove all clients. Subclasses that override this method should
        call base class method.
        """
        while len(self._clients) > 0:
            client = self._clients.pop()
            if client.registered:
                self.unregister(client)
                client._close(force=True, timeout=did_timeout)

    def register(self, client):
        """
        Register a client. Subclasses that override this method should
        call base class method.
        """
        assert client in self._clients
        assert client.registered == False

        self.reg_clients[client.reader_fileno()] = client
        self.reg_clients[client.writer_fileno()] = client
        client._iostate = Engine.IOSTATE_ANY
        client.registered = True

        # start timeout timer
        self.timerq.insert(client)

    def unregister(self, client):
        """
        Unregister a client. Subclasses that override this method should
        call base class method.
        """
        assert client.registered == True
        
        # remove timeout timer
        self.timerq.remove(client)

        del self.reg_clients[client.writer_fileno()]
        del self.reg_clients[client.reader_fileno()]
        client.registered = False

    def add_timer(self, timer):
        """
        Add engine timer.
        """
        self.timerq.insert(timer)

    def remove_timer(self, timer):
        """
        Remove engine timer.
        """
        self.timerq.remove(timer)

    def fire_timers(self):
        """
        Fire expired timers for processing.
        """
        while self.timerq.expired():
            self.timerq.fire()

    def start_all(self):
        """
        Start and register all possible clients, in respect of task fanout.
        """
        fanout = self.info["fanout"]
        if fanout <= len(self.reg_clients):
            return

        for client in self._clients:
            if not client.registered:
                self.register(client._start())
                if fanout <= len(self.reg_clients):
                    break
    
    def run(self, timeout):
        """
        Run engine in calling thread.
        """
        # change to running state
        if not self.run_lock.acquire(0):
            raise EngineAlreadyRunningError()

        # start clients now
        self.start_all()

        # we're started
        self.start_lock.release()

        # note: try-except-finally not supported before python 2.5
        try:
            try:
                self.runloop(timeout)
            except Exception, e:
                # any exceptions invalidate clients
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

