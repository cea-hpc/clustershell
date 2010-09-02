#!/usr/bin/env python
#
# Copyright CEA/DAM/DIF (2008, 2009, 2010)
#  Contributor: Henri DOREAU <henri.doreau@gmail.com>
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
#
# $Id$

"""
ClusterShell Propagation module. Use the topology tree to send commands through
gateways, and gather results.
"""


from ClusterShell.NodeSet import NodeSet
from ClusterShell.Task import task_self
from ClusterShell.Communication import Channel, Driver
from ClusterShell.Communication import ConfigurationMessage
from ClusterShell.Communication import ControlMessage


class PropagationTreeRouter:
    """performs routes resolving operations whithin a propagation tree. This
    object provides a next_hop method, that will look for the best directly
    connected node to use to forward a message to a remote node.

    Upon instanciation, the router will parse the topology tree to generate its
    routing table.
    """
    def __init__(self, root, topology):
        """
        """
        self.topology = topology
        self.fanout = 32 # some default
        self.nodes_fanin = {}
        self.table = None
        self.root = root

        self.table_generate(root, topology)
        self._unreachable_hosts = NodeSet()

    def table_generate(self, root, topology):
        """The router relies on a routing table. The keys are the destination
        nodes, and the values are the next hop gateways to use to reach these
        nodes.
        """
        self.table = {}
        root_group = None

        for entry in topology.groups:
            if root in entry.nodeset:
                root_group = entry
                break

        if root_group is None:
            raise RoutesResolvingError('Invalid admin node: %s' % root)

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
        """dispatch nodes from a target nodeset to the directly connected
        gateways.

        The method acts as an iterator, returning a gateway, and the associated
        hosts. It should provide a rather good load balancing between the
        gateways.
        """
        nb_parts = len(dst)/self.fanout or 1
        for networks in self.table.iterkeys():
            dst_inter = networks & dst
            for subnet in dst_inter.split(nb_parts):
                dst.difference_update(subnet)
                yield self.next_hop(subnet), subnet

    def next_hop(self, dst):
        """perform the next hop resolution. If several hops are available, then,
        the one with the least number of current jobs will be returned
        """
        if dst in self._unreachable_hosts:
            raise RoutesResolvingError(
                'Invalid destination: %s, host is unreachable' % dst)

        # can't resolve if source == destination
        if self.root == dst:
            raise RoutesResolvingError(
                'Invalid resolution request: %s -> %s' % (self.root, dst))

        for network, nxthops in self.table.iteritems():
            if dst in network:
                res = self._best_next_hop(nxthops)
                self.nodes_fanin[res] += len(dst)
                return res
            if dst in nxthops:
                return dst

        raise RoutesResolvingError(
            'No route from %s to host %s' % (self.root, dst))

    def mark_unreachable(self, dst):
        """mark node dst as unreachable and don't advertise routes through it
        anymore. The cache will be updated only when necessary to avoid
        performing expensive traversals.
        """
        # Simply mark dst as unreachable in a dedicated NodeSet. This list will
        # be consulted by the resolution method
        self._unreachable_hosts.add(dst)

    def _best_next_hop(self, candidates):
        """find out a good next hop gateway"""
        backup = None
        backup_connections = 1e400 # infinity

        for host in candidates:
            if host not in self._unreachable_hosts:
                connections = self.nodes_fanin.setdefault(host, 0)
                if connections < self.fanout:
                    # currently, the first one is the best
                    return host
                if backup_connections > connections:
                    backup = host
                    backup_connections = connections
        return backup

class PropagationTree:
    """This class represents the complete propagation tree and provides the
    ability to propagate tasks through it.
    """
    def __init__(self, topology, admin):
        """
        """
        # topology tree
        self.topology = topology
        # name of the administration node, at the root of the tree
        self.admin = admin
        # builtin router
        self.router = PropagationTreeRouter(admin, topology)
        # communication endpoint
        self.invoke_gateway = 'python -m gateway.py'

    def execute(self, cmd, nodes, fanout=32, timeout=4):
        """execute `cmd' on the nodeset specified at loading"""
        task = task_self()
        dst_nodeset = NodeSet(nodes)
        next_hops = self._distribute(fanout, dst_nodeset)
        for gw, target in next_hops.iteritems():
            # high level logic
            driver = PropagationDriver(cmd, target, self.topology)
            # tunnelled message passing
            chan = Channel(self.admin, gw, driver)
            # invoke remote gateway engine
            task.shell(self.invoke_gateway, nodes=gw, handler=chan,
                timeout=timeout)
        task.resume()

    def _distribute(self, fanout, dst_nodeset):
        """distribute target nodes between next hop gateways"""
        distribution = {}
        self.router.fanout = fanout

        for gw, dstset in self.router.dispatch(dst_nodeset):
            if distribution.has_key(gw):
                distribution[gw].add(dstset)
            else:
                distribution[gw] = dstset
        return distribution

    def next_hop(self, dst):
        """routing operation: resolve next hop gateway"""
        return self.router.next_hop(dst)

    def mark_unreachable(self, dst):
        """routing operation: mark an host as unreachable"""
        return self.router.mark_unreachable(dst)

class PropagationDriver(Driver):
    """Admin node propagation logic. Instances are able to handle incoming
    messages from a directly connected gateway, process them and reply.

    In order to take decisions, the instance acts as a finite states machine,
    whose current state evolves according to received data.
    """
    def __init__(self, cmd, target, topology):
        """
        """
        Driver.__init__(self)
        self.cmd = cmd
        self.target = target
        self.topology = topology

        self.current_state = None
        self.states = {
            'STATE_CFG': self._state_config,
            'STATE_CTL': self._state_control,
            'STATE_GTR': self._state_gather,
        }

        self._history = {} # track informations about previous states
        self.results = [] # (<-- stub)

    def start(self):
        """initial actions"""
        cfg = ConfigurationMessage()
        cfg.data_encode(self.topology)
        self._history['cfg_id'] = cfg.msgid
        self.send(cfg)
        self.current_state = self.states['STATE_CFG']

    def recv(self, msg):
        """process incoming messages"""
        #print 'RCVD: %s' % msg.xml()
        self.current_state(msg)

    def _state_config(self, msg):
        """handle incoming messages for state 'propagate configuration'"""
        if msg.ack == self._history['cfg_id']:
            self.current_state = self.states['STATE_CTL']

            ctl = ControlMessage()
            ctl.action = 'shell'
            ctl.target = self.target
            ctl.data_encode({'cmd': self.cmd})

            self._history['ctl_id'] = ctl.msgid
            self.send(ctl)

    def _state_control(self, msg):
        """handle incoming messages for state 'control'"""
        if msg.ack == self._history['ctl_id']:
            self.current_state = self.states['STATE_GTR']

    def _state_gather(self, msg):
        """handle incoming messages for state 'gather results'"""
        # !! this class, and especially this method, is stub to be improved !! #
        self.results.append(msg.data_decode())

class RoutesResolvingError(Exception):
    """error raised on invalid conditions during routing operations"""

