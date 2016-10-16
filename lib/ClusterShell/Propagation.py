#!/usr/bin/env python
#
# Copyright (C) 2010-2016 CEA/DAM
# Copyright (C) 2010-2011 Henri Doreau <henri.doreau@cea.fr>
# Copyright (C) 2015-2016 Stephane Thiell <sthiell@stanford.edu>
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
ClusterShell Propagation module. Use the topology tree to send commands
through gateways and gather results.
"""

from collections import deque
import logging

from ClusterShell.Defaults import DEFAULTS
from ClusterShell.NodeSet import NodeSet
from ClusterShell.Communication import Channel
from ClusterShell.Communication import ControlMessage, StdOutMessage
from ClusterShell.Communication import StdErrMessage, RetcodeMessage
from ClusterShell.Communication import StartMessage, EndMessage
from ClusterShell.Communication import RoutedMessageBase, ErrorMessage
from ClusterShell.Communication import ConfigurationMessage, TimeoutMessage
from ClusterShell.Topology import TopologyError


class RouteResolvingError(Exception):
    """error raised on invalid conditions during routing operations"""

class PropagationTreeRouter(object):
    """performs routes resolving operations within a propagation tree.
    This object provides a next_hop method, that will look for the best
    directly connected node to use to forward a message to a remote
    node.

    Upon instanciation, the router will parse the topology tree to
    generate its routing table.
    """
    def __init__(self, root, topology, fanout=0):
        self.root = root
        self.topology = topology
        self.fanout = fanout
        self.nodes_fanin = {}
        self.table = None

        self.table_generate(root, topology)
        self._unreachable_hosts = NodeSet()

    def table_generate(self, root, topology):
        """The router relies on a routing table. The keys are the
        destination nodes and the values are the next hop gateways to
        use to reach these nodes.
        """
        self.table = {}
        try:
            root_group = topology.find_nodegroup(root)
        except TopologyError:
            msgfmt = "Invalid root or gateway node: %s"
            raise RouteResolvingError(msgfmt % root)

        for group in root_group.children():
            self.table[group.nodeset] = NodeSet()
            stack = [group]
            while len(stack) > 0:
                curr = stack.pop()
                self.table[group.nodeset].add(curr.children_ns())
                stack += curr.children()

        # reverse table (it was crafted backward)
        self.table = dict((v, k) for k, v in self.table.iteritems())

    def dispatch(self, dst):
        """dispatch nodes from a target nodeset to the directly
        connected gateways.

        The method acts as an iterator, returning a gateway and the
        associated hosts. It should provide a rather good load balancing
        between the gateways.
        """
        ### Disabled to handle all remaining nodes as directly connected nodes
        ## Check for directly connected targets
        #res = [tmp & dst for tmp in self.table.values()]
        #nexthop = NodeSet()
        #[nexthop.add(x) for x in res]
        #if len(nexthop) > 0:
        #    yield nexthop, nexthop

        # Check for remote targets, that require a gateway to be reached
        for network in self.table.iterkeys():
            dst_inter = network & dst
            dst.difference_update(dst_inter)
            for host in dst_inter.nsiter():
                yield self.next_hop(host), host

        # remaining nodes are considered as directly connected nodes
        if dst:
            yield dst, dst

    def next_hop(self, dst):
        """perform the next hop resolution. If several hops are
        available, then, the one with the least number of current jobs
        will be returned
        """
        if dst in self._unreachable_hosts:
            raise RouteResolvingError(
                'Invalid destination: %s, host is unreachable' % dst)

        # can't resolve if source == destination
        if self.root == dst:
            raise RouteResolvingError(
                'Invalid resolution request: %s -> %s' % (self.root, dst))

        ## ------------------
        # the routing table is organized this way:
        #
        #  NETWORK    | NEXT HOP
        # ------------+-----------
        # node[0-9]   | gateway0
        # node[10-19] | gateway[1-2]
        #            ...
        # ---------
        for network, nexthops in self.table.iteritems():
            # destination contained in current network
            if dst in network:
                res = self._best_next_hop(nexthops)
                if res is None:
                    raise RouteResolvingError('No route available to %s' % \
                        str(dst))
                self.nodes_fanin[res] += len(dst)
                return res
            # destination contained in current next hops (ie. directly
            # connected)
            if dst in nexthops:
                return dst

        raise RouteResolvingError(
            'No route from %s to host %s' % (self.root, dst))

    def mark_unreachable(self, dst):
        """mark node dst as unreachable and don't advertise routes
        through it anymore. The cache will be updated only when
        necessary to avoid performing expensive traversals.
        """
        # Simply mark dst as unreachable in a dedicated NodeSet. This
        # list will be consulted by the resolution method
        self._unreachable_hosts.add(dst)

    def _best_next_hop(self, candidates):
        """find out a good next hop gateway"""
        backup = None
        backup_connections = 1e400 # infinity

        candidates = candidates.difference(self._unreachable_hosts)

        for host in candidates:
            # the router tracks established connections in the
            # nodes_fanin table to avoid overloading a gateway
            connections = self.nodes_fanin.setdefault(host, 0)
            # FIXME
            #if connections < self.fanout:
            #    # currently, the first one is the best
            #    return host
            if backup_connections > connections:
                backup = host
                backup_connections = connections
        return backup


class PropagationChannel(Channel):
    """Admin node propagation logic. Instances are able to handle
    incoming messages from a directly connected gateway, process them
    and reply.

    In order to take decisions, the instance acts as a finite states
    machine, whose current state evolves according to received data.

    -- INTERNALS --
    Instance can be in one of the 4 different states:
      - init (implicit)
        This is the very first state. The instance enters the init
        state at start() method, and will then send the configuration
        to the remote node.  Once the configuration is sent away, the
        state changes to cfg.

      - cfg
        During this second state, the instance will wait for a valid
        acknowledgement from the gateway to the previously sent
        configuration message. If such a message is delivered, the
        control message (the one that contains the actions to perform)
        is sent, and the state is set to ctl.

      - ctl
        Third state, the instance is waiting for a valid ack for from
        the gateway to the ctl packet. Then, the state switch to gtr
        (gather).

      - gtr
        Final state: wait for results from the subtree and store them.
    """
    def __init__(self, task, gateway):
        """
        """
        Channel.__init__(self)
        self.task = task
        self.gateway = gateway
        self.workers = {}
        self._cfg_write_hist = deque() # track write requests
        self._sendq = deque()
        self._rc = None
        self.logger = logging.getLogger(__name__)

    def send_queued(self, ctl):
        """helper used to send a message, using msg queue if needed"""
        if self.setup and not self._sendq:
            # send now if channel is setup and sendq empty
            self.send(ctl)
        else:
            self.logger.debug("send_queued: %d", len(self._sendq))
            self._sendq.appendleft(ctl)

    def send_dequeue(self):
        """helper used to send one queued message (if any)"""
        if self._sendq:
            ctl = self._sendq.pop()
            self.logger.debug("dequeuing sendq: %s", ctl)
            self.send(ctl)

    def start(self):
        """start propagation channel"""
        self._init()
        self._open()
        # Immediately send CFG
        cfg = ConfigurationMessage(self.gateway)
        cfg.data_encode(self.task.topology)
        self.send(cfg)

    def recv(self, msg):
        """process incoming messages"""
        self.logger.debug("recv: %s", msg)
        if msg.type == EndMessage.ident:
            #??#self.ptree.notify_close()
            self.logger.debug("got EndMessage; closing")
            # abort worker (now working)
            self.worker.abort()
        elif self.setup:
            self.recv_ctl(msg)
        elif self.opened:
            self.recv_cfg(msg)
        elif msg.type == StartMessage.ident:
            self.opened = True
            self.logger.debug('channel started (version %s on remote gateway)',
                              self._xml_reader.version)
        else:
            self.logger.error('unexpected message: %s', str(msg))

    def shell(self, nodes, command, worker, timeout, stderr, gw_invoke_cmd,
              remote):
        """command execution through channel"""
        self.logger.debug("shell nodes=%s timeout=%s worker=%s remote=%s",
                          nodes, timeout, id(worker), remote)

        self.workers[id(worker)] = worker

        ctl = ControlMessage(id(worker))
        ctl.action = 'shell'
        ctl.target = nodes

        # keep only valid task info pairs
        info = dict((k, v) for k, v in self.task._info.items()
                    if k not in DEFAULTS._task_info_pkeys_bl)

        ctl_data = {
            'cmd': command,
            'invoke_gateway': gw_invoke_cmd, # XXX
            'taskinfo': info,
            'stderr': stderr,
            'timeout': timeout,
            'remote': remote,
        }
        ctl.data_encode(ctl_data)
        self.send_queued(ctl)

    def write(self, nodes, buf, worker):
        """write buffer through channel to nodes on standard input"""
        self.logger.debug("write buflen=%d", len(buf))
        assert id(worker) in self.workers

        ctl = ControlMessage(id(worker))
        ctl.action = 'write'
        ctl.target = nodes

        ctl_data = {
            'buf': buf,
        }
        ctl.data_encode(ctl_data)
        self._cfg_write_hist.appendleft((ctl.msgid, nodes, len(buf), worker))
        self.send_queued(ctl)

    def set_write_eof(self, nodes, worker):
        """send EOF through channel to specified nodes"""
        self.logger.debug("set_write_eof")
        assert id(worker) in self.workers

        ctl = ControlMessage(id(worker))
        ctl.action = 'eof'
        ctl.target = nodes
        self.send_queued(ctl)

    def recv_cfg(self, msg):
        """handle incoming messages for state 'propagate configuration'"""
        self.logger.debug("recv_cfg")
        if msg.type == 'ACK':
            self.logger.debug("CTL - connection with gateway fully established")
            self.setup = True
            self.send_dequeue()
        else:
            self.logger.debug("_state_config error (msg=%s)", msg)

    def recv_ctl(self, msg):
        """handle incoming messages for state 'control'"""
        if msg.type == 'ACK':
            self.logger.debug("got ack (%s)", msg.type)
            # check if ack matches write history msgid to generate ev_written
            if self._cfg_write_hist and msg.ack == self._cfg_write_hist[-1][0]:
                _, nodes, bytes_count, metaworker = self._cfg_write_hist.pop()
                for node in nodes:
                    # we are losing track of the gateway here, we could override
                    # on_written in WorkerTree if needed (eg. for stats)
                    metaworker._on_written(node, bytes_count, 'stdin')
            self.send_dequeue()
        elif isinstance(msg, RoutedMessageBase):
            metaworker = self.workers[msg.srcid]
            if msg.type == StdOutMessage.ident:
                nodeset = NodeSet(msg.nodes)
                decoded = msg.data_decode() + '\n'
                for line in decoded.splitlines():
                    for node in nodeset:
                        metaworker._on_remote_node_msgline(node, line, 'stdout',
                                                           self.gateway)
            elif msg.type == StdErrMessage.ident:
                nodeset = NodeSet(msg.nodes)
                decoded = msg.data_decode() + '\n'
                for line in decoded.splitlines():
                    for node in nodeset:
                        metaworker._on_remote_node_msgline(node, line, 'stderr',
                                                           self.gateway)
            elif msg.type == RetcodeMessage.ident:
                rc = msg.retcode
                for node in NodeSet(msg.nodes):
                    metaworker._on_remote_node_rc(node, rc, self.gateway)
            elif msg.type == TimeoutMessage.ident:
                self.logger.debug("TimeoutMessage for %s", msg.nodes)
                for node in NodeSet(msg.nodes):
                    metaworker._on_remote_node_timeout(node, self.gateway)
        elif msg.type == ErrorMessage.ident:
            # tree runtime error, could generate a new event later
            raise TopologyError("%s: %s" % (self.gateway, msg.reason))
        else:
            self.logger.debug("recv_ctl: unhandled msg %s", msg)
        """
        return
        if self.ptree.upchannel is not None:
            self.logger.debug("_state_gather ->upchan %s" % msg)
            self.ptree.upchannel.send(msg) # send to according event handler passed by shell()
        else:
            assert False
        """

    def ev_hup(self, worker):
        """Channel command is closing"""
        self._rc = worker.current_rc

    def ev_close(self, worker):
        """Channel is closing"""
        # do not use worker buffer or rc accessors here as we doesn't use
        # common stream names
        gateway = str(worker.nodes)
        self.logger.debug("ev_close gateway=%s %s", gateway, self)
        self.logger.debug("ev_close rc=%s", self._rc) # may be None

        if self._rc: # got explicit error code
            # ev_routing?
            self.logger.debug("unreachable gateway %s", gateway)
            worker.task.router.mark_unreachable(gateway)
            self.logger.debug("worker.task.gateways=%s", worker.task.gateways)
            # TODO: find best gateway, update WorkerTree counters, relaunch...
