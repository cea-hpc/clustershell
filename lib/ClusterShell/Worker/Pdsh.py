# WorkerPdsh.py -- ClusterShell pdsh worker with poll()
# Copyright (C) 2007, 2008 CEA
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
# $Id: WorkerPdsh.py 24 2008-03-19 14:02:13Z st-cea $

"""
WorkerPdsh

ClusterShell worker
"""

from ClusterShell.NodeSet import NodeSet
from Worker import Worker

import errno
import fcntl
import os
import popen2


class WorkerPdsh(Worker):

    def __init__(self, nodes, handler, info, **kwargs):
        Worker.__init__(self, handler, info)
        self.nodes = NodeSet(nodes)
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

        self.fid = None
        self.buf = ""
        self.last_nn = None
        self.last_msg = None

        """
        # root of msg tree
        self._msg_root = _MsgTreeElem()
        # dict of nodes to msg tree elem
        self._d_msg_nodes = {}
        # dict of nodes to retcode
        self._d_rc_nodes = {}
        # dict of retcode to NodeSet
        self._d_rc = {}
        """

    def __iter__(self):
        for line in self.fid.fromchild:
            yield line

    def start(self):
        # Initialize worker read buffer
        self.clearbuf()

        #for node in self.nodes:
        self._invoke_ev_start()

        if self.command is not None:
            # Build pdsh command

            cmd_l = [ "/usr/bin/pdsh", "-b" ]

            fanout = self.info.get("fanout", 0)
            if fanout > 0:
                cmd_l.append("-f %d" % fanout)

            connect_timeout = self.info.get("connect_timeout", 0)
            if connect_timeout > 0:
                cmd_l.append("-t %d" % connect_timeout)

            command_timeout = self.info.get("command_timeout", 0)
            if command_timeout > 0:
                cmd_l.append("-u %d" % command_timeout)

            cmd_l.append("-w '%s'" % self.nodes)
            cmd_l.append("'%s'" % self.command)

            cmd = ' '.join(cmd_l)
            print "PDSH : %s" % cmd
        else:
            # Build pdcp command
            cmd = "/usr/bin/pdcp -b -f %d -w '%s' '%s' '%s'" % \
                    (self.pcmdnum, \
                    self.nodes, \
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
        self._invoke_ev_close()
        return rc

    def handle_read(self):
        # read a chunk
        readbuf = self.read()
        assert len(readbuf) > 0, "poll() POLLIN event flag but no data to read"
        buf = self.getbuf() + readbuf
        lines = buf.splitlines(True)
        self.clearbuf()
        for line in lines:
            #print "LINE %s" % line,
            if line.endswith('\n'):
                if line.startswith("pdsh@") or line.startswith("pdcp@") or line.startswith("sending "):
                    try:
                        # pdsh@cors113: cors115: ssh exited with exit code 1
                        #       0          1      2     3     4    5    6  7
                        # corsUNKN: ssh: corsUNKN: Name or service not known
                        #     0      1       2       3  4     5     6    7
                        # pdsh@fortoy0: fortoy101: command timeout
                        #     0             1         2       3
                        # sending SIGTERM to ssh fortoy112 pid 32014
                        #     0      1     2  3      4      5    6
                        # pdcp@cors113: corsUNKN: ssh exited with exit code 255
                        #     0             1      2    3     4    5    6    7
                        # pdcp@cors113: cors115: fatal: /var/cache/shine/conf/testfs.xmf: No such file or directory
                        #     0             1      2                   3...

                        words  = line.split()
                        # Set return code for nodename of worker
                        if self.mode == 'pdsh':
                            if len(words) == 4 and words[2] == "command" and words[3] == "timeout":
                                pass
                            elif len(words) == 8 and words[3] == "exited" and words[7].isdigit():
                                self._set_node_rc(words[1][:-1], int(words[7]))
                        elif self.mode == 'pdcp':
                            self._set_node_rc(words[1][:-1], errno.ENOENT)

                    except:
                        print "exception in pdsh@"
                        raise
                else:
                    #        
                    # split pdsh reply "nodename: msg"
                    nodename, msgline = line.split(': ', 1)
                    self._add_node_msgline(nodename, msgline)
                    self._invoke_ev_read()
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

    def _add_node_msgline(self, nodename, msg):
        """
        Update last_* and add node message line to messages tree.
        """
        self.last_nn, self.last_msg = nodename, msg[:-1]

        self.engine.add_msg((self, nodename), msg)

    def _set_node_rc(self, nodename, rc):
        self.engine.set_key_rc(nodename, rc)

    def last_buffer(self):
        """
        Get last (node, buffer) in an EventHandler.
        """
        return self.last_nn, self.last_msg

    def node_buffer(self, nodename):
        """
        Get specific node buffer.
        """
        return self.engine.message_by_source((self, nodename))
        
    def node_rc(self, nodename):
        """
        Get specific node return code.
        """
        return self.engine.rc_by_source((self, nodename))

    def iter_buffers(self):
        """
        Returns an iterator over available buffers with associated NodeSet.
        """
        for msg, keys in self.engine.iter_messages_by_worker(self):
            yield msg, NodeSet.fromlist(keys)

    def iter_node_buffers(self):
        """
        Returns an iterator over nodes and associated buffers.
        """
        # Get iterator from underlying engine.
        return self.engine.iter_key_messages_by_worker(self)

    def iter_retcodes(self):
        """
        Returns an iterator over return codes with associated NodeSet.
        """
        for rc, keys in self.engine.iter_retcodes_by_worker(self):
            yield rc, NodeSet.fromlist(keys)

    def iter_node_retcodes(self):
        """
        """
        # Get iterator from underlying engine.
        return self.engine.iter_key_retcodes_by_worker(self)

    """
    def iter_retcodes(self):
        for rc, nodeset in self._d_rc.iteritems():
            yield nodeset, rc

    def iter_retcodes_by_node(self):
        for nodename, rc in self._d_rc_nodes.iteritems():
            yield nodename, rc
    """

    def nodes_cs(self):
        result = ""
        for n in self.nodes:
            result += "%s," % n
        return result[:-1]
