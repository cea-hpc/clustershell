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
ClusterShell topology module

This module contains the network topology parser and its related classes.
These classes are used to build a topology tree of nodegroups according to the
configuration file.

This file must be written using the following syntax:

# for now only DEFAULT tree is taken in account
[DEFAULT]
admin: first_level_gateways[0-10]
first_level_gateways[0-10]: second_level_gateways[0-100]
second_level_gateways[0-100]: nodes[0-2000]
...
"""

import sys
import signal
import ConfigParser

from ClusterShell.NodeSet import NodeSet


class TopologyNodeGroup:
    """Base element for in-memory representation of the propagation tree.
    Contains a nodeset, with parent-children relationships with other
    instances.
    """
    def __init__(self, nodeset):
        """
        """
        assert isinstance(nodeset, NodeSet)
        assert len(nodeset) > 0

        # Base nodeset
        self.nodeset = nodeset
        # Parent TopologyNodeGroup (TNG) instance
        self.parent = None
        # List of children TNG instances
        self._children = []
        self._children_len = 0
        # provided for convenience
        self._children_ns = NodeSet()

    def printable_subtree(self, prefix=''):
        """recursive method that returns a printable version the subtree from
        the current node with a nice presentation
        """
        res = ''

        # TODO : get rid of recursivity
        if self.parent is None:
            # root
            res = '%s\n' % str(self.nodeset)
        elif self.parent.parent is None:
            # first level
            res = '|_ %s\n' % str(self.nodeset)
        else:
            # deepest levels...
            if not self.parent._is_last():
                prefix += '|  '
            else:
                # fix last line
                prefix += '   '
            res = '%s|_ %s\n' % (prefix, str(self.nodeset))
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
        self._children_ns.add(child.nodeset)

    def clear_child(self, child, strict=False):
        """remove a child"""
        try:
            self._children.remove(child)
            self._children_ns.difference_update(child.nodeset)
        except ValueError:
            if strict:
                raise

    def clear_children(self):
        """delete all children"""
        self._children = []
        self._children_ns = NodeSet()

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
        return len(self._children_ns)

    def _is_last(self):
        """used to display the subtree: we won't prefix the line the same way if
        the current instance is the last child of the children list of its
        parent.
        """
        # Root node, not concerned
        if self.parent is None:
            return True
        return self.parent._children[-1::][0] == self

    def __str__(self):
        """printable representation of the nodegroup"""
        if self.parent is None:
            parent_str = ''
        else:
            parent_str = '%s -> ' % str(self.parent.nodeset)
        ch_str = ','.join([str(ch.nodeset) for ch in self._children])

        return '%s%s -> <%s>' % ( parent_str, str(self.nodeset), ch_str )

class TopologyTree:
    """represent a simplified network topology as a tree of machines to use to
    connect to other ones
    """
    class TreeIterator:
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
        """
        """
        self.root = None
        self.groups = []

    def load(self, rootnode):
        """
        """
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
            return ''
        return self.root.printable_subtree()

class TopologyRoute:
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

    def update_union(self, other):
        """update the route by adding both source and destination nodes of
        another route to current instance
        """
        self.src.add(other.src)
        self.dst.add(other.dst)

    def __str__(self):
        """printable representation"""
        return '%s -> %s' % (str(self.src), str(self.dst))

class TopologyRoutingTable:
    """This class provides a convenient way to store and manage topology
    routes
    """
    def __init__(self):
        """
        """
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

class TopologyGraph:
    """represent a complete network topology by storing every "can reach"
    relations between nodes.
    """
    def __init__(self):
        """
        """
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
        """return the current graph out using <src> -> <dst> relations"""
        if len(self._nodegroups) == 0:
            return self._routing.__str__()
        else:
            return '\n'.join(['%s: %s' % (str(k), str(v)) for k, v in \
                self._nodegroups.iteritems()])

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
            uniq = route.dst - aggregated_src
            if len(uniq) > 0:
                self._nodegroups[str(uniq)] = TopologyNodeGroup(uniq)

        # add the parent <--> children relationships
        for nodegroup in self._nodegroups.itervalues():
            dst_ns = self._routing.connected(nodegroup.nodeset)
            if dst_ns is not None:
                for child in self._nodegroups.itervalues():
                    if child.nodeset in dst_ns:
                        nodegroup.add_child(child)

    def _validate(self, root):
        """ensure that the graph is valid for conversion to tree"""
        assert len(self._nodegroups) != 0

        # ensure that every node is reachable
        src_all = self._routing.aggregated_src
        dst_all = self._routing.aggregated_dst

        # every node is a destination, appart the root
        root_candidates = src_all - dst_all
        if root not in root_candidates:
            raise TopologyError('"%s" is not a valid root node!' % root)
        self._root = root

        # if several root are available, then remove the unused ones
        try:
            root_grp = self._nodegroups[str(root_candidates)]
            root_grp.nodeset = NodeSet(root)
            del self._nodegroups[str(root_candidates)]
            self._nodegroups[root] = root_grp
        except KeyError:
            raise TopologyError('Invalid topology or specification!')

class TopologyParser(ConfigParser.ConfigParser):
    """This class offers a way to interpret network topologies supplied under
    the form :

    # Comment
    <these machines> : <can reach these ones>
    """
    def __init__(self):
        """instance wide variables initialization"""
        ConfigParser.ConfigParser.__init__(self)
        self.optionxform = str # case sensitive parser

        self._topology = {}
        self._graph = None
        self._tree = None

    def load(self, filename):
        """read a given topology configuration file and store the results in
        self._routes. Then build a propagation tree.
        """
        if self.read(filename) == []:
            raise TopologyError(
                'Invalid configuration file: %s' % filename)
        self._topology = self.defaults()
        self._build_graph()

    def _build_graph(self):
        """build a network topology graph according to the information we got
        from the configuration file.
        """
        self._graph = TopologyGraph()
        for k, v in self._topology.iteritems():
            src = NodeSet(k)
            dst = NodeSet(v)
            self._graph.add_route(src, dst)

    def graph(self):
        """return the loaded graph or None if graph generation has not been
        done yet
        """
        return self._graph

    def tree(self, root, force_rebuild=False):
        """Return a previously generated propagation tree or build it if
        required. As rebuilding tree can be quite expensive, once built, the
        propagation tree is cached. you can force a re-generation using the
        optionnal `force_rebuild' parameter.
        """
        if self._tree is None or force_rebuild:
            self._tree = self._graph.to_tree(root)
        return self._tree

class TopologyError(Exception):
    """topology parser error to report invalid configurations or parsing
    errors
    """


def _main(args):
    """Main script function"""
    if len(args) < 2:
        sys.exit(__doc__)
    parser = TopologyParser()
    parser.load(args[1])
    try:
        admin = sys.argv[2]
    except IndexError:
        import socket
        admin = socket.gethostname().split('.')[0]
    print parser.tree(admin)


if __name__ == '__main__':
    try:
        _main(sys.argv)
    except KeyboardInterrupt:
        sys.exit(128 + signal.SIGINT)

