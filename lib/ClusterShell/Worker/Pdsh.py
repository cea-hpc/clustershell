# WorkerPdsh.py -- ClusterShell pdsh worker with poll()
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
# $Id: WorkerPdsh.py 24 2008-03-19 14:02:13Z st-cea $


from ClusterShell.NodeSet import NodeSet
from Worker import Worker

import errno
import fcntl
import os
import popen2


class _Msg:
    def __init__(self):
        self.buf = ""
        self.rc = 0


class WorkerPdsh(Worker):

    def __init__(self, nodes, handler, **kwargs):
        Worker.__init__(self, handler)
        self.nodes = nodes
        if kwargs.has_key('command'):
            # PDSH
            self.command = kwargs['command']
            self.source = None
            self.dest = None
            self.mode = 'pdsh'
        elif kwargs.has_key('source'):
            # PDCP
            self.command = None
            self.source = kwargs['source']
            self.dest = kwargs['dest']
            self.mode = 'pdcp'
        else:
            raise WorkerBadArgumentException()

        if len(nodes) > 32:
            mod = len(nodes) % 32
        else:
            mod = 0

        self.pcmdnum = min(256, len(nodes) + mod)
        self.fid = None
        self.buf = ""
        self.buffers = {}
        self.last_nn = None
        self.last_msg = None

    def __iter__(self):
        for line in self.fid.fromchild:
            yield line

    def start(self):
        # Initialize worker read buffer
        self.clearbuf()

        #for node in self.nodes:
        self.invoke_ev_start()

        if self.command:
            # Build pdsh command
            cmd = "/usr/bin/pdsh -b -f %d -w '%s' '%s'" % \
                    (self.pcmdnum, \
                    self.nodes.as_ranges(), \
                    self.command)
            #print "PDSH : %s" % cmd
        else:
            # Build pdcp command
            cmd = "/usr/bin/pdcp -b -f %d -w '%s' '%s' '%s'" % \
                    (self.pcmdnum, \
                    self.nodes.as_ranges(), \
                    self.source, self.dest)
            #print "PDCP : %s" % cmd

        try:
            # Launch process in non-blocking mode
            self.fid = popen2.Popen4(cmd)
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
        rc = self.fid.fromchild.close()
        self.invoke_ev_close()
        return rc

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
                if line.startswith("pdsh@") or line.startswith("pdcp@"):
                    try:
                        # pdsh@cors113: cors115: ssh exited with exit code 1
                        #       0          1      2     3     4    5    6  7
                        # corsUNKN: ssh: corsUNKN: Name or service not known
                        #     0      1       2       3  4     5     6    7
                        # pdcp@cors113: corsUNKN: ssh exited with exit code 255
                        #     0             1      2    3     4    5    6    7
                        # pdcp@cors113: cors115: fatal: /var/cache/shine/conf/testfs.xmf: No such file or directory
                        #     0             1      2                   3...

                        words  = line.split()
                        # Set return code for nodename of worker
                        if self.mode == 'pdsh' and words[7].isdigit():
                            self.set_node_rc(nn=words[1][:-1], rc=int(words[7]))
                        elif self.mode == 'pdcp':
                            self.set_node_rc(nn=words[1][:-1], rc=errno.ENOENT)

                    except:
                        print "exception in pdsh@"
                        raise
                else:
                    #        
                    # split pdsh reply "nodename: msg"
                    nodename, msgline = line.split(': ', 1)
                    self.add_node_msg(nodename, msgline)
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
        return self.last_nn, self.last_msg

    def add_node_msg(self, nn, msg):
        self.last_nn, self.last_msg = nn, msg[:-1]
        if nn not in self.buffers:
            self.buffers[nn] = _Msg()
        self.buffers[nn].buf += msg

    def set_node_rc(self, nn, rc):
        if nn not in self.buffers:
            self.buffers[nn] = _Msg()
        self.buffers[nn].rc = rc

    def read_node_buffer(self, nn):
        return self.buffers.get(nn, _Msg()).buf

    def get_node_rc(self, nn):
        return self.buffers.get(nn, _Msg()).rc

    def gather(self):
        gbuf, result = {}, {}

        # Group by buffer
        for n, m in self.buffers.iteritems():
            gbuf.setdefault(m.buf, []).append(n)

        # Reverse dict
        for b, l in gbuf.iteritems():
            result[NodeSet.fromlist(l)] = b

        return result

    def gather_rc(self):
        gbuf, result = {}, {}

        # Group by rc
        for n, m in self.buffers.iteritems():
            gbuf.setdefault(m.rc, []).append(n)

        # Reverse dict
        for rc, l in gbuf.iteritems():
            result[NodeSet.fromlist(l)] = rc

        return result

    def nodes_cs(self):
        result = ""
        for n in self.nodes:
            result += "%s," % n
        return result[:-1]

