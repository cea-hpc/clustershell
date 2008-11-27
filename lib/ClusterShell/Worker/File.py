# WorkerFile.py -- File ClusterShell worker
# Copyright (C) 2008 CEA
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
WorkerFile

ClusterShell worker for file objects.
"""

from ClusterShell.NodeSet import NodeSet
from Worker import Worker

import fcntl
import os

class WorkerFile(Worker):
    """
    Implements the Worker interface.
    """

    def __init__(self, file, key, handler, timeout, task):
        """
        Initialize File worker.
        """
        Worker.__init__(self, handler, timeout, task)
        self._file = file
        self.last_msg = None
        self.key = key or self

    def set_key(self, key):
        """
        Source key for File worker is free for use. This method is a
        way to set such a custom source key for this worker.
        """
        self.key = key

    def _start(self):
        """
        Start worker. Implements worker interface.
        """
        # initialize worker read buffer
        self.buf = ""
        # save file f_flag
        self.fl_save = fcntl.fcntl(self._file, fcntl.F_GETFL)
        # turn file object into non blocking mode
        fcntl.fcntl(self._file.fileno(), fcntl.F_SETFL, os.O_NDELAY)
        self._invoke("ev_start")
        return self

    def fileno(self):
        """
        Returns the file descriptor as an integer.
        """
        return self._file.fileno()

    def closed(self):
        """
        Returns True if the underlying file object is closed.
        """
        return self._file.closed

    def _read(self, size=-1):
        return self._file.read(size)

    def _close(self, force, timeout):
        """
        Close worker. Called by engine after worker has been
        unregistered. This method should handle all termination types
        (normal, forced or on timeout).
        """
        if timeout:
            self._invoke("ev_timeout")
        # restore file f_flag
        self._invoke("ev_close")
        fcntl.fcntl(self._file, fcntl.F_SETFL, self.fl_save)

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
                print "LINE (File): %s" % line,
            if line.endswith('\n'):
                self._add_msg(line)
                self._invoke("ev_read")
            else:
                # keep partial line in buffer
                self.buf = line
                # will break here

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
        pass

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
        return 0
   
