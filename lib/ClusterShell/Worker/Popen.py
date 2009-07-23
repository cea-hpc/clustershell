#
# Copyright CEA/DAM/DIF (2008, 2009)
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
WorkerPopen

ClusterShell worker for executing local commands.
"""

from ClusterShell.NodeSet import NodeSet

from Worker import WorkerSimple

import fcntl
import os
import signal


class WorkerPopen(WorkerSimple):
    """
    Implements the Popen Worker.
    """

    def __init__(self, command, key, handler, timeout, autoclose=False):
        """
        Initialize Popen worker.
        """
        WorkerSimple.__init__(self, None, None, None, key, handler, timeout, autoclose)

        self.command = command
        if not self.command:
            raise WorkerBadArgumentException()

        self.popen = None
        self.rc = None

    def _start(self):
        """
        Start worker.
        """
        assert self.popen is None

        self.popen = self._exec_nonblock(self.command, shell=True)
        self.file_reader = self.popen.stdout
        self.file_writer = self.popen.stdin

        if self.task.info("debug", False):
            self.task.info("print_debug")(self.task, "POPEN: %s" % self.command)

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
            prc = self.popen.poll()
            if prc is None:
                # process is still running, kill it
                os.kill(self.popen.pid, signal.SIGKILL)
        else:
            # close process / check if it has terminated
            prc = self.popen.wait()
            # get exit status
            if prc >= 0:
                # process exited normally
                rc = prc
            else:
                # if process was signaled, return 128 + signum (bash-like)
                rc = 128 + -prc

        self.popen.stdin.close()
        self.popen.stdout.close()

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
   
