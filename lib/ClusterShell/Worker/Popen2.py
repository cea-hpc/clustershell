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
from Worker import Worker

import fcntl
import os
import popen2
import signal


class WorkerPopen2(Worker):
    """
    Implements the Worker interface.
    """

    def __init__(self, command, key, handler, timeout, task):
        """
        Initialize Popen2 worker.
        """
        Worker.__init__(self, handler, timeout, task)
        self.command = command
        if not self.command:
            raise WorkerBadArgumentException()
        self.fid = None
        self.buf = ""
        self.last_msg = None
        self.rc = None
        self.key = key or self

    def set_key(self, key):
        """
        Source key for Popen2 worker is free for use. This method is a
        way to set such a custom source key for this worker.
        """
        self.key = key

    def _start(self):
        """
        Start worker. Implements worker interface.
        """
        assert self.fid is None

        self.buf = ""                # initialize worker read buffer

        # Launch process in non-blocking mode
        self.fid = popen2.Popen4(self.command)
        fcntl.fcntl(self.fid.fromchild, fcntl.F_SETFL, os.O_NDELAY)

        if self._task.info("debug", False):
            print "POPEN2: %s" % self.command

        self._invoke("ev_start")

        return self

    def fileno(self):
        """
        Returns the file descriptor as an integer.
        """
        return self.fid.fromchild.fileno()

    def closed(self):
        """
        Returns True if the underlying file object is closed.
        """
        return self.fid.fromchild.closed

    def _read(self, size=-1):
        """
        Read data from process.
        """
        return self.fid.fromchild.read(size)

    def _close(self, force, timeout):
        """
        Close worker. Called by engine after worker has been
        unregistered. This method should handle all termination types
        (normal, forced or on timeout).
        """
        if force or timeout:
            # check if process has terminated
            status = self.fid.poll()
            if status == -1:
                # process is still running, kill it
                os.kill(self.fid.pid, signal.SIGKILL)
            # trigger timeout event
            if timeout:
                self._invoke("ev_timeout")
        else:
            # close process / check if it has terminated
            status = self.fid.wait()
            # get exit status
            if os.WIFEXITED(status):
                # process exited normally
                self._set_rc(os.WEXITSTATUS(status))
            elif os.WIFSIGNALED(status):
                # if process was signaled, return 128 + signum (bash-like)
                self._set_rc(128 + os.WSTOPSIG(status))
            else:
                # unknown condition
                self._set_rc(255)

        self.fid.tochild.close()
        self.fid.fromchild.close()
        self._invoke("ev_close")

    def _handle_read(self):
        """
        Engine is telling us a read is available.
        """
        debug = self._task.info("debug", False)

        # read a chunk
        readbuf = self._read()
        assert len(readbuf) > 0, "_handle_read() called with no data to read"

        buf = self.buf + readbuf
        lines = buf.splitlines(True)
        self.buf = ""
        for line in lines:
            if debug:
                print "LINE %s" % line,
            if line.endswith('\n'):
                self._add_msg(line)
                self._invoke("ev_read")
            else:
                # keep partial line in buffer
                self.buf = line
                # will break here
        return True

    def last_read(self):
        """
        Read last msg, useful in an EventHandler.
        """
        return self.last_msg

    def _add_msg(self, msg):
        """
        Add a message.
        """
        # add last msg to local buffer
        self.last_msg = msg[:-1]

        # tell engine
        self.engine.add_msg((self, self.key), msg)

    def _set_rc(self, rc):
        """
        Set return code.
        """
        self.rc = rc
        self.engine.set_rc((self, self.key), rc)

    def read(self):
        """
        Read worker buffer.
        """
        for key, msg in self.engine.iter_key_messages_by_worker(self):
            assert key == self.key
            return msg

    def retcode(self):
        """
        Return return code or None if command is still in progress.
        """
        return self.rc
   
