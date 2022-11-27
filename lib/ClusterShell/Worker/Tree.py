#
# Copyright (C) 2011-2016 CEA/DAM
# Copyright (C) 2015-2017 Stephane Thiell <sthiell@stanford.edu>
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
# This file is part of the ClusterShell library.

"""
ClusterShell tree propagation worker
"""

import base64
import logging
import os
from os.path import basename, dirname, isfile, normpath
import sys
import tarfile
import tempfile

from ClusterShell.Event import EventHandler
from ClusterShell.NodeSet import NodeSet
from ClusterShell.Worker.EngineClient import EnginePort
from ClusterShell.Worker.Worker import DistantWorker, WorkerError
from ClusterShell.Worker.Worker import _eh_sigspec_invoke_compat
from ClusterShell.Worker.Exec import ExecWorker

from ClusterShell.Propagation import PropagationTreeRouter


class MetaWorkerEventHandler(EventHandler):
    """Handle events for the meta worker TreeWorker"""

    def __init__(self, metaworker):
        self.metaworker = metaworker
        self.logger = logging.getLogger(__name__)

    def ev_start(self, worker):
        """
        Called to indicate that a worker has just started.
        """
        self.logger.debug("MetaWorkerEventHandler: ev_start")
        self.metaworker._start_count += 1

    def ev_read(self, worker, node, sname, msg):
        """
        Called to indicate that a worker has data to read.
        """
        self.metaworker._on_node_msgline(node, msg, sname)

    def ev_written(self, worker, node, sname, size):
        """
        Called to indicate that writing has been done.
        """
        metaworker = self.metaworker
        metaworker.current_node = node
        metaworker.current_sname = sname
        if metaworker.eh:
            metaworker.eh.ev_written(metaworker, node, sname, size)

    def ev_hup(self, worker, node, rc):
        """
        Called to indicate that a worker's connection has been closed.
        """
        self.metaworker._on_node_close(node, rc)

    def ev_close(self, worker, timedout):
        """
        Called to indicate that a worker has just finished. It may have failed
        on timeout if timedout is set.
        """
        self.logger.debug("MetaWorkerEventHandler: ev_close, timedout=%s",
                          timedout)
        if timedout:
            # WARNING!!! this is not possible as metaworker is changing task's
            # shared timeout set!
            #for node in worker.iter_keys_timeout():
            #    self.metaworker._on_node_timeout(node)
            # we use NodeSet to copy set
            for node in NodeSet._fromlist1(worker.iter_keys_timeout()):
                self.metaworker._on_node_timeout(node)
        self.metaworker._check_fini()


class TreeWorker(DistantWorker):
    """
    ClusterShell tree worker Class.

    """
    # copy and rcopy tar command formats
    # the choice of single or double quotes is essential
    UNTAR_CMD_FMT = "tar -xf - -C '%s'"
    TAR_CMD_FMT = "tar -cf - -C '%s' " \
                  "--transform \"s,^\\([^/]*\\)[/]*,\\1.$(hostname -s)/,\" " \
                  "'%s' | base64 -w 65536"

    class _IOPortHandler(EventHandler):
        """
        Special control port event handler used for:
        * start the TreeWorker when the engine starts
        * early write handling: write buffering and eof tracking
        """
        def __init__(self, treeworker):
            EventHandler.__init__(self)
            self.treeworker = treeworker

        def ev_port_start(self, port):
            """Event when port is registered."""
            self.treeworker._start()

        def ev_msg(self, port, msg):
            """
            Message received: call appropriate worker method.
            Used for TreeWorker.write() and set_write_eof().
            """
            func, args = msg[0], msg[1:]
            func(self.treeworker, *args)

    def __init__(self, nodes, handler, timeout, **kwargs):
        """
        Initialize Tree worker instance.

        :param nodes: Targeted nodeset.
        :param handler: Worker EventHandler.
        :param timeout: Timeout value for worker.
        :param command: Command to execute.
        :param topology: Force specific TopologyTree.
        :param newroot: Root node of TopologyTree.
        """
        DistantWorker.__init__(self, handler)

        self.logger = logging.getLogger(__name__)
        self.workers = []
        self.nodes = NodeSet(nodes)
        self.timeout = timeout
        self.command = kwargs.get('command')
        self.source = kwargs.get('source')
        self.dest = kwargs.get('dest')
        autoclose = kwargs.get('autoclose', False)
        self.stderr = kwargs.get('stderr', False)
        self.logger.debug("stderr=%s", self.stderr)
        self.remote = kwargs.get('remote', True)
        self.preserve = kwargs.get('preserve', None)
        self.reverse = kwargs.get('reverse', False)
        self._rcopy_bufs = {}
        self._rcopy_tars = {}
        self._close_count = 0
        self._start_count = 0
        self._child_count = 0
        self._target_count = 0
        self._has_timeout = False
        self._started = False

        if self.command is None and self.source is None:
            raise ValueError("missing command or source parameter in "
                             "TreeWorker constructor")

        # rcopy is enforcing separated stderr to handle tar error messages
        # because stdout is used for data transfer
        if self.source and self.reverse:
            self.stderr = True

        # build gateway invocation command
        invoke_gw_args = []
        for envname in ('PYTHONPATH',
                        'CLUSTERSHELL_GW_PYTHON_EXECUTABLE',
                        'CLUSTERSHELL_GW_LOG_DIR',
                        'CLUSTERSHELL_GW_LOG_LEVEL',
                        'CLUSTERSHELL_GW_B64_LINE_LENGTH'):
            envval = os.getenv(envname)
            if envval:
                invoke_gw_args.append("%s=%s" % (envname, envval))

        # It is critical to launch a remote Python executable with the same
        # major version (ie. python or python3) as we use the (default) pickle
        # protocol and for example, version 3+ (Python 3 with bytes
        # support) cannot be unpickled by Python 2.
        python_executable = os.getenv('CLUSTERSHELL_GW_PYTHON_EXECUTABLE',
                                      basename(sys.executable or 'python'))
        invoke_gw_args.append(python_executable)
        invoke_gw_args.extend(['-m', 'ClusterShell.Gateway', '-Bu'])
        self.invoke_gateway = ' '.join(invoke_gw_args)

        self.topology = kwargs.get('topology')
        if self.topology is not None:
            self.newroot = kwargs.get('newroot') or \
                           str(self.topology.root.nodeset)
            self.router = PropagationTreeRouter(self.newroot, self.topology)
        else:
            self.router = None

        self.upchannel = None

        self.metahandler = MetaWorkerEventHandler(self)

        # gateway (string) -> active targets selection
        self.gwtargets = {}

        # IO port
        self._port = EnginePort(handler=TreeWorker._IOPortHandler(self),
                                autoclose=True)

    def _start(self):
        # Engine has started: initalize router
        self.topology = self.topology or self.task.topology
        self.router = self.task._default_router(self.router)
        self._launch(self.nodes)
        self._check_ini()
        self._started = True

    def _launch(self, nodes):
        self.logger.debug("TreeWorker._launch on %s (fanout=%d)", nodes,
                          self.task.info("fanout"))

        # Prepare copy params if source is defined
        destdir = None
        if self.source:
            if self.reverse:
                self.logger.debug("rcopy source=%s, dest=%s", self.source,
                                  self.dest)
                # dest is a directory
                destdir = self.dest
            else:
                self.logger.debug("copy source=%s, dest=%s", self.source,
                                  self.dest)
                # Special processing to determine best arcname and destdir for
                # tar. The only case that we don't support is when source is a
                # file and dest is a dir without a finishing / (in that case we
                # cannot determine remotely whether it is a file or a
                # directory).
                if isfile(self.source):
                    # dest is not normalized here
                    arcname = basename(self.dest) or \
                              basename(normpath(self.source))
                    destdir = dirname(self.dest)
                else:
                    # source is a directory: if dest has a trailing slash
                    # like in /tmp/ then arcname is basename(source)
                    # but if dest is /tmp/newname (without leading slash) then
                    # arcname becomes newname.
                    if self.dest[-1] == '/':
                        arcname = basename(self.source)
                    else:
                        arcname = basename(self.dest)
                    # dirname has not the same behavior when a leading slash is
                    # present, and we want that.
                    destdir = dirname(self.dest)
                self.logger.debug("copy arcname=%s destdir=%s", arcname,
                                  destdir)

        # And launch stuffs
        next_hops = self._distribute(self.task.info("fanout"), nodes.copy())
        self.logger.debug("next_hops=%s" % [(str(n), str(v))
                                            for n, v in next_hops])
        for gw, targets in next_hops:
            if gw == targets:
                self.logger.debug('task.shell cmd=%s source=%s nodes=%s '
                                  'timeout=%s remote=%s', self.command,
                                  self.source, nodes, self.timeout, self.remote)
                self._child_count += 1
                self._target_count += len(targets)
                if self.remote:
                    if self.source:
                        # Note: specific case where targets are not in topology
                        # as self.source is never used on remote gateways
                        # so we try a direct copy/rcopy:
                        self.logger.debug('_launch copy r=%s source=%s dest=%s',
                                          self.reverse, self.source, self.dest)
                        worker = self.task.copy(self.source, self.dest, targets,
                                                handler=self.metahandler,
                                                stderr=self.stderr,
                                                timeout=self.timeout,
                                                preserve=self.preserve,
                                                reverse=self.reverse,
                                                tree=False)
                    else:
                        worker = self.task.shell(self.command,
                                                 nodes=targets,
                                                 timeout=self.timeout,
                                                 handler=self.metahandler,
                                                 stderr=self.stderr,
                                                 tree=False)
                else:
                    assert self.source is None
                    workerclass = self.task.default('local_worker')
                    worker = workerclass(nodes=targets,
                                         command=self.command,
                                         handler=self.metahandler,
                                         timeout=self.timeout,
                                         stderr=self.stderr)
                    self.task.schedule(worker)

                self.workers.append(worker)
                self.logger.debug("added child worker %s count=%d", worker,
                                  len(self.workers))
            else:
                self.logger.debug("trying gateway %s to reach %s", gw, targets)
                if self.source:
                    self._copy_remote(self.source, destdir, targets, gw,
                                      self.timeout, self.reverse)
                else:
                    self._execute_remote(self.command, targets, gw,
                                         self.timeout)

        # Copy mode: send tar data after above workers have been initialized
        if self.source and not self.reverse:
            try:
                # create temporary tar file with all source files
                tmptar = tempfile.TemporaryFile()
                tar = tarfile.open(fileobj=tmptar, mode='w:')
                tar.add(self.source, arcname=arcname)
                tar.close()
                tmptar.flush()
                # read generated tar file
                tmptar.seek(0)
                rbuf = tmptar.read(32768)
                # send tar data to remote targets only
                while len(rbuf) > 0:
                    self._write_remote(rbuf)
                    rbuf = tmptar.read(32768)
            except OSError as exc:
                raise WorkerError(exc)

    def _distribute(self, fanout, dst_nodeset):
        """distribute target nodes between next hop gateways"""
        self.router.fanout = fanout

        distribution = {}
        for gw, dstset in self.router.dispatch(dst_nodeset):
            distribution.setdefault(str(gw), NodeSet()).add(dstset)

        return tuple((NodeSet(k), v) for k, v in distribution.items())

    def _copy_remote(self, source, dest, targets, gateway, timeout, reverse):
        """run a remote copy in tree mode (using gateway)"""
        self.logger.debug("_copy_remote gateway=%s source=%s dest=%s "
                          "reverse=%s", gateway, source, dest, reverse)

        self._target_count += len(targets)

        self.gwtargets.setdefault(str(gateway), NodeSet()).add(targets)

        # tar commands are built here and launched on targets
        if reverse:
            # these weird replace calls aim to escape single quotes ' within ''
            srcdir = dirname(source).replace("'", '\'\"\'\"\'')
            srcbase = basename(normpath(self.source)).replace("'", '\'\"\'\"\'')
            cmd = self.TAR_CMD_FMT % (srcdir, srcbase)
        else:
            cmd = self.UNTAR_CMD_FMT % dest.replace("'", '\'\"\'\"\'')

        self.logger.debug('_copy_remote: tar cmd: %s', cmd)

        pchan = self.task._pchannel(gateway, self)
        pchan.shell(nodes=targets, command=cmd, worker=self, timeout=timeout,
                    stderr=self.stderr, gw_invoke_cmd=self.invoke_gateway,
                    remote=self.remote)


    def _execute_remote(self, cmd, targets, gateway, timeout):
        """run command against a remote node via a gateway"""
        self.logger.debug("_execute_remote gateway=%s cmd=%s targets=%s",
                          gateway, cmd, targets)

        self._target_count += len(targets)

        self.gwtargets.setdefault(str(gateway), NodeSet()).add(targets)

        pchan = self.task._pchannel(gateway, self)
        pchan.shell(nodes=targets, command=cmd, worker=self, timeout=timeout,
                    stderr=self.stderr, gw_invoke_cmd=self.invoke_gateway,
                    remote=self.remote)

    def _relaunch(self, previous_gateway):
        """Redistribute and relaunch commands on targets that were running
        on previous_gateway (which is probably marked unreachable by now)

        NOTE: Relaunch is always called after failed remote execution, so
        previous_gateway must be defined. However, it is not guaranteed that
        the relaunch is going to be performed using gateways (that's a feature).
        """
        targets = self.gwtargets[previous_gateway].copy()
        self.logger.debug("_relaunch on targets %s from previous_gateway %s",
                          targets, previous_gateway)

        for target in targets:
            self.gwtargets[previous_gateway].remove(target)

        self._check_fini(previous_gateway)
        self._target_count -= len(targets)
        self._launch(targets)

    def _engine_clients(self):
        """
        Access underlying engine clients.
        """
        return [self._port]

    def _on_remote_node_msgline(self, node, msg, sname, gateway):
        """remote msg received"""
        if not self.source or not self.reverse or sname != 'stdout':
            DistantWorker._on_node_msgline(self, node, msg, sname)
            return

        # rcopy only: we expect base64 encoded tar content on stdout
        encoded = self._rcopy_bufs.setdefault(node, b'') + msg
        if node not in self._rcopy_tars:
            self._rcopy_tars[node] = tempfile.TemporaryFile()

        # partial base64 decoding requires a multiple of 4 characters
        encoded_sz = (len(encoded) // 4) * 4
        # write decoded binary msg to node temporary tarfile
        self._rcopy_tars[node].write(base64.b64decode(encoded[0:encoded_sz]))
        # keep trailing encoded chars for next time
        self._rcopy_bufs[node] = encoded[encoded_sz:]

    def _on_remote_node_close(self, node, rc, gateway):
        """remote node closing with return code"""
        DistantWorker._on_node_close(self, node, rc)
        self.logger.debug("_on_remote_node_close %s %s via gw %s", node,
                          self._close_count, gateway)

        # finalize rcopy: extract tar data
        if self.source and self.reverse:
            for bnode, buf in self._rcopy_bufs.items():
                tarfileobj = self._rcopy_tars[bnode]
                if len(buf) > 0:
                    self.logger.debug("flushing node %s buf %d bytes", bnode,
                                      len(buf))
                    tarfileobj.write(buf)
                tarfileobj.flush()
                tarfileobj.seek(0)
                tmptar = tarfile.open(fileobj=tarfileobj)
                try:
                    self.logger.debug("%s extracting %d members in dest %s",
                                      bnode, len(tmptar.getmembers()),
                                      self.dest)
                    tmptar.extractall(path=self.dest)
                except IOError as ex:
                    self._on_remote_node_msgline(bnode, ex, 'stderr', gateway)
                finally:
                    tmptar.close()
            self._rcopy_bufs = {}
            self._rcopy_tars = {}

        self.gwtargets[str(gateway)].remove(node)
        self._close_count += 1
        self._check_fini(gateway)

    def _on_remote_node_timeout(self, node, gateway):
        """remote node timeout received"""
        DistantWorker._on_node_timeout(self, node)
        self.logger.debug("_on_remote_node_timeout %s via gw %s", node, gateway)
        self._close_count += 1
        self._has_timeout = True
        self.gwtargets[str(gateway)].remove(node)
        self._check_fini(gateway)

    def _on_node_close(self, node, rc):
        DistantWorker._on_node_close(self, node, rc)
        self.logger.debug("_on_node_close %s %s (%s)", node, rc,
                          self._close_count)
        self._close_count += 1

    def _on_node_timeout(self, node):
        DistantWorker._on_node_timeout(self, node)
        self.logger.debug("_on_node_timeout %s (%s)", node, self._close_count)
        self._close_count += 1
        self._has_timeout = True

    def _check_ini(self):
        self.logger.debug("TreeWorker: _check_ini (%d, %d)", self._start_count,
                          self._child_count)
        if self.eh and self._start_count >= self._child_count:
            # this part is called once
            self.eh.ev_start(self)
            # Blindly generate pickup events: this could maybe be improved, for
            # example, generated only when commands are sent to the gateways
            # or for direct targets, using MetaWorkerEventHandler.
            for node in self.nodes:
                _eh_sigspec_invoke_compat(self.eh.ev_pickup, 2, self, node)

    def _check_fini(self, gateway=None):
        self.logger.debug("check_fini %s %s", self._close_count,
                          self._target_count)
        if self._close_count >= self._target_count:
            handler = self.eh
            if handler:
                # also use hasattr check because ev_timeout was missing in 1.8.0
                if self._has_timeout and hasattr(handler, 'ev_timeout'):
                    handler.ev_timeout(self)
                _eh_sigspec_invoke_compat(handler.ev_close, 2, self,
                                          self._has_timeout)

        # check completion of targets per gateway
        if gateway:
            targets = self.gwtargets[str(gateway)]
            if not targets:
                # no more active targets for this gateway
                self.logger.debug("TreeWorker._check_fini %s call pchannel_"
                                  "release for gw %s", self, gateway)
                self.task._pchannel_release(gateway, self)
                del self.gwtargets[str(gateway)]

    def _write_remote(self, buf):
        """Write buf to remote clients only."""
        for gateway, targets in self.gwtargets.items():
            assert len(targets) > 0
            self.task._pchannel(gateway, self).write(nodes=targets, buf=buf,
                                                     worker=self)

    def _set_write_eof_remote(self):
        for gateway, targets in self.gwtargets.items():
            assert len(targets) > 0
            self.task._pchannel(gateway, self).set_write_eof(nodes=targets,
                                                             worker=self)

    def write(self, buf):
        """Write to worker clients."""
        if not self._started:
            self._port.msg_send((TreeWorker.write, buf))
            return

        osexc = None
        # Differentiate directly handled writes from remote ones
        for worker in self.workers:
            try:
                worker.write(buf)
            except OSError as exc:
                osexc = exc

        self._write_remote(buf)

        if osexc:
            raise osexc

    def set_write_eof(self):
        """
        Tell worker to close its writer file descriptor once flushed. Do not
        perform writes after this call.
        """
        if not self._started:
            self._port.msg_send((TreeWorker.set_write_eof, ))
            return

        # Differentiate directly handled EOFs from remote ones
        for worker in self.workers:
            worker.set_write_eof()

        self._set_write_eof_remote()

    def abort(self):
        """Abort processing any action by this worker."""
        # Not yet supported by TreeWorker
        raise NotImplementedError("see github issue #229")


# TreeWorker's former name (deprecated as of 1.8)
WorkerTree = TreeWorker
