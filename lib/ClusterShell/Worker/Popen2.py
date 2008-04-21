# WorkerPopen2.py -- Local shell worker
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
# $Id: WorkerPopen2.py 24 2008-03-19 14:02:13Z st-cea $

from ClusterShell.NodeSet import NodeSet
from Worker import Worker

import fcntl
import os
import popen2


class _Msg:
    def __init__(self):
        self.buf = ""
        self.rc = 0


class WorkerPopen2(Worker):

    def __init__(self, command, handler):
        Worker.__init__(self, handler)
        self.command = command
        if not self.command:
            raise WorkerBadArgumentException()
        self.fid = None
        self.buf = ""
        self.msg = None 
        self.last_msg = None

    def __iter__(self):
        for line in self.fid.fromchild:
            yield line

    def start(self):
        # Initialize worker read buffer
        self.clearbuf()

        self.invoke_ev_start()

        try:
            # Launch process in non-blocking mode
            self.fid = popen2.Popen4(self.command)
            fl = fcntl.fcntl(self.fid.fromchild, fcntl.F_GETFL)
            fcntl.fcntl(self.fid.fromchild, fcntl.F_SETFL, os.O_NDELAY)
        except OSError, e:
            raise e
        return self

    def fileno(self):
        return self.fid.fromchild.fileno()

    def read(self, size=-1):
        return self.fid.fromchild.read(size)

    def close(self):
        status = self.fid.wait()
        if os.WIFEXITED(status):
            self.set_rc(os.WEXITSTATUS(status))
        else:
            self.set_rc(0)
        self.fid.tochild.close()
        self.fid.fromchild.close()
        self.invoke_ev_close()

    def handle_read(self):
        # read a chunk
        readbuf = self.read()
        assert len(readbuf) > 0, "poll() POLLIN event flag but no data to read"
        buf = self.getbuf() + readbuf
        lines = buf.splitlines(True)
        self.clearbuf()
        for line in lines:
            #print "LINE %s" % line
            if line.endswith('\n'):
                self.add_msg(line)
                self.invoke_ev_read()
            else:
                # keep partial line in buffer
                self.setbuf(line)
                # will break here

    def getbuf(self):
        return self.buf

    def setbuf(self, buf):
        self.buf = buf

    def clearbuf(self):
        self.buf = ""

    def get_last_read(self):
        return self.last_msg

    def add_msg(self, msg):
        self.last_msg = msg[:-1]
        if not self.msg:
            self.msg = _Msg()
        self.msg.buf += msg

    def set_rc(self, rc):
        if not self.msg:
            self.msg = _Msg()
        self.msg.rc = rc

    def read_buffer(self):
        return self.msg.buf

    def get_rc(self):
        return self.msg.rc

   
