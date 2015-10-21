#
# Copyright CEA/DAM/DIF (2008-2015)
#  Contributor: Stephane THIELL <sthiell@stanford.edu>
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
