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
ClusterShell propagation module

The ClusterShell's commands propagation tree consists of three different kind of
nodes:
  - admin node: at the root of the tree
  - gateways nodes: that forward commands from the root to the leaves, and
    harvest outputs from their subtree to send it to the root.
  - edge nodes: the leaves of the tree, that simply receive and execute
    commands.

This module contains everything needed to convert a TopologyTree, with
undifferenciated nodes, into a PropagationTree, made of an admin node, gateways
and edge nodes.

Specialized nodes are able to communicate using a message passing system.
Messages are forwarded in the tree using a router, shared between the nodes
"""

import time

from ClusterShell.NodeSet import NodeSet
from ClusterShell.Task import Task, task_self
from ClusterShell.Event import EventHandler
from ClusterShell.Communication import Channel, Driver

class PropagationNode:
    """base class that implements common operations and attributes for every
    nodes of the propagation tree
    """
    def __init__(self, name, tree):
        """
        """
        self.name = name
        # the propagation tree we're in
        self.tree = tree
        # parent and children nodesets
        self.parents = None
        self.children = None

    def _dbg(self, msg):
        """debug method: print sth out"""
        #print '<%s>: %s' % (self.name, msg)
        pass

    def __str__(self):
        """printable representation of the node"""
        return self.name

class CommunicatingNode(PropagationNode):
    """subclass that provides inter nodes communication code. both admin and
    gateways are communicating nodes. Edge nodes are not, as they are only
    reachable by volatile SSH connections to execute commands.
    """
    def __init__(self, name, tree):
        """
        """
        PropagationNode.__init__(self, name, tree)
        self.connected = []
        self.active_connections = 0

    def recv_message(self, msg):
        """this method is a stub to simulate communication between nodes"""
        if msg.dst != self.name:
            raise InvalidMessageError(
                'Received message at %s while destination set for %s' \
                % (self.name, msg.dst))

        self._dbg('received message: %s' % str(msg))

    def send_message(self, msg):
        """send a message to a directly connected node or to the next hop
        gateway for forwarding
        """
        dst = msg.dst
        if dst is None:
            raise InvalidMessageError(
                'Mandatory destination field not set on message %s' % str(msg))
        elif dst in self.children:
            data = msg.decode()
            
            if data['msgtype'] == PropagationMessage.TYPE_TASK_SHELL:
                if dst in self.children:
                    cmd = data['task']
                    self._dbg('Execute command %s on %s' % (cmd, dst))
            elif data['msgtype'] == PropagationMessage.TYPE_CTRL_MSG:
                self._dbg('Forwarding message to neighbour node %s' % dst)
                self.tree[dst].recv_message(msg)
        else:
            self._dbg('Forwarding message to remote node %s' % dst)
            self.tree.next_hop(self.name, dst).forward(msg)

    def dst_invalidate(self, dst):
        """mark a route from self to dst as invalid"""
        self.tree.mark_unreachable(dst)

class AdminNode(CommunicatingNode):
    """administration node. This kind of node is instanciated only once per
    propagation tree. It is mainly charged to distribute tasks to the directly
    connected gateways, perform retransmissions on failure and gather outputs
    """

class GatewayNode(CommunicatingNode):
    """the gateway nodes are able to forward message to both their children and
    their parent (another gateway node or admin).
    """
    def forward(self, msg):
        """process an incoming message not destinated to us"""
        if msg.dst not in self.connected:
            self.connected.append(msg.dst)
        self.send_message(msg)

class EdgeNode(PropagationNode):
    """the edge nodes are the leaves of the propagation tree. They know nothing
    about the propagation tree and are only able to receive messages and return
    outputs
    """

class PropagationTreeRouter:
    """performs routes resolving operations on a propagation tree. This object
    provides a next_hop function to know to which hop forward a message for a
    given destination. The routes resolution is only performed in the sense
    root -> leaves. For the other sense, a node just need to forward the message
    to one of its parent, as upward routes are convergent.
    """
    def __init__(self):
        """
        """
        self.nodes_table = {}
        self.fanout = 32 # some default
        self._unreachable_hosts = NodeSet()

    def next_hop(self, src, dst):
        """perform the next hop resolution. If several hops are available, then,
        the one with the least number of current jobs will be returned
        """
        # check for arguments validity
        if not self.nodes_table.has_key(src):
            raise RoutesResolvingError('Invalid source: %s' % src)
        if not self.nodes_table.has_key(dst):
            raise RoutesResolvingError('Invalid destination: %s' % dst)

        if dst in self._unreachable_hosts:
            raise RoutesResolvingError(
                'Invalid destination: %s, host is unreachable' % dst)

        src_inst = self.nodes_table[src]
        dst_current = dst
        while True:
            # start from the destination for efficiency
            dst_inst = self.nodes_table[dst_current]
            ng = dst_inst.parents
            # compute the intersection between current node's parents and
            # source's children
            inter = src_inst.children & ng
            if len(inter) != 0:
                # return the best
                best_nh = self._best_next_hop(inter)
                nexthop = self.nodes_table[best_nh]
                return nexthop
            else:
                # iterate once again on the upper level
                valid_gw = ng - self._unreachable_hosts
                if len(valid_gw) < 1:
                    raise RoutesResolvingError('No route available to %s' % dst)

                dst_current = valid_gw[0]

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
                connections = self.nodes_table[host].active_connections
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
    def __init__(self):
        """
        """
        # list of available nodes, available by their name
        self.nodes = {}
        # name of the administration node, at the root of the tree
        self.admin = ''
        # destination nodeset
        self.targets = None
        # builtin router
        self.router = None

    def __str__(self):
        """printable representation of the tree"""
        return '\n'.join(['%s: %s' % (str(k), str(v)) for k, v in
            self.nodes.iteritems()])

    def load(self, topology_tree, nodeset, fanout):
        """load data from a previously generated topology tree, a destination
        nodeset and the selected fanout.
        """
        self.nodes = {}
        self.targets = NodeSet(nodeset)
        self.router = PropagationTreeRouter()
        self.router.fanout = fanout

        # --- generate one specialized instance per node --- #
        for nodegroup in topology_tree:
            group_key = str(nodegroup.nodeset)
            if nodegroup.parent is None:
                # Admin node (no parents)
                curr = AdminNode(group_key, self)
                curr.children = nodegroup.children_ns()
                self.nodes[group_key] = curr
                self.admin = group_key
            elif nodegroup.children_len() == 0:
                # Edge node (no children)
                ns_util = nodegroup.nodeset & self.targets
                for node in ns_util:
                    node_key = str(node)
                    curr = EdgeNode(node_key, self)
                    curr.parents = nodegroup.parent.nodeset
                    self.nodes[node_key] = curr
            else:
                # Gateway node (no other possibility)
                for node in nodegroup.nodeset:
                    node_key = str(node)
                    curr = GatewayNode(node_key, self)
                    curr.parents = nodegroup.parent.nodeset
                    curr.children = nodegroup.children_ns()
                    self.nodes[node_key] = curr

        # --- instanciate and return the actual tree --- #
        self.router.nodes_table = self.nodes

    def execute(self, cmd):
        """execute `cmd' on the nodeset specified at loading"""
        task = task_self()
        next_hops = self._distribute()
        for gw, target in next_hops.iteritems():
            admin_driver = PropagationDriver(self.admin, gw)
            channel = Channel(admin_driver)
            # TODO : remove hardcoded timeout & script name
            task.shell('python -m gateway', nodes=gw, handler=channel, timeout=4)
        task.resume()

    def _distribute(self):
        """distribute target nodes between next hop gateways"""
        # TODO : bad performances issue
        distribution = {}
        for node in self.targets:
            gw = self.next_hop(self.admin, node)
            gw_name = gw.name
            if distribution.has_key(gw_name):
                distribution[gw_name].add(node)
            else:
                distribution[gw_name] = NodeSet(node)
            gw.active_connections += 1
        return distribution

    def __getitem__(self, nodename):
        """return a reference on the instance of a node given a node name"""
        return self.nodes[nodename]
    
    def next_hop(self, src, dst):
        """routing operation: resolve next hop gateway"""
        return self.router.next_hop(src, dst)

    def mark_unreachable(self, dst):
        """routing operation: mark an host as unreachable"""
        return self.router.mark_unreachable(dst)

class PropagationDriver(Driver):
    """Admin node propagation logic. Instances are able to handle incoming
    messages from a directly connected gateway, process them and reply.

    In order to take decisions, the instance acts as a finite states machine,
    whose current state evolves according to received data.
    """
    def __init__(self, src, dst):
        """
        """
        Driver.__init__(self, src, dst)
        # TODO: implement state machine

    def read_msg(self, msg):
        """
        """
        pass

    def next_msg(self):
        """
        """
        pass

class PropagationMessage:
    """message to a node. This is just a stub"""
    # Message types
    TYPE_TASK_SHELL = 1
    TYPE_CTRL_MSG = 2
    # this class variable is used to uniquely identify each message
    class_counter = 0

    def __init__(self):
        """
        """
        self.src = None
        self.dst = None
        self._infos = {}
        PropagationMessage.class_counter += 1
        self._msg_id = PropagationMessage.class_counter

    def decode(self):
        """return raw data, as a dictionnary"""
        return self._infos

    def add_info(self, key, arg):
        """add a key/value couple to the message"""
        self._infos[key] = arg

    def __str__(self):
        """printable summary of the message"""
        return 'message #%d: %s -> %s' % (self._msg_id, self.src, self.dst)

class InvalidMessageError(Exception):
    """error raised on performing operations on invalid messages"""

class RoutesResolvingError(Exception):
    """error raised on invalid conditions during routing operations"""

