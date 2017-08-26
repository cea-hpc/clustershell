# ClusterShell.Gateway test suite
# Written by H. Doreau and S. Thiell

"""Unit test for Gateway"""

import os
import sys
import unittest
import tempfile

import logging

sys.path.insert(0, '../lib')

from ClusterShell.Event import EventHandler
from ClusterShell.NodeSet import NodeSet
from ClusterShell.Propagation import PropagationTree
from ClusterShell.Topology import TopologyParser
from TLib import load_cfg, my_node


class DirectHandler(EventHandler):
    """
    Test Direct EventHandler
    """
    def ev_read(self, worker):
        """stdout event"""
        node, buf = worker.last_read()
        print "%s: %s" % (node, buf)

    def ev_error(self, worker):
        """stderr event"""
        node, buf = worker.last_error()
        print "(stderr) %s: %s" % (node, buf)

    def ev_close(self, worker):
        """close event"""
        print "ev_close %s" % worker


class GatewayTest(unittest.TestCase):
    """TestCase for ClusterShell.Gateway module."""

    def testCompletePropagation(self):
        """test a complete command propagation trip"""
        #
        # This test relies on configured parameters (topology2.conf)
        tmpfile = tempfile.NamedTemporaryFile()

        logging.basicConfig(
                level=logging.DEBUG
                )
        logging.debug("STARTING")

        hostname = my_node()
        cfgparser = load_cfg('topology2.conf')
        neighbors = cfgparser.get('CONFIG', 'NEIGHBORS')
        targets = cfgparser.get('CONFIG', 'TARGETS')

        tmpfile.write('[DEFAULT]\n')
        tmpfile.write('%s: %s\n' % (hostname, neighbors))
        tmpfile.write('%s: %s\n' % (neighbors, targets))
        tmpfile.flush()
        parser = TopologyParser()
        parser.load(tmpfile.name)
        tmpfile.close()

        nfs_tmpdir = os.path.expanduser('~/.clustershell/tests/tmp')

        tree = parser.tree(hostname)
        print tree

        ptree = PropagationTree(tree, hostname)
        ptree.upchannel = None
        ptree.edgehandler = DirectHandler()

        ptree.fanout = 20
        ptree.invoke_gateway = \
            'cd %s; PYTHONPATH=../lib python -m ClusterShell/Gateway -Bu' % \
                os.getcwd()
        #print ptree.invoke_gateway

        ## delete remaining files from previous tests
        for filename in os.listdir(nfs_tmpdir):
            if filename.startswith("fortoy"):
                os.remove(os.path.join(nfs_tmpdir, filename))

        dst = NodeSet(targets)
        task = ptree.execute('python -c "import time; print time.time()" > ' + \
                             os.path.join(nfs_tmpdir, '$(hostname)'), dst, 20)
        #task = ptree.execute('sleep 2; echo "output from $(hostname)"', \
        #                      dst, 20)
        self.assert_(task)

        res = NodeSet()
        times = []
        for filename in os.listdir(nfs_tmpdir):
            for k in dst:
                if filename.startswith(str(k)):
                    res.add(k)
                    fd = open(os.path.join(nfs_tmpdir, filename))
                    times.append(float(fd.read()))
                    fd.close()

        self.assertEquals(str(res), str(dst))
        print "Complete propagation time: %fs for %d nodes" % \
                (max(times) - min(times), len(dst))
