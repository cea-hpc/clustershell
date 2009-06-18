# WorkerPdsh.py -- ClusterShell pdsh worker
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

ClusterShell worker based on pdsh
"""

from ClusterShell.NodeSet import NodeSet

from EngineClient import *
from Worker import DistantWorker, WorkerError

import errno
import fcntl
import os
import popen2
import signal


class WorkerPdsh(EngineClient,DistantWorker):
    """
    ClusterShell pdsh-based worker Class.

    Remote Shell (pdsh) usage example:
        worker = WorkerPdsh(nodeset, handler=MyEventHandler(),
                        timeout=30, command="/bin/hostname")
    Remote Copy (pdcp) usage example: 
        worker = WorkerPdsh(nodeset, handler=MyEventHandler(),
                        timeout=30, source="/etc/my.conf",
                        dest="/etc/my.conf")
        ...
        task.schedule(worker)   # schedule worker for execution
        ...
        task.resume()           # run

    Known Limitations:
        * write() is not supported by WorkerPdsh
        * return codes == 0 are not garanteed when a timeout is used (rc > 0
          are fine)
    """

    def __init__(self, nodes, handler, timeout, **kwargs):
        """
        Initialize Pdsh worker instance.
        """
        DistantWorker.__init__(self, handler)
        EngineClient.__init__(self, self, timeout, kwargs.get('autoclose', False))

        self.nodes = NodeSet(nodes)
        self.closed_nodes = NodeSet()

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

    def _engine_clients(self):
        return [self]

    def _start(self):
        """
        Start worker, initialize buffers, prepare command.
        """
        # Initialize worker read buffer
        self._buf = ""

        if self.command is not None:
            # Build pdsh command
            cmd_l = [ self.task.info("pdsh_path") or "pdsh", "-b" ]

            fanout = self.task.info("fanout", 0)
            if fanout > 0:
                cmd_l.append("-f %d" % fanout)

            # Pdsh flag '-t' do not really works well. Better to use
            # PDSH_SSH_ARGS_APPEND variable to transmit ssh ConnectTimeout
            # flag.
            connect_timeout = self.task.info("connect_timeout", 0)
            if connect_timeout > 0:
                cmd_l.insert(0, 
                    "PDSH_SSH_ARGS_APPEND=\"-o ConnectTimeout=%d\"" %
                    connect_timeout)

            command_timeout = self.task.info("command_timeout", 0)
            if command_timeout > 0:
                cmd_l.append("-u %d" % command_timeout)

            cmd_l.append("-w '%s'" % self.nodes)
            cmd_l.append("'%s'" % self.command)

            cmd = ' '.join(cmd_l)

            if self.task.info("debug", False):
                self.task.info("print_debug")(self.task, "PDSH: %s" % cmd)
        else:
            # Build pdcp command
            cmd_l = [ self.task.info("pdcp_path") or "pdcp", "-b" ]

            fanout = self.task.info("fanout", 0)
            if fanout > 0:
                cmd_l.append("-f %d" % fanout)

            connect_timeout = self.task.info("connect_timeout", 0)
            if connect_timeout > 0:
                cmd_l.append("-t %d" % connect_timeout)

            cmd_l.append("-w '%s'" % self.nodes)

            cmd_l.append("'%s'" % self.source)
            cmd_l.append("'%s'" % self.dest)
            cmd = ' '.join(cmd_l)

            if self.task.info("debug", False):
                self.task.info("print_debug")(self.task,"PDCP: %s" % cmd)

        self.fid = self._exec_nonblock(cmd)

        self._on_start()

        return self

    def reader_fileno(self):
        """
        Return the reader file descriptor as an integer.
        """
        return self.fid.fromchild.fileno()
    
    def writer_fileno(self):
        """
        Return the writer file descriptor as an integer.
        """
        return self.fid.tochild.fileno()

    def _read(self, size=-1):
        """
        Read data from process.
        """
        result = self.fid.fromchild.read(size)
        if result > 0:
            self._set_reading()
        return result

    def write(self, buf):
        """
        Write data to process. Not supported with Pdsh worker.
        """
        raise EngineClientNotSupportedError("writing is not supported by pdsh worker")

    def _close(self, force, timeout):
        """
        Close worker. Called by engine after worker has been
        unregistered. This method should handle all termination types
        (normal, forced or on timeout).
        """
        if force or timeout:
            status = self.fid.poll()
            if status == -1:
                # process is still running, kill it
                os.kill(self.fid.pid, signal.SIGKILL)
            if timeout:
                self._invoke("ev_timeout")
        else:
            status = self.fid.wait()
            if os.WIFEXITED(status):
                rc = os.WEXITSTATUS(status)
                if rc != 0:
                    raise WorkerError("Cannot run pdsh (error %d)" % rc)

        # close
        self.fid.tochild.close()
        self.fid.fromchild.close()

        if timeout:
            for node in (self.nodes - self.closed_nodes):
                self._on_node_timeout(node)
        else:
            for node in (self.nodes - self.closed_nodes):
                self._on_node_rc(node, 0)

        self._invoke("ev_close")

    def _handle_read(self):
        """
        Engine is telling us a read is available.
        """
        debug = self.task.info("debug", False)
        if debug:
            print_debug = self.task.info("print_debug")

        # read a chunk
        readbuf = self._read()
        assert len(readbuf) > 0, "_handle_read() called with no data to read"

        buf = self._buf + readbuf
        lines = buf.splitlines(True)
        self._buf = ""
        for line in lines:
            if debug:
                print_debug(self.task, "LINE: %s" % line[:-1])
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
                                self._on_node_rc(words[1][:-1], int(words[7]))
                        elif self.mode == 'pdcp':
                            self._on_node_rc(words[1][:-1], errno.ENOENT)

                    except Exception, e:
                        print >>sys.stderr, e
                        raise EngineClientError()
                else:
                    #        
                    # split pdsh reply "nodename: msg"
                    nodename, msg = line.split(': ', 1)
                    if msg.endswith('\n'):
                        if msg.endswith('\r\n'):
                            msgline = msg[:-2] # trim CRLF
                        else:
                            msgline = msg[:-1] # trim LF
                    self._on_node_msgline(nodename, msgline)
            else:
                # keep partial line in buffer
                self._buf = line

    def _on_node_rc(self, node, rc):
        """
        Return code received from a node, update last* stuffs.
        """
        DistantWorker._on_node_rc(self, node, rc)
        self.closed_nodes.add(node)

