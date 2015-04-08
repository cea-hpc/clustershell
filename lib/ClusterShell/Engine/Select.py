#
# Copyright CEA/DAM/DIF (2009-2015)
#  Contributors:
#   Henri DOREAU <henri.doreau@cea.fr>
#   Aurelien DEGREMONT <aurelien.degremont@cea.fr>
#   Stephane THIELL <stephane.thiell@cea.fr>
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
                    print >> sys.stderr, "EngineSelect: %s" % ex_strerror
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

        self._debug("LOOP EXIT evlooprefcnt=%d (reg_clifds=%s) (timers=%d)" % \
                (self.evlooprefcnt, self.reg_clifds, len(self.timerq)))

