#
# Copyright CEA/DAM/DIF (2009)
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
#
# $Id$

"""
A ClusterShell Engine using epoll, an I/O event notification facility.

The epoll event distribution interface is available on Linux 2.6, and
has been included in Python 2.6.
"""

from Engine import *

from ClusterShell.Worker.EngineClient import EngineClientEOF

import errno
import os
import select
import signal
import sys
import time
import thread


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
            print >> sys.stderr, "Error: select.epoll() not supported"
            raise

        # runloop-has-exited flag
        self.exited = False

    def _register_specific(self, fd, event):
        """
        Engine-specific fd registering. Called by Engine register.
        """
        if event == Engine.E_READABLE:
            eventmask = select.EPOLLIN
        elif event == Engine.E_WRITABLE:
            eventmask = select.EPOLLOUT

        self.epolling.register(fd, eventmask)

    def _unregister_specific(self, fd, ev_is_set):
        """
        Engine-specific fd unregistering. Called by Engine unregister.
        """
        self.epolling.unregister(fd)

    def _modify_specific(self, fd, event, setvalue):
        """
        Engine-specific modifications after a interesting event change for
        a file descriptor. Called automatically by Engine set_events().
        For the epoll engine, it modifies the event mask associated to a file
        descriptor.
        """
        self._debug("MODSPEC fd=%d event=%x setvalue=%d" % (fd, event, setvalue))

        eventmask = 0
        if setvalue:
            if event == Engine.E_READABLE:
                eventmask = select.EPOLLIN
            elif event == Engine.E_WRITABLE:
                eventmask = select.EPOLLOUT

        self.epolling.modify(fd, eventmask)

    def set_reading(self, client):
        """
        Set client reading state.
        """
        # listen for readable events
        self.modify(client, Engine.E_READABLE, 0)

    def set_writing(self, client):
        """
        Set client writing state.
        """
        # listen for writable events
        self.modify(client, Engine.E_WRITABLE, 0)

    def runloop(self, timeout):
        """
        Run epoll main loop.
        """
        if timeout == 0:
            timeout = -1

        start_time = time.time()

        # run main event loop...
        while self.evlooprefcnt > 0:
            self._debug("LOOP evlooprefcnt=%d (reg_clients=%s) (timers=%d)" % \
                    (self.evlooprefcnt, self.reg_clients.keys(), len(self.timerq)))
            try:
                timeo = self.timerq.nextfire_delay()
                if timeout > 0 and timeo >= timeout:
                    # task timeout may invalidate clients timeout
                    self.timerq.clear()
                    timeo = timeout
                elif timeo == -1:
                    timeo = timeout

                self.reg_clients_changed = False
                evlist = self.epolling.poll(timeo + 0.001)

            except select.error, (ex_errno, ex_strerror):
                # might get interrupted by a signal
                if ex_errno == errno.EINTR:
                    continue
                elif ex_errno == errno.EINVAL:
                    print >>sys.stderr, \
                            "EngineEPoll: please increase RLIMIT_NOFILE"
                raise

            for fd, event in evlist:

                if self.reg_clients_changed:
                    self._debug("REG CLIENTS CHANGED - Aborting current evlist")
                    # Oops, reconsider evlist by calling poll() again.
                    break

                # get client instance
                if not self.reg_clients.has_key(fd):
                    continue

                client = self.reg_clients[fd]

                # process this client
                client._processing = True

                # check for poll error condition of some sort
                if event & select.EPOLLERR:
                    self._debug("EPOLLERR %s" % client)
                    self.unregister_writer(client)
                    client.file_writer.close()
                    client.file_writer = None
                    continue

                # check for data to read
                if event & select.EPOLLIN:
                    assert client._events & Engine.E_READABLE
                    self.modify(client, 0, Engine.E_READABLE)
                    try:
                        client._handle_read()
                    except EngineClientEOF, e:
                        self._debug("EngineClientEOF %s" % client)
                        self.remove(client)
                        continue

                # or check for end of stream (do not handle both at the same time
                # because handle_read() may perform a partial read)
                elif event & select.EPOLLHUP:
                    self._debug("EPOLLHUP fd=%d %s (r%s,w%s)" % (fd, client.__class__.__name__,
                        client.reader_fileno(), client.writer_fileno()))
                    self.remove(client)

                # check for writing
                if event & select.EPOLLOUT:
                    self._debug("EPOLLOUT fd=%d %s (r%s,w%s)" % (fd, client.__class__.__name__,
                        client.reader_fileno(), client.writer_fileno()))
                    assert client._events & Engine.E_WRITABLE
                    self.modify(client, 0, Engine.E_WRITABLE)
                    client._handle_write()

                # post processing
                client._processing = False

                # apply any changes occured during processing
                if client.registered:
                    self.set_events(client, client._new_events)

            # check for task runloop timeout
            if timeout > 0 and time.time() >= start_time + timeout:
                raise EngineTimeoutException()

            # process clients timeout
            self.fire_timers()

        self._debug("LOOP EXIT evlooprefcnt=%d (reg_clients=%s) (timers=%d)" % \
                (self.evlooprefcnt, self.reg_clients, len(self.timerq)))

    def exited(self):
        """
        Returns True if the engine has exited the runloop once.
        """
        return not self.running and self.exited

    def join(self):
        """
        Block calling thread until runloop has finished.
        """
        self.start_lock.acquire()
        self.start_lock.release()
        self.run_lock.acquire()
        self.run_lock.release()

