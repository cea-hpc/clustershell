#
# Copyright CEA/DAM/DIF (2007, 2008, 2009, 2010, 2011)
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
A poll() based ClusterShell Engine.

The poll() system call is available on Linux and BSD.
"""

import errno
import os
import select
import sys
import time

from ClusterShell.Engine.Engine import Engine
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
        if event & (Engine.E_READ | Engine.E_ERROR):
            eventmask = select.POLLIN
        elif event == Engine.E_WRITE:
            eventmask = select.POLLOUT

        self.polling.register(fd, eventmask)

    def _unregister_specific(self, fd, ev_is_set):
        if ev_is_set:
            self.polling.unregister(fd)

    def _modify_specific(self, fd, event, setvalue):
        """
        Engine-specific modifications after a interesting event change for
        a file descriptor. Called automatically by Engine register/unregister and
        set_events().  For the poll() engine, it reg/unreg or modifies the event mask
        associated to a file descriptor.
        """
        self._debug("MODSPEC fd=%d event=%x setvalue=%d" % (fd, event,
                                                            setvalue))
        if setvalue:
            eventmask = 0
            if event & (Engine.E_READ | Engine.E_ERROR):
                eventmask = select.POLLIN
            elif event == Engine.E_WRITE:
                eventmask = select.POLLOUT
            self.polling.register(fd, eventmask)
        else:
            self.polling.unregister(fd)

    def runloop(self, timeout):
        """
        Poll engine run(): start clients and properly get replies
        """
        if timeout == 0:
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
                    print >> sys.stderr, \
                            "EnginePoll: please increase RLIMIT_NOFILE"
                raise

            for fd, event in evlist:

                if event & select.POLLNVAL:
                    raise EngineException("Caught POLLNVAL on fd %d" % fd)

                # get client instance
                client, fdev = self._fd2client(fd)
                if client is None:
                    continue

                # process this client
                client._current_client = client

                # check for poll error condition of some sort
                if event & select.POLLERR:
                    self._debug("POLLERR %s" % client)
                    self.unregister_writer(client)
                    os.close(client.fd_writer)
                    client.fd_writer = None
                    client._current_client = None
                    continue

                # check for data to read
                if event & select.POLLIN:
                    assert fdev & (Engine.E_READ | Engine.E_ERROR)
                    assert client._events & fdev
                    self.modify(client, 0, fdev)
                    try:
                        if fdev & Engine.E_READ:
                            client._handle_read()
                        else:
                            client._handle_error()
                    except EngineClientEOF:
                        self._debug("EngineClientEOF %s" % client)
                        if fdev & Engine.E_READ:
                            self.remove(client)
                        client._current_client = None
                        continue

                # or check for end of stream (do not handle both at the same
                # time because handle_read() may perform a partial read)
                elif event & select.POLLHUP:
                    self._debug("POLLHUP fd=%d %s (r%s,e%s,w%s)" % (fd,
                        client.__class__.__name__, client.fd_reader,
                        client.fd_error, client.fd_writer))		
                    if fdev & Engine.E_READ:
                        if client._events & Engine.E_ERROR:
                            self.modify(client, 0, fdev)
                        else:
                            self.remove(client)
                    else:
                        if client._events & Engine.E_READ:
                            self.modify(client, 0, fdev)
                        else:
                            self.remove(client)

                # check for writing
                if event & select.POLLOUT:
                    self._debug("POLLOUT fd=%d %s (r%s,e%s,w%s)" % (fd,
                        client.__class__.__name__, client.fd_reader,
                        client.fd_error, client.fd_writer))
                    assert fdev == Engine.E_WRITE
                    assert client._events & fdev
                    self.modify(client, 0, fdev)
                    client._handle_write()

                client._current_client = None

                # apply any changes occured during processing
                if client.registered:
                    self.set_events(client, client._new_events)

            # check for task runloop timeout
            if timeout > 0 and time.time() >= start_time + timeout:
                raise EngineTimeoutException()

            # process clients timeout
            self.fire_timers()

        self._debug("LOOP EXIT evlooprefcnt=%d (reg_clifds=%s) (timers=%d)" % \
                (self.evlooprefcnt, self.reg_clifds, len(self.timerq)))

