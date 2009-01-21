# WorkerPdsh.py -- ClusterShell pdsh worker with poll()
# Copyright (C) 2007, 2008, 2009 CEA
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
WorkerPdsh

ClusterShell worker
"""

from ClusterShell.NodeSet import NodeSet
from Worker import Worker

import errno
import fcntl
import os
import popen2
import signal


class WorkerPdsh(Worker):

    def __init__(self, nodes, handler, timeout, task, **kwargs):
        """
        Initialize Pdsh worker instance.
        """
        Worker.__init__(self, handler, timeout, task)
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
        self.last_node = None
        self.last_msg = None

    def _start(self):
        """
        Start worker, initialize buffers, prepare command.
        """
        # Initialize worker read buffer
        self._buf = ""

        self._invoke("ev_start")

        if self.command is not None:
            # Build pdsh command
            cmd_l = [ "/usr/bin/pdsh", "-b" ]

            fanout = self._task.info("fanout", 0)
            if fanout > 0:
                cmd_l.append("-f %d" % fanout)

            connect_timeout = self._task.info("connect_timeout", 0)
            if connect_timeout > 0:
                cmd_l.append("-t %d" % connect_timeout)

            command_timeout = self._task.info("command_timeout", 0)
            if command_timeout > 0:
                cmd_l.append("-u %d" % command_timeout)

            cmd_l.append("-w '%s'" % self.nodes)
            cmd_l.append("'%s'" % self.command)

            cmd = ' '.join(cmd_l)

            if self._task.info("debug", False):
                print "PDSH: %s" % cmd
        else:
            # Build pdcp command
            cmd_l = [ "/usr/bin/pdcp", "-b" ]

            fanout = self._task.info("fanout", 0)
            if fanout > 0:
                cmd_l.append("-f %d" % fanout)

            connect_timeout = self._task.info("connect_timeout", 0)
            if connect_timeout > 0:
                cmd_l.append("-t %d" % connect_timeout)

            cmd_l.append("-w '%s'" % self.nodes)

            cmd_l.append("'%s'" % self.source)
            cmd_l.append("'%s'" % self.dest)
            cmd = ' '.join(cmd_l)

            if self._task.info("debug", False):
                print "PDCP: %s" % cmd
        try:
            # Launch process in non-blocking mode
            self.fid = popen2.Popen4(cmd)
            fl = fcntl.fcntl(self.fid.fromchild, fcntl.F_GETFL)
            fcntl.fcntl(self.fid.fromchild, fcntl.F_SETFL, os.O_NDELAY)
        except OSError, e:
            raise e
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
        # rc code default to 0 for all nodes
        for nodename in self.nodes:
            self.engine.set_rc((self, nodename), 0, override=False)

        if force or timeout:
            status = self.fid.poll()
            if status == -1:
                # process is still running, kill it
                os.kill(self.fid.pid, signal.SIGKILL)
            if timeout:
                self._invoke("ev_timeout")
        else:
            self.fid.wait()

        # close
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

        buf = self._buf + readbuf
        lines = buf.splitlines(True)
        self._buf = ""
        for line in lines:
            if debug:
                print "LINE: %s" % line,
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
                            if len(words) == 4 and words[2] == "command" and \
                                words[3] == "timeout":
                                    pass
                            elif len(words) == 8 and words[3] == "exited" and words[7].isdigit():
                                self._set_node_rc(words[1][:-1], int(words[7]))
                        elif self.mode == 'pdcp':
                            self._set_node_rc(words[1][:-1], errno.ENOENT)

                    except:
                        raise WorkerError()
                else:
                    #        
                    # split pdsh reply "nodename: msg"
                    nodename, msgline = line.split(': ', 1)
                    self._add_node_msgline(nodename, msgline)
                    self._invoke("ev_read")
            else:
                # keep partial line in buffer
                self._buf = line
                # will break here
        return True

    def _add_node_msgline(self, nodename, msg):
        """
        Update last_* and add node message line to messages tree.
        """
        self.last_node, self.last_msg = nodename, msg[:-1]

        self.engine.add_msg((self, nodename), msg)

    def _set_node_rc(self, nodename, rc):
        """
        Set node specific return code.
        """
        self.engine.set_rc((self, nodename), rc)

    def last_read(self):
        """
        Get last (node, buffer) in an EventHandler.
        """
        return self.last_node, self.last_msg

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
        Returns an iterator over available buffers and associated
        NodeSet.
        """
        for msg, keys in self.engine.iter_messages_by_worker(self):
            yield msg, NodeSet.fromlist(keys)

    def iter_node_buffers(self):
        """
        Returns an iterator over each node and associated buffer.
        """
        # Get iterator from underlying engine.
        return self.engine.iter_key_messages_by_worker(self)

    def iter_retcodes(self):
        """
        Returns an iterator over return codes and associated NodeSet.
        """
        for rc, keys in self.engine.iter_retcodes_by_worker(self):
            yield rc, NodeSet.fromlist(keys)

    def iter_node_retcodes(self):
        """
        Returns an iterator over each node and associated return code.
        """
        # Get iterator from underlying engine.
        return self.engine.iter_key_retcodes_by_worker(self)

