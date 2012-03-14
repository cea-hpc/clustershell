#
# Copyright CEA/DAM/DIF (2008, 2009, 2010, 2011)
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

import os

from ClusterShell.Worker.Worker import WorkerSimple


class WorkerPopen(WorkerSimple):
    """
    Implements the Popen Worker.
    """

    def __init__(self, command, key=None, handler=None,
        stderr=False, timeout=-1, autoclose=False):
        """
        Initialize Popen worker.
        """
        WorkerSimple.__init__(self, None, None, None, key, handler,
            stderr, timeout, autoclose)

        self.command = command
        if not self.command:
            raise ValueError("missing command parameter in WorkerPopen " \
			     "constructor")

        self.popen = None
        self.rc = None

    def _start(self):
        """
        Start worker.
        """
        assert self.popen is None

        self.popen = self._exec_nonblock(self.command, shell=True)

        if self.task.info("debug", False):
            self.task.info("print_debug")(self.task, "POPEN: %s" % self.command)

        if self.eh:
            self.eh.ev_start(self)

        return self

    def _close(self, abort, flush, timeout):
        """
        Close client. See EngineClient._close().
        """
        if flush and self._rbuf:
            # We still have some read data available in buffer, but no
            # EOL. Generate a final message before closing.
            self.worker._on_msgline(self._rbuf)

        rc = -1
        if abort:
            # check if process has terminated
            prc = self.popen.poll()
            if prc is None:
                # process is still running, kill it
                self.popen.kill()
        # release process
        prc = self.popen.wait()
        # get exit status
        if prc >= 0:
            # process exited normally
            rc = prc
        elif not abort:
            # if process was signaled, return 128 + signum (bash-like)
            rc = 128 + -prc

        os.close(self.fd_reader)
        self.fd_reader = None
        if self.fd_error:
            os.close(self.fd_error)
            self.fd_error = None
        if self.fd_writer:
            os.close(self.fd_writer)
            self.fd_writer = None

        if rc >= 0: # filter valid rc
            self._on_rc(rc)
        elif timeout:
            assert abort, "abort flag not set on timeout"
            self._on_timeout()

        if self.eh:
            self.eh.ev_close(self)

    def _on_rc(self, rc):
        """
        Set return code.
        """
        self.rc = rc        # 1.4- compat
        WorkerSimple._on_rc(self, rc)

    def retcode(self):
        """
        Return return code or None if command is still in progress.
        """
        return self.rc
   
