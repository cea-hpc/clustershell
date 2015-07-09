#
# Copyright CEA/DAM/DIF (2007-2015)
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

"""
Interface of underlying Task's Engine.

An Engine implements a loop your thread enters and uses to call event handlers
in response to incoming events (from workers, timers, etc.).
"""

import errno
import heapq
import logging
import sys
import time
import traceback

# Engine client fd I/O event interest bits
E_READ = 0x1
E_WRITE = 0x2

# Define epsilon value for time float arithmetic operations
EPSILON = 1.0e-3

class EngineException(Exception):
    """
    Base engine exception.
    """

class EngineAbortException(EngineException):
    """
    Raised on user abort.
    """
    def __init__(self, kill):
        EngineException.__init__(self)
        self.kill = kill

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

class EngineNotSupportedError(EngineException):
    """
    Error raised when the engine mechanism is not supported.
    """
    def __init__(self, engineid):
        EngineException.__init__(self)
        self.engineid = engineid


class EngineBaseTimer:
    """
    Abstract class for ClusterShell's engine timer. Such a timer
    requires a relative fire time (delay) in seconds (as float), and
    supports an optional repeating interval in seconds (as float too).

    See EngineTimer for more information about ClusterShell timers.
    """

    def __init__(self, fire_delay, interval=-1.0, autoclose=False):
        """
        Create a base timer.
        """
        self.fire_delay = fire_delay
        self.interval = interval
        self.autoclose = autoclose
        self._engine = None
        self._timercase = None

    def _set_engine(self, engine):
        """
        Bind to engine, called by Engine.
        """
        if self._engine:
            # A timer can be registered to only one engine at a time.
            raise EngineIllegalOperationError("Already bound to engine.")

        self._engine = engine

    def invalidate(self):
        """
        Invalidates a timer object, stopping it from ever firing again.
        """
        if self._engine:
            self._engine.timerq.invalidate(self)
            self._engine = None

    def is_valid(self):
        """
        Returns a boolean value that indicates whether an EngineTimer
        object is valid and able to fire.
        """
        return self._engine is not None

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
        if not self.is_valid():
            raise EngineIllegalOperationError("Operation on invalid timer.")

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

    def __init__(self, fire_delay, interval, autoclose, handler):
        EngineBaseTimer.__init__(self, fire_delay, interval, autoclose)
        self.eh = handler
        assert self.eh is not None, "An event handler is needed for timer."

    def _fire(self):
        self.eh.ev_timer(self)

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
            assert self.client.fire_delay > -EPSILON
            self.fire_date = self.client.fire_delay + time.time()

        def __cmp__(self, other):
            return cmp(self.fire_date, other.fire_date)

        def arm(self, client):
            assert client is not None
            self.client = client
            self.client._timercase = self
            # setup next firing date
            time_current = time.time()
            if self.client.fire_delay > -EPSILON:
                self.fire_date = self.client.fire_delay + time_current
            else:
                interval = float(self.client.interval)
                assert interval > 0
                # Keep it simple: increase fire_date by interval even if
                # fire_date stays in the past, as in that case it's going to
                # fire again at next runloop anyway.
                self.fire_date += interval
                # Just print a debug message that could help detect issues
                # coming from a long-running timer handler.
                if self.fire_date < time_current:
                    logging.getLogger(__name__).debug(
                        "Warning: passed interval time for %r (long running "
                        "event handler?)", self.client)

        def disarm(self):
            client = self.client
            client._timercase = None
            self.client = None
            return client

        def armed(self):
            return self.client is not None


    def __init__(self, engine):
        """
        Initializer.
        """
        self._engine = engine
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
        if client.fire_delay > -EPSILON:
            heapq.heappush(self.timers, _EngineTimerQ._EngineTimerCase(client))
            self.armed_count += 1
            if not client.autoclose:
                self._engine.evlooprefcnt += 1

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
            # if timer is being fire, invalidate its values
            client.fire_delay = -1.0
            client.interval = -1.0
            return

        if self.armed_count <= 0:
            raise ValueError, "Engine client timer not found in timer queue"

        client._timercase.disarm()
        self.armed_count -= 1
        if not client.autoclose:
            self._engine.evlooprefcnt -= 1

    def _dequeue_disarmed(self):
        """
        Dequeue disarmed timers (sort of garbage collection).
        """
        while len(self.timers) > 0 and not self.timers[0].armed():
            heapq.heappop(self.timers)

    def fire_expired(self):
        """
        Remove expired timers from the queue and fire associated clients.
        """
        self._dequeue_disarmed()

        # Build a queue of expired timercases. Any expired (and still armed)
        # timer is fired, but only once per call.
        expired_timercases = []
        now = time.time()
        while self.timers and (self.timers[0].fire_date - now) <= EPSILON:
            expired_timercases.append(heapq.heappop(self.timers))
            self._dequeue_disarmed()

        for timercase in expired_timercases:
            # Be careful to recheck and skip any disarmed timers (eg. timer
            # could be invalidated from another timer's event handler)
            if not timercase.armed():
                continue

            # Disarm timer
            client = timercase.disarm()

            # Fire timer
            client.fire_delay = -1.0
            client._fire()

            # Rearm it if needed - Note: fire=0 is valid, interval=0 is not
            if client.fire_delay >= -EPSILON or client.interval > EPSILON:
                timercase.arm(client)
                heapq.heappush(self.timers, timercase)
            else:
                self.armed_count -= 1
                if not client.autoclose:
                    self._engine.evlooprefcnt -= 1

    def nextfire_delay(self):
        """
        Return next timer fire delay (relative time).
        """
        self._dequeue_disarmed()
        if len(self.timers) > 0:
            return max(0., self.timers[0].fire_date - time.time())

        return -1

    def clear(self):
        """
        Stop and clear all timers.
        """
        for timer in self.timers:
            if timer.armed():
                timer.client.invalidate()

        self.timers = []
        self.armed_count = 0


class Engine:
    """
    Base class for ClusterShell Engines.

    Subclasses have to implement a runloop listening for client events.
    Subclasses that override other than "pure virtual methods" should call
    corresponding base class methods.
    """

    identifier = "(none)"

    def __init__(self, info):
        """Initialize base class."""
        # take a reference on info dict
        self.info = info

        # and update engine id
        self.info['engine'] = self.identifier

        # keep track of all clients
        self._clients = set()
        self._ports = set()

        # keep track of the number of registered clients (delayable only)
        self.reg_clients = 0

        # keep track of registered file descriptors in a dict where keys
        # are fileno and values are (EngineClient, EngineClientStream) tuples
        self.reg_clifds = {}

        # Current loop iteration counter. It is the number of performed engine
        # loops in order to keep track of client registration epoch, so we can
        # safely process FDs by chunk and re-use FDs (see Engine._fd2client).
        self._current_loopcnt = 0

        # Current stream being processed
        self._current_stream = None

        # timer queue to handle both timers and clients timeout
        self.timerq = _EngineTimerQ(self)

        # reference count to the event loop (must include registered
        # clients and timers configured WITHOUT autoclose)
        self.evlooprefcnt = 0

        # running state
        self.running = False
        # runloop-has-exited flag
        self._exited = False

    def release(self):
        """Release engine-specific resources."""
        pass

    def clients(self):
        """Get a copy of clients set."""
        return self._clients.copy()

    def ports(self):
        """
        Get a copy of ports set.
        """
        return self._ports.copy()

    def _fd2client(self, fd):
        client, stream = self.reg_clifds.get(fd, (None, None))
        if client:
            if client._reg_epoch < self._current_loopcnt:
                return client, stream
            else:
                self._debug("ENGINE _fd2client: ignoring just re-used FD %d" \
                            % stream.fd)
        return (None, None)

    def add(self, client):
        """Add a client to engine."""
        # bind to engine
        client._set_engine(self)

        if client.delayable:
            # add to regular client set
            self._clients.add(client)
        else:
            # add to port set (non-delayable)
            self._ports.add(client)

        if self.running:
            # in-fly add if running
            if not client.delayable:
                self.register(client)
            elif self.info["fanout"] > self.reg_clients:
                self.register(client._start())

    def _remove(self, client, abort, did_timeout=False):
        """Remove a client from engine (subroutine)."""
        # be careful to also remove ports when engine has not started yet
        if client.registered or not client.delayable:
            if client.registered:
                self.unregister(client)
            # care should be taken to ensure correct closing flags
            client._close(abort=abort, timeout=did_timeout)

    def remove(self, client, abort=False, did_timeout=False):
        """
        Remove a client from engine. Does NOT aim to flush individual stream
        read buffers.
        """
        self._debug("REMOVE %s" % client)
        if client.delayable:
            self._clients.remove(client)
        else:
            self._ports.remove(client)
        self._remove(client, abort, did_timeout)
        self.start_all()

    def remove_stream(self, client, stream):
        """
        Regular way to remove a client stream from engine, performing
        needed read flush as needed. If no more retainable stream
        remains for this client, this method automatically removes the
        entire client from engine.
        """
        self.unregister_stream(client, stream)
        # _close_stream() will flush pending read buffers so may generate events
        client._close_stream(stream.name)
        # client may have been removed by previous events, if not check whether
        # some retained streams still remain
        if client in self._clients and not client.streams.retained():
            self.remove(client)

    def clear(self, did_timeout=False, clear_ports=False):
        """
        Remove all clients. Does not flush read buffers.
        Subclasses that override this method should call base class method.
        """
        all_clients = [self._clients]
        if clear_ports:
            all_clients.append(self._ports)

        for clients in all_clients:
            while len(clients) > 0:
                client = clients.pop()
                self._remove(client, True, did_timeout)

    def register(self, client):
        """
        Register an engine client. Subclasses that override this method
        should call base class method.
        """
        assert client in self._clients or client in self._ports
        assert not client.registered

        self._debug("REG %s (%s)(autoclose=%s)" % \
                (client.__class__.__name__, client.streams,
                 client.autoclose))

        client.registered = True
        client._reg_epoch = self._current_loopcnt

        if client.delayable:
            self.reg_clients += 1

        # set interest event bits...
        for streams, ievent in ((client.streams.active_readers, E_READ),
                                (client.streams.active_writers, E_WRITE)):
            for stream in streams():
                self.reg_clifds[stream.fd] = client, stream
                stream.events |= ievent
                if not client.autoclose:
                    self.evlooprefcnt += 1
                self._register_specific(stream.fd, ievent)

        # start timeout timer
        self.timerq.schedule(client)

    def unregister_stream(self, client, stream):
        """Unregister a stream from a client."""
        self._debug("UNREG_STREAM stream=%s" % stream)
        assert stream is not None and stream.fd is not None
        assert stream.fd in self.reg_clifds, \
            "stream fd %d not registered" % stream.fd
        assert client.registered
        self._unregister_specific(stream.fd, stream.events & stream.evmask)
        self._debug("UNREG_STREAM unregistering stream fd %d (%d)" % \
                    (stream.fd, len(client.streams)))
        stream.events &= ~stream.evmask
        del self.reg_clifds[stream.fd]
        if not client.autoclose:
            self.evlooprefcnt -= 1

    def unregister(self, client):
        """Unregister a client"""
        # sanity check
        assert client.registered
        self._debug("UNREG %s (%s)" % (client.__class__.__name__, \
                client.streams))

        # remove timeout timer
        self.timerq.invalidate(client)

        # clear interest events...
        for streams, ievent in ((client.streams.active_readers, E_READ),
                                (client.streams.active_writers, E_WRITE)):
            for stream in streams():
                if stream.fd in self.reg_clifds:
                    self._unregister_specific(stream.fd, stream.events & ievent)
                    stream.events &= ~ievent
                    del self.reg_clifds[stream.fd]
                    if not client.autoclose:
                        self.evlooprefcnt -= 1

        client.registered = False
        if client.delayable:
            self.reg_clients -= 1

    def modify(self, client, sname, setmask, clearmask):
        """Modify the next loop interest events bitset for a client stream."""
        self._debug("MODEV set:0x%x clear:0x%x %s (%s)" % (setmask, clearmask,
                                                           client, sname))
        stream = client.streams[sname]
        stream.new_events &= ~clearmask
        stream.new_events |= setmask

        if self._current_stream is not stream:
            # modifying a non processing stream, apply new_events now
            self.set_events(client, stream)

    def _register_specific(self, fd, event):
        """Engine-specific register fd for event method."""
        raise NotImplementedError("Derived classes must implement.")

    def _unregister_specific(self, fd, ev_is_set):
        """Engine-specific unregister fd method."""
        raise NotImplementedError("Derived classes must implement.")

    def _modify_specific(self, fd, event, setvalue):
        """Engine-specific modify fd for event method."""
        raise NotImplementedError("Derived classes must implement.")

    def set_events(self, client, stream):
        """Set the active interest events bitset for a client stream."""
        self._debug("SETEV new_events:0x%x events:0x%x for %s[%s]" % \
            (stream.new_events, stream.events, client, stream.name))

        if not client.registered:
            logging.getLogger(__name__).debug( \
                "set_events: client %s not registered" % self)
            return

        chgbits = stream.new_events ^ stream.events
        if chgbits == 0:
            return

        # configure interest events as appropriate
        for interest in (E_READ, E_WRITE):
            if chgbits & interest:
                assert stream.evmask & interest
                status = stream.new_events & interest
                self._modify_specific(stream.fd, interest, status)
                if status:
                    stream.events |= interest
                else:
                    stream.events &= ~interest

        stream.new_events = stream.events

    def set_reading(self, client, sname):
        """Set client reading state."""
        # listen for readable events
        self.modify(client, sname, E_READ, 0)

    def set_writing(self, client, sname):
        """Set client writing state."""
        # listen for writable events
        self.modify(client, sname, E_WRITE, 0)

    def add_timer(self, timer):
        """Add a timer instance to engine."""
        timer._set_engine(self)
        self.timerq.schedule(timer)

    def remove_timer(self, timer):
        """Remove engine timer from engine."""
        self.timerq.invalidate(timer)

    def fire_timers(self):
        """Fire expired timers for processing."""
        # Only fire timers if runloop is still retained
        if self.evlooprefcnt > 0:
            # Fire once any expired timers
            self.timerq.fire_expired()

    def start_ports(self):
        """Start and register all port clients."""
        # Ports are special, non-delayable engine clients
        for port in self._ports:
            if not port.registered:
                self._debug("START PORT %s" % port)
                self.register(port)

    def start_all(self):
        """
        Start and register all other possible clients, in respect of task
        fanout.
        """
        # Get current fanout value
        fanout = self.info["fanout"]
        assert fanout > 0
        if fanout <= self.reg_clients:
            return

        # Register regular engine clients within the fanout limit
        for client in self._clients:
            if not client.registered:
                self._debug("START CLIENT %s" % client.__class__.__name__)
                self.register(client._start())
                if fanout <= self.reg_clients:
                    break

    def run(self, timeout):
        """Run engine in calling thread."""
        # change to running state
        if self.running:
            raise EngineAlreadyRunningError()

        # note: try-except-finally not supported before python 2.5
        try:
            self.running = True
            try:
                # start port clients
                self.start_ports()
                # peek in ports for early pending messages
                self.snoop_ports()
                # start all other clients
                self.start_all()
                # run loop until all clients and timers are removed
                self.runloop(timeout)
            except EngineTimeoutException:
                self.clear(did_timeout=True)
                raise
            except: # MUST use BaseException as soon as possible (py2.5+)
                # The game is over.
                exc_t, exc_val, exc_tb = sys.exc_info()
                try:
                    # Close Engine clients
                    self.clear()
                except:
                    # self.clear() may still generate termination events that
                    # may raises exceptions, overriding the other one above.
                    # In the future, we should block new user events to avoid
                    # that. Also, such cases could be better handled with
                    # BaseException. For now, print a backtrace in debug to
                    # help detect the problem.
                    tbexc = traceback.format_exception(exc_t, exc_val, exc_tb)
                    logging.getLogger(__name__).debug(''.join(tbexc))
                    raise
                raise
        finally:
            # cleanup
            self.timerq.clear()
            self.running = False

    def snoop_ports(self):
        """
        Peek in ports for possible early pending messages.
        This method simply tries to read port pipes in non-blocking mode.
        """
        # make a copy so that early messages on installed ports may
        # lead to new ports
        ports = self._ports.copy()
        for port in ports:
            try:
                port._handle_read('in')
            except (IOError, OSError), ex:
                if ex.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                    # no pending message
                    return
                # raise any other error
                raise

    def runloop(self, timeout):
        """Engine specific run loop. Derived classes must implement."""
        raise NotImplementedError("Derived classes must implement.")

    def abort(self, kill):
        """Abort runloop."""
        if self.running:
            raise EngineAbortException(kill)

        self.clear(clear_ports=kill)

    def exited(self):
        """Returns True if the engine has exited the runloop once."""
        return not self.running and self._exited

    def _debug(self, s):
        """library engine debugging hook"""
        #logging.getLogger(__name__).debug(s)
        pass
