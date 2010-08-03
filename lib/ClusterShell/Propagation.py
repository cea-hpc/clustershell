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

import sys
import time

from collections import deque

from ClusterShell.NodeSet import NodeSet
from ClusterShell.Topology import TopologyParser



class PropagationNode:
    """base class that implements common operations and attributes for every
    nodes of the propagation tree
    """
    def __init__(self, name):
        """instance initialization"""
        self.name = name
        self.job_queue = deque()
        # parent and children nodesets
        self.parents = None
        self.children = None

    def _dbg(self, msg):
        """debug method: print sth out"""
        #print '%s: %s' % (self.name, msg)
        pass

    def __str__(self):
        """printable representation of the node"""
        return '%s (%d task(s) running)' % (self.name, len(self.job_queue))

class CommunicatingNode(PropagationNode):
    """subclass that provides inter nodes communication code. both admin and
    gateways are communicating nodes. Edge nodes are not, as they are only
    reachable by volatile SSH connections to execute commands.
    """
    def __init__(self, name, router):
        """instance initialization"""
        PropagationNode.__init__(self, name)
        self.resolver = router

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
            data = msg.decode()
            target = data['target']

            if target in self.children:
                cmd = data['task']
                self._dbg('Execute command %s on %s' % (cmd, target))
            else:
                self.resolver.next_hop(self.name, target).forward(msg)

        elif dst in self.children:
            self.resolver.node(dst).recv_message(msg)

        else:
            self.resolver.next_hop(self.name, dst).forward(msg)

    def dst_invalidate(self, dst):
        """mark a route from self to dst as invalid"""
        self.resolver.mark_unreachable(dst)

class AdminNode(CommunicatingNode):
    """administration node. This kind of node is instanciated only once per
    propagation tree. It is mainly charged to distribute tasks to the directly
    connected gateways, perform retransmissions on failure and gather outputs
    """

class GatewayNode(CommunicatingNode):
    """the gateway nodes are able to forward message to both their children and
    their parent (another gateway node or admin).
    """
    def __init__(self, name, router):
        """
        """
        CommunicatingNode.__init__(self, name, router)
        self.job_counter = 0

    def forward(self, msg):
        """process an incoming message not destinated to us"""
        self._dbg('forwarding msg: <%s>' % str(msg))
        self.send_message(msg)
        self.job_counter += 1

    def recv_message(self, msg):
        """process an incoming message destinated to us"""
        CommunicatingNode.recv_message(self, msg)
        self.job_counter += 1

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
    # TODO : this class might be put in the PropagationTree class
    def __init__(self, fanout, nodes=None):
        """instance initialization"""
        self.nodes_table = nodes or {}
        self.fanout = fanout
        self._unreachable_hosts = NodeSet()
        self._cached_routes = {}

    def node(self, nodename):
        """return a reference on the instance of a node given a node name"""
        try:
            return self.nodes_table[nodename]
        except KeyError:
            return None

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
            raise UnavailableDestinationError(
                'Invalid destination %s, host is unreachable' % dst)

        # is the route already cached?
        nxt_hop = self._cache_lookup(src, dst)
        if nxt_hop is not None:
            return nxt_hop

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
                cached = self._cached_routes.setdefault(dst, {})
                cached[src] = nexthop
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
        # be consulted by the resolution function and during cache access
        self._unreachable_hosts.add(dst)

    def _cache_lookup(self, src, dst):
        """search for already known routes"""
        if self._cached_routes.has_key(dst):
            if self._cached_routes[dst].has_key(src):
                nxt_hop = self._cached_routes[dst][src]
                # does this route has been marked as invalid?
                if nxt_hop.name in self._unreachable_hosts:
                    # delete the entry and fin sth better
                    del self._cached_routes[dst][src]
                elif nxt_hop.job_counter < self.fanout:
                    return nxt_hop
        return None

    def _best_next_hop(self, candidates):
        """find out a good next hop gateway"""
        for host in candidates:
            if host not in self._unreachable_hosts and \
                self.nodes_table[host].job_counter < self.fanout:
                # currently, the first one is the best
                return host

        raise RoutesResolvingError('No valid route to reach requested host')


class PropagationTree:
    """This class represents the complete propagation tree and provides the
    ability to propagate tasks through it.
    """
    def __init__(self):
        """instance initialization"""
        # list of available nodes, available by their name
        self.nodes = {}
        # name of the administration node, at the root of the tree
        self.admin = ''
        # destination nodeset
        self.targets = None
        # selected fanout => maximum arity of the tree
        self.fanout = None

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
        self.fanout = fanout
        router = PropagationTreeRouter(fanout)
        # --- generate one specialized instance per node --- #
        for nodegroup in topology_tree:
            group_key = str(nodegroup.nodeset)
            if nodegroup.parent is None:
                # Admin node (no parents)
                curr = AdminNode(group_key, router)
                curr.children = nodegroup.children_ns()
                self.nodes[group_key] = curr
                self.admin = group_key
            elif nodegroup.children_len() == 0:
                # Edge node (no children)
                ns_util = nodegroup.nodeset & self.targets
                for node in ns_util:
                    node_key = str(node)
                    curr = EdgeNode(node_key)
                    curr.parents = nodegroup.parent.nodeset
                    self.nodes[node_key] = curr
            else:
                # Gateway node (no other possibility)
                for node in nodegroup.nodeset:
                    node_key = str(node)
                    curr = GatewayNode(node_key, router)
                    curr.parents = nodegroup.parent.nodeset
                    curr.children = nodegroup.children_ns()
                    self.nodes[node_key] = curr

        # --- instanciate and return the actual tree --- #
        router.nodes_table = self.nodes

    def execute(self, cmd):
        """execute `cmd' on the nodeset specified at loading"""
        admin = self.nodes[self.admin]
        for node in self.targets:
            msg = PropagationMessage()
            msg.src = admin.name
            msg.add_info('target', node)
            msg.add_info('task', cmd)
            admin.send_message(msg)

class PropagationMessage:
    """message to a node. This is just a stub"""
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

class UnavailableDestinationError(RoutesResolvingError):
    """error raised on trynig to reach a host already marked as unreachable"""


if __name__ == '__main__':
    if len(sys.argv[1]) < 3:
        sys.exit('Usage : %s <filename> <root node>' % sys.argv[0])
    before = time.time()
    parser = TopologyParser()
    parser.load(sys.argv[1])
    admin_hostname = sys.argv[2]
    topology = parser.tree(admin_hostname)
    print '[!] Generating topology tree: %f s' % (time.time() - before)

    before = time.time()
    ptree = PropagationTree()
    ptree.load(topology, 'n[0-10000]', 64)
    print '[!] Loading propagation tree: %f s' % (time.time() - before)

    message = PropagationMessage()
    message.src = admin_hostname
    message.dst = 'STB1564'
    message.add_info('str', 'Hello, world!')

    before = time.time()
    ptree.nodes[admin_hostname].send_message(message)
    print '[!] Sending message through the propagation tree: %f s' \
        % (time.time() - before)

    message.add_info('str', 'Hello, world, again!')

    before = time.time()
    ptree.nodes[admin_hostname].send_message(message)
    print '[!] Sending message through the propagation tree: %f s' \
        % (time.time() - before)

