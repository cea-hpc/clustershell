#
# Copyright (C) 2014-2015 CEA/DAM
# Copyright (C) 2014-2015 Aurelien Degremont <aurelien.degremont@cea.fr>
# Copyright (C) 2014-2017 Stephane Thiell <sthiell@stanford.edu>
#
# This file is part of ClusterShell.
#
# ClusterShell is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# ClusterShell is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with ClusterShell; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

"""
ClusterShell base worker for process-based workers.

This module manages the worker class to spawn local commands, possibly using
a nodeset to behave like a distant worker. Like other workers it can run
commands or copy files, locally.

This is the base class for most of other distant workers.
"""

import os
from string import Template

from ClusterShell.NodeSet import NodeSet
from ClusterShell.Worker.EngineClient import EngineClient
from ClusterShell.Worker.Worker import WorkerError, DistantWorker
from ClusterShell.Worker.Worker import _eh_sigspec_invoke_compat


def _replace_cmd(pattern, node, rank):
    """
    Replace keywords in `pattern' with value from `node' and `rank'.

    %h, %host map `node'
    %n, %rank map `rank'
    """
    variables = {
        'h':     node,
        'host':  node,
        'hosts': node,
        'n':     rank or 0,
        'rank':  rank or 0,
    #    'u': None,
    }
    class Replacer(Template):
        delimiter = '%'
    try:
        cmd = Replacer(pattern).substitute(variables)
    except (KeyError, ValueError) as error:
        msg = "%s is not a valid pattern, use '%%%%' to escape '%%'" % error
        raise WorkerError(msg)
    return cmd

class ExecClient(EngineClient):
    """
    Run a simple local command.

    Useful as a superclass for other more specific workers.
    """

    def __init__(self, node, command, worker, stderr, timeout, autoclose=False,
                 rank=None):
        """
        Create an EngineClient-type instance to locally run `command'.

        :param node: will be used as key.
        """
        EngineClient.__init__(self, worker, node, stderr, timeout, autoclose)
        self.rank = rank
        self.command = command
        self.popen = None
        # Declare writer stream to allow early buffering
        self.streams.set_writer(worker.SNAME_STDIN, None, retain=True)

    def _build_cmd(self):
        """
        Build the shell command line to start the commmand.

        Return a tuple containing command and arguments as a string or a list
        of string, and a dict of additional environment variables. None could
        be returned if no environment change is required.
        """
        return (_replace_cmd(self.command, self.key, self.rank), None)

    def _start(self):
        """Prepare command and start client."""

        # Build command
        cmd, cmd_env = self._build_cmd()

        # If command line is string, we need to interpret it as a shell command
        shell = isinstance(cmd, str)

        task = self.worker.task
        if task.info("debug", False):
            name = self.__class__.__name__.upper().split('.')[-1]
            if shell:
                task.info("print_debug")(task, "%s: %s" % (name, cmd))
            else:
                task.info("print_debug")(task, "%s: %s" % (name, ' '.join(cmd)))

        self.popen = self._exec_nonblock(cmd, env=cmd_env, shell=shell)
        self._on_nodeset_start(self.key)
        return self

    def _close(self, abort, timeout):
        """Close client. See EngineClient._close()."""
        if abort:
            # it's safer to call poll() first for long time completed processes
            prc = self.popen.poll()
            # if prc is None, process is still running
            if prc is None:
                try: # try to kill it
                    self.popen.kill()
                except OSError:
                    pass
        prc = self.popen.wait()

        self.streams.clear()
        self.invalidate()

        if prc >= 0:
            self._on_nodeset_close(self.key, prc)
        elif timeout:
            assert abort, "abort flag not set on timeout"
            self.worker._on_node_timeout(self.key)
        elif not abort:
            # if process was signaled, return 128 + signum (bash-like)
            self._on_nodeset_close(self.key, 128 + -prc)

        self.worker._check_fini()

    def _on_nodeset_start(self, nodes):
        """local wrapper over _on_start that can also handle nodeset"""
        if isinstance(nodes, NodeSet):
            for node in nodes:
                self.worker._on_start(node)
        else:
            self.worker._on_start(nodes)

    def _on_nodeset_close(self, nodes, rc):
        """local wrapper over _on_node_rc that can also handle nodeset"""
        if isinstance(nodes, NodeSet):
            for node in nodes:
                self.worker._on_node_close(node, rc)
        else:
            self.worker._on_node_close(nodes, rc)

    def _on_nodeset_msgline(self, nodes, msg, sname):
        """local wrapper over _on_node_msgline that can also handle nodeset"""
        if isinstance(nodes, NodeSet):
            for node in nodes:
                self.worker._on_node_msgline(node, msg, sname)
        else:
            self.worker._on_node_msgline(nodes, msg, sname)

    def _flush_read(self, sname):
        """Called at close time to flush stream read buffer."""
        stream = self.streams[sname]
        if stream.readable() and stream.rbuf:
            # We still have some read data available in buffer, but no
            # EOL. Generate a final message before closing.
            self._on_nodeset_msgline(self.key, stream.rbuf, sname)

    def _handle_read(self, sname):
        """
        Handle a read notification. Called by the engine as the result of an
        event indicating that a read is available.
        """
        # Local variables optimization
        worker = self.worker
        task = worker.task
        key = self.key
        node_msgline = self._on_nodeset_msgline
        debug = task.info("debug", False)
        if debug:
            print_debug = task.info("print_debug")
        for msg in self._readlines(sname):
            if debug:
                print_debug(task, "%s: %s" % (key, msg))
            node_msgline(key, msg, sname)  # handle full msg line

class CopyClient(ExecClient):
    """
    Run a local `cp' between a source and destination.

    Destination could be a directory.
    """

    def __init__(self, node, source, dest, worker, stderr, timeout, autoclose,
                 preserve, reverse, rank=None):
        """Create an EngineClient-type instance to locally run 'cp'."""
        ExecClient.__init__(self, node, None, worker, stderr, timeout,
                            autoclose, rank)
        self.source = source
        self.dest = dest

        # Preserve modification times and modes?
        self.preserve = preserve

        # Reverse copy?
        self.reverse = reverse

        # Directory?
        # FIXME: file sanity checks could be moved to Copy._start() as we
        # should now be able to handle error when starting (#215).
        if self.reverse:
            self.isdir = os.path.isdir(self.dest)
            if not self.isdir:
                raise ValueError("reverse copy dest must be a directory")
        else:
            self.isdir = os.path.isdir(self.source)

    def _build_cmd(self):
        """
        Build the shell command line to start the rcp commmand.
        Return an array of command and arguments.
        """
        source = _replace_cmd(self.source, self.key, self.rank)
        dest = _replace_cmd(self.dest, self.key, self.rank)

        cmd_l = [ "cp" ]

        if self.isdir:
            cmd_l.append("-r")

        if self.preserve:
            cmd_l.append("-p")

        if self.reverse:
            cmd_l.append(dest)
            cmd_l.append(source)
        else:
            cmd_l.append(source)
            cmd_l.append(dest)

        return (cmd_l, None)


class ExecWorker(DistantWorker):
    """
    ClusterShell simple execution worker Class.

    It runs commands locally. If a node list is provided, one command will be
    launched for each node and specific keywords will be replaced based on node
    name and rank.

    Local shell usage example:

       >>> worker = ExecWorker(nodeset, handler=MyEventHandler(),
       ...                     timeout=30, command="/bin/uptime")
       >>> task.schedule(worker)   # schedule worker for execution
       >>> task.run()              # run

    Local copy usage example:

       >>> worker = ExecWorker(nodeset, handler=MyEventHandler(),
       ...                     source="/etc/my.cnf",
       ...                     dest="/etc/my.cnf.bak")
       >>> task.schedule(worker)      # schedule worker for execution
       >>> task.run()                 # run

    connect_timeout option is ignored by this worker.
    """

    SHELL_CLASS = ExecClient
    COPY_CLASS = CopyClient

    def __init__(self, nodes, handler, timeout=None, **kwargs):
        """Create an ExecWorker and its engine client instances."""
        DistantWorker.__init__(self, handler)
        self._close_count = 0
        self._has_timeout = False
        self._clients = []

        self.nodes = NodeSet(nodes)
        self.command = kwargs.get('command')
        self.source = kwargs.get('source')
        self.dest = kwargs.get('dest')

        self._create_clients(timeout=timeout, **kwargs)

    #
    # Spawn and manage EngineClient classes
    #

    def _create_clients(self, **kwargs):
        """
        Create several shell and copy engine client instances based on worker
        properties.

        Additional arguments in `kwargs' will be used for client creation.
        There will be one client per node in self.nodes
        """
        # do not iterate if special %hosts placeholder is found in command
        if self.command and ('%hosts' in self.command or
                             '%{hosts}' in self.command):
            self._add_client(self.nodes, rank=None, **kwargs)
        else:
            for rank, node in enumerate(self.nodes):
                self._add_client(node, rank=rank, **kwargs)

    def _add_client(self, nodes, **kwargs):
        """Create one shell or copy client."""
        autoclose = kwargs.get('autoclose', False)
        stderr = kwargs.get('stderr', False)
        rank = kwargs.get('rank')
        timeout = kwargs.get('timeout')

        if self.command is not None:
            cls = self.__class__.SHELL_CLASS
            self._clients.append(cls(nodes, self.command, self, stderr,
                                     timeout, autoclose, rank))
        elif self.source:
            cls = self.__class__.COPY_CLASS
            self._clients.append(cls(nodes, self.source, self.dest, self,
                                     stderr, timeout, autoclose,
                                     kwargs.get('preserve', False),
                                     kwargs.get('reverse', False), rank))
        else:
            raise ValueError("missing command or source parameter in "
                             "worker constructor")

    def _engine_clients(self):
        """
        Used by upper layer to get the list of underlying created engine
        clients.
        """
        return self._clients

    def write(self, buf, sname=None):
        """Write to worker clients."""
        sname = sname or self.SNAME_STDIN
        for client in self._clients:
            if sname in client.streams:
                client._write(sname, buf)

    def set_write_eof(self, sname=None):
        """
        Tell worker to close its writer file descriptors once flushed. Do not
        perform writes after this call.
        """
        for client in self._clients:
            client._set_write_eof(sname or self.SNAME_STDIN)

    def abort(self):
        """Abort processing any action by this worker."""
        for client in self._clients:
            client.abort()

    #
    # Events
    #

    def _on_node_timeout(self, node):
        DistantWorker._on_node_timeout(self, node)
        self._has_timeout = True

    def _check_fini(self):
        """
        Must be called by each client when closing.

        If they are all closed, trigger the required events.
        """
        self._close_count += 1
        assert self._close_count <= len(self._clients)
        if self._close_count == len(self._clients) and self.eh is not None:
            # also use hasattr check because ev_timeout was missing in 1.8.0
            if self._has_timeout and hasattr(self.eh, 'ev_timeout'):
                # Legacy ev_timeout event
                self.eh.ev_timeout(self)
            _eh_sigspec_invoke_compat(self.eh.ev_close, 2, self,
                                      self._has_timeout)


WORKER_CLASS = ExecWorker
