#
# Copyright (C) 2009-2015 CEA/DAM
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
A ClusterShell Engine using epoll, an I/O event notification facility.

The epoll event distribution interface is available on Linux 2.6, and
has been included in Python 2.6.
"""

import errno
import select
import time

from ClusterShell.Engine.Engine import Engine, E_READ, E_WRITE
from ClusterShell.Engine.Engine import EngineNotSupportedError
from ClusterShell.Engine.Engine import EngineTimeoutException
from ClusterShell.Worker.EngineClient import EngineClientEOF


class EngineEPoll(Engine):
    """
    EPoll Engine

    ClusterShell Engine class using the select.epoll mechanism.
    """

    identifier = "epoll"

    def __init__(self, info):
        """
        Initialize Engine.
        """
        Engine.__init__(self, info)
        try:
            # get an epoll object
            self.epolling = select.epoll()
        except AttributeError:
            raise EngineNotSupportedError(EngineEPoll.identifier)

    def release(self):
        """Release engine-specific resources."""
        self.epolling.close()

    def _register_specific(self, fd, event):
        """Engine-specific fd registering. Called by Engine register."""
        if event & E_READ:
            eventmask = select.EPOLLIN
        else:
            assert event & E_WRITE
            eventmask = select.EPOLLOUT

        self.epolling.register(fd, eventmask)

    def _unregister_specific(self, fd, ev_is_set):
        """
        Engine-specific fd unregistering. Called by Engine unregister.
        """
        self._debug("UNREGSPEC fd=%d ev_is_set=%x"% (fd, ev_is_set))
        if ev_is_set:
            self.epolling.unregister(fd)

    def _modify_specific(self, fd, event, setvalue):
        """
        Engine-specific modifications after a interesting event change for
        a file descriptor. Called automatically by Engine set_events().
        For the epoll engine, it modifies the event mask associated to a file
        descriptor.
        """
        self._debug("MODSPEC fd=%d event=%x setvalue=%d" % (fd, event,
                                                            setvalue))
        if setvalue:
            self._register_specific(fd, event)
        else:
            self.epolling.unregister(fd)

    def runloop(self, timeout):
        """
        Run epoll main loop.
        """
        if not timeout:
            timeout = -1

        start_time = time.time()

        # run main event loop...
        while self.evlooprefcnt > 0:
            self._debug("LOOP evlooprefcnt=%d (reg_clifds=%s) (timers=%d)" % \
                    (self.evlooprefcnt, self.reg_clifds.keys(),
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

                if timeo < 0:
                    poll_timeo = -1
                else:
                    poll_timeo = timeo
                evlist = self.epolling.poll(poll_timeo)

            except IOError as ex:
                # might get interrupted by a signal
                if ex.errno == errno.EINTR:
                    continue

            for fd, event in evlist:

                # get client instance
                client, stream = self._fd2client(fd)
                if client is None:
                    continue

                fdev = stream.evmask
                sname = stream.name

                # set as current processed stream
                self._current_stream = stream

                # check for poll error condition of some sort
                if event & select.EPOLLERR:
                    self._debug("EPOLLERR fd=%d sname=%s fdev=0x%x (%s)" % \
                                (fd, sname, fdev, client))
                    assert fdev & E_WRITE
                    self.remove_stream(client, stream)
                    self._current_stream = None
                    continue

                # check for data to read
                if event & select.EPOLLIN:
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
                elif event & select.EPOLLHUP:
                    assert fdev & E_READ, "fdev 0x%x & E_READ" % fdev
                    self._debug("EPOLLHUP fd=%d sname=%s %s (%s)" % \
                                (fd, sname, client, client.streams))
                    self.remove_stream(client, stream)
                    self._current_stream = None
                    continue

                # check for writing
                if event & select.EPOLLOUT:
                    self._debug("EPOLLOUT fd=%d sname=%s %s (%s)" % \
                                (fd, sname, client, client.streams))
                    assert fdev & E_WRITE
                    assert stream.events & fdev, (stream.events, fdev)
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

