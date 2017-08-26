# ClusterShell propagation test suite
# Written by H. Doreau

"""Unit test for Propagation"""

import os
import sys
import unittest
import tempfile

# profiling imports
#import cProfile
#from guppy import hpy
# ---

sys.path.insert(0, '../lib')

from ClusterShell.Propagation import *
from ClusterShell.NodeSet import NodeSet
from ClusterShell.Topology import TopologyParser
from ClusterShell.Worker.Tree import WorkerTree
from ClusterShell.Task import task_self

from TLib import load_cfg, my_node


class PropagationTest(unittest.TestCase):
    def setUp(self):
        """generate a sample topology tree"""
        tmpfile = tempfile.NamedTemporaryFile()

        tmpfile.write('[Main]\n')
        tmpfile.write('admin[0-2]: proxy\n')
        tmpfile.write('proxy: STA[0-400]\n')
        tmpfile.write('STA[0-400]: STB[0-2000]\n')
        tmpfile.write('STB[0-2000]: node[0-11000]\n')

        tmpfile.flush()
        parser = TopologyParser()
        parser.load(tmpfile.name)

        self.topology = parser.tree('admin1')

        # XXX
        os.environ["PYTHONPATH"] = "%s/../lib" % os.getcwd()

    def testRouting(self):
        """test basic routing mecanisms"""
        ptr = PropagationTreeRouter('admin1', self.topology)
        self.assertRaises(RouteResolvingError, ptr.next_hop, 'admin1')

        self.assertEquals(ptr.next_hop('STA0'), 'proxy')
        self.assertEquals(ptr.next_hop('STB2000'), 'proxy')
        self.assertEquals(ptr.next_hop('node10'), 'proxy')

        ptr = PropagationTreeRouter('proxy', self.topology)
        self.assert_(ptr.next_hop('STB0') in NodeSet('STA[0-4000]'))

        ptr = PropagationTreeRouter('STB7', self.topology)
        self.assertEquals(ptr.next_hop('node500'), 'node500')

        ptr = PropagationTreeRouter('STB7', self.topology)
        self.assertRaises(RouteResolvingError, ptr.next_hop, 'foo')
        self.assertRaises(RouteResolvingError, ptr.next_hop, 'admin1')

        self.assertRaises(RouteResolvingError, PropagationTreeRouter, 'bar', self.topology)

    def testHostRepudiation(self):
        """test marking hosts as unreachable"""
        ptr = PropagationTreeRouter('STA42', self.topology)

        res1 = ptr.next_hop('node42')
        self.assertEquals(res1 in NodeSet('STB[0-2000]'), True)

        ptr.mark_unreachable(res1)
        self.assertRaises(RouteResolvingError, ptr.next_hop, res1)

        res2 = ptr.next_hop('node42')
        self.assertEquals(res2 in NodeSet('STB[0-2000]'), True)
        self.assertNotEquals(res1, res2)

    def testRoutingTableGeneration(self):
        """test routing table generation"""
        ptr = PropagationTreeRouter('admin1', self.topology)
        res = [str(v) for v in ptr.table.values()]
        self.assertEquals(res, ['proxy'])

        ptr = PropagationTreeRouter('STA200', self.topology)
        res = [str(v) for v in ptr.table.values()]
        self.assertEquals(res, ['STB[0-2000]'])

    def testFullGateway(self):
        """test router's ability to share the tasks between gateways"""
        ptr = PropagationTreeRouter('admin1', self.topology)
        ptr.fanout = 32
        for node in NodeSet('STB[0-200]'):
            self.assertEquals(ptr.next_hop(node), 'proxy')

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
        tmpfile.write('[Main]\n')
        tmpfile.write('admin[0-2]: localhost\n')
        tmpfile.write('localhost: node[0-500]\n')

        gwfile = tempfile.NamedTemporaryFile()
        gwfile.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        gwfile.write('<channel>\n')
        gwfile.write('<message type="ACK" msgid="0" ack="0"></message>\n')
        gwfile.write('<message type="ACK" msgid="1" ack="1"></message>\n')
        gwfile.write('<message type="ACK" msgid="2" ack="2"></message>\n')
        gwfile.write('<message type="CTL" target="node[0-500]" msgid="3" ' \
            'action="res">' \
            'UydMaW51eCAyLjYuMTgtOTIuZWw1ICMxIFNNUCBUdWUgQXByIDI5IDEzOjE2OjE1IEVEVCAyMDA4' \
            'IHg4Nl82NCB4ODZfNjQgeDg2XzY0IEdOVS9MaW51eCcKcDEKLg==' \
            '</message>\n')
        gwfile.write('</channel>\n')

        tmpfile.flush()
        gwfile.flush()

        parser = TopologyParser()
        parser.load(tmpfile.name)

        """
        XXX need a way to override the way the gateway is remotely launch
        """
        raise RuntimeError

        """
        ptree = PropagationTree(tree, 'admin1')

        ptree.invoke_gateway = 'cat %s' % gwfile.name
        ptree.execute('uname -a', 'node[0-500]', 128, 1)
        """

    def testDistributeTasksSimple(self):
        """test dispatch work between several gateways (simple case)"""
        tmpfile = tempfile.NamedTemporaryFile()

        tmpfile.write('[Main]\n')
        tmpfile.write('admin[0-2]: gw[0-3]\n')
        tmpfile.write('gw[0-1]: node[0-9]\n')
        tmpfile.write('gw[2-3]: node[10-19]\n')

        tmpfile.flush()
        parser = TopologyParser()
        parser.load(tmpfile.name)

        tree = parser.tree('admin1')
        wtree = WorkerTree('dummy', None, 0, command=':', topology=tree,
                           newroot='admin1')
        dist = wtree._distribute(128, NodeSet('node[2-18]'))
        self.assertEquals(dist['gw0'], NodeSet('node[2-8/2]'))
        self.assertEquals(dist['gw2'], NodeSet('node[10-18/2]'))

    def testDistributeTasksComplex(self):
        """test dispatch work between several gateways (more complex case)"""
        tmpfile = tempfile.NamedTemporaryFile()

        tmpfile.write('[Main]\n')
        tmpfile.write('admin[0-2]: gw[0-1]\n')
        tmpfile.write('gw0: n[0-9]\n')
        tmpfile.write('gw1: gwa[0-1]\n')
        tmpfile.write('gwa0: n[10-19]\n')
        tmpfile.write('gwa1: n[20-29]\n')

        tmpfile.flush()
        parser = TopologyParser()
        parser.load(tmpfile.name)

        tree = parser.tree('admin1')
        wtree = WorkerTree('dummy', None, 0, command=':', topology=tree,
                           newroot='admin1')
        dist = wtree._distribute(5, NodeSet('n[0-29]'))
        self.assertEquals(str(dist['gw0']), 'n[0-9]')
        self.assertEquals(str(dist['gw1']), 'n[10-29]')

    def testExecuteTasksOnNeighbors(self):
        """test execute tasks on directly connected machines"""
        tmpfile = tempfile.NamedTemporaryFile()

        myhost = my_node()
        cfgparser = load_cfg('topology1.conf')
        neighbor = cfgparser.get('CONFIG', 'NEIGHBOR')
        gateways = cfgparser.get('CONFIG', 'GATEWAYS')
        targets = cfgparser.get('CONFIG', 'TARGETS')

        tmpfile.write('[Main]\n')
        tmpfile.write('%s: %s\n' % (myhost, neighbor))
        tmpfile.write('%s: %s\n' % (neighbor, gateways))
        tmpfile.write('%s: %s\n' % (gateways, targets))
        tmpfile.flush()
        parser = TopologyParser()
        parser.load(tmpfile.name)

        tree = parser.tree(myhost)
        wtree = WorkerTree(NodeSet(targets), None, 0, command='echo ok',
                           topology=tree, newroot=myhost)
        # XXX Need to propagate topology for this to work in tests
        raise RuntimeError

        task = task_self()
        task.set_info('debug', True)
        task.schedule(wtree)
        task.resume()

        for buf, nodes in task.iter_buffers():
            print '-' * 15
            print str(nodes)
            print '-' * 15
            print buf
            print ''
