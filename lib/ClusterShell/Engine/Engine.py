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

class EngineIllegalOperationError(EngineException):
    """
    Error raised when an illegal operation has been performed.
    """

class EngineAlreadyRunningError(EngineIllegalOperationError):
    """
    Error raised when the engine is already running.
    """


class EngineBaseTimer:
    """
    Abstract class for ClusterShell's engine timer. Such a timer
    requires a relative fire time (delay) in seconds (as float), and
    supports an optional repeating interval in seconds (as float too).

    See EngineTimer for more information about ClusterShell timers.
    """

    def __init__(self, fire_delay, interval=-1.0):
        """
        Create a base timer.
        """
        self.fire_delay = fire_delay
        self.interval = interval
        self._engine = None
        self._timercase = None

    def _set_engine(self, engine):
        """
        Bind to engine, called by Engine.
        """
        if self._engine is not None:
            # A timer can be registered to only one engine at a time.
            raise EngineIllegalOperationError("Already bound to engine.")

        self._engine = engine

    def invalidate(self):
        """
        Invalidates a timer object, stopping it from ever firing again.
        """
        self._engine.timerq.invalidate(self)

    def set_nextfire(self, fire_delay, interval=-1):
        """
        Set the next firing delay in seconds for an EngineTimer object.

        The optional paramater `interval' sets the firing interval
        of the timer. If not specified, the timer fires once and then
        is automatically invalidated.

        Time values are expressed in second using floating point
        values. Precision is implementation (and system) dependent.

        It is safe to call this method from the task owning this
        timer object, in any event handlers, anywhere.

        However, resetting a timer's next firing time may be a
        relatively expensive operation. It is more efficient to let
        timers autorepeat or to use this method from the timer's own
        event handler callback (ie. from its ev_timer).
        """
        self.fire_delay = fire_delay
        self.interval = interval
        self._engine.timerq.reschedule(self)

    def _fire(self):
        raise NotImplementedError("Derived classes must implement.")


class EngineTimer(EngineBaseTimer):
    """
    Concrete class EngineTimer

    An EngineTimer object represents a timer bound to an engine that
    fires at a preset time in the future. Timers can fire either only
    once or repeatedly at fixed time intervals. Repeating timers can
    also have their next firing time manually adjusted.

    A timer is not a real-time mechanism; it fires when the task's
    underlying engine to which the timer has been added is running and
    able to check if the timer's firing time has passed.
    """

    def __init__(self, fire_delay, interval, handler):
        EngineBaseTimer.__init__(self, fire_delay, interval)
        self.eh = handler
        assert self.eh != None, "An event handler is needed for timer."

    def _fire(self):
        self.eh._invoke("ev_timer", self)

class _EngineTimerQ:

    class _EngineTimerCase:
        """
        Helper class that allows comparisons of fire times, to be easily used
        in an heapq.
        """
        def __init__(self, client):
            self.client = client
            self.client._timercase = self
            # arm timer (first time)
            assert self.client.fire_delay > 0
            self.fire_date = self.client.fire_delay + time.time()

        def __cmp__(self, other):
            if self.fire_date < other.fire_date:
                return -1
            elif self.fire_date > other.fire_date:
                return 1
            else:
                return 0

        def arm(self, client):
            assert client != None
            self.client = client
            self.client._timercase = self
            # setup next firing date
            time_current = time.time()
            if self.client.fire_delay > 0:
                self.fire_date = self.client.fire_delay + time_current
            else:
                interval = float(self.client.interval)
                assert interval > 0
                self.fire_date += interval
                # If the firing time is delayed so far that it passes one
                # or more of the scheduled firing times, reschedule the
                # timer for the next scheduled firing time in the future.
                while self.fire_date < time_current:
                    self.fire_date += interval

        def disarm(self):
            client = self.client
            client._timercase = None
            self.client = None
            return client

        def armed(self):
            return self.client != None
            

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

    def schedule(self, client):
        """
        Insert and arm a client's timer.
        """
        # arm only if fire is set
        if client.fire_delay > 0:
            heapq.heappush(self.timers, _EngineTimerQ._EngineTimerCase(client))
            self.armed_count += 1

    def reschedule(self, client):
        """
        Re-insert client's timer.
        """
        if client._timercase:
            self.invalidate(client)
            self._dequeue_disarmed()
            self.schedule(client)

    def invalidate(self, client):
        """
        Invalidate client's timer. Current implementation doesn't really remove
        the timer, but simply flags it as disarmed.
        """
        if not client._timercase:
            # invalidate fire_delay, needed when the timer is being fired
            client.fire_delay = 0
            return

        if self.armed_count <= 0:
            raise ValueError, "Engine client timer not found in timer queue"

        client._timercase.disarm()
        self.armed_count -= 1

    def _dequeue_disarmed(self):
        """
        Dequeue disarmed timers (sort of garbage collection).
        """
        while len(self.timers) > 0 and not self.timers[0].armed():
            heapq.heappop(self.timers)

    def fire(self):
        """
        Remove the smallest timer from the queue and fire its associated client.
        Raise IndexError if the queue is empty.
        """
        self._dequeue_disarmed()

        timercase = heapq.heappop(self.timers)
        client = timercase.disarm()
        
        client.fire_delay = 0
        client._fire()

        if client.fire_delay > 0 or client.interval > 0:
            timercase.arm(client)
            heapq.heappush(self.timers, timercase)
        else:
            self.armed_count -= 1

    def nextfire_delay(self):
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
        self.timerq.schedule(client)

    def unregister(self, client):
        """
        Unregister a client. Subclasses that override this method should
        call base class method.
        """
        assert client.registered == True
        
        # remove timeout timer
        self.timerq.invalidate(client)

        del self.reg_clients[client.writer_fileno()]
        del self.reg_clients[client.reader_fileno()]
        client.registered = False

    def add_timer(self, timer):
        """
        Add engine timer.
        """
        timer._set_engine(self)

        self.timerq.schedule(timer)

    def remove_timer(self, timer):
        """
        Remove engine timer.
        """
        self.timerq.invalidate(timer)

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

