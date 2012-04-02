#
# Copyright CEA/DAM/DIF (2011, 2012)
#  Contributor: Stephane THIELL <stephane.thiell@cea.fr>
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

from ClusterShell.Event import EventHandler
from ClusterShell.NodeSet import NodeSet
from ClusterShell.Worker.Worker import DistantWorker

from ClusterShell.Propagation import PropagationTreeRouter


class MetaWorkerEventHandler(EventHandler):
    """
    """
    def __init__(self, metaworker):
        self.metaworker = metaworker

    def ev_start(self, worker):
        """
        Called to indicate that a worker has just started.
        """
        self.metaworker._start_count += 1
        self.metaworker._check_ini()

    def ev_read(self, worker):
        """
        Called to indicate that a worker has data to read.
        """
        self.metaworker._on_node_msgline(worker.current_node,
                                         worker.current_msg)

    def ev_error(self, worker):
        """
        Called to indicate that a worker has error to read (on stderr).
        """
        self.metaworker._on_node_errline(worker.current_node,
                                         worker.current_errmsg)

    def ev_written(self, worker):
        """
        Called to indicate that writing has been done.
        """
        metaworker = self.metaworker
        metaworker.current_node = worker.current_node
        metaworker.eh.ev_written(metaworker)

    def ev_hup(self, worker):
        """
        Called to indicate that a worker's connection has been closed.
        """
        #print >>sys.stderr, "ev_hup?"
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
        for node in NodeSet._fromlist1(worker.iter_keys_timeout()):
            self.metaworker._on_node_timeout(node)

    def ev_close(self, worker):
        """
        Called to indicate that a worker has just finished (it may already
        have failed on timeout).
        """
        #self.metaworker._check_fini()
        pass
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

    def __init__(self, nodes, handler, timeout, **kwargs):
        """
        Initialize Tree worker instance.

        @param nodes: Targeted nodeset.
        @param handler: Worker EventHandler.
        @param timeout: Timeout value for worker.
        @param command: Command to execute.
        @param topology: Force specific TopologyTree.
        @param newroot: Root node of TopologyTree.
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
        self._close_count = 0
        self._start_count = 0
        self._child_count = 0
        self._target_count = 0
        self._has_timeout = False
        self.logger = logging.getLogger(__name__)

        if self.command is not None:
            pass
        elif self.source:
            raise NotImplementedError
        else:
            raise ValueError("missing command or source parameter in " \
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
            self.newroot = kwargs.get('newroot') or str(self.topology.root.nodeset)
            self.router = PropagationTreeRouter(self.newroot, self.topology)
        else:
            self.router = None

        self.upchannel = None
        self.metahandler = MetaWorkerEventHandler(self)

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
        # And launch stuffs
        next_hops = self._distribute(self.task.info("fanout"), self.nodes)
        for gw, targets in next_hops.iteritems():
            if gw == targets:
                self.logger.debug('task.shell cmd=%s nodes=%s timeout=%d' % \
                    (self.command, self.nodes, self.timeout))
                self._child_count += 1
                self._target_count += len(targets)
                self.workers.append(self.task.shell(self.command,
                    nodes=targets, timeout=self.timeout,
                    handler=self.metahandler, stderr=self.stderr, tree=False))
            else:
                self._execute_remote(self.command, targets, gw, self.timeout)

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

    def _execute_remote(self, cmd, targets, gateway, timeout):
        """run command against a remote node via a gateway"""
        self.logger.debug("_execute_remote gateway=%s cmd=%s targets=%s" % \
            (gateway, cmd, targets))
        #self._start_count += 1
        #self._child_count += 1
        self._target_count += len(targets)
        self.task.pchannel(gateway, self).shell(nodes=targets,
            command=cmd, worker=self, timeout=timeout, stderr=self.stderr,
            gw_invoke_cmd=self.invoke_gateway)

    def _engine_clients(self):
        """
        Access underlying engine clients.
        """
        return []

    def _on_node_rc(self, node, rc):
        DistantWorker._on_node_rc(self, node, rc)
        self._close_count += 1
        self._check_fini()

    def _on_node_timeout(self, node):
        DistantWorker._on_node_timeout(self, node)
        self._close_count += 1
        self._has_timeout = True
        self._check_fini()

    def _check_ini(self):
        self.logger.debug("WorkerTree: _check_ini (%d, %d)" % \
            (self._start_count,self._child_count))
        if self._start_count >= self._child_count:
            self.eh.ev_start(self)

    def _check_fini(self):
        if self._close_count >= self._target_count:
            handler = self.eh
            if handler:
                if self._has_timeout:
                    handler.ev_timeout(self)
                handler.ev_close(self)
            self.task._pchannel_release(self)

    def write(self, buf):
        """
        Write to worker clients.
        """
        for c in self._engine_clients():
            c._write(buf)

    def set_write_eof(self):
        """
        Tell worker to close its writer file descriptor once flushed. Do not
        perform writes after this call.
        """
        for c in self._engine_clients():
            c._set_write_eof()

    def abort(self):
        """
        Abort processing any action by this worker.
        """
        for c in self._engine_clients():
            c.abort()

