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
            print >> sys.stderr, "Fatal error: select.poll() not supported?"
            raise

        # keep track of registered workers
        self.workers = {}

        # runloop-has-exited flag
        self.exited = False

        # thread stuffs
        self.run_lock = thread.allocate_lock()
        self.start_lock = thread.allocate_lock()
        self.start_lock.acquire()

    def register(self, worker):
        """
        Register a worker (listen for input events).
        """
        self.workers[worker.fileno()] = worker
        self.polling.register(worker, select.POLLIN)

    def unregister(self, worker):
        """
        Unregister a worker
        """
        self.polling.unregister(worker)
        del self.workers[worker.fileno()]
        worker._close()

    def start_workers(self):
        """
        # Start workers and register them in the poll()-based engine.
        """
        for worker in self.worker_list:
            self.register(worker._start())

    def stop_workers(self):
        """
        Stop all workers. This method is used in case of timeout.
        """
        for worker in self.worker_list:
            if not worker.closed():
                self.unregister(worker)

    def add(self, worker):
        """
        Add a worker to engine.
        """
        Engine.add(self, worker)

        if self.run_lock.locked():
            self.register(worker._start())

    def runloop(self, timeout):
        """
        Pdsh engine run(): start workers and properly get replies
        """

        # Start workers
        self.start_workers()

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

                    # get worker instance
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

            # unregister all workers
            self.stop_workers()
            self.exited = True

            # change to idle state
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

