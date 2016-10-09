#
# Copyright (C) 2007-2016 CEA/DAM
# Copyright (C) 2016 Stephane Thiell <sthiell@stanford.edu>
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
A poll() based ClusterShell Engine.

The poll() system call is available on Linux and BSD.
"""

import errno
import logging
import select
import time

from ClusterShell.Engine.Engine import Engine, E_READ, E_WRITE
from ClusterShell.Engine.Engine import EngineException
from ClusterShell.Engine.Engine import EngineNotSupportedError
from ClusterShell.Engine.Engine import EngineTimeoutException
from ClusterShell.Worker.EngineClient import EngineClientEOF


class EnginePoll(Engine):
    """
    Poll Engine

    ClusterShell engine using the select.poll mechanism (Linux poll()
    syscall).
    """

    identifier = "poll"

    def __init__(self, info):
        """
        Initialize Engine.
        """
        Engine.__init__(self, info)
        try:
            # get a polling object
            self.polling = select.poll()
        except AttributeError:
            raise EngineNotSupportedError(EnginePoll.identifier)

    def _register_specific(self, fd, event):
        """Engine-specific fd registering. Called by Engine register."""
        if event & E_READ:
            eventmask = select.POLLIN
        else:
            assert event & E_WRITE
            eventmask = select.POLLOUT

        self.polling.register(fd, eventmask)

    def _unregister_specific(self, fd, ev_is_set):
        if ev_is_set:
            self.polling.unregister(fd)

    def _modify_specific(self, fd, event, setvalue):
        """
        Engine-specific modifications after a interesting event change for
        a file descriptor. Called automatically by Engine register/unregister
        and set_events().  For the poll() engine, it reg/unreg or modifies the
        event mask associated to a file descriptor.
        """
        self._debug("MODSPEC fd=%d event=%x setvalue=%d" % (fd, event,
                                                            setvalue))
        if setvalue:
            self._register_specific(fd, event)
        else:
            self.polling.unregister(fd)

    def runloop(self, timeout):
        """
        Poll engine run(): start clients and properly get replies
        """
        if not timeout:
            timeout = -1

        start_time = time.time()

        # run main event loop...
        while self.evlooprefcnt > 0:
            self._debug("LOOP evlooprefcnt=%d (reg_clifds=%s) (timers=%d)" \
                % (self.evlooprefcnt, self.reg_clifds.keys(), \
                   len(self.timerq)))
            try:
                timeo = self.timerq.nextfire_delay()
                if timeout > 0 and timeo >= timeout:
                    # task timeout may invalidate clients timeout
                    self.timerq.clear()
                    timeo = timeout
                elif timeo == -1:
                    timeo = timeout

                self._current_loopcnt += 1
                evlist = self.polling.poll(timeo * 1000.0 + 1.0)

            except select.error, (ex_errno, ex_strerror):
                # might get interrupted by a signal
                if ex_errno == errno.EINTR:
                    continue
                elif ex_errno == errno.EINVAL:
                    msg = "Increase RLIMIT_NOFILE?"
                    logging.getLogger(__name__).error(msg)
                raise

            for fd, event in evlist:

                if event & select.POLLNVAL:
                    raise EngineException("Caught POLLNVAL on fd %d" % fd)

                # get client instance
                client, stream = self._fd2client(fd)
                if client is None:
                    continue

                fdev = stream.evmask
                sname = stream.name

                # process this stream
                self._current_stream = stream

                # check for poll error condition of some sort
                if event & select.POLLERR:
                    self._debug("POLLERR %s" % client)
                    assert fdev & E_WRITE
                    self._debug("POLLERR: remove_stream sname %s fdev 0x%x"
                                % (sname, fdev))
                    self.remove_stream(client, stream)
                    self._current_stream = None
                    continue

                # check for data to read
                if event & select.POLLIN:
                    assert fdev & E_READ
                    assert stream.events & fdev, (stream.events, fdev)
                    self.modify(client, sname, 0, fdev)
                    try:
                        client._handle_read(sname)
                    except EngineClientEOF:
                        self._debug("EngineClientEOF %s %s" % (client, sname))
                        self.remove_stream(client, stream)
                        self._current_stream = None
                        continue

                # or check for end of stream (do not handle both at the same
                # time because handle_read() may perform a partial read)
                elif event & select.POLLHUP:
                    self._debug("POLLHUP fd=%d %s (%s)" %
                                (fd, client.__class__.__name__, client.streams))
                    self.remove_stream(client, stream)
                    self._current_stream = None
                    continue

                # check for writing
                if event & select.POLLOUT:
                    self._debug("POLLOUT fd=%d %s (%s)" %
                                (fd, client.__class__.__name__, client.streams))
                    assert fdev == E_WRITE
                    assert stream.events & fdev
                    self.modify(client, sname, 0, fdev)
                    client._handle_write(sname)

                self._current_stream = None

                # apply any changes occured during processing
                if client.registered:
                    self.set_events(client, stream)

            # check for task runloop timeout
            if timeout > 0 and time.time() >= start_time + timeout:
                raise EngineTimeoutException()

            # process clients timeout
            self.fire_timers()

        self._debug("LOOP EXIT evlooprefcnt=%d (reg_clifds=%s) (timers=%d)" % \
                (self.evlooprefcnt, self.reg_clifds, len(self.timerq)))

