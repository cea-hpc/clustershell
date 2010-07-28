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
        self._tasks = deque()
        # parent & children nodesets
        self.parents = None
        self.children = None

    def _dbg(self, msg):
        """debug method: print sth out"""
        print '%s: %s' % (self.name, msg)
        #pass

    def __str__(self):
        """printable representation of the node"""
        return self.name

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
        if msg['dst'] != self.name:
            raise InvalidMessageError(
                'Received message at %s while destination set for %s' \
                % (self.name, msg['dst']))

        self._dbg('received message from <%s>: %s' % (msg['src'] or
            'anonymous', msg['str']))

    def send_message(self, msg):
        """send a message to a directly connected node or to the next hop
        gateway for forwarding
        """
        try:
            dst = msg['dst']
        except KeyError:
            raise InvalidMessageError('Mandatory destination field not set')

        if dst in self.children:
            self.resolver.node(dst).recv_message(msg)
        else:
            self.resolver.next_hop(self.name, dst).forward(msg)

    def dst_invalidate(self, dst):
        """mark a route from self to dst as invalid"""
        self.resolver.route_invalidate(self.name, dst)

class AdminNode(CommunicatingNode):
    """
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
        """
        """
        self._dbg('forwarding msg: <%s> to %s' % (msg, msg['dst']))
        self.send_message(msg)

    def recv_message(self, msg):
        """
        """
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
    # TODO : this might be put in the PropagationTree class
    def __init__(self, nodes=None):
        """instance initialization"""
        self.nodes_table = nodes or {}
        self._invalid_routes = {}
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
        if not self.nodes_table.has_key(src) or not \
            self.nodes_table.has_key(dst):
            raise RoutesResolvingError('Invalid parameters %s -> %s' % (src,
                dst))

        # is the route already cached?
        if self._cached_routes.has_key(dst):
            if self._cached_routes[dst].has_key(src):
                return self._cached_routes[dst][src]

        # otherwise we'll find it out...
        src_inst = self.nodes_table[src]
        dst_current = dst
        while True:
            # start from the destination for efficiency
            dst_inst = self.nodes_table[dst_current]
            ng = NodeSet.fromlist(dst_inst.parents)
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
                dst_current = ng[0]

    def route_invalidate(self, src, dst):
        """mark the route from src to dst as invalid and don't announce it
        anymore
        """
        # TODO : update the cache!!
        entry = self._invalid_routes.setdefault(dst, NodeSet())
        entry.add(src)

    def _best_next_hop(self, candidates):
        """
        """
        sorted_candidates = sorted(candidates,
            key=lambda x: self.nodes_table[x].job_counter)
        return sorted_candidates[0]

class PropagationTree:
    """
    """
    def __init__(self, nodes=None):
        """
        """
        self.nodes = nodes

    def __str__(self):
        """
        """
        return '\n'.join(['%s: %s' % (str(k), str(v)) for k, v in
            self.nodes.iteritems()])

    def load(self, topology_tree, nodeset, fanout):
        """load data from a previously generated topology tree, a destination
        nodeset and the selected fanout.
        """
        self.nodes = {}
        dst_nodeset = NodeSet(nodeset)
        router = PropagationTreeRouter()
        # --- generate one specialized instance per node --- #
        for nodegroup in topology_tree:
            group_key = str(nodegroup.nodeset)
            if nodegroup.parent is None:
                curr = AdminNode(group_key, router)
                curr.children = nodegroup.children_ns()
                self.nodes[group_key] = curr
            elif nodegroup.children_len() == 0:
                ns_util = nodegroup.nodeset & dst_nodeset
                for node in ns_util:
                    node_key = str(node)
                    curr = EdgeNode(node_key)
                    curr.parents = nodegroup.parent.nodeset
                    self.nodes[node_key] = curr
            else:
                for node in nodegroup.nodeset:
                    node_key = str(node)
                    curr = GatewayNode(node_key, router)
                    curr.parents = nodegroup.parent.nodeset
                    curr.children = nodegroup.children_ns()
                    self.nodes[node_key] = curr

        # --- instanciate and return the actual tree --- #
        router.nodes_table = self.nodes

class RoutesResolvingError(Exception):
    """error raised on invalid conditions during routing operations"""

class InvalidMessageError(Exception):
    """error raised on performing operations on invalid messages"""

class PropagationMessage:
    """message to a node. This is just a stub"""
    def __init__(self):
        """
        """
        self._infos = {}

    def __getitem__(self, i):
        """
        """
        try:
            return self._infos[i]
        except KeyError:
            return None

    def __setitem__(self, i, y):
        """
        """
        self._infos[i] = y

    def __str__(self):
        """printable summary of the message"""
        return ', '.join(['%s: %s' % (k, str(v)) for k, v in \
            self._infos.iteritems()])


if __name__ == '__main__':
    if len(sys.argv[1]) < 3:
        sys.exit('Usage : %s <filename> <root node>' % sys.argv[0])
    before = time.time()
    parser = TopologyParser()
    parser.load(sys.argv[1])
    admin = sys.argv[2]
    topology = parser.tree(admin)
    print '[!] Generating topology tree: %f s' % (time.time() - before)

    before = time.time()
    ptree = PropagationTree()
    ptree.load(topology, 'n[0-10000]', 64)
    print '[!] Loading propagation tree: %f s' % (time.time() - before)

    message = PropagationMessage()
    message['src'] = admin
    message['dst'] = 'STB1564'
    message['str'] = 'Hello, world!'

    before = time.time()
    ptree.nodes[admin].send_message(message)
    print '[!] Sending message through the propagation tree: %f s' \
        % (time.time() - before)

    message['str'] = 'Hello, world, again!'

    before = time.time()
    ptree.nodes[admin].send_message(message)
    print '[!] Sending message through the propagation tree: %f s' \
        % (time.time() - before)

