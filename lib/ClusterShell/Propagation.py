#!/usr/bin/env python
#
# Copyright CEA/DAM/DIF (2010, 2011, 2012)
#  Contributor: Henri DOREAU <henri.doreau@gmail.com>
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
ClusterShell Propagation module. Use the topology tree to send commands
through gateways and gather results.
"""

import logging

from ClusterShell.NodeSet import NodeSet
from ClusterShell.Communication import Channel
from ClusterShell.Communication import ControlMessage, StdOutMessage
from ClusterShell.Communication import StdErrMessage, RetcodeMessage
from ClusterShell.Communication import RoutedMessageBase, EndMessage
from ClusterShell.Communication import ConfigurationMessage, TimeoutMessage


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
        root_group = None

        for entry in topology.groups:
            if root in entry.nodeset:
                root_group = entry
                break

        if root_group is None:
            raise RouteResolvingError('Invalid admin node: %s' % root)

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
        # Check for directly connected targets
        res = [tmp & dst for tmp in self.table.values()]
        nexthop = NodeSet()
        [nexthop.add(x) for x in res]
        if len(nexthop) > 0:
            yield nexthop, nexthop

        # Check for remote targets, that require a gateway to be reached
        for network in self.table.iterkeys():
            dst_inter = network & dst
            dst.difference_update(dst_inter)
            for host in dst_inter.nsiter():
                yield self.next_hop(host), host

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
    def __init__(self, task):
        """
        """
        Channel.__init__(self)
        self.task = task
        self.workers = {}

        self.current_state = None
        self.states = {
            'STATE_CFG': self._state_config,
            'STATE_CTL': self._state_control,
            #'STATE_GTR': self._state_gather,
        }

        self._history = {} # track informations about previous states
        self._sendq = []
        self.logger = logging.getLogger(__name__)

    def start(self):
        """initial actions"""
        #print '[DBG] start'
        self._open()
        cfg = ConfigurationMessage()
        #cfg.data_encode(self.task._default_topology())
        cfg.data_encode(self.task.topology)
        self._history['cfg_id'] = cfg.msgid
        self.send(cfg)
        self.current_state = self.states['STATE_CFG']

    def recv(self, msg):
        """process incoming messages"""
        self.logger.debug("[DBG] rcvd from: %s" % str(msg))
        if msg.ident == EndMessage.ident:
            #??#self.ptree.notify_close()
            self.logger.debug("closing")
            # abort worker (now working)
            self.worker.abort()
        else:
            self.current_state(msg)

    def shell(self, nodes, command, worker, timeout, stderr, gw_invoke_cmd):
        """command execution through channel"""
        self.logger.debug("shell nodes=%s timeout=%f worker=%s" % \
            (nodes, timeout, id(worker)))

        self.workers[id(worker)] = worker
        
        ctl = ControlMessage(id(worker))
        ctl.action = 'shell'
        ctl.target = nodes

        info = self.task._info.copy()
        info['debug'] = False
        
        ctl_data = {
            'cmd': command,
            'invoke_gateway': gw_invoke_cmd, # XXX
            'taskinfo': info, #self.task._info,
            'stderr': stderr,
            'timeout': timeout,
        }
        ctl.data_encode(ctl_data)

        self._history['ctl_id'] = ctl.msgid
        if self.current_state == self.states['STATE_CTL']:
            # send now if channel state is CTL
            self.send(ctl)
        else:
            self._sendq.append(ctl)
    
    def _state_config(self, msg):
        """handle incoming messages for state 'propagate configuration'"""
        if msg.type == 'ACK': # and msg.ack == self._history['cfg_id']:
            self.current_state = self.states['STATE_CTL']
            for ctl in self._sendq:
                self.send(ctl)
        else:
            print str(msg)

    def _state_control(self, msg):
        """handle incoming messages for state 'control'"""
        if msg.type == 'ACK': # and msg.ack == self._history['ctl_id']:
            #self.current_state = self.states['STATE_GTR']
            self.logger.debug("PropChannel: _state_control -> STATE_GTR")
        elif isinstance(msg, RoutedMessageBase):
            metaworker = self.workers[msg.srcid]
            if msg.type == StdOutMessage.ident:
                if metaworker.eh:
                    nodeset = NodeSet(msg.nodes)
                    self.logger.debug("StdOutMessage: \"%s\"", msg.data)
                    for line in msg.data.splitlines():
                        for node in nodeset:
                            metaworker._on_node_msgline(node, line)
            elif msg.type == StdErrMessage.ident:
                if metaworker.eh:
                    nodeset = NodeSet(msg.nodes)
                    self.logger.debug("StdErrMessage: \"%s\"", msg.data)
                    for line in msg.data.splitlines():
                        for node in nodeset:
                            metaworker._on_node_errline(node, line)
            elif msg.type == RetcodeMessage.ident:
                rc = msg.retcode
                for node in NodeSet(msg.nodes):
                    metaworker._on_node_rc(node, rc)
            elif msg.type == TimeoutMessage.ident:
                self.logger.debug("TimeoutMessage for %s", msg.nodes)
                for node in NodeSet(msg.nodes):
                    metaworker._on_node_timeout(node)
        else:
            self.logger.debug("PropChannel: _state_gather unhandled msg %s" % \
                              msg)
        """
        return
        if self.ptree.upchannel is not None:
            self.logger.debug("_state_gather ->upchan %s" % msg)
            self.ptree.upchannel.send(msg) # send to according event handler passed by shell()
        else:
            assert False
        """
 
    def ev_close(self, worker):
        worker.flush_buffers()

