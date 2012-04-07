#!/usr/bin/env python
# ClusterShell.Node* test suite
# Written by S. Thiell 2010-03-18


"""Unit test for NodeSet with Group support"""

import copy
import shutil
import sys
import unittest

sys.path.insert(0, '../lib')

from TLib import *

# Wildcard import for testing purpose
import ClusterShell.NodeSet
from ClusterShell.NodeSet import *
from ClusterShell.NodeUtils import *


def makeTestG1():
    """Create a temporary group file 1"""
    f1 = make_temp_file("""
#
oss: montana5,montana4
mds: montana6
io: montana[4-6]
#42: montana3
compute: montana[32-163]
chassis1: montana[32-33]
chassis2: montana[34-35]
 
chassis3: montana[36-37]
  
chassis4: montana[38-39]
chassis5: montana[40-41]
chassis6: montana[42-43]
chassis7: montana[44-45]
chassis8: montana[46-47]
chassis9: montana[48-49]
chassis10: montana[50-51]
chassis11: montana[52-53]
chassis12: montana[54-55]
Uppercase: montana[1-2]
gpuchassis: @chassis[4-5]
gpu: montana[38-41]
all: montana[1-6,32-163]
""")
    # /!\ Need to return file object and not f1.name, otherwise the temporary
    # file might be immediately unlinked.
    return f1

def makeTestG2():
    """Create a temporary group file 2"""
    f2 = make_temp_file("""
#
#
para: montana[32-37,42-55]
gpu: montana[38-41]
""")
    return f2

def makeTestG3():
    """Create a temporary group file 3"""
    f3 = make_temp_file("""
#
#
all: montana[32-55]
para: montana[32-37,42-55]
gpu: montana[38-41]
login: montana[32-33]
overclock: montana[41-42]
chassis1: montana[32-33]
chassis2: montana[34-35]
chassis3: montana[36-37]
single: idaho
""")
    return f3

def makeTestR3():
    """Create a temporary reverse group file 3"""
    r3 = make_temp_file("""
#
#
montana32: all,para,login,chassis1
montana33: all,para,login,chassis1
montana34: all,para,chassis2
montana35: all,para,chassis2
montana36: all,para,chassis3
montana37: all,para,chassis3
montana38: all,gpu
montana39: all,gpu
montana40: all,gpu
montana41: all,gpu,overclock
montana42: all,para,overclock
montana43: all,para
montana44: all,para
montana45: all,para
montana46: all,para
montana47: all,para
montana48: all,para
montana49: all,para
montana50: all,para
montana51: all,para
montana52: all,para
montana53: all,para
montana54: all,para
montana55: all,para
idaho: single
""")
    return r3

class NodeSetGroupTest(unittest.TestCase):

    def testGroupResolverSimple(self):
        """test NodeSet with simple custom GroupResolver"""

        test_groups1 = makeTestG1()

        source = GroupSource("simple",
                             "sed -n 's/^$GROUP:\(.*\)/\\1/p' %s" % test_groups1.name,
                             "sed -n 's/^all:\(.*\)/\\1/p' %s" % test_groups1.name,
                             "sed -n 's/^\([0-9A-Za-z_-]*\):.*/\\1/p' %s" % test_groups1.name,
                             None)

        # create custom resolver with default source
        res = GroupResolver(source)
        self.assertFalse(res.has_node_groups())
        self.assertFalse(res.has_node_groups("dummy_namespace"))

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

    def testAllNoResolver(self):
        """test NodeSet.fromall() with no resolver"""
        self.assertRaises(NodeSetExternalError, NodeSet.fromall,
                          resolver=RESOLVER_NOGROUP)
            
    def testGroupsNoResolver(self):
        """test NodeSet.groups() with no resolver"""
        nodeset = NodeSet("foo", resolver=RESOLVER_NOGROUP)
        self.assertRaises(NodeSetExternalError, nodeset.groups)

    def testGroupResolverAddSourceError(self):
        """test GroupResolver.add_source() error"""

        test_groups1 = makeTestG1()

        source = GroupSource("simple",
                             "sed -n 's/^$GROUP:\(.*\)/\\1/p' %s" % test_groups1.name,
                             "sed -n 's/^all:\(.*\)/\\1/p' %s" % test_groups1.name,
                             "sed -n 's/^\([0-9A-Za-z_-]*\):.*/\\1/p' %s" % test_groups1.name,
                             None)

        res = GroupResolver(source)
        # adding the same source again should raise ValueError
        self.assertRaises(ValueError, res.add_source, source)

    def testGroupResolverMinimal(self):
        """test NodeSet with minimal GroupResolver"""
        
        test_groups1 = makeTestG1()

        source = GroupSource("minimal",
                             "sed -n 's/^$GROUP:\(.*\)/\\1/p' %s" % test_groups1.name,
                             None, None, None)

        # create custom resolver with default source
        res = GroupResolver(source)

        nodeset = NodeSet("@gpu", resolver=res)
        self.assertEqual(nodeset, NodeSet("montana[38-41]"))
        self.assertEqual(str(nodeset), "montana[38-41]")

        self.assertRaises(NodeSetExternalError, NodeSet.fromall, resolver=res)

    
    def testConfigEmpty(self):
        """test groups with an empty configuration file"""
        f = make_temp_file("")
        res = GroupResolverConfig(f.name)
        nodeset = NodeSet("example[1-100]", resolver=res)
        self.assertEqual(str(nodeset), "example[1-100]")
        self.assertRaises(GroupResolverSourceError, nodeset.regroup)
        # non existant group
        self.assertRaises(GroupResolverSourceError, NodeSet, "@bar", resolver=res)

    def testConfigBasicLocal(self):
        """test groups with a basic local config file"""
        f = make_temp_file("""
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
        self.assertEqual(nodeset.groups().keys(), ["@foo"])
        self.assertEqual(str(NodeSet("@foo", resolver=res)), "example[1-100]")

        # No 'all' defined: all_nodes() should raise an error
        self.assertRaises(GroupSourceNoUpcall, res.all_nodes)
        # No 'reverse' defined: node_groups() should raise an error
        self.assertRaises(GroupSourceNoUpcall, res.node_groups, "example1")

        # regroup with rest
        nodeset = NodeSet("example[1-101]", resolver=res)
        self.assertEqual(nodeset.regroup(), "@foo,example101")

        # regroup incomplete
        nodeset = NodeSet("example[50-200]", resolver=res)
        self.assertEqual(nodeset.regroup(), "example[50-200]")

        # regroup no matching
        nodeset = NodeSet("example[102-200]", resolver=res)
        self.assertEqual(nodeset.regroup(), "example[102-200]")

    def testConfigWrongSyntax(self):
        """test wrong groups config syntax"""
        f = make_temp_file("""
# A comment

[Main]
default: local

[local]
something: echo example[1-100]
        """)
        self.assertRaises(GroupResolverConfigError, GroupResolverConfig, f.name)

    def testConfigBasicLocalVerbose(self):
        """test groups with a basic local config file (verbose)"""
        f = make_temp_file("""
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
        f = make_temp_file("""
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
        f = make_temp_file("""
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
        f = make_temp_file("""
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
        f = make_temp_file("""
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
        f = make_temp_file("""
# A comment

[Main]
default: local

[local]
map: false
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
        f = make_temp_file("""
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
        f = make_temp_file("""
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
        f = make_temp_file("""
# A comment

[Main]
default: local

[local]
map: echo example[1-100]
#all:
list: :
reverse: echo foo
        """)
        res = GroupResolverConfig(f.name)
        nodeset = NodeSet("example[1-100]", resolver=res)
        self.assertEqual(str(nodeset), "example[1-100]")
        self.assertEqual(nodeset.regroup(), "@foo")

    def testConfigResolverSources(self):
        """test sources() with groups config of 2 sources"""
        f = make_temp_file("""
# A comment

[Main]
default: local

[local]
map: echo example[1-100]

[other]
map: echo example[1-10]
        """)
        res = GroupResolverConfig(f.name)
        self.assertEqual(len(res.sources()), 2)
        self.assert_('local' in res.sources())
        self.assert_('other' in res.sources())

    def testConfigCrossRefs(self):
        """test groups config with cross references"""
        f = make_temp_file("""
# A comment

[Main]
default: other

[local]
map: echo example[1-100]

[other]
map: echo "foo: @local:foo" | sed -n 's/^$GROUP:\(.*\)/\\1/p'
""")
        res = GroupResolverConfig(f.name)
        nodeset = NodeSet("@other:foo", resolver=res)
        self.assertEqual(str(nodeset), "example[1-100]")

    def testConfigGroupsDirDummy(self):
        """test groups with groupsdir defined (dummy)"""
        f = make_temp_file("""

[Main]
default: local
groupsdir: /path/to/nowhere

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

    def testConfigGroupsDirExists(self):
        """test groups with groupsdir defined (real, other)"""
        dname = make_temp_dir()
        f = make_temp_file("""

[Main]
default: new_local
groupsdir: %s

[local]
map: echo example[1-100]
#all:
list: echo foo
#reverse:
        """ % dname)
        f2 = make_temp_file("""
[new_local]
map: echo example[1-100]
#all:
list: echo bar
#reverse:
        """, suffix=".conf", dir=dname)
        try:
            res = GroupResolverConfig(f.name)
            nodeset = NodeSet("example[1-100]", resolver=res)
            self.assertEqual(str(nodeset), "example[1-100]")
            self.assertEqual(nodeset.regroup(), "@bar")
            self.assertEqual(str(NodeSet("@bar", resolver=res)), "example[1-100]")
        finally:
            f2.close()
            f.close()
            shutil.rmtree(dname, ignore_errors=True)

    def testConfigGroupsDirExistsNoOther(self):
        """test groups with groupsdir defined (real, no other)"""
        dname1 = make_temp_dir()
        dname2 = make_temp_dir()
        f = make_temp_file("""

[Main]
default: new_local
groupsdir: %s %s
        """ % (dname1, dname2))
        f2 = make_temp_file("""
[new_local]
map: echo example[1-100]
#all:
list: echo bar
#reverse:
        """, suffix=".conf", dir=dname2)
        try:
            res = GroupResolverConfig(f.name)
            nodeset = NodeSet("example[1-100]", resolver=res)
            self.assertEqual(str(nodeset), "example[1-100]")
            self.assertEqual(nodeset.regroup(), "@bar")
            self.assertEqual(str(NodeSet("@bar", resolver=res)), "example[1-100]")
        finally:
            f2.close()
            f.close()
            shutil.rmtree(dname1, ignore_errors=True)
            shutil.rmtree(dname2, ignore_errors=True)

    def testConfigGroupsDirNotADirectory(self):
        """test groups with groupsdir defined (not a directory)"""
        dname = make_temp_dir()
        fdummy = make_temp_file("wrong")
        f = make_temp_file("""

[Main]
default: new_local
groupsdir: %s
        """ % fdummy.name)
        try:
            self.assertRaises(GroupResolverConfigError, GroupResolverConfig, f.name)
        finally:
            fdummy.close()
            f.close()
            shutil.rmtree(dname, ignore_errors=True)


class NodeSetGroup2GSTest(unittest.TestCase):

    def setUp(self):
        """configure simple RESOLVER_STD_GROUP"""

        # create temporary groups file and keep a reference to avoid file closing
        self.test_groups1 = makeTestG1()
        self.test_groups2 = makeTestG2()

        # create 2 GroupSource objects
        default = GroupSource("default",
                              "sed -n 's/^$GROUP:\(.*\)/\\1/p' %s" % self.test_groups1.name,
                              "sed -n 's/^all:\(.*\)/\\1/p' %s" % self.test_groups1.name,
                              "sed -n 's/^\([0-9A-Za-z_-]*\):.*/\\1/p' %s" % self.test_groups1.name,
                              None)

        source2 = GroupSource("source2",
                              "sed -n 's/^$GROUP:\(.*\)/\\1/p' %s" % self.test_groups2.name,
                              "sed -n 's/^all:\(.*\)/\\1/p' %s" % self.test_groups2.name,
                              "sed -n 's/^\([0-9A-Za-z_-]*\):.*/\\1/p' %s" % self.test_groups2.name,
                              None)

        ClusterShell.NodeSet.RESOLVER_STD_GROUP = GroupResolver(default)
        ClusterShell.NodeSet.RESOLVER_STD_GROUP.add_source(source2)

    def tearDown(self):
        """restore default RESOLVER_STD_GROUP"""
        ClusterShell.NodeSet.RESOLVER_STD_GROUP = ClusterShell.NodeSet.DEF_RESOLVER_STD_GROUP
        del self.test_groups1
        del self.test_groups2

    def testGroupSyntaxes(self):
        """test NodeSet group operation syntaxes"""
        nodeset = NodeSet("@gpu")
        self.assertEqual(str(nodeset), "montana[38-41]")

        nodeset = NodeSet("@chassis[1-3,5]&@chassis[2-3]")
        self.assertEqual(str(nodeset), "montana[34-37]")

        nodeset1 = NodeSet("@io!@mds")
        nodeset2 = NodeSet("@oss")
        self.assertEqual(str(nodeset1), str(nodeset2))
        self.assertEqual(str(nodeset1), "montana[4-5]")

    def testGroupListDefault(self):
        """test NodeSet group listing GroupResolver.grouplist()"""
        groups = ClusterShell.NodeSet.RESOLVER_STD_GROUP.grouplist()
        self.assertEqual(len(groups), 20)
        helper_groups = grouplist()
        self.assertEqual(len(helper_groups), 20)
        total = 0
        nodes = NodeSet()
        for group in groups:
            ns = NodeSet("@%s" % group)
            total += len(ns)
            nodes.update(ns)
        self.assertEqual(total, 310)

        all_nodes = NodeSet.fromall()
        self.assertEqual(len(all_nodes), len(nodes))
        self.assertEqual(all_nodes, nodes)

    def testGroupListSource2(self):
        """test NodeSet group listing GroupResolver.grouplist(source)"""
        groups = ClusterShell.NodeSet.RESOLVER_STD_GROUP.grouplist("source2")
        self.assertEqual(len(groups), 2)
        total = 0
        for group in groups:
            total += len(NodeSet("@source2:%s" % group))
        self.assertEqual(total, 24)

    def testGroupNoPrefix(self):
        """test NodeSet group noprefix option"""
        nodeset = NodeSet("montana[32-37,42-55]")
        self.assertEqual(nodeset.regroup("source2"), "@source2:para")
        self.assertEqual(nodeset.regroup("source2", noprefix=True), "@para")

    def testGroupGroups(self):
        """test NodeSet.groups()"""
        nodeset = NodeSet("montana[32-37,42-55]")
        self.assertEqual(sorted(nodeset.groups().keys()), ['@all', '@chassis1', '@chassis10', '@chassis11', '@chassis12', '@chassis2', '@chassis3', '@chassis6', '@chassis7', '@chassis8', '@chassis9', '@compute'])
        testns = NodeSet()
        for gnodes, inodes in nodeset.groups().itervalues():
            testns.update(inodes)
        self.assertEqual(testns, nodeset)


class NodeSetRegroupTest(unittest.TestCase):

    def testGroupResolverReverse(self):
        """test NodeSet GroupResolver with reverse upcall"""

        test_groups3 = makeTestG3()
        test_reverse3 = makeTestR3()

        source = GroupSource("test",
                             "sed -n 's/^$GROUP:\(.*\)/\\1/p' %s" % test_groups3.name,
                             "sed -n 's/^all:\(.*\)/\\1/p' %s" % test_groups3.name,
                             "sed -n 's/^\([0-9A-Za-z_-]*\):.*/\\1/p' %s" % test_groups3.name,
                             "awk -F: '/^$NODE:/ { gsub(\",\",\"\\n\",$2); print $2 }' %s" % test_reverse3.name)

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
    suites = [unittest.TestLoader().loadTestsFromTestCase(NodeSetGroupTest)]
    suites.append(unittest.TestLoader().loadTestsFromTestCase(NodeSetGroup2GSTest))
    suites.append(unittest.TestLoader().loadTestsFromTestCase(NodeSetRegroupTest))
    unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(suites))
