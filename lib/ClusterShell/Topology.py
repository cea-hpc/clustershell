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
ClusterShell topology module

This module contains the network topology parser and its related
classes. These classes are used to build a topology tree of nodegroups
according to the configuration file.

This file must be written using the following syntax:

# for now only [routes] tree is taken in account:
[routes]
admin: first_level_gateways[0-10]
first_level_gateways[0-10]: second_level_gateways[0-100]
second_level_gateways[0-100]: nodes[0-2000]
...
"""

import ConfigParser

from ClusterShell.NodeSet import NodeSet


class TopologyError(Exception):
    """topology parser error to report invalid configurations or parsing
    errors
    """

class TopologyNodeGroup(object):
    """Base element for in-memory representation of the propagation tree.
    Contains a nodeset, with parent-children relationships with other
    instances.
    """
    def __init__(self, nodeset=None):
        """initialize a new TopologyNodeGroup instance."""
        # Base nodeset
        self.nodeset = nodeset
        # Parent TopologyNodeGroup (TNG) instance
        self.parent = None
        # List of children TNG instances
        self._children = []
        self._children_len = 0
        # provided for convenience
        self._children_ns = None

    def printable_subtree(self, prefix=''):
        """recursive method that returns a printable version the subtree from
        the current node with a nice presentation
        """
        res = ''
        # For now, it is ok to use a recursive method here as we consider that
        # tree depth is relatively small.
        if self.parent is None:
            # root
            res = '%s\n' % str(self.nodeset)
        elif self.parent.parent is None:
            # first level
            if not self._is_last():
                res = '|- %s\n' % str(self.nodeset)
            else:
                res = '`- %s\n' % str(self.nodeset)
        else:
            # deepest levels...
            if not self.parent._is_last():
                prefix += '|  '
            else:
                # fix last line
                prefix += '   '
            if not self._is_last():
                res = '%s|- %s\n' % (prefix, str(self.nodeset))
            else:
                res = '%s`- %s\n' % (prefix, str(self.nodeset))
        # perform recursive calls to print out every node
        for child in self._children:
            res += child.printable_subtree(prefix)
        return res

    def add_child(self, child):
        """add a child to the children list and define the current instance as
        its parent
        """
        assert isinstance(child, TopologyNodeGroup)

        if child in self._children:
            return
        child.parent = self
        self._children.append(child)
        if self._children_ns is None:
            self._children_ns = NodeSet()
        self._children_ns.add(child.nodeset)

    def clear_child(self, child, strict=False):
        """remove a child"""
        try:
            self._children.remove(child)
            self._children_ns.difference_update(child.nodeset)
            if len(self._children_ns) == 0:
                self._children_ns = None
        except ValueError:
            if strict:
                raise

    def clear_children(self):
        """delete all children"""
        self._children = []
        self._children_ns = None

    def children(self):
        """get the children list"""
        return self._children

    def children_ns(self):
        """return the children as a nodeset"""
        return self._children_ns

    def children_len(self):
        """returns the number of children as the sum of the size of the
        children's nodeset
        """
        if self._children_ns is None:
            return 0
        else:
            return len(self._children_ns)

    def _is_last(self):
        """used to display the subtree: we won't prefix the line the same way if
        the current instance is the last child of the children list of its
        parent.
        """
        return self.parent._children[-1::][0] == self

    def __str__(self):
        """printable representation of the nodegroup"""
        return '<TopologyNodeGroup (%s)>' % str(self.nodeset)

class TopologyTree(object):
    """represent a simplified network topology as a tree of machines to use to
    connect to other ones
    """
    class TreeIterator(object):
        """efficient tool for tree-traversal"""
        def __init__(self, tree):
            """we do simply manage a stack with the remaining nodes"""
            self._stack = [tree.root]

        def next(self):
            """return the next node in the stack or raise a StopIteration
            exception if the stack is empty
            """
            if len(self._stack) > 0 and self._stack[0] is not None:
                node = self._stack.pop()
                self._stack += node.children()
                return node
            else:
                raise StopIteration()

    def __init__(self):
        """initialize a new TopologyTree instance."""
        self.root = None
        self.groups = []

    def load(self, rootnode):
        """load topology tree"""
        self.root = rootnode

        stack = [rootnode]
        while len(stack) > 0:
            curr = stack.pop()
            self.groups.append(curr)
            if curr.children_len() > 0:
                stack += curr.children()

    def __iter__(self):
        """provide an iterator on the tree's elements"""
        return TopologyTree.TreeIterator(self)

    def __str__(self):
        """printable representation of the tree"""
        if self.root is None:
            return '<TopologyTree instance (empty)>'
        return self.root.printable_subtree()

    def find_nodegroup(self, node):
        """Find TopologyNodeGroup from given node (helper to find new root)"""
        for group in self.groups:
            if node in group.nodeset:
                return group
        raise TopologyError('TopologyNodeGroup not found for node %s' % node)

    def inner_node_count(self):
        """helper to get inner node count (root and gateway nodes)"""
        return sum(len(group.nodeset) for group in self.groups
                                      if group.children_len() > 0)

    def leaf_node_count(self):
        """helper to get leaf node count"""
        return sum(len(group.nodeset) for group in self.groups
                                      if group.children_len() == 0)

class TopologyRoute(object):
    """A single route between two nodesets"""
    def __init__(self, src_ns, dst_ns):
        """both src_ns and dst_ns are expected to be non-empty NodeSet
        instances
        """
        self.src = src_ns
        self.dst = dst_ns
        if len(src_ns & dst_ns) != 0:
            raise TopologyError(
                'Source and destination nodesets overlap')

    def dest(self, nodeset=None):
        """get the route's destination. The optionnal argument serves for
        convenience and provides a way to use the method for a subset of the
        whole source nodeset
        """
        if nodeset is None or nodeset in self.src:
            return self.dst
        else:
            return None

    def __str__(self):
        """printable representation"""
        return '%s -> %s' % (str(self.src), str(self.dst))

class TopologyRoutingTable(object):
    """This class provides a convenient way to store and manage topology
    routes
    """
    def __init__(self):
        """Initialize a new TopologyRoutingTable instance."""
        self._routes = []
        self.aggregated_src = NodeSet()
        self.aggregated_dst = NodeSet()

    def add_route(self, route):
        """add a new route to the table. The route argument is expected to be a
        TopologyRoute instance
        """
        if self._introduce_circular_reference(route):
            raise TopologyError(
                'Loop detected! Cannot add route %s' % str(route))
        if self._introduce_convergent_paths(route):
            raise TopologyError(
                'Convergent path detected! Cannot add route %s' % str(route))

        self._routes.append(route)

        self.aggregated_src.add(route.src)
        self.aggregated_dst.add(route.dst)

    def connected(self, src_ns):
        """find out and return the aggregation of directly connected children
        from src_ns.
        Argument src_ns is expected to be a NodeSet instance. Result is returned
        as a NodeSet instance
        """
        next_hop = NodeSet.fromlist([dst for dst in \
            [route.dest(src_ns) for route in self._routes] if dst is not None])
        if len(next_hop) == 0:
            return None
        return next_hop

    def __str__(self):
        """printable representation"""
        return '\n'.join([str(route) for route in self._routes])

    def __iter__(self):
        """return an iterator over the list of rotues"""
        return iter(self._routes)

    def _introduce_circular_reference(self, route):
        """check whether the last added route adds a topology loop or not"""
        current_ns = route.dst
        # iterate over the destinations until we find None or we come back on
        # the src
        while True:
            _dest = self.connected(current_ns)
            if _dest is None or len(_dest) == 0:
                return False
            if len(_dest & route.src) != 0:
                return True
            current_ns = _dest

    def _introduce_convergent_paths(self, route):
        """check for undesired convergent paths"""
        for known_route in self._routes:
            # source cannot be a superset of an already known destination
            if route.src > known_route.dst:
                return True
            # same thing...
            if route.dst < known_route.src:
                return True
            # two different nodegroups cannot point to the same one
            if len(route.dst & known_route.dst) != 0 \
                and route.src != known_route.src:
                return True
        return False

class TopologyGraph(object):
    """represent a complete network topology by storing every "can reach"
    relations between nodes.
    """
    def __init__(self):
        """initialize a new TopologyGraph instance."""
        self._routing = TopologyRoutingTable()
        self._nodegroups = {}
        self._root = ''

    def add_route(self, src_ns, dst_ns):
        """add a new route from src nodeset to dst nodeset. The destination
        nodeset must not overlap with already known destination nodesets
        (otherwise a TopologyError is raised)
        """
        assert isinstance(src_ns, NodeSet)
        assert isinstance(dst_ns, NodeSet)

        #print 'adding %s -> %s' % (str(src_ns), str(dst_ns))
        self._routing.add_route(TopologyRoute(src_ns, dst_ns))

    def dest(self, from_nodeset):
        """return the aggregation of the destinations for a given nodeset"""
        return self._routing.connected(from_nodeset)

    def to_tree(self, root):
        """convert the routing table to a topology tree of nodegroups"""
        # convert the routing table into a table of linked TopologyNodeGroup's
        self._routes_to_tng()
        # ensure this is a valid pseudo-tree
        self._validate(root)
        tree = TopologyTree()
        tree.load(self._nodegroups[self._root])
        return tree

    def __str__(self):
        """printable representation of the graph"""
        res = '<TopologyGraph>\n'
        res += '\n'.join(['%s: %s' % (str(k), str(v)) for k, v in \
            self._nodegroups.iteritems()])
        return res

    def _routes_to_tng(self):
        """convert the routing table into a graph of TopologyNodeGroup
        instances. Loops are not very expensive here as the number of routes
        will always be much lower than the number of nodes.
        """
        # instanciate nodegroups as biggest groups of nodes sharing both parent
        # and destination
        aggregated_src = self._routing.aggregated_src
        for route in self._routing:
            self._nodegroups[str(route.src)] = TopologyNodeGroup(route.src)
            # create a nodegroup for the destination if it is a leaf group.
            # Otherwise, it will be created as src for another route
            leaf = route.dst - aggregated_src
            if len(leaf) > 0:
                self._nodegroups[str(leaf)] = TopologyNodeGroup(leaf)

        # add the parent <--> children relationships
        for group in self._nodegroups.itervalues():
            dst_ns = self._routing.connected(group.nodeset)
            if dst_ns is not None:
                for child in self._nodegroups.itervalues():
                    if child.nodeset in dst_ns:
                        group.add_child(child)

    def _validate(self, root):
        """ensure that the graph is valid for conversion to tree"""
        if len(self._nodegroups) == 0:
            raise TopologyError("No route found in topology definition!")

        # ensure that every node is reachable
        src_all = self._routing.aggregated_src
        dst_all = self._routing.aggregated_dst

        res = [(k, v) for k, v in self._nodegroups.items() if root in v.nodeset]
        if len(res) > 0:
            kgroup, group = res[0]
            del self._nodegroups[kgroup]
            self._nodegroups[root] = group
        else:
            raise TopologyError('"%s" is not a valid root node!' % root)

        self._root = root

class TopologyParser(ConfigParser.ConfigParser):
    """This class offers a way to interpret network topologies supplied under
    the form :

    # Comment
    <these machines> : <can reach these ones>
    """
    def __init__(self, filename=None):
        """instance wide variables initialization"""
        ConfigParser.ConfigParser.__init__(self)
        self.optionxform = str # case sensitive parser

        self._topology = {}
        self.graph = None
        self._tree = None

        if filename:
            self.load(filename)

    def load(self, filename):
        """read a given topology configuration file and store the results in
        self._routes. Then build a propagation tree.
        """
        try:
            self.read(filename)
            if self.has_section("routes"):
                self._topology = self.items("routes")
            else:
                # compat routes section [deprecated since v1.7]
                self._topology = self.items("Main")
        except ConfigParser.Error:
            raise TopologyError(
                'Invalid configuration file: %s' % filename)
        self._build_graph()

    def _build_graph(self):
        """build a network topology graph according to the information we got
        from the configuration file.
        """
        self.graph = TopologyGraph()
        for src, dst in self._topology:
            self.graph.add_route(NodeSet(src), NodeSet(dst))

    def tree(self, root, force_rebuild=False):
        """Return a previously generated propagation tree or build it if
        required. As rebuilding tree can be quite expensive, once built,
        the propagation tree is cached. you can force a re-generation
        using the optionnal `force_rebuild' parameter.
        """
        if self._tree is None or force_rebuild:
            self._tree = self.graph.to_tree(root)
        return self._tree

