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

from EngineClient import EngineClient, EngineClientEOF
from Worker import DistantWorker

from ClusterShell.NodeSet import NodeSet

import copy
import errno
import os
import signal


class Ssh(EngineClient):
    """
    Ssh EngineClient.
    """

    def __init__(self, node, command, worker, timeout, autoclose=False):
        """
        Initialize Ssh EngineClient instance.
        """
        EngineClient.__init__(self, worker, timeout, autoclose)

        self.key = copy.copy(node)
        self.command = command
        self.fid = None
        self.file_reader = None
        self.file_writer = None

    def _start(self):
        """
        Start worker, initialize buffers, prepare command.
        """
        task = self.worker.task

        # Build ssh command
        cmd_l = [ "ssh", "-a", "-x" ]

        user = task.info("ssh_user")
        if user:
            cmd_l.append("-l %s" % user)

        connect_timeout = task.info("connect_timeout", 0)
        if connect_timeout > 0:
            cmd_l.append("-oConnectTimeout=%d" % connect_timeout)

        # Disable passphrase/password querying
        cmd_l.append("-oBatchMode=yes")

        cmd_l.append("%s" % self.key)
        cmd_l.append("'%s'" % self.command)

        cmd = ' '.join(cmd_l)

        if task.info("debug", False):
            task.info("print_debug")(task, "SSH: %s" % cmd)

        self.fid = self._exec_nonblock(cmd)
        self.file_reader = self.fid.fromchild
        self.file_writer = self.fid.tochild

        self.worker._on_start()

        return self

    def reader_fileno(self):
        """
        Return the reader file descriptor as an integer.
        """
        if self.file_reader:
            return self.file_reader.fileno()
        return None
    
    def writer_fileno(self):
        """
        Return the writer file descriptor as an integer.
        """
        if self.file_writer:
            return self.file_writer.fileno()
        return None

    def _read(self, size=-1):
        """
        Read data from process.
        """
        result = self.file_reader.read(size)
        if not len(result):
            raise EngineClientEOF()
        self._set_reading()
        return result

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

        for msg in self._readlines():
            if debug:
                print_debug(self.worker.task, "%s: %s" % (self.key, msg))
            # handle full msg line
            self.worker._on_node_msgline(self.key, msg)


class Scp(Ssh):
    """
    Scp EngineClient.
    """

    def __init__(self, node, source, dest, worker, timeout):
        """
        Initialize Scp instance.
        """
        Ssh.__init__(self, node, None, worker, timeout)
        self.source = source
        self.dest = dest
        self.fid = None
        self.file_reader = None
        self.file_writer = None

    def _start(self):
        """
        Start worker, initialize buffers, prepare command.
        """
        task = self.worker.task

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
        self.file_reader = self.fid.fromchild
        self.file_writer = self.fid.tochild

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

        autoclose = kwargs.get('autoclose', False)

        # Prepare underlying engine clients (ssh/scp processes)
        if kwargs.has_key('command'):
            # secure remote shell
            for node in self.nodes:
                self.clients.append(Ssh(node, kwargs['command'], self,
                    timeout,autoclose))
        elif kwargs.has_key('source'):
            # secure copy
            for node in self.nodes:
                self.clients.append(Scp(node, kwargs['source'], kwargs['dest'],
                    self, timeout))
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

    def write(self, buf):
        """
        Write to worker clients.
        """
        for c in self.clients:
            c._write(buf)

    def set_write_eof(self):
        """
        Tell worker to close its writer file descriptor once flushed. Do not
        perform writes after this call.
        """
        for c in self.clients:
            c._set_write_eof()

