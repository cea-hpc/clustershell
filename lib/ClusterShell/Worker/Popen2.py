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

from EngineClient import EngineClient
from Worker import Worker

import fcntl
import os
import popen2
import signal


class WorkerPopen2(EngineClient,Worker):
    """
    Implements the Worker interface.
    """

    def __init__(self, command, key, handler, timeout):
        """
        Initialize Popen2 worker.
        """
        Worker.__init__(self, handler)
        EngineClient.__init__(self, timeout, self)

        self.command = command
        if not self.command:
            raise WorkerBadArgumentException()

        self.fid = None
        self.buf = ""
        self.last_msg = None
        self.rc = None
        self.key = key or self

    def _engine_clients(self):
        """
        Return a list of underlying engine clients.
        """
        return [self]

    def set_key(self, key):
        """
        Source key for Popen2 worker is free for use. This method is a
        way to set such a custom source key for this worker.
        """
        self.key = key

    def _start(self):
        """
        Start worker.
        """
        assert self.fid is None

        self.buf = ""                # initialize worker read buffer

        self.fid = self._exec_nonblock(self.command)

        if self.task.info("debug", False):
            print "POPEN2: %s" % self.command

        self._invoke("ev_start")

        return self

    def reader_fileno(self):
        """
        Returns the reader file descriptor as an integer.
        """
        return self.fid.fromchild.fileno()
    
    def writer_fileno(self):
        """
        Returns the writer file descriptor as an integer.
        """
        return self.fid.tochild.fileno()

    def closed(self):
        """
        Returns True if the underlying file object is closed.
        """
        return self.fid.fromchild.closed

    def _read(self, size=-1):
        """
        Read data from process.
        """
        result = self.fid.fromchild.read(size)
        if result > 0:
            self._set_reading()
        return result

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

    def _handle_read(self):
        """
        Engine is telling us a read is available.
        """
        debug = self.task.info("debug", False)

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
                if line.endswith('\r\n'):
                    msgline = line[:-2]
                else:
                    msgline = line[:-1]
                self._on_msgline(msgline)
            else:
                # keep partial line in buffer
                self.buf = line
                # will break here
        return True

    def _handle_write(self):
        pass

    def last_read(self):
        """
        Read last msg, useful in an EventHandler.
        """
        return self.last_msg

    def _on_msgline(self, msg):
        """
        Add a message.
        """
        # add last msg to local buffer
        self.last_msg = msg

        # update task
        self.task._msg_add((self, self.key), msg)

        self._invoke("ev_read")

    def _on_rc(self, rc):
        """
        Set return code.
        """
        self.rc = rc
        self.task._rc_set((self, self.key), rc)

        self._invoke("ev_hup")

    def _on_timeout(self):
        """
        Update on timeout.
        """
        self.task._timeout_add((self, self.key))

        # trigger timeout event
        self._invoke("ev_timeout")

    def read(self):
        """
        Read worker buffer.
        """
        for key, msg in self.task._kmsg_iter_by_worker(self):
            assert key == self.key
            return msg

    def retcode(self):
        """
        Return return code or None if command is still in progress.
        """
        return self.rc
   
