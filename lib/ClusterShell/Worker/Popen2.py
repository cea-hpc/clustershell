# WorkerPopen2.py -- Local shell worker
# Copyright (C) 2007, 2008 CEA
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
# $Id: WorkerPopen2.py 24 2008-03-19 14:02:13Z st-cea $


"""
WorkerPopen2

ClusterShell worker for local commands.
"""

from ClusterShell.NodeSet import NodeSet
from Worker import Worker

import fcntl
import os
import popen2


class WorkerPopen2(Worker):
    """
    Implements the Worker interface.
    """

    def __init__(self, command, key, handler, task):
        """
        Initialize Popen2 worker
        """
        Worker.__init__(self, handler, task)
        self.command = command
        if not self.command:
            raise WorkerBadArgumentException()
        self.fid = None
        self.buf = ""
        self.last_msg = None
        self.rc = None
        self.key = key or self

    def __iter__(self):
        for line in self.fid.fromchild:
            yield line

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
        self._clearbuf()             # initialize worker read buffer
        self._invoke_ev_start()
        try:
            # Launch process in non-blocking mode
            self.fid = popen2.Popen4(self.command)
            fl = fcntl.fcntl(self.fid.fromchild, fcntl.F_GETFL)
            fcntl.fcntl(self.fid.fromchild, fcntl.F_SETFL, os.O_NDELAY)
        except OSError, e:
            raise e
        return self

    def _fileno(self):
        return self.fid.fromchild.fileno()

    def _read(self, size=-1):
        return self.fid.fromchild.read(size)

    def _close(self):
        status = self.fid.wait()
        if os.WIFEXITED(status):
            self._set_rc(os.WEXITSTATUS(status))
        else:
            self._set_rc(0)

        self.fid.tochild.close()
        self.fid.fromchild.close()
        self._invoke_ev_close()

    def _handle_read(self):
        debug = self._task.info("debug", False)
        # read a chunk
        readbuf = self._read()
        assert len(readbuf) > 0, "poll() POLLIN event flag but no data to read"
        buf = self._getbuf() + readbuf
        lines = buf.splitlines(True)
        self._clearbuf()
        for line in lines:
            if debug:
                print "LINE %s" % line,
            if line.endswith('\n'):
                self._add_msg(line)
                self._invoke_ev_read()
            else:
                # keep partial line in buffer
                self._setbuf(line)
                # will break here

    def _getbuf(self):
        return self.buf

    def _setbuf(self, buf):
        self.buf = buf

    def _clearbuf(self):
        self.buf = ""

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

    def read(self):
        """
        Read worker buffer.
        """
        for key, msg in self.engine.iter_key_messages_by_worker(self):
            assert key == self.key
            return msg

    def retcode(self):
        ## raise if not exited

        return self.rc

   
