# WorkerPdsh.py -- ClusterShell pdsh worker with poll()
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
# $Id: WorkerPdsh.py 24 2008-03-19 14:02:13Z st-cea $


from ClusterShell.NodeSet import NodeSet
from Worker import Worker

import errno
import fcntl
import os
import popen2


class _MsgTreeElem:
    """
    Helper class used to build a messages tree. Here, the main advantages of a messages tree are:
    (1) low memory consumption especially on a cluster when all nodes return similar messages,
    (2) gathering of messages is done (almost) automatically.

    Note: a `node' is a host node here, not a tree node (called `element')
    """
    def __init__(self, msg=None, parent=None):
        """
        Initialize message tree element.
        """
        # structure
        self.parent = parent
        self.children = {}
        # content
        self.msg = msg
        self.nodes = None

    def _add_node(self, nodename):
        """
        Add a node to this element.
        """
        if not self.nodes:
            self.nodes = NodeSet(nodename)
        else:
            self.nodes.add(nodename)
    
    def _remove_node(self, nodename):
        """
        Remove a node from this element (used when moving it to a child).
        """
        if self.nodes:
            self.nodes.sub(nodename)
        
    def add_child(self, msg, nodename):
        """
        A new message line is coming, add msg and node.
        """
        # remove node from parent (self)
        self._remove_node(nodename)

        # add node to child
        elem = self.children.setdefault(msg, _MsgTreeElem(msg, self))
        elem._add_node(nodename)
        return elem

    def get_leaves(self):
        leaves = []
        for elem in self.children.itervalues():
            if len(elem.children) == 0:
                leaves.append(elem)
            else:
                leaves += elem.get_leaves()
        return leaves
    
    def message(self):
        """
        Get the whole message buffer from this tree element.
        """
        msg = ""

        # no msg in root elem
        if not self.msg:
            return msg

        # build reverse msg
        rev_msgs = [self.msg]
        parent = self.parent
        while parent and parent.msg:
            rev_msgs.append(parent.msg)
            parent = parent.parent

        # reverse to get well ordered buffer
        for i in range(len(rev_msgs)-1, -1, -1):
            msg += rev_msgs[i]
        
        return msg


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
        self.last_nn = None
        self.last_msg = None

        # root of msg tree
        self._msg_root = _MsgTreeElem()
        # dict of nodes to msg tree elem
        self._d_msg_nodes = {}
        # dict of nodes to retcode
        self._d_rc_nodes = {}
        # dict of retcode to NodeSet
        self._d_rc = {}

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
                    self.nodes, \
                    self.command)
            #print "PDSH : %s" % cmd
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
                            self.set_node_rc(words[1][:-1], int(words[7]))
                        elif self.mode == 'pdcp':
                            self.set_node_rc(words[1][:-1], errno.ENOENT)

                    except:
                        print "exception in pdsh@"
                        raise
                else:
                    #        
                    # split pdsh reply "nodename: msg"
                    nodename, msgline = line.split(': ', 1)
                    self.add_node_msgline(nodename, msgline)
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

    def add_node_msgline(self, nodename, msg):
        """
        Update last_* and add node message line to messages tree.
        """
        self.last_nn, self.last_msg = nodename, msg[:-1]

        # try first to get current element in msgs tree
        e_msg = self._d_msg_nodes.get(nodename)
        if not e_msg:
            # node not found (first msg from it)
            e_msg = self._msg_root

        # add child msg and update dict
        self._d_msg_nodes[nodename] = e_msg.add_child(msg, nodename)

    def set_node_rc(self, nodename, rc):
        # dict by nodename
        self._d_rc_node[nodename] = rc

        # dict by rc
        e = self._d_rc.get(rc)
        if e is None:
            self._d_rc[rc] = NodeSet(nodename)
        else:
            self._d_rc[rc].add(nodename)

    def read_node_buffer(self, nodename):
        e_msg = self._d_msg_nodes.get(nodename)
        if not e_msg:
            return ""
        
        return e_msg.message()

    def get_node_rc(self, nodename):
        try:
            return self._d_rc_nodes[nodename]
        except:
            # XXX
            raise

    def iterbuffers(self):
        """
        Iterate over (NodeSet, buffer).
        Use this iterator to get worker result buffers.
        """
        for e in self._msg_root.get_leaves():
            yield e.nodes, e.message()

    def iterbuffers_by_node(self):
        """
        Iterate over (nodename, buffer).
        Use this iterator to get worker result buffers.
        """
        for n, e in self._d_msg_nodes.iteritems():
            yield n, e.message()

    def iterretcode(self):
        for rc, nodeset in self._d_rc.iteritems():
            yield nodeset, rc

    def iterretcode_by_node(self):
        for nodename, rc in self._d_rc_nodes.iteritems():
            yield nodename, rc

    def nodes_cs(self):
        result = ""
        for n in self.nodes:
            result += "%s," % n
        return result[:-1]

