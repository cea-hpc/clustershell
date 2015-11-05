#
# Copyright CEA/DAM/DIF (2011-2015)
#  Contributor: Stephane THIELL <sthiell@stanford.edu>
#
# This file is part of the ClusterShell library.
#
# This software is governed by the CeCILL-C license under French law and
# abiding by the rules of distribution of free software.  You can  use,
# modify and/ or redistribute the software under the terms of the CeCILL-C
# license as circulated by CEA, CNRS and INRIA at the following URL
# "http://www.cecill.info".
#
# As a counterpart to the access to the source code and  rights to copy,
# modify and redistribute granted by the license, users are provided only
# with a limited warranty  and the software's author,  the holder of the
# economic rights,  and the successive licensors  have only  limited
# liability.
#
# In this respect, the user's attention is drawn to the risks associated
# with loading,  using,  modifying and/or developing or reproducing the
# software by the user in light of its specific status of free software,
# that may mean  that it is complicated to manipulate,  and  that  also
# therefore means  that it is reserved for developers  and  experienced
# professionals having in-depth computer knowledge. Users are therefore
# encouraged to load and test the software's suitability as regards their
# requirements in conditions enabling the security of their systems and/or
# data to be ensured and,  more generally, to use and operate it in the
# same conditions as regards security.
#
# The fact that you are presently reading this means that you have had
# knowledge of the CeCILL-C license and that you accept its terms.

"""
ClusterShell v2 tree propagation worker
"""

import logging
import os
from os.path import basename, dirname, isfile, normpath
import tarfile
import tempfile

from ClusterShell.Event import EventHandler
from ClusterShell.NodeSet import NodeSet
from ClusterShell.Worker.Worker import DistantWorker, WorkerError
from ClusterShell.Worker.Exec import ExecWorker

from ClusterShell.Propagation import PropagationTreeRouter


class MetaWorkerEventHandler(EventHandler):
    """Handle events for the meta worker WorkerTree"""

    def __init__(self, metaworker):
        self.metaworker = metaworker
        self.logger = logging.getLogger(__name__)

    def ev_start(self, worker):
        """
        Called to indicate that a worker has just started.
        """
        self.logger.debug("MetaWorkerEventHandler: ev_start")
        self.metaworker._start_count += 1
        self.metaworker._check_ini()

    def ev_read(self, worker):
        """
        Called to indicate that a worker has data to read.
        """
        self.logger.debug("MetaWorkerEventHandler: ev_read (%s)",
                          worker.current_sname)
        self.metaworker._on_node_msgline(worker.current_node,
                                         worker.current_msg,
                                         'stdout')

    def ev_error(self, worker):
        """
        Called to indicate that a worker has error to read (on stderr).
        """
        self.metaworker._on_node_msgline(worker.current_node,
                                         worker.current_errmsg,
                                         'stderr')

    def ev_written(self, worker, node, sname, size):
        """
        Called to indicate that writing has been done.
        """
        metaworker = self.metaworker
        metaworker.current_node = node
        metaworker.current_sname = sname
        metaworker.eh.ev_written(metaworker, node, sname, size)

    def ev_hup(self, worker):
        """
        Called to indicate that a worker's connection has been closed.
        """
        self.metaworker._on_node_rc(worker.current_node, worker.current_rc)

    def ev_timeout(self, worker):
        """
        Called to indicate that a worker has timed out (worker timeout only).
        """
        # WARNING!!! this is not possible as metaworking is changing task's
        # shared timeout set!
        #for node in worker.iter_keys_timeout():
        #    self.metaworker._on_node_timeout(node)
        # we use NodeSet to copy set
        self.logger.debug("MetaWorkerEventHandler: ev_timeout")
        for node in NodeSet._fromlist1(worker.iter_keys_timeout()):
            self.metaworker._on_node_timeout(node)

    def ev_close(self, worker):
        """
        Called to indicate that a worker has just finished (it may already
        have failed on timeout).
        """
        self.logger.debug("MetaWorkerEventHandler: ev_close")
        self.metaworker._check_fini()
        ##print >>sys.stderr, "ev_close?"
        #self._completed += 1
        #if self._completed >= self.grpcount:
        #    #print >>sys.stderr, "ev_close!"
        #    metaworker = self.metaworker
        #    metaworker.eh.ev_close(metaworker)


class WorkerTree(DistantWorker):
    """
    ClusterShell tree worker Class.

    """
    UNTAR_CMD_FMT = 'tar -xf - -C "%s"'

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

        self.workers = []
        self.nodes = NodeSet(nodes)
        self.timeout = timeout
        self.command = kwargs.get('command')
        self.source = kwargs.get('source')
        self.dest = kwargs.get('dest')
        autoclose = kwargs.get('autoclose', False)
        self.stderr = kwargs.get('stderr', False)
        self.remote = kwargs.get('remote', True)
        self._close_count = 0
        self._start_count = 0
        self._child_count = 0
        self._target_count = 0
        self._has_timeout = False
        self.logger = logging.getLogger(__name__)

        if self.command is None and self.source is None:
            raise ValueError("missing command or source parameter in "
                             "WorkerTree constructor")

        # build gateway invocation command
        invoke_gw_args = []
        for envname in ('PYTHONPATH', \
                        'CLUSTERSHELL_GW_LOG_DIR', \
                        'CLUSTERSHELL_GW_LOG_LEVEL'):
            envval = os.getenv(envname)
            if envval:
                invoke_gw_args.append("%s=%s" % (envname, envval))
        invoke_gw_args.append("python -m ClusterShell/Gateway -Bu")
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

        # gateway -> active targets selection
        self.gwtargets = {}

    def _set_task(self, task):
        """
        Bind worker to task. Called by task.schedule().
        WorkerTree metaworker: override to schedule sub-workers.
        """
        ##if fanout is None:
        ##    fanout = self.router.fanout
        ##self.task.set_info('fanout', fanout)

        DistantWorker._set_task(self, task)
        # Now bound to task - initalize router
        self.topology = self.topology or task.topology
        self.router = self.router or task._default_router()
        self._launch(self.nodes)
        self._check_ini()

    def _launch(self, nodes):
        self.logger.debug("WorkerTree._launch on %s (fanout=%d)", nodes,
                          self.task.info("fanout"))

        # Prepare copy params if source is defined
        destdir = None
        if self.source:
            self.logger.debug("copy self.dest=%s", self.dest)
            # Special processing to determine best arcname and destdir for tar.
            # The only case that we don't support is when source is a file and
            # dest is a dir without a finishing / (in that case we cannot
            # determine remotely whether it is a file or a directory).
            if isfile(self.source):
                # dest is not normalized here
                arcname = basename(self.dest) or basename(normpath(self.source))
                destdir = dirname(self.dest)
            else:
                arcname = basename(normpath(self.source))
                destdir = os.path.normpath(self.dest)
            self.logger.debug("copy arcname=%s destdir=%s", arcname, destdir)

        # And launch stuffs
        next_hops = self._distribute(self.task.info("fanout"), nodes.copy())
        self.logger.debug("next_hops=%s"
                          % [(str(n), str(v)) for n, v in next_hops.items()])
        for gw, targets in next_hops.iteritems():
            if gw == targets:
                self.logger.debug('task.shell cmd=%s source=%s nodes=%s '
                                  'timeout=%s remote=%s', self.command,
                                  self.source, nodes, self.timeout, self.remote)
                self._child_count += 1
                self._target_count += len(targets)
                if self.remote:
                    if self.source:
                        self.logger.debug('_launch remote untar (destdir=%s)',
                                          destdir)
                        self.command = self.UNTAR_CMD_FMT % destdir
                        worker = self.task.shell(self.command,
                                                 nodes=targets,
                                                 timeout=self.timeout,
                                                 handler=self.metahandler,
                                                 stderr=self.stderr,
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
                    worker = ExecWorker(nodes=targets,
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
                                      self.timeout)
                else:
                    self._execute_remote(self.command, targets, gw,
                                         self.timeout)

        # Copy mode: send tar data after above workers have been initialized
        if self.source:
            try:
                # create temporary tar file with all source files
                tmptar = tempfile.TemporaryFile()
                tar = tarfile.open(fileobj=tmptar, mode='w:')
                tar.add(self.source, arcname=arcname)
                tar.close()
                tmptar.flush()
                # read generated tar file and send to worker
                tmptar.seek(0)
                rbuf = tmptar.read(32768)
                while len(rbuf) > 0:
                    self.write(rbuf)
                    rbuf = tmptar.read(32768)
            except OSError, exc:
                raise WorkerError(exc)

    def _distribute(self, fanout, dst_nodeset):
        """distribute target nodes between next hop gateways"""
        distribution = {}
        self.router.fanout = fanout

        for gw, dstset in self.router.dispatch(dst_nodeset):
            if gw in distribution:
                distribution[gw].add(dstset)
            else:
                distribution[gw] = dstset
        return distribution

    def _copy_remote(self, source, dest, targets, gateway, timeout):
        """run a remote copy in tree mode (using gateway)"""
        self.logger.debug("_copy_remote gateway=%s source=%s dest=%s",
                          gateway, source, dest)

        self._target_count += len(targets)

        self.gwtargets[gateway] = targets.copy()

        cmd = self.UNTAR_CMD_FMT % dest

        pchan = self.task._pchannel(gateway, self)
        pchan.shell(nodes=targets, command=cmd, worker=self, timeout=timeout,
                    stderr=self.stderr, gw_invoke_cmd=self.invoke_gateway,
                    remote=self.remote)


    def _execute_remote(self, cmd, targets, gateway, timeout):
        """run command against a remote node via a gateway"""
        self.logger.debug("_execute_remote gateway=%s cmd=%s targets=%s",
                          gateway, cmd, targets)

        self._target_count += len(targets)

        self.gwtargets[gateway] = targets.copy()

        pchan = self.task._pchannel(gateway, self)
        pchan.shell(nodes=targets, command=cmd, worker=self, timeout=timeout,
                    stderr=self.stderr, gw_invoke_cmd=self.invoke_gateway,
                    remote=self.remote)

    def _engine_clients(self):
        """
        Access underlying engine clients.
        """
        return []

    def _on_remote_node_msgline(self, node, msg, sname, gateway):
        DistantWorker._on_node_msgline(self, node, msg, sname)

    def _on_remote_node_rc(self, node, rc, gateway):
        DistantWorker._on_node_rc(self, node, rc)
        self.logger.debug("_on_remote_node_rc %s %s via gw %s", node,
                          self._close_count, gateway)
        self.gwtargets[gateway].remove(node)
        self._close_count += 1
        self._check_fini(gateway)

    def _on_remote_node_timeout(self, node, gateway):
        DistantWorker._on_node_timeout(self, node)
        self.logger.debug("_on_remote_node_timeout %s via gw %s", node, gateway)
        self._close_count += 1
        self._has_timeout = True
        self.gwtargets[gateway].remove(node)
        self._check_fini(gateway)

    def _on_node_rc(self, node, rc):
        DistantWorker._on_node_rc(self, node, rc)
        self.logger.debug("_on_node_rc %s %s (%s)", node, rc, self._close_count)
        self._close_count += 1

    def _on_node_timeout(self, node):
        DistantWorker._on_node_timeout(self, node)
        self._close_count += 1
        self._has_timeout = True

    def _check_ini(self):
        self.logger.debug("WorkerTree: _check_ini (%d, %d)", self._start_count,
                          self._child_count)
        if self.eh and self._start_count >= self._child_count:
            self.eh.ev_start(self)

    def _check_fini(self, gateway=None):
        self.logger.debug("check_fini %s %s", self._close_count,
                          self._target_count)
        if self._close_count >= self._target_count:
            handler = self.eh
            if handler:
                if self._has_timeout:
                    handler.ev_timeout(self)
                handler.ev_close(self)

        # check completion of targets per gateway
        if gateway:
            targets = self.gwtargets[gateway]
            if not targets:
                self.logger.debug("WorkerTree._check_fini %s call pchannel_"
                                  "release for gw %s", self, gateway)
                self.task._pchannel_release(gateway, self)

    def write(self, buf):
        """Write to worker clients."""
        osexc = None
        # Differentiate directly handled writes from remote ones
        for worker in self.workers:
            try:
                worker.write(buf)
            except OSError, exc:
                osexc = exc
        for gateway, targets in self.gwtargets.items():
            self.task._pchannel(gateway, self).write(nodes=targets,
                                                     buf=buf,
                                                     worker=self)
        if osexc:
            raise osexc

    def set_write_eof(self):
        """
        Tell worker to close its writer file descriptor once flushed. Do not
        perform writes after this call.
        """
        # Differentiate directly handled EOFs from remote ones
        for worker in self.workers:
            worker.set_write_eof()
        for gateway, targets in self.gwtargets.items():
            self.task._pchannel(gateway, self).set_write_eof(nodes=targets,
                                                             worker=self)

    def abort(self):
        """Abort processing any action by this worker."""
        # Not yet supported by WorkerTree
        raise NotImplementedError("see github issue #229")

