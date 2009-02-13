# EnginePdsh.py -- ClusterShell pdsh engine with poll()
# Copyright (C) 2007, 2008, 2009 CEA
# Written by S. Thiell
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
A poll() based ClusterShell engine.
"""

from Engine import *

import errno
import os
import select
import signal
import sys
import time
import thread


class EnginePoll(Engine):
    """
    Poll Engine

    ClusterShell engine using the select.poll mechanism (Linux poll()
    syscall).
    """
    def __init__(self, info):
        """
        Initialize Engine.
        """
        Engine.__init__(self, info)
        try:
            # get a polling object
            self.polling = select.poll()
        except AttributeError:
            print >> sys.stderr, "Error: select.poll() not supported"
            raise

        # runloop-has-exited flag
        self.exited = False

    def register(self, client):
        """
        Register a client.
        """
        # call base class method
        Engine.register(self, client)

        # add file-object client to polling system
        self.polling.register(client.reader_fileno(), select.POLLIN)
        self.polling.register(client.writer_fileno(), select.POLLOUT)

    def unregister(self, client):
        """
        Unregister a client.
        """
        # remove file-object client from polling system
        self.polling.unregister(client.writer_fileno())
        self.polling.unregister(client.reader_fileno())

        # call base class method
        Engine.unregister(self, client)

    def _modify(self, client, set, clear):
        """
        Modify event mask for a client.
        """
        client._iostate &= ~clear
        client._iostate |= set

        if client._processing:
            # don't change poll flags while the client is being processed,
            # but wait for post-process changes.
            return

        if ((set ^ clear) & Engine.IOSTATE_READING): # readable has changed
            eventmask = 0
            if set & Engine.IOSTATE_READING:
                eventmask = select.POLLIN
            self.polling.register(client.reader_fileno(), eventmask)

        if ((set ^ clear) & Engine.IOSTATE_WRITING): # writable has changed
            eventmask = 0
            if set & Engine.IOSTATE_WRITING:
                eventmask = select.POLLOUT
            self.polling.register(client.writer_fileno(), eventmask)

    def set_reading(self, client):
        """
        Set client reading state.
        """
        self._modify(client, Engine.IOSTATE_READING, 0)

    def set_writing(self, client):
        """
        Set client writing state.
        """
        self._modify(client, Engine.IOSTATE_WRITING, 0)

    def runloop(self, timeout):
        """
        Pdsh engine run(): start clients and properly get replies
        """
        if timeout == 0:
            timeout = -1

        start_time = time.time()

        # run main event loop...
        while len(self.reg_clients) > 0:
            try:
                timeo = self.timerq.expire_relative()
                if timeout > 0 and timeo >= timeout:
                    # task timeout may invalidate clients timeout
                    self.timerq.clear()
                    timeo = timeout
                elif timeo == -1:
                    timeo = timeout

                evlist = self.polling.poll(timeo * 1000.0 + 1.0)

            except select.error, (ex_errno, ex_strerror):
                # might get interrupted by a signal
                if ex_errno == errno.EINTR:
                    continue
                elif ex_errno == errno.EINVAL:
                    print >>sys.stderr, \
                            "EnginePoll: please increase RLIMIT_NOFILE"
                raise

            # check for empty evlist which means poll() timed out
            if len(evlist) == 0:

                # task timeout
                if len(self.timerq) == 0:
                    raise EngineTimeoutException()

                # clients timeout
                assert self.timerq.expired()

                while self.timerq.expired():
                    self.remove(self.timerq.pop(), did_timeout=True)

            for fd, event in evlist:

                # get client instance
                if not self.reg_clients.has_key(fd):
                    continue

                client = self.reg_clients[fd]

                # save client's IO state before processing
                iostate_sav = client._iostate
                # process this client
                client._processing = True

                # check for poll error condition of some sort
                if event & select.POLLERR:
                    if client._iostate & Engine.IOSTATE_READING:
                        client._iostate &= ~Engine.IOSTATE_WRITING
                    else:
                        self.remove(client)
                    continue

                # check for data to read
                if event & select.POLLIN:
                    assert client._iostate & Engine.IOSTATE_READING
                    client._iostate &= ~Engine.IOSTATE_READING
                    client._handle_read()

                # check for end of stream
                if event & select.POLLHUP:
                    self.remove(client)
                    #client._processing = False
                    #return

                # check for writing
                if event & select.POLLOUT:
                    assert client._iostate & Engine.IOSTATE_WRITING
                    client._iostate &= ~Engine.IOSTATE_WRITING
                    client._handle_write()

                # post processing
                client._processing = False

                # apply any changes occured during processing
                if client.registered and client._iostate != iostate_sav:
                    self._modify(client, client._iostate, Engine.IOSTATE_ANY)

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

