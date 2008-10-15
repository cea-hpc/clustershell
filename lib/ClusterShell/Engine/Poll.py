# EnginePdsh.py -- ClusterShell pdsh engine with poll()
# Copyright (C) 2007, 2008 CEA
#
# This file is part of shine
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
# $Id: EnginePdsh.py 11 2008-01-11 15:19:44Z st-cea $

from Engine import *

import os
import select
import sys
import thread


class EnginePoll(Engine):
    """
    Poll Engine

    ClusterShell engine using the select.poll mechanism (Linux poll() syscall).
    """
    def __init__(self, info):
        """
        Initialize Engine.
        """
        Engine.__init__(self, info)
        try:
            # Get a polling object
            self.polling = select.poll()
        except:
            print "Fatal error: select.poll() not supported?"
            raise
        self.workers = {}
        self.dictout = {}
        self.exited = False
        self.run_lock = thread.allocate_lock()
        self.start_lock = thread.allocate_lock()
        self.start_lock.acquire()

    def register(self, worker):
        """
        Register a worker for input I/O
        """
        fd = worker._fileno()
        self.polling.register(fd, select.POLLIN)
        self.workers[fd] = worker

    def unregister(self, worker):
        """
        Unregister a worker
        """
        fd = worker._fileno()
        self.polling.unregister(fd)
        del self.workers[fd]
        worker._close()

    def add(self, worker):
        Engine.add(self, worker)
        if self.run_lock.locked():
            self.register(worker.start())

    def _runloop(self, timeout):
        """
        Pdsh engine run(): start workers and properly get replies
        """
        self.dictout = {}
        self.workers = {}

        # Start workers and register them in the poll()-based engine
        for worker in self.worker_list:
            self.register(worker._start())

        if timeout == 0:
            timeout = -1

        status = self.run_lock.acquire(0)
        assert status == True, "cannot acquire run lock"

        self.start_lock.release()

        try:
            # Run main event loop
            while len(self.workers) > 0:

                # Wait for I/O
                evlist = self.polling.poll(timeout * 1000)

                # No event means timed out
                if len(evlist) == 0:
                    raise EngineTimeoutError()

                for fd, event in evlist:

                    # Get worker object
                    worker = self.workers[fd]

                    # check for poll error
                    if event & select.POLLERR:
                        print >> sys.stderr, "EnginePoll: POLLERR"
                        self.unregister(worker)
                        continue

                    if event & select.POLLIN:
                        worker._handle_read()

                    # check for hung hup (EOF)
                    if event & select.POLLHUP:
                        self.unregister(worker)
                        continue

                    assert event & select.POLLIN, "poll() returned without data to read"
        finally:
            self.exited = True
            self.start_lock.acquire()
            self.run_lock.release()

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

