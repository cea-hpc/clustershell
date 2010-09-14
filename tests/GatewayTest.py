#!/usr/bin/env python
# ClusterShell.Gateway test suite
# Written by H. Doreau
# $Id$


"""Unit test for Gateway"""

import os
import sys
import unittest
import socket
import tempfile

sys.path.insert(0, '../lib')

from ClusterShell.Task import task_self
from ClusterShell.NodeSet import NodeSet
from ClusterShell.Topology import TopologyParser
from ClusterShell.Propagation import PropagationTree


class GatewayTest(unittest.TestCase):
    def testCompletePropagation(self):
        """test a complete command propagation trip"""
        #
        # This test relies on hardcoded parameters (topology, path...)
        # We have to find something more generic and reliable to efficiently
        # test the gateway module.
        ##
        tmpfile = tempfile.NamedTemporaryFile()

        hostname = socket.gethostname().split('.')[0]

        # XXX hardcoded topology!
        tmpfile.write('[DEFAULT]\n')
        tmpfile.write('%s: fortoy[34-35]\n' % hostname)
        tmpfile.write('fortoy[34-35]: fortoy[83-103,112-130]\n')

        tmpfile.flush()
        parser = TopologyParser()
        parser.load(tmpfile.name)

        tmpfile.close()

        # XXX hardcoded path!
        TEST_DIR = os.path.expanduser('~/tmp/')

        tree = parser.tree(hostname)
        ptree = PropagationTree(tree)
        ptree.fanout = 64
        # XXX hardcoded path!
        ptree.invoke_gateway = 'cd clustershell/branches/exp-2.0/tests; python -m ClusterShell/Gateway'

        ## delete remaining files from previous tests
        for filename in os.listdir(TEST_DIR):
            if filename.startswith("fortoy"):
                os.remove(TEST_DIR + filename)

        dst = NodeSet('fortoy[83-103,112-130]')
        task = ptree.execute('echo $(date) > ' + TEST_DIR + '$(hostname)', dst)

        res = NodeSet()
        for f in os.listdir(TEST_DIR):
            for k in dst:
                if f.startswith(str(k)):
                    res.add(k)

        self.assertEquals(str(res), str(dst))


def main():
    suite = unittest.TestLoader().loadTestsFromTestCase(GatewayTest)
    unittest.TextTestRunner(verbosity=2).run(suite)

if __name__ == '__main__':
    main()

