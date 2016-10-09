#
# Copyright (C) 2008-2015 CEA/DAM
# Copyright (C) 2015 Stephane Thiell <sthiell@stanford.edu>
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
WorkerPopen

ClusterShell worker for executing local commands.

Usage example:
   >>> worker = WorkerPopen("/bin/uname", key="mykernel")
   >>> task.schedule(worker)    # schedule worker
   >>> task.resume()            # run task
   >>> worker.retcode()         # get return code
   0
   >>> worker.read()            # read command output
   'Linux'

"""

from ClusterShell.Worker.Worker import WorkerSimple, StreamClient


class PopenClient(StreamClient):

    def __init__(self, worker, key, stderr, timeout, autoclose):
        StreamClient.__init__(self, worker, key, stderr, timeout, autoclose)
        self.popen = None
        self.rc = None
        # Declare writer stream to allow early buffering
        self.streams.set_writer(worker.SNAME_STDIN, None, retain=False)

    def _start(self):
        """Worker is starting."""
        assert not self.worker.started
        assert self.popen is None

        self.popen = self._exec_nonblock(self.worker.command, shell=True)

        task = self.worker.task
        if task.info("debug", False):
            task.info("print_debug")(task, "POPEN: %s" % self.worker.command)

        self.worker._on_start(self.key)
        return self

    def _close(self, abort, timeout):
        """
        Close client. See EngineClient._close().
        """
        if abort:
            # it's safer to call poll() first for long time completed processes
            prc = self.popen.poll()
            # if prc is None, process is still running
            if prc is None:
                try: # try to kill it
                    self.popen.kill()
                except OSError:
                    pass
        prc = self.popen.wait()

        self.streams.clear()

        if prc >= 0: # filter valid rc
            self.rc = prc
            self.worker._on_rc(self.key, prc)
        elif timeout:
            assert abort, "abort flag not set on timeout"
            self.worker._on_timeout(self.key)
        elif not abort:
            # if process was signaled, return 128 + signum (bash-like)
            self.rc = 128 + -prc
            self.worker._on_rc(self.key, self.rc)

        if self.worker.eh:
            self.worker.eh.ev_close(self.worker)


class WorkerPopen(WorkerSimple):
    """
    Implements the Popen Worker.
    """
    def __init__(self, command, key=None, handler=None,
                 stderr=False, timeout=-1, autoclose=False):
        """Initialize Popen worker."""
        WorkerSimple.__init__(self, None, None, None, key, handler, stderr,
                              timeout, autoclose, client_class=PopenClient)
        self.command = command
        if not self.command:
            raise ValueError("missing command parameter in WorkerPopen "
                             "constructor")

    def retcode(self):
        """Return return code or None if command is still in progress."""
        return self.clients[0].rc

WORKER_CLASS = WorkerPopen
