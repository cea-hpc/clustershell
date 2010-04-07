#!/usr/bin/env python
# ClusterShell.Node* test suite
# Written by S. Thiell 2010-03-18
# $Id$


"""Unit test for NodeSet with Group support"""

import copy
import sys
import tempfile
import unittest

sys.path.insert(0, '../lib')

# Wildcard import for testing purpose
import ClusterShell.NodeSet
from ClusterShell.NodeSet import *
from ClusterShell.NodeUtils import *


class NodeSetGroupTest(unittest.TestCase):

    def setSimpleStdGroupResolver(self):
        # create 2 GroupSource objects
        default = GroupSource("default",
                              "awk -F: '/^$GROUP:/ {print $2}' test_groups1",
                              "awk -F: '/^all:/ {print $2}' test_groups1",
                              "awk -F: '/^\w/ {print $1}' test_groups1",
                              None)

        source2 = GroupSource("source2",
                              "awk -F: '/^$GROUP:/ {print $2}' test_groups2",
                              "awk -F: '/^all:/ {print $2}' test_groups2",
                              "awk -F: '/^\w/ {print $1}' test_groups2",
                              None)

        ClusterShell.NodeSet.STD_GROUP_RESOLVER = GroupResolver(default)
        ClusterShell.NodeSet.STD_GROUP_RESOLVER.add_source(source2)

    def restoreStdGroupResolver(self):
        ClusterShell.NodeSet.STD_GROUP_RESOLVER = ClusterShell.NodeSet.DEF_STD_GROUP_RESOLVER

    def makeTestFile(self, text):
        """
        Create a temporary file with the provided text.
        """
        f = tempfile.NamedTemporaryFile()
        f.write(text)
        f.flush()
        return f

    def testGroupResolverSimple(self):
        """test NodeSet with simple custom GroupResolver"""

        source = GroupSource("simple",
                             "awk -F: '/^$GROUP:/ {print $2}' test_groups1",
                             "awk -F: '/^all:/ {print $2}' test_groups1",
                             "awk -F: '/^\w/ {print $1}' test_groups1",
                             None)

        # create custom resolver with default source
        res = GroupResolver(source)

        nodeset = NodeSet("@gpu", resolver=res)
        self.assertEqual(nodeset, NodeSet("montana[38-41]"))
        self.assertEqual(str(nodeset), "montana[38-41]")

        nodeset = NodeSet("@chassis3", resolver=res)
        self.assertEqual(str(nodeset), "montana[36-37]")

        nodeset = NodeSet("@chassis[3-4]", resolver=res)
        self.assertEqual(str(nodeset), "montana[36-39]")

        nodeset = NodeSet("@chassis[1,3,5]", resolver=res)
        self.assertEqual(str(nodeset), "montana[32-33,36-37,40-41]")

        nodeset = NodeSet("@chassis[2-12/2]", resolver=res)
        self.assertEqual(str(nodeset), "montana[34-35,38-39,42-43,46-47,50-51,54-55]")

        nodeset = NodeSet("@chassis[1,3-4,5-11/3]", resolver=res)
        self.assertEqual(str(nodeset), "montana[32-33,36-41,46-47,52-53]")

        # test recursive group gpuchassis
        nodeset1 = NodeSet("@chassis[4-5]", resolver=res)
        nodeset2 = NodeSet("@gpu", resolver=res)
        nodeset3 = NodeSet("@gpuchassis", resolver=res)
        self.assertEqual(nodeset1, nodeset2)
        self.assertEqual(nodeset2, nodeset3)

        # test also with some inline operations
        nodeset = NodeSet("montana3,@gpuchassis!montana39,montana77^montana38",
                          resolver=res)
        self.assertEqual(str(nodeset), "montana[3,40-41,77]")

    def testGroupSyntaxes(self):
        """test NodeSet group operation syntaxes"""

        self.setSimpleStdGroupResolver()
        try:
            nodeset = NodeSet("@gpu")
            self.assertEqual(str(nodeset), "montana[38-41]")

            nodeset = NodeSet("@chassis[1-3,5]&@chassis[2-3]")
            self.assertEqual(str(nodeset), "montana[34-37]")

            nodeset1 = NodeSet("@io!@mds")
            nodeset2 = NodeSet("@oss")
            self.assertEqual(str(nodeset1), str(nodeset2))
            self.assertEqual(str(nodeset1), "montana[4-5]")

        finally:
            self.restoreStdGroupResolver()

    def testGroupListDefault(self):
        """test group listing GroupResolver.grouplist()"""
        self.setSimpleStdGroupResolver()
        try:
            groups = ClusterShell.NodeSet.STD_GROUP_RESOLVER.grouplist()
            self.assertEqual(len(groups), 21)
            helper_groups = grouplist()
            self.assertEqual(len(helper_groups), 21)
            total = 0
            nodes = NodeSet()
            for group in groups:
                ns = NodeSet("@%s" % group)
                total += len(ns)
                nodes.update(ns)
            self.assertEqual(total, 311)

            all_nodes = NodeSet.fromall()
            self.assertEqual(len(all_nodes), len(nodes))
            self.assertEqual(all_nodes, nodes)
        finally:
            self.restoreStdGroupResolver()

    def testGroupListSource2(self):
        """test group listing GroupResolver.grouplist(source)"""
        self.setSimpleStdGroupResolver()
        try:
            groups = ClusterShell.NodeSet.STD_GROUP_RESOLVER.grouplist("source2")
            self.assertEqual(len(groups), 2)
            total = 0
            for group in groups:
                total += len(NodeSet("@source2:%s" % group))
            self.assertEqual(total, 24)
        finally:
            self.restoreStdGroupResolver()

    def testAllNoResolver(self):
        """test NodeSet.fromall() with no resolver"""
        self.assertRaises(NodeSetExternalError, NodeSet.fromall,
                          resolver=NOGROUP_RESOLVER)
            
    def testGroupResolverMinimal(self):
        """test NodeSet with minimal GroupResolver"""

        source = GroupSource("minimal",
                             "awk -F: '/^$GROUP:/ {print $2}' test_groups1",
                             None, None, None)

        # create custom resolver with default source
        res = GroupResolver(source)

        nodeset = NodeSet("@gpu", resolver=res)
        self.assertEqual(nodeset, NodeSet("montana[38-41]"))
        self.assertEqual(str(nodeset), "montana[38-41]")

        NodeSet.fromall(resolver=res)
        #self.assertRaises(NodeSetExternalError, NodeSet.fromall)

    
    def testConfigEmpty(self):
        """test groups with an empty configuration file"""
        f = self.makeTestFile("")
        res = GroupResolverConfig(f.name)
        nodeset = NodeSet("example[1-100]", resolver=res)
        self.assertEqual(str(nodeset), "example[1-100]")
        self.assertEqual(nodeset.regroup(), "example[1-100]")
        # non existant group
        self.assertRaises(NodeSetParseError, NodeSet, "@bar", resolver=res)

    def testConfigBasicLocal(self):
        """test groups with a basic local config file"""
        f = self.makeTestFile("""
# A comment

[Main]
default: local

[local]
map: echo example[1-100]
#all:
list: echo foo
#reverse:
        """)
        res = GroupResolverConfig(f.name)
        nodeset = NodeSet("example[1-100]", resolver=res)
        self.assertEqual(str(nodeset), "example[1-100]")
        self.assertEqual(nodeset.regroup(), "@foo")
        self.assertEqual(str(NodeSet("@foo", resolver=res)), "example[1-100]")

        # regroup with rest
        nodeset = NodeSet("example[1-101]", resolver=res)
        self.assertEqual(nodeset.regroup(), "@foo,example101")

        # regroup incomplete
        nodeset = NodeSet("example[50-200]", resolver=res)
        self.assertEqual(nodeset.regroup(), "example[50-200]")

        # regroup no matching
        nodeset = NodeSet("example[102-200]", resolver=res)
        self.assertEqual(nodeset.regroup(), "example[102-200]")

    def testConfigBasicLocalVerbose(self):
        """test groups with a basic local config file (verbose)"""
        f = self.makeTestFile("""
# A comment

[Main]
default: local

[local]
map: echo example[1-100]
#all:
list: echo foo
#reverse:
        """)
        res = GroupResolverConfig(f.name)
        res.set_verbosity(1)
        nodeset = NodeSet("example[1-100]", resolver=res)
        self.assertEqual(str(nodeset), "example[1-100]")
        self.assertEqual(nodeset.regroup(), "@foo")
        self.assertEqual(str(NodeSet("@foo", resolver=res)), "example[1-100]")

    def testConfigBasicLocalAlternative(self):
        """test groups with a basic local config file (= alternative)"""
        f = self.makeTestFile("""
# A comment

[Main]
default=local

[local]
map=echo example[1-100]
#all=
list=echo foo
#reverse=
        """)
        res = GroupResolverConfig(f.name)
        nodeset = NodeSet("example[1-100]", resolver=res)
        self.assertEqual(str(nodeset), "example[1-100]")
        self.assertEqual(nodeset.regroup(), "@foo")
        self.assertEqual(str(NodeSet("@foo", resolver=res)), "example[1-100]")
        # @truc?

    def testConfigBasicEmptyDefault(self):
        """test groups with a empty default namespace"""
        f = self.makeTestFile("""
# A comment

[Main]
default: 

[local]
map: echo example[1-100]
#all:
list: echo foo
#reverse:
        """)
        res = GroupResolverConfig(f.name)
        nodeset = NodeSet("example[1-100]", resolver=res)
        self.assertEqual(str(nodeset), "example[1-100]")
        self.assertEqual(nodeset.regroup(), "@foo")
        self.assertEqual(str(NodeSet("@foo", resolver=res)), "example[1-100]")

    def testConfigBasicNoMain(self):
        """test groups with a local config without main section"""
        f = self.makeTestFile("""
# A comment

[local]
map: echo example[1-100]
#all:
list: echo foo
#reverse:
        """)
        res = GroupResolverConfig(f.name)
        nodeset = NodeSet("example[1-100]", resolver=res)
        self.assertEqual(str(nodeset), "example[1-100]")
        self.assertEqual(nodeset.regroup(), "@foo")
        self.assertEqual(str(NodeSet("@foo", resolver=res)), "example[1-100]")

    def testConfigBasicWrongDefault(self):
        """test groups with a wrong default namespace"""
        f = self.makeTestFile("""
# A comment

[Main]
default: pointless

[local]
map: echo example[1-100]
#all:
list: echo foo
#reverse:
        """)
        self.assertRaises(GroupResolverConfigError, GroupResolverConfig, f.name)

    def testConfigQueryFailed(self):
        """test groups with config and failed query"""
        f = self.makeTestFile("""
# A comment

[Main]
default: local

[local]
map: /bin/false
#all:
list: echo foo
#reverse:
        """)
        res = GroupResolverConfig(f.name)
        nodeset = NodeSet("example[1-100]", resolver=res)
        self.assertEqual(str(nodeset), "example[1-100]")
        self.assertRaises(NodeSetExternalError, nodeset.regroup)

    def testConfigRegroupWrongNamespace(self):
        """test groups by calling regroup(wrong_namespace)"""
        f = self.makeTestFile("""
# A comment

[Main]
default: local

[local]
map: echo example[1-100]
#all:
list: echo foo
#reverse:
        """)
        res = GroupResolverConfig(f.name)
        nodeset = NodeSet("example[1-100]", resolver=res)
        self.assertRaises(GroupResolverSourceError, nodeset.regroup, "unknown")

    def testConfigNoListButReverseQuery(self):
        """test groups with no list but reverse upcall"""
        f = self.makeTestFile("""
# A comment

[Main]
default: local

[local]
map: echo example[1-100]
#all:
#list: echo foo
reverse: echo foo
        """)
        res = GroupResolverConfig(f.name)
        nodeset = NodeSet("example[1-100]", resolver=res)
        self.assertEqual(str(nodeset), "example[1-100]")
        self.assertEqual(nodeset.regroup(), "@foo")

    def testConfigWithEmptyList(self):
        """test groups with list upcall returning nothing"""
        f = self.makeTestFile("""
# A comment

[Main]
default: local

[local]
map: echo example[1-100]
#all:
list: echo -n
reverse: echo foo
        """)
        res = GroupResolverConfig(f.name)
        nodeset = NodeSet("example[1-100]", resolver=res)
        self.assertEqual(str(nodeset), "example[1-100]")
        self.assertEqual(nodeset.regroup(), "@foo")

    def testConfigCrossRefs(self):
        """test groups config with cross references"""
        f = self.makeTestFile("""
# A comment

[Main]
default: local

[local]
map: echo example[1-100]

[other]
map: echo @local:foo
        """)
        res = GroupResolverConfig(f.name)
        nodeset = NodeSet("@other:foo", resolver=res)
        self.assertEqual(str(nodeset), "example[1-100]")


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(NodeSetGroupTest)
    unittest.TextTestRunner(verbosity=2).run(suite)
