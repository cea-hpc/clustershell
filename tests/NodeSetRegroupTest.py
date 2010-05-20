#!/usr/bin/env python
# ClusterShell.Node* test suite
# Written by S. Thiell 2010-03-18
# $Id$


"""Unit test for NodeSet with Group support"""

import copy
import sys
import unittest

sys.path.insert(0, '../lib')

# Wildcard import for testing purpose
from ClusterShell.NodeSet import *
import ClusterShell.NodeUtils as NodeUtils
from ClusterShell.NodeUtils import *


class NodeSetGroupTest(unittest.TestCase):

    def testGroupResolverReverse(self):
        """test NodeSet GroupResolver with reverse upcall"""

        source = GroupSource("test",
                             "awk -F: '/^$GROUP:/ {print $2}' test_groups3",
                             "awk -F: '/^all:/ {print $2}' test_groups3",
                             "awk -F: '/^\w/ { print $1 }' test_groups3",
                             "awk -F: '/^$NODE:/ { gsub(\",\",\"\\n\",$2); print $2 }' test_reverse3")

        # create custom resolver with default source
        res = GroupResolver(source)

        nodeset = NodeSet("@all", resolver=res)
        self.assertEqual(nodeset, NodeSet("montana[32-55]"))
        self.assertEqual(str(nodeset), "montana[32-55]")
        self.assertEqual(nodeset.regroup(), "@all")
        self.assertEqual(nodeset.regroup(), "@all")

        nodeset = NodeSet("@overclock", resolver=res)
        self.assertEqual(nodeset, NodeSet("montana[41-42]"))
        self.assertEqual(str(nodeset), "montana[41-42]")
        self.assertEqual(nodeset.regroup(), "@overclock")
        self.assertEqual(nodeset.regroup(), "@overclock")

        nodeset = NodeSet("@gpu,@overclock", resolver=res)
        self.assertEqual(nodeset, NodeSet("montana[38-42]"))
        self.assertEqual(str(nodeset), "montana[38-42]")
        # un-overlap :)
        self.assertEqual(nodeset.regroup(), "@gpu,montana42")
        self.assertEqual(nodeset.regroup(), "@gpu,montana42")
        self.assertEqual(nodeset.regroup(overlap=True), "@gpu,@overclock")

        nodeset = NodeSet("montana41", resolver=res)
        self.assertEqual(nodeset.regroup(), "montana41")
        self.assertEqual(nodeset.regroup(), "montana41")

        # test regroup code when using unindexed node
        nodeset = NodeSet("idaho", resolver=res)
        self.assertEqual(nodeset.regroup(), "@single")
        self.assertEqual(nodeset.regroup(), "@single")
        nodeset = NodeSet("@single", resolver=res)
        self.assertEqual(str(nodeset), "idaho")
        # unresolved unindexed:
        nodeset = NodeSet("utah", resolver=res)
        self.assertEqual(nodeset.regroup(), "utah")
        self.assertEqual(nodeset.regroup(), "utah")

        nodeset = NodeSet("@all!montana38", resolver=res)
        self.assertEqual(nodeset, NodeSet("montana[32-37,39-55]"))
        self.assertEqual(str(nodeset), "montana[32-37,39-55]")
        self.assertEqual(nodeset.regroup(), "@para,montana[39-41]")
        self.assertEqual(nodeset.regroup(), "@para,montana[39-41]")
        self.assertEqual(nodeset.regroup(overlap=True),
            "@chassis[1-3],@login,@overclock,@para,montana[39-40]")
        self.assertEqual(nodeset.regroup(overlap=True),
            "@chassis[1-3],@login,@overclock,@para,montana[39-40]")

        nodeset = NodeSet("montana[32-37]", resolver=res)
        self.assertEqual(nodeset.regroup(), "@chassis[1-3]")
        self.assertEqual(nodeset.regroup(), "@chassis[1-3]")



if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(NodeSetGroupTest)
    unittest.TextTestRunner(verbosity=2).run(suite)
