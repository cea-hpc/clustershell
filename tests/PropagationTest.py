#!/usr/bin/env python
# ClusterShell propagation test suite
# Written by H. Doreau
# $Id$


"""Unit test for Propagation"""

import copy
import sys
import time
import unittest
import tempfile

# profiling imports
import cProfile
#from guppy import hpy
# ---

sys.path.insert(0, '../lib')

from ClusterShell.Propagation import *
from ClusterShell.Topology import TopologyParser
from ClusterShell.NodeSet import NodeSet


def chrono(func):
    def timing(*args):
        start = time.time()
        res = func(*args)
        print "execution time: %f s" % (time.time() - start)
        return res
    return timing


class PropagationTest(unittest.TestCase):
    def setUp(self):
        """generate a sample topology tree"""
        tmpfile = tempfile.NamedTemporaryFile()

        tmpfile.write('[DEFAULT]\n')
        tmpfile.write('admin[0-2]: proxy\n')
        tmpfile.write('proxy: STA[0-400]\n')
        tmpfile.write('STA[0-400]: STB[0-2000]\n')
        tmpfile.write('STB[0-2000]: node[0-11000]\n')

        tmpfile.flush()
        parser = TopologyParser()
        parser.load(tmpfile.name)

        self.topology = parser.tree('admin1')

    def testRouting(self):
        """test basic routing mecanisms"""
        ptree = PropagationTree(self.topology, 'admin1')
        self.assertRaises(RoutesResolvingError, ptree.next_hop, 'admin1')

        self.assertEquals(ptree.next_hop('STA0'), 'proxy')
        self.assertEquals(ptree.next_hop('STB2000'), 'proxy')
        self.assertEquals(ptree.next_hop('node10'), 'proxy')

        ptree = PropagationTree(self.topology, 'proxy')
        self.assertEquals(ptree.next_hop('STB0') in NodeSet('STA[0-4000]'), True)

        ptree = PropagationTree(self.topology, 'STB7')
        self.assertEquals(ptree.next_hop('node500'), 'node500')

        ptree = PropagationTree(self.topology, 'STB7')
        self.assertRaises(RoutesResolvingError, ptree.next_hop, 'foo')
        self.assertRaises(RoutesResolvingError, ptree.next_hop, 'admin1')

        self.assertRaises(RoutesResolvingError, PropagationTree, self.topology, 'bar')

    def testHostRepudiation(self):
        """test marking hosts as unreachable"""
        ptree = PropagationTree(self.topology, 'STA42')

        res1 = ptree.next_hop('node42')
        self.assertEquals(res1 in NodeSet('STB[0-2000]'), True)

        ptree.mark_unreachable(res1)
        self.assertRaises(RoutesResolvingError, ptree.next_hop, res1)

        res2 = ptree.next_hop('node42')
        self.assertEquals(res2 in NodeSet('STB[0-2000]'), True)
        self.assertNotEquals(res1, res2)

    def testRoutingTableGeneration(self):
        """test routing table generation"""
        ptree = PropagationTree(self.topology, 'admin1')
        res = [str(v) for v in ptree.router.table.values()]
        self.assertEquals(res, ['proxy'])

        ptree = PropagationTree(self.topology, 'STA200')
        res = [str(v) for v in ptree.router.table.values()]
        self.assertEquals(res, ['STB[0-2000]'])

    def testFullGateway(self):
        """test router's ability to share the tasks between gateways"""
        ptree = PropagationTree(self.topology, 'admin1')
        ptree.router.fanout = 32
        for node in NodeSet('STB[0-200]'):
            self.assertEquals(ptree.router.next_hop(node), 'proxy')

    def testPropagationDriver(self):
        """test propagation logic"""
        ## --------
        # This test use a tricky topology, whose next hop for any admin node is
        # localhost. This way, the test machine will connect to itself as if it
        # was a remote gateway.
        # Then, instead of talking to a gateway instance, it will load a
        # specifically crafted file, that contains XML messages as those sent by
        # an actual gateway.
        # -----------------------
        tmpfile = tempfile.NamedTemporaryFile()
        tmpfile.write('[DEFAULT]\n')
        tmpfile.write('admin[0-2]: localhost\n')
        tmpfile.write('localhost: node[0-500]\n')

        gwfile = tempfile.NamedTemporaryFile()
        gwfile.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        gwfile.write('<channel src="admin" dst="gateway">\n')
        gwfile.write('<message type="ACK" msgid="0" ack="0"></message>\n')
        gwfile.write('<message type="ACK" msgid="1" ack="1"></message>\n')
        gwfile.write('<message type="ACK" msgid="2" ack="2"></message>\n')
        gwfile.write('<message type="CTL" target="node[0-500]" msgid="3"' \
            ' action="res">UydMaW51eCAyLjYuMTgtOTIuZWw1ICMxIFNNUCBUdWUgQXByIDI5IDEzOjE2OjE1IEVEVCAyMDA4\nIHg4Nl82NCB4ODZfNjQgeDg2XzY0IEdOVS9MaW51eCcKcDEKLg==\n</message>\n')
        gwfile.write('</channel>\n')

        tmpfile.flush()
        gwfile.flush()

        parser = TopologyParser()
        parser.load(tmpfile.name)

        tree = parser.tree('admin1')
        ptree = PropagationTree(tree, 'admin1')

        ptree.invoke_gateway = 'cat %s' % gwfile.name
        ptree.execute('uname -a', 'node[0-500]', 128, 1)

    def testDistributeTasksSimple(self):
        """test dispatch work between several gateways (simple case)"""
        tmpfile = tempfile.NamedTemporaryFile()

        tmpfile.write('[DEFAULT]\n')
        tmpfile.write('admin[0-2]: gw[0-3]\n')
        tmpfile.write('gw[0-1]: node[0-9]\n')
        tmpfile.write('gw[2-3]: node[10-19]\n')

        tmpfile.flush()
        parser = TopologyParser()
        parser.load(tmpfile.name)

        tree = parser.tree('admin1')
        ptree = PropagationTree(tree, 'admin1')
        dist = ptree._distribute(128, NodeSet('node[2-18]'))
        self.assertEquals(str(dist['gw0']), 'node[2-9]')
        self.assertEquals(str(dist['gw2']), 'node[10-18]')

    def testDistributeTasksComplex(self):
        """test dispatch work between several gateways (more complex case)"""
        tmpfile = tempfile.NamedTemporaryFile()

        tmpfile.write('[DEFAULT]\n')
        tmpfile.write('admin[0-2]: gw[0-1]\n')
        tmpfile.write('gw0: n[0-9]\n')
        tmpfile.write('gw1: gwa[0-1]\n')
        tmpfile.write('gwa0: n[10-19]\n')
        tmpfile.write('gwa1: n[20-29]\n')

        tmpfile.flush()
        parser = TopologyParser()
        parser.load(tmpfile.name)

        tree = parser.tree('admin1')
        ptree = PropagationTree(tree, 'admin1')
        dist = ptree._distribute(5, NodeSet('n[0-29]'))
        self.assertEquals(str(dist['gw0']), 'n[0-9]')
        self.assertEquals(str(dist['gw1']), 'n[10-29]')


def main():
    suite = unittest.TestLoader().loadTestsFromTestCase(PropagationTest)
    unittest.TextTestRunner(verbosity=2).run(suite)

if __name__ == '__main__':
    #cProfile.run('main()')
    main()

