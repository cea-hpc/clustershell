#!/usr/bin/env python
# ClusterShell.Topology test suite
# Written by H. Doreau
# $Id$


"""Unit test for Topology"""

import copy
import sys
import time
import unittest
import tempfile

# profiling imports
#import cProfile
#from guppy import hpy
# ---

sys.path.insert(0, '../lib')

from ClusterShell.Topology import *
from ClusterShell.NodeSet import NodeSet


def chrono(func):
    def timing(*args):
        start = time.time()
        res = func(*args)
        print "execution time: %f s" % (time.time() - start)
        return res
    return timing


class TopologyTest(unittest.TestCase):

    @chrono
    def testTopologyGraphGeneration(self):
        """test graph generation"""
        g = TopologyGraph()
        ns1 = NodeSet('nodes[0-5]')
        ns2 = NodeSet('nodes[6-10]')
        g.add_route(ns1, ns2)
        self.assertEqual(g.dest(ns1), ns2)

    @chrono
    def testTopologyGraphNoOverlap(self):
        """test invalid routes detection"""
        g = TopologyGraph()
        admin = NodeSet('admin')
        ns0 = NodeSet('nodes[0-9]')
        ns1 = NodeSet('nodes[10-19]')
        g.add_route(admin, ns0)
        g.add_route(ns0, ns1)
        # Add the same nodeset twice
        ns2 = NodeSet('nodes[20-29]')
        self.assertRaises(InvalidTopologyError, g.add_route, ns2, ns2)
        # Add an already src nodeset to a new dst nodeset
        g.add_route(ns0, ns2)
        # Add the same dst nodeset twice
        self.assertRaises(InvalidTopologyError, g.add_route, ns2, ns1)
        # Add a known src nodeset as a dst nodeset
        self.assertRaises(InvalidTopologyError, g.add_route, ns2, ns0)
        # Add a known dst nodeset as a src nodeset
        ns3 = NodeSet('nodes[30-39]')
        g.add_route(ns1, ns3)
        # Add a subset of a known src nodeset as src
        ns0_sub = NodeSet(','.join(ns0[:3:]))
        ns4 = NodeSet('nodes[40-49]')
        g.add_route(ns0_sub, ns4)
        # Add a subset of a known dst nodeset as src
        ns1_sub = NodeSet(','.join(ns1[:3:]))
        self.assertRaises(InvalidTopologyError, g.add_route, ns4, ns1_sub)
        # Add a subset of a known src nodeset as dst
        self.assertRaises(InvalidTopologyError, g.add_route, ns4, ns0_sub)
        # Add a subset of a known dst nodeset as dst
        self.assertRaises(InvalidTopologyError, g.add_route, ns4, ns1_sub)
        # src <- subset of -> dst
        ns5 = NodeSet('nodes[50-59]')
        ns5_sub = NodeSet(','.join(ns5[:3:]))
        self.assertRaises(InvalidTopologyError, g.add_route, ns5, ns5_sub)
        self.assertRaises(InvalidTopologyError, g.add_route, ns5_sub, ns5)

        #g.to_tree("admin")._display()

        self.assertEqual(g.dest(ns0), (ns1 | ns2))
        self.assertEqual(g.dest(ns1), ns3)
        self.assertEqual(g.dest(ns2), None)
        self.assertEqual(g.dest(ns3), None)
        self.assertEqual(g.dest(ns4), None)
        self.assertEqual(g.dest(ns5), None)
        self.assertEqual(g.dest(ns0_sub), (ns1 | ns2 | ns4))

        g = TopologyGraph()
        root = NodeSet('root')
        ns01 = NodeSet('nodes[0-1]')
        ns23 = NodeSet('nodes[2-3]')
        ns45 = NodeSet('nodes[4-5]')
        ns67 = NodeSet('nodes[6-7]')
        ns89 = NodeSet('nodes[8-9]')

        g.add_route(root, ns01)
        g.add_route(root, ns23 | ns45)
        self.assertRaises(InvalidTopologyError, g.add_route, ns23, ns23)
        self.assertRaises(InvalidTopologyError, g.add_route, ns45, root)
        g.add_route(ns23, ns67)
        g.add_route(ns67, ns89)
        self.assertRaises(InvalidTopologyError, g.add_route, ns89, ns67)
        self.assertRaises(InvalidTopologyError, g.add_route, ns89, ns89)
        self.assertRaises(InvalidTopologyError, g.add_route, ns89, ns23)

        ns_all = NodeSet('root,nodes[0-9]')
        for nodegroup in g.to_tree('root'):
            ns_all.difference_update(nodegroup.nodeset)
        self.assertEqual(len(ns_all), 0)

    @chrono
    def testTopologyGraphBigGroups(self):
        """test adding huge nodegroups in routes"""
        g = TopologyGraph()
        ns0 = NodeSet('nodes[0-10000]')
        ns1 = NodeSet('nodes[12000-23000]')
        g.add_route(ns0, ns1)
        self.assertEqual(g.dest(ns0), ns1)

        ns2 = NodeSet('nodes[30000-35000]')
        ns3 = NodeSet('nodes[35001-45000]')
        g.add_route(ns2, ns3)
        self.assertEqual(g.dest(ns2), ns3)

    @chrono
    def testTopologyGraphManyRoutes(self):
        """test adding 200 routes (400+ nodes)"""
        g = TopologyGraph()

        ns_begin = NodeSet('admin')
        ns_end = NodeSet('nodes[0-1]')
        g.add_route(ns_begin, ns_end)

        for i in xrange(0, 200*2, 2):
            ns_begin = NodeSet('nodes[%d-%d]' % (i, i+1))
            ns_end = NodeSet('nodes[%d-%d]' % (i+2, i+3))
            g.add_route(ns_begin, ns_end)
            self.assertEqual(g.dest(ns_begin), ns_end)

        tree = g.to_tree('admin')
        ns_all = NodeSet('admin,nodes[0-401]')
        ns_tree = NodeSet()
        for nodegroup in tree:
           ns_tree.add(nodegroup.nodeset)
        self.assertEqual(ns_all, ns_tree)

    @chrono
    def testConfigurationParser(self):
        """test configuration parsing"""
        tmpfile = tempfile.NamedTemporaryFile()
        tmpfile.write('# this is a comment\n')
        tmpfile.write('[DEFAULT]\n')
        tmpfile.write('admin: nodes[0-1]\n')
        tmpfile.write('nodes[0-1]: nodes[2-5]\n')
        tmpfile.write('nodes[4-5]: nodes[6-9]\n')
        tmpfile.flush()
        parser = TopologyParser()
        parser.load(tmpfile.name)

        parser.tree('admin')
        ns_all = NodeSet('admin,nodes[0-9]')
        ns_tree = NodeSet()
        for nodegroup in parser.tree('admin'):
           ns_tree.add(nodegroup.nodeset)
        self.assertEqual(ns_all, ns_tree)

    @chrono
    def testConfigurationShortSyntax(self):
        """test short topology specification syntax"""
        tmpfile = tempfile.NamedTemporaryFile()
        tmpfile.write('# this is a comment\n')
        tmpfile.write('[DEFAULT]\n')
        tmpfile.write('admin: nodes[0-9]\n')
        tmpfile.write('nodes[0-3,5]: nodes[10-19]\n')
        tmpfile.write('nodes[4,6-9]: nodes[30-39]\n')
        tmpfile.flush()
        parser = TopologyParser()
        parser.load(tmpfile.name)

        ns_all = NodeSet('admin,nodes[0-19,30-39]')
        ns_tree = NodeSet()
        for nodegroup in parser.tree('admin'):
           ns_tree.add(nodegroup.nodeset)
        self.assertEqual(ns_all, ns_tree)

    @chrono
    def testConfigurationLongSyntax(self):
        """test detailed topology description syntax"""
        tmpfile = tempfile.NamedTemporaryFile()
        tmpfile.write('# this is a comment\n')
        tmpfile.write('[DEFAULT]\n')
        tmpfile.write('admin: proxy\n')
        tmpfile.write('proxy: STA[0-1]\n')
        tmpfile.write('STA0: STB[0-1]\n')
        tmpfile.write('STB0: nodes[0-2]\n')
        tmpfile.write('STB1: nodes[3-5]\n')
        tmpfile.write('STA1: STB[2-3]\n')
        tmpfile.write('STB2: nodes[6-7]\n')
        tmpfile.write('STB3: nodes[8-10]\n')

        tmpfile.flush()
        parser = TopologyParser()
        parser.load(tmpfile.name)

        ns_all = NodeSet('admin,proxy,STA[0-1],STB[0-3],nodes[0-10]')
        ns_tree = NodeSet()
        for nodegroup in parser.tree('admin'):
           ns_tree.add(nodegroup.nodeset)
        self.assertEqual(ns_all, ns_tree)


    @chrono
    def testConfigurationParserDeepTree(self):
        """test a configuration that generates a deep tree"""
        tmpfile = tempfile.NamedTemporaryFile()
        tmpfile.write('# this is a comment\n')
        tmpfile.write('[DEFAULT]\n')
        tmpfile.write('admin: nodes[0-9]\n')

        levels = 15 # how deep do you want the tree to be?
        for i in xrange(0, levels*10, 10):
            line = 'nodes[%d-%d]: nodes[%d-%d]\n' % (i, i+9, i+10, i+19)
            tmpfile.write(line)
        tmpfile.flush()
        parser = TopologyParser()
        parser.load(tmpfile.name)

        ns_all = NodeSet('admin,nodes[0-159]')
        ns_tree = NodeSet()
        for nodegroup in parser.tree('admin'):
           ns_tree.add(nodegroup.nodeset)
        self.assertEqual(ns_all, ns_tree)

    @chrono
    def testConfigurationParserBigTree(self):
        """test configuration parser against big propagation tree"""
        tmpfile = tempfile.NamedTemporaryFile()
        tmpfile.write('# this is a comment\n')
        tmpfile.write('[DEFAULT]\n')
        tmpfile.write('admin: ST[0-4]\n')
        tmpfile.write('ST[0-4]: STA[0-49]\n')
        tmpfile.write('STA[0-49]: nodes[0-10000]\n')
        tmpfile.flush()
        parser = TopologyParser()
        parser.load(tmpfile.name)

        ns_all = NodeSet('admin,ST[0-4],STA[0-49],nodes[0-10000]')
        ns_tree = NodeSet()
        for nodegroup in parser.tree('admin'):
           ns_tree.add(nodegroup.nodeset)
        self.assertEqual(ns_all, ns_tree)
        #print hpy().heap()
        #print hpy().heap().more
        #print hpy().heap().more.more

    @chrono
    def testConfigurationParserConvergentPaths(self):
        """convergent paths detection"""
        tmpfile = tempfile.NamedTemporaryFile()
        tmpfile.write('# this is a comment\n')
        tmpfile.write('[DEFAULT]\n')
        tmpfile.write('fortoy32: fortoy[33-34]\n')
        tmpfile.write('fortoy33: fortoy35\n')
        tmpfile.write('fortoy34: fortoy36\n')
        tmpfile.write('fortoy[35-36]: fortoy37\n')

        tmpfile.flush()
        parser = TopologyParser()
        self.assertRaises(InvalidTopologyError, parser.load, tmpfile.name)


def main():
    suite = unittest.TestLoader().loadTestsFromTestCase(TopologyTest)
    unittest.TextTestRunner(verbosity=2).run(suite)

if __name__ == '__main__':
    #cProfile.run('main()')
    main()

