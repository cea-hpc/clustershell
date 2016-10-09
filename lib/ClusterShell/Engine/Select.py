#
# Copyright (C) 2009-2016 CEA/DAM
# Copyright (C) 2009-2012 Henri Doreau <henri.doreau@cea.fr>
# Copyright (C) 2009-2012 Aurelien Degremont <aurelien.degremont@cea.fr>
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
A select() based ClusterShell Engine.

The select() system call is available on almost every UNIX-like systems.
"""

import errno
import select
import sys
import time

from ClusterShell.Engine.Engine import Engine, E_READ, E_WRITE
from ClusterShell.Engine.Engine import EngineTimeoutException
from ClusterShell.Worker.EngineClient import EngineClientEOF


class EngineSelect(Engine):
    """
    Select Engine

    ClusterShell engine using the select.select mechanism
    """

    identifier = "select"

    def __init__(self, info):
        """
        Initialize Engine.
        """
        Engine.__init__(self, info)
        self._fds_r = []
        self._fds_w = []

    def _register_specific(self, fd, event):
        """
        Engine-specific fd registering. Called by Engine register.
        """
        if event & E_READ:
            self._fds_r.append(fd)
        else:
            assert event & E_WRITE
            self._fds_w.append(fd)

    def _unregister_specific(self, fd, ev_is_set):
        """
        Engine-specific fd unregistering. Called by Engine unregister.
        """
        if ev_is_set or True:
            if fd in self._fds_r:
                self._fds_r.remove(fd)
            if fd in self._fds_w:
                self._fds_w.remove(fd)

    def _modify_specific(self, fd, event, setvalue):
        """
        Engine-specific modifications after a interesting event change
        for a file descriptor. Called automatically by Engine
        register/unregister and set_events(). For the select() engine,
        it appends/remove the fd to/from the concerned fd_sets.
        """
        self._debug("MODSPEC fd=%d event=%x setvalue=%d" % (fd, event,
                                                            setvalue))
        if setvalue:
            self._register_specific(fd, event)
        else:
            self._unregister_specific(fd, True)

    def runloop(self, timeout):
        """
        Select engine run(): start clients and properly get replies
        """
        if not timeout:
            timeout = -1

        start_time = time.time()

        # run main event loop...
        while self.evlooprefcnt > 0:
            self._debug("LOOP evlooprefcnt=%d (reg_clifds=%s) (timers=%d)" % 
                (self.evlooprefcnt, self.reg_clifds.keys(), len(self.timerq)))
            try:
                timeo = self.timerq.nextfire_delay()
                if timeout > 0 and timeo >= timeout:
                    # task timeout may invalidate clients timeout
                    self.timerq.clear()
                    timeo = timeout
                elif timeo == -1:
                    timeo = timeout

                self._current_loopcnt += 1
                if timeo >= 0:
                    r_ready, w_ready, x_ready = \
                        select.select(self._fds_r, self._fds_w, [], timeo)
                else:
                    # no timeout specified, do not supply the timeout argument
                    r_ready, w_ready, x_ready = \
                        select.select(self._fds_r, self._fds_w, [])
            except select.error, (ex_errno, ex_strerror):
                # might get interrupted by a signal
                if ex_errno == errno.EINTR:
                    continue
                elif ex_errno in [errno.EINVAL, errno.EBADF, errno.ENOMEM]:
                    msg = "Increase RLIMIT_NOFILE?"
                    logging.getLogger(__name__).error(msg)
                raise

            # iterate over fd on which events occured
            for fd in set(r_ready) | set(w_ready):

                # get client instance
                client, stream = self._fd2client(fd)
                if client is None:
                    continue

                fdev = stream.evmask
                sname = stream.name

                # process this stream
                self._current_stream = stream

                # check for possible unblocking read on this fd
                if fd in r_ready:
                    self._debug("R_READY fd=%d %s (%s)" % (fd,
                        client.__class__.__name__, client.streams))
                    assert fdev & E_READ
                    assert stream.events & fdev
                    self.modify(client, sname, 0, fdev)
                    try:
                        client._handle_read(sname)
                    except EngineClientEOF:
                        self._debug("EngineClientEOF %s" % client)
                        self.remove_stream(client, stream)

                # check for writing
                if fd in w_ready:
                    self._debug("W_READY fd=%d %s (%s)" % (fd,
                        client.__class__.__name__, client.streams))
                    assert fdev == E_WRITE
                    assert stream.events & fdev
                    self.modify(client, sname, 0, fdev)
                    client._handle_write(sname)

                # post processing
                self._current_stream = None

                # apply any changes occured during processing
                if client.registered:
                    self.set_events(client, stream)

            # check for task runloop timeout
            if timeout > 0 and time.time() >= start_time + timeout:
                raise EngineTimeoutException()

            # process clients timeout
            self.fire_timers()

        self._debug("LOOP EXIT evlooprefcnt=%d (reg_clifds=%s) (timers=%d)" %
                    (self.evlooprefcnt, self.reg_clifds, len(self.timerq)))
