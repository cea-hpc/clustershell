# WorkerPopen2.py -- Local shell worker
# Copyright (C) 2007, 2008, 2009 CEA
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
WorkerPopen2

ClusterShell worker for local commands.
"""

from ClusterShell.NodeSet import NodeSet

from Worker import WorkerSimple

import fcntl
import os
import popen2
import signal


class WorkerPopen2(WorkerSimple):
    """
    Implements the Popen2 Worker.
    """

    def __init__(self, command, key, handler, timeout, autoclose=False):
        """
        Initialize Popen2 worker.
        """
        WorkerSimple.__init__(self, None, None, None, key, handler, timeout, autoclose)

        self.command = command
        if not self.command:
            raise WorkerBadArgumentException()

        self.fid = None
        self.rc = None

    def _start(self):
        """
        Start worker.
        """
        assert self.fid is None

        self.fid = self._exec_nonblock(self.command)
        self.file_reader = self.fid.fromchild
        self.file_writer = self.fid.tochild

        if self.task.info("debug", False):
            self.task.info("print_debug")(self.task,
                    "POPEN2: %s" % self.command)

        self._invoke("ev_start")

        return self

    def _close(self, force, timeout):
        """
        Close worker. Called by engine after worker has been
        unregistered. This method should handle all termination types
        (normal, forced or on timeout).
        """
        rc = -1
        if force or timeout:
            # check if process has terminated
            status = self.fid.poll()
            if status == -1:
                # process is still running, kill it
                os.kill(self.fid.pid, signal.SIGKILL)
        else:
            # close process / check if it has terminated
            status = self.fid.wait()
            # get exit status
            if os.WIFEXITED(status):
                # process exited normally
                rc = os.WEXITSTATUS(status)
            elif os.WIFSIGNALED(status):
                # if process was signaled, return 128 + signum (bash-like)
                rc = 128 + os.WSTOPSIG(status)
            else:
                # unknown condition
                rc = 255

        self.fid.tochild.close()
        self.fid.fromchild.close()

        if rc >= 0:
            self._on_rc(rc)
        elif timeout:
            self._on_timeout()

        self._invoke("ev_close")

    def _on_rc(self, rc):
        """
        Set return code.
        """
        self.rc = rc
        self.task._rc_set((self, self.key), rc)

        self._invoke("ev_hup")

    def retcode(self):
        """
        Return return code or None if command is still in progress.
        """
        return self.rc
   
