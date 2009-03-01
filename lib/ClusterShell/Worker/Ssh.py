# WorkerSsh.py -- ClusterShell ssh worker
# Copyright (C) 2008, 2009 CEA
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
ClusterShell Ssh/Scp support

This module implements OpenSSH engine client and task's worker.
"""

from ClusterShell.NodeSet import NodeSet
from EngineClient import EngineClient
from Worker import DistantWorker

import copy
import errno
import os
import signal


class Ssh(EngineClient):
    """
    Ssh EngineClient.
    """

    def __init__(self, node, command, timeout, worker):
        """
        Initialize Ssh EngineClient instance.
        """
        EngineClient.__init__(self, timeout, worker)

        self.key = copy.copy(node)
        self.command = command
        self.fid = None
        self.sendbuf = ""

    def _start(self):
        """
        Start worker, initialize buffers, prepare command.
        """
        task = self.worker.task

        # Initialize worker read buffer
        self._buf = ""

        # Build ssh command
        cmd_l = [ "ssh", "-a", "-x" ]

        user = task.info("ssh_user")
        if user:
            cmd_l.append("-l %s" % user)

        connect_timeout = task.info("connect_timeout", 0)
        if connect_timeout > 0:
            cmd_l.append("-oConnectTimeout=%d" % connect_timeout)

        cmd_l.append("%s" % self.key)
        cmd_l.append("'%s'" % self.command)

        cmd = ' '.join(cmd_l)

        if task.info("debug", False):
            task.info("print_debug")(task, "SSH: %s" % cmd)

        self.fid = self._exec_nonblock(cmd)

        self.worker._on_start()

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
        Write data to process.
        """
        result = os.write(self.writer_fileno(), buf)
        # XXX check result
        #print "Ssh write result=%s" % result
        self._set_writing()
    
    def _close(self, force, timeout):
        """
        Close client. Called by engine after the client has been
        unregistered. This method should handle all termination types
        (normal, forced or on timeout).
        """
        rc = -1
        if force or timeout:
            status = self.fid.poll()
            if status == -1:
                # process is still running, kill it
                os.kill(self.fid.pid, signal.SIGKILL)
        else:
            status = self.fid.wait()
            if os.WIFEXITED(status):
                rc = os.WEXITSTATUS(status)

        self.fid.tochild.close()
        self.fid.fromchild.close()

        if rc >= 0:
            self.worker._on_node_rc(self.key, rc)
        elif timeout:
            self.worker._on_node_timeout(self.key)

        self.worker._check_fini()

    def _handle_read(self):
        """
        Handle a read notification. Called by the engine as the result of an
        event indicating that a read is available.
        """
        debug = self.worker.task.info("debug", False)
        if debug:
            print_debug = self.worker.task.info("print_debug")

        # read a chunk of data
        readbuf = self._read()
        assert len(readbuf) > 0, "_handle_read() called with no data to read"

        # Current version of this worker implements line-buffered reads.
        # If needed, we could easily provide direct, non-buffered, data
        # reads in the future.

        buf = self._buf + readbuf
        lines = buf.splitlines(True)
        self._buf = ""
        for line in lines:
            if line.endswith('\n'):
                if line.endswith('\r\n'):
                    msg = line[:-2] # trim CRLF
                else:
                    # trim LF
                    msg = line[:-1] # trim LF
                if debug:
                    print_debug(self.worker.task, "%s: %s" % (self.key, msg))
                # full line
                self.worker._on_node_msgline(self.key, msg)
            else:
                # keep partial line in buffer
                self._buf = line
                # will break here

    def _handle_write(self):
        """
        Handle a write notification. Called by the engine as the result of an
        event indicating that a write can be performed now.
        """
        if len(self.sendbuf) > 0:
            # XXX writing is still experimental!
            #print "writing %s" % self.sendbuf
            self.fid.tochild.write(self.sendbuf)
            self.fid.tochild.flush()
            self.sendbuf = ""
            self._set_writing()


class Scp(Ssh):
    """
    Scp EngineClient.
    """

    def __init__(self, node, source, dest, timeout, worker):
        """
        Initialize Scp instance.
        """
        Ssh.__init__(self, node, None, timeout, worker)
        self.source = source
        self.dest = dest

    def _start(self):
        """
        Start worker, initialize buffers, prepare command.
        """
        task = self.worker.task

        # Initialize worker read buffer
        self._buf = ""

        # Build scp command
        cmd_l = [ "scp" ]

        connect_timeout = task.info("connect_timeout", 0)
        if connect_timeout > 0:
            cmd_l.append("-oConnectTimeout=%d" % connect_timeout)

        cmd_l.append("'%s'" % self.source)

        user = task.info("ssh_user")
        if user:
            cmd_l.append("%s@%s:%s" % (user, self.key, self.dest))
        else:
            cmd_l.append("'%s:%s'" % (self.key, self.dest))
        cmd = ' '.join(cmd_l)

        if task.info("debug", False):
            task.info("print_debug")(task, "SCP: %s" % cmd)

        self.fid = self._exec_nonblock(cmd)

        return self


class WorkerSsh(DistantWorker):
    """
    ClusterShell ssh-based worker Class.

    Remote Shell (ssh) usage example:
        worker = WorkerSsh(nodeset, handler=MyEventHandler(),
                        timeout=30, command="/bin/hostname")
    Remote Copy (scp) usage example: 
        worker = WorkerSsh(nodeset, handler=MyEventHandler(),
                        timeout=30, source="/etc/my.conf",
                        dest="/etc/my.conf")
        ...
        task.schedule(worker)   # schedule worker for execution
        ...
        task.resume()           # run
    """

    def __init__(self, nodes, handler, timeout, **kwargs):
        """
        Initialize Ssh worker instance.
        """
        DistantWorker.__init__(self, handler)

        self.clients = []
        self.nodes = NodeSet(nodes)
        self._close_count = 0
        self._has_timeout = False

        # Prepare underlying engine clients (ssh/scp processes)
        if kwargs.has_key('command'):
            # secure remote shell
            for node in self.nodes:
                self.clients.append(Ssh(node, kwargs['command'], timeout, self))
        elif kwargs.has_key('source'):
            # secure copy
            for node in self.nodes:
                self.clients.append(Scp(node, kwargs['source'],
                    kwargs['dest'], timeout, self))
        else:
            raise WorkerBadArgumentException()

    def _engine_clients(self):
        """
        Access underlying engine clients.
        """
        return self.clients

    def _on_node_rc(self, node, rc):
        DistantWorker._on_node_rc(self, node, rc)
        self._close_count += 1

    def _on_node_timeout(self, node):
        DistantWorker._on_node_timeout(self, node)
        self._close_count += 1
        self._has_timeout = True

    def _check_fini(self):
        if self._close_count >= len(self.clients):
            if self._has_timeout:
                self._invoke("ev_timeout")
            self._invoke("ev_close")


