"""
Unit test for NodeSet with Group support
"""

import os
import posixpath
import sys
from textwrap import dedent
import unittest

from TLib import *

# Wildcard import for testing purpose
from ClusterShell.NodeSet import *
from ClusterShell.NodeUtils import *


def makeTestG1():
    """Create a temporary group file 1"""
    f1 = make_temp_file(dedent("""
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
        """).encode('ascii'))
    # /!\ Need to return file object and not f1.name, otherwise the temporary
    # file might be immediately unlinked.
    return f1

def makeTestG2():
    """Create a temporary group file 2"""
    f2 = make_temp_file(dedent("""
        #
        #
        para: montana[32-37,42-55]
        gpu: montana[38-41]
        escape%test: montana[87-90]
        esc%test2: @escape%test
        """).encode('ascii'))
    return f2

def makeTestG3():
    """Create a temporary group file 3"""
    f3 = make_temp_file(dedent("""
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
        """).encode('ascii'))
    return f3

def makeTestR3():
    """Create a temporary reverse group file 3"""
    r3 = make_temp_file(dedent("""
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
        """).encode('ascii'))
    return r3

def makeTestG4():
    """Create a temporary group file 4 (nD)"""
    f4 = make_temp_file(dedent("""
        #
        rack-x1y1: idaho1z1,idaho2z1
        rack-x1y2: idaho2z1,idaho3z1
        rack-x2y1: idaho4z1,idaho5z1
        rack-x2y2: idaho6z1,idaho7z1
        rack-x1: @rack-x1y[1-2]
        rack-x2: @rack-x2y[1-2]
        rack-y1: @rack-x[1-2]y1
        rack-y2: @rack-x[1-2]y2
        rack-all: @rack-x[1-2]y[1-2]
        """).encode('ascii'))
    return f4

class NodeSetGroupTest(unittest.TestCase):

    def setUp(self):
        """setUp test reproducibility: change standard group resolver
        to ensure that no local group source is used during tests"""
        set_std_group_resolver(GroupResolver()) # dummy resolver

    def tearDown(self):
        """tearDown: restore standard group resolver"""
        set_std_group_resolver(None) # restore std resolver

    def testGroupResolverSimple(self):
        """test NodeSet with simple custom GroupResolver"""

        test_groups1 = makeTestG1()

        source = UpcallGroupSource(
                    "simple",
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

        # Also test with a nonfunctional resolver (#263)
        res = GroupResolver()
        self.assertRaises(NodeSetExternalError, NodeSet.fromall, resolver=res)

    def testGroupsNoResolver(self):
        """test NodeSet.groups() with no resolver"""
        nodeset = NodeSet("foo", resolver=RESOLVER_NOGROUP)
        self.assertRaises(NodeSetExternalError, nodeset.groups)

    def testGroupResolverAddSourceError(self):
        """test GroupResolver.add_source() error"""

        test_groups1 = makeTestG1()

        source = UpcallGroupSource("simple",
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

        source = UpcallGroupSource("minimal",
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
        f = make_temp_file(b"")
        res = GroupResolverConfig(f.name)
        # NodeSet should work
        nodeset = NodeSet("example[1-100]", resolver=res)
        self.assertEqual(str(nodeset), "example[1-100]")
        # without group support
        self.assertRaises(GroupResolverSourceError, nodeset.regroup)
        self.assertRaises(GroupResolverSourceError, NodeSet, "@bar", resolver=res)

    def testConfigResolverEmpty(self):
        """test groups resolver with an empty file list"""
        # empty file list OR as if no config file is parsable
        res = GroupResolverConfig([])
        # NodeSet should work
        nodeset = NodeSet("example[1-100]", resolver=res)
        self.assertEqual(str(nodeset), "example[1-100]")
        # without group support
        self.assertRaises(GroupResolverSourceError, nodeset.regroup)
        self.assertRaises(GroupResolverSourceError, NodeSet, "@bar", resolver=res)

    def testConfigBasicLocal(self):
        """test groups with a basic local config file"""
        f = make_temp_file(dedent("""
            # A comment

            [Main]
            default: local

            [local]
            map: echo example[1-100]
            #all:
            list: echo foo
            #reverse:
            """).encode('ascii'))
        res = GroupResolverConfig(f.name)
        nodeset = NodeSet("example[1-100]", resolver=res)
        self.assertEqual(str(nodeset), "example[1-100]")
        self.assertEqual(nodeset.regroup(), "@foo")
        self.assertEqual(list(nodeset.groups().keys()), ["@foo"])
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

        # test default_source_name property
        self.assertEqual(res.default_source_name, "local")

        # check added with lazy init
        res = GroupResolverConfig(f.name)
        self.assertEqual(res.default_source_name, "local")

    def testConfigWrongSyntax(self):
        """test wrong groups config syntax"""
        f = make_temp_file(dedent("""
            # A comment

            [Main]
            default: local

            [local]
            something: echo example[1-100]
            """).encode('ascii'))

        resolver = GroupResolverConfig(f.name)
        self.assertRaises(GroupResolverConfigError, resolver.grouplist)

    def testConfigBasicLocalVerbose(self):
        """test groups with a basic local config file (verbose)"""
        f = make_temp_file(dedent("""
            # A comment

            [Main]
            default: local

            [local]
            map: echo example[1-100]
            #all:
            list: echo foo
            #reverse:
            """).encode('ascii'))
        res = GroupResolverConfig(f.name)
        nodeset = NodeSet("example[1-100]", resolver=res)
        self.assertEqual(str(nodeset), "example[1-100]")
        self.assertEqual(nodeset.regroup(), "@foo")
        self.assertEqual(str(NodeSet("@foo", resolver=res)), "example[1-100]")

    def testConfigBasicLocalAlternative(self):
        """test groups with a basic local config file (= alternative)"""
        f = make_temp_file(dedent("""
            # A comment

            [Main]
            default=local

            [local]
            map=echo example[1-100]
            #all=
            list=echo foo
            #reverse=
            """).encode('ascii'))
        res = GroupResolverConfig(f.name)
        nodeset = NodeSet("example[1-100]", resolver=res)
        self.assertEqual(str(nodeset), "example[1-100]")
        self.assertEqual(nodeset.regroup(), "@foo")
        self.assertEqual(str(NodeSet("@foo", resolver=res)), "example[1-100]")
        # @truc?

    def testConfigBasicEmptyDefault(self):
        """test groups with a empty default namespace"""
        f = make_temp_file(dedent("""
            # A comment

            [Main]
            default: 

            [local]
            map: echo example[1-100]
            #all:
            list: echo foo
            #reverse:
            """).encode('ascii'))
        res = GroupResolverConfig(f.name)
        nodeset = NodeSet("example[1-100]", resolver=res)
        self.assertEqual(str(nodeset), "example[1-100]")
        self.assertEqual(nodeset.regroup(), "@foo")
        self.assertEqual(str(NodeSet("@foo", resolver=res)), "example[1-100]")

    def testConfigBasicNoMain(self):
        """test groups with a local config without main section"""
        f = make_temp_file(dedent("""
            # A comment

            [local]
            map: echo example[1-100]
            #all:
            list: echo foo
            #reverse:
            """).encode('ascii'))
        res = GroupResolverConfig(f.name)
        nodeset = NodeSet("example[1-100]", resolver=res)
        self.assertEqual(str(nodeset), "example[1-100]")
        self.assertEqual(nodeset.regroup(), "@foo")
        self.assertEqual(str(NodeSet("@foo", resolver=res)), "example[1-100]")

    def testConfigBasicWrongDefault(self):
        """test groups with a wrong default namespace"""
        f = make_temp_file(dedent("""
            # A comment

            [Main]
            default: pointless

            [local]
            map: echo example[1-100]
            #all:
            list: echo foo
            #reverse:
            """).encode('ascii'))

        resolver = GroupResolverConfig(f.name)
        self.assertRaises(GroupResolverConfigError, resolver.grouplist)

    def testConfigQueryFailed(self):
        """test groups with config and failed query"""
        f = make_temp_file(dedent("""
            # A comment

            [Main]
            default: local

            [local]
            map: false
            all: false
            list: echo foo
            #reverse:
            """).encode('ascii'))
        res = GroupResolverConfig(f.name)
        nodeset = NodeSet("example[1-100]", resolver=res)
        self.assertEqual(str(nodeset), "example[1-100]")
        self.assertRaises(NodeSetExternalError, nodeset.regroup)

        # all_nodes()
        self.assertRaises(NodeSetExternalError, NodeSet.fromall, resolver=res)

    def testConfigQueryFailedReverse(self):
        """test groups with config and failed query (reverse)"""
        f = make_temp_file(dedent("""
            # A comment

            [Main]
            default: local

            [local]
            map: echo example1
            list: echo foo
            reverse: false
            """).encode('ascii'))
        res = GroupResolverConfig(f.name)
        nodeset = NodeSet("@foo", resolver=res)
        self.assertEqual(str(nodeset), "example1")
        self.assertRaises(NodeSetExternalError, nodeset.regroup)

    def testConfigRegroupWrongNamespace(self):
        """test groups by calling regroup(wrong_namespace)"""
        f = make_temp_file(dedent("""
            # A comment

            [Main]
            default: local

            [local]
            map: echo example[1-100]
            #all:
            list: echo foo
            #reverse:
            """).encode('ascii'))
        res = GroupResolverConfig(f.name)
        nodeset = NodeSet("example[1-100]", resolver=res)
        self.assertRaises(GroupResolverSourceError, nodeset.regroup, "unknown")

    def testConfigNoListNoReverse(self):
        """test groups with no list and not reverse upcall"""
        f = make_temp_file(dedent("""
            # A comment

            [Main]
            default: local

            [local]
            map: echo example[1-100]
            #all:
            #list:
            #reverse:
            """).encode('ascii'))
        res = GroupResolverConfig(f.name)
        nodeset = NodeSet("example[1-100]", resolver=res)
        self.assertEqual(str(nodeset), "example[1-100]")
        # not able to regroup, should still return valid nodeset
        self.assertEqual(nodeset.regroup(), "example[1-100]")

    def testConfigNoListButReverseQuery(self):
        """test groups with no list but reverse upcall"""
        f = make_temp_file(dedent("""
            # A comment

            [Main]
            default: local

            [local]
            map: echo example[1-100]
            #all:
            #list: echo foo
            reverse: echo foo
            """).encode('ascii'))
        res = GroupResolverConfig(f.name)
        nodeset = NodeSet("example[1-100]", resolver=res)
        self.assertEqual(str(nodeset), "example[1-100]")
        self.assertEqual(nodeset.regroup(), "@foo")

    def testConfigNoMap(self):
        """test groups with no map upcall"""
        f = make_temp_file(dedent("""
            # A comment

            [Main]
            default: local

            [local]
            #map: echo example[1-100]
            all:
            list: echo foo
            #reverse: echo foo
            """).encode('ascii'))

        # map is a mandatory upcall, an exception should be raised early
        resolver = GroupResolverConfig(f.name)
        self.assertRaises(GroupResolverConfigError, resolver.grouplist)

    def testConfigWithEmptyList(self):
        """test groups with list upcall returning nothing"""
        f = make_temp_file(dedent("""
            # A comment

            [Main]
            default: local

            [local]
            map: echo example[1-100]
            #all:
            list: :
            reverse: echo foo
            """).encode('ascii'))
        res = GroupResolverConfig(f.name)
        nodeset = NodeSet("example[1-100]", resolver=res)
        self.assertEqual(str(nodeset), "example[1-100]")
        self.assertEqual(nodeset.regroup(), "@foo")

    def testConfigListAllWithAll(self):
        """test all groups listing with all upcall"""
        f = make_temp_file(dedent("""
            # A comment

            [Main]
            default: local

            [local]
            map: echo example[1-100]
            all: echo foo bar
            list: echo foo
            #reverse:
            """).encode('ascii'))
        res = GroupResolverConfig(f.name)
        nodeset = NodeSet("example[1-50]", resolver=res)
        self.assertEqual(str(nodeset), "example[1-50]")
        self.assertEqual(str(NodeSet.fromall(resolver=res)), "bar,foo")
        # test "@*" magic group listing
        nodeset = NodeSet("@*", resolver=res)
        self.assertEqual(str(nodeset), "bar,foo")
        nodeset = NodeSet("rab,@*,oof", resolver=res)
        self.assertEqual(str(nodeset), "bar,foo,oof,rab")
        # with group source
        nodeset = NodeSet("@local:*", resolver=res)
        self.assertEqual(str(nodeset), "bar,foo")
        nodeset = NodeSet("rab,@local:*,oof", resolver=res)
        self.assertEqual(str(nodeset), "bar,foo,oof,rab")


    def testConfigListAllWithoutAll(self):
        """test all groups listing without all upcall"""
        f = make_temp_file(dedent("""
            # A comment

            [Main]
            default: local

            [local]
            map: echo example[1-100]
            #all:
            list: echo foo bar
            #reverse:
            """).encode('ascii'))
        res = GroupResolverConfig(f.name)
        nodeset = NodeSet("example[1-50]", resolver=res)
        self.assertEqual(str(nodeset), "example[1-50]")
        self.assertEqual(str(NodeSet.fromall(resolver=res)), "example[1-100]")
        # test "@*" magic group listing
        nodeset = NodeSet("@*", resolver=res)
        self.assertEqual(str(nodeset), "example[1-100]")
        nodeset = NodeSet("@*,example[101-104]", resolver=res)
        self.assertEqual(str(nodeset), "example[1-104]")
        nodeset = NodeSet("example[105-149],@*,example[101-104]", resolver=res)
        self.assertEqual(str(nodeset), "example[1-149]")
        # with group source
        nodeset = NodeSet("@local:*", resolver=res)
        self.assertEqual(str(nodeset), "example[1-100]")
        nodeset = NodeSet("example0,@local:*,example[101-110]", resolver=res)
        self.assertEqual(str(nodeset), "example[0-110]")

    def testConfigListAllNDWithoutAll(self):
        """test all groups listing without all upcall (nD)"""
        # Even in nD, ensure that $GROUP is a simple group that has been previously expanded
        f = make_temp_file(dedent("""
            # A comment

            [Main]
            default: local

            [local]
            map: if [ "$GROUP" = "x1y[3-4]" ]; then exit 1; elif [ "$GROUP" = "x1y1" ]; then echo rack[1-5]z[1-42]; else echo rack[6-10]z[1-42]; fi
            #all:
            list: echo x1y1 x1y2 x1y[3-4]
            #reverse:
            """).encode('ascii'))
        res = GroupResolverConfig(f.name, illegal_chars=ILLEGAL_GROUP_CHARS)
        nodeset = NodeSet("rack3z40", resolver=res)
        self.assertEqual(str(NodeSet.fromall(resolver=res)), "rack[1-10]z[1-42]")
        self.assertEqual(res.grouplist(), ['x1y1', 'x1y2', 'x1y[3-4]']) # raw
        self.assertEqual(grouplist(resolver=res), ['x1y1', 'x1y2', 'x1y3', 'x1y4']) # cleaned
        # test "@*" magic group listing
        nodeset = NodeSet("@*", resolver=res)
        self.assertEqual(str(nodeset), "rack[1-10]z[1-42]")
        # with group source
        nodeset = NodeSet("@local:*", resolver=res)
        self.assertEqual(str(nodeset), "rack[1-10]z[1-42]")
        nodeset = NodeSet("rack11z1,@local:*,rack11z[2-42]", resolver=res)
        self.assertEqual(str(nodeset), "rack[1-11]z[1-42]")

    def testConfigIllegalCharsND(self):
        """test group list containing illegal characters"""
        f = make_temp_file(dedent("""
            # A comment

            [Main]
            default: local

            [local]
            map: echo rack[6-10]z[1-42]
            #all:
            list: echo x1y1 x1y2 @illegal x1y[3-4]
            #reverse:
            """).encode('ascii'))
        res = GroupResolverConfig(f.name, illegal_chars=ILLEGAL_GROUP_CHARS)
        nodeset = NodeSet("rack3z40", resolver=res)
        self.assertRaises(GroupResolverIllegalCharError, res.grouplist)

    def testConfigResolverSources(self):
        """test sources() with groups config of 2 sources"""
        f = make_temp_file(dedent("""
            # A comment

            [Main]
            default: local

            [local]
            map: echo example[1-100]

            [other]
            map: echo example[1-10]
            """).encode('ascii'))
        res = GroupResolverConfig(f.name)
        self.assertEqual(len(res.sources()), 2)
        self.assertTrue('local' in res.sources())
        self.assertTrue('other' in res.sources())

    def testConfigCrossRefs(self):
        """test groups config with cross references"""
        f = make_temp_file(dedent("""
            # A comment

            [Main]
            default: other

            [local]
            map: echo example[1-100]

            [other]
            map: echo "foo: @local:foo" | sed -n 's/^$GROUP:\(.*\)/\\1/p'

            [third]
            map: printf "bar: @ref-rel\\nref-rel: @other:foo\\nref-all: @*\\n" | sed -n 's/^$GROUP:\(.*\)/\\1/p'
            list: echo bar
            """).encode('ascii'))
        res = GroupResolverConfig(f.name)
        nodeset = NodeSet("@other:foo", resolver=res)
        self.assertEqual(str(nodeset), "example[1-100]")
        # @third:bar -> @ref-rel (third) -> @other:foo -> @local:foo -> nodes
        nodeset = NodeSet("@third:bar", resolver=res)
        self.assertEqual(str(nodeset), "example[1-100]")
        nodeset = NodeSet("@third:ref-all", resolver=res)
        self.assertEqual(str(nodeset), "example[1-100]")

    def testConfigGroupsDirDummy(self):
        """test groups with groupsdir defined (dummy)"""
        f = make_temp_file(dedent("""

            [Main]
            default: local
            groupsdir: /path/to/nowhere

            [local]
            map: echo example[1-100]
            #all:
            list: echo foo
            #reverse:
            """).encode('ascii'))
        res = GroupResolverConfig(f.name)
        nodeset = NodeSet("example[1-100]", resolver=res)
        self.assertEqual(str(nodeset), "example[1-100]")
        self.assertEqual(nodeset.regroup(), "@foo")
        self.assertEqual(str(NodeSet("@foo", resolver=res)), "example[1-100]")

    def testConfigGroupsDirExists(self):
        """test groups with groupsdir defined (real, other)"""
        dname = make_temp_dir()
        f = make_temp_file(dedent("""

            [Main]
            default: new_local
            groupsdir: %s

            [local]
            map: echo example[1-100]
            #all:
            list: echo foo
            #reverse:
            """ % dname).encode('ascii'))
        f2 = make_temp_file(dedent("""
            [new_local]
            map: echo example[1-100]
            #all:
            list: echo bar
            #reverse:
            """).encode('ascii'), suffix=".conf", dir=dname)
        try:
            res = GroupResolverConfig(f.name)
            nodeset = NodeSet("example[1-100]", resolver=res)
            self.assertEqual(str(nodeset), "example[1-100]")
            self.assertEqual(nodeset.regroup(), "@bar")
            self.assertEqual(str(NodeSet("@bar", resolver=res)), "example[1-100]")
        finally:
            f2.close()
            f.close()
            os.rmdir(dname)

    def testConfigGroupsMultipleDirs(self):
        """test groups with multiple confdir defined"""
        dname1 = make_temp_dir()
        dname2 = make_temp_dir()
        # Notes:
        #   - use dname1 two times to check dup checking code
        #   - use quotes on one of the directory path
        f = make_temp_file(dedent("""

            [Main]
            default: local2
            confdir: "%s" %s %s

            [local]
            map: echo example[1-100]
            list: echo foo
            """ % (dname1, dname2, dname1)).encode('ascii'))
        fs1 = make_temp_file(dedent("""
            [local1]
            map: echo loc1node[1-100]
            list: echo bar
            """).encode('ascii'), suffix=".conf", dir=dname1)
        fs2 = make_temp_file(dedent("""
            [local2]
            map: echo loc2node[02-50]
            list: echo toto
            """).encode('ascii'), suffix=".conf", dir=dname2)
        try:
            res = GroupResolverConfig(f.name)
            nodeset = NodeSet("example[1-100]", resolver=res)
            self.assertEqual(str(nodeset), "example[1-100]")
            # local
            self.assertEqual(nodeset.regroup("local"), "@local:foo")
            self.assertEqual(str(NodeSet("@local:foo", resolver=res)), "example[1-100]")
            # local1
            nodeset = NodeSet("loc1node[1-100]", resolver=res)
            self.assertEqual(nodeset.regroup("local1"), "@local1:bar")
            self.assertEqual(str(NodeSet("@local1:bar", resolver=res)), "loc1node[1-100]")
            # local2
            nodeset = NodeSet("loc2node[02-50]", resolver=res)
            self.assertEqual(nodeset.regroup(), "@toto") # default group source
            self.assertEqual(str(NodeSet("@toto", resolver=res)), "loc2node[02-50]")
        finally:
            fs2.close()
            fs1.close()
            f.close()
            os.rmdir(dname2)
            os.rmdir(dname1)

    def testConfigGroupsDirDupConfig(self):
        """test groups with duplicate in groupsdir"""
        dname = make_temp_dir()
        f = make_temp_file(dedent("""

            [Main]
            default: iamdup
            groupsdir: %s

            [local]
            map: echo example[1-100]
            #all:
            list: echo foo
            #reverse:
            """ % dname).encode('ascii'))
        f2 = make_temp_file(dedent("""
            [iamdup]
            map: echo example[1-100]
            #all:
            list: echo bar
            #reverse:
            """).encode('ascii'), suffix=".conf", dir=dname)
        f3 = make_temp_file(dedent("""
            [iamdup]
            map: echo example[10-200]
            #all:
            list: echo patato
            #reverse:
            """).encode('ascii'), suffix=".conf", dir=dname)
        try:
            resolver = GroupResolverConfig(f.name)
            self.assertRaises(GroupResolverConfigError, resolver.grouplist)
        finally:
            f3.close()
            f2.close()
            f.close()
            os.rmdir(dname)

    def testConfigGroupsDirExistsNoOther(self):
        """test groups with groupsdir defined (real, no other)"""
        dname1 = make_temp_dir()
        dname2 = make_temp_dir()
        f = make_temp_file(dedent("""

            [Main]
            default: new_local
            groupsdir: %s %s
            """ % (dname1, dname2)).encode('ascii'))
        f2 = make_temp_file(dedent("""
            [new_local]
            map: echo example[1-100]
            #all:
            list: echo bar
            #reverse:
            """).encode('ascii'), suffix=".conf", dir=dname2)
        try:
            res = GroupResolverConfig(f.name)
            nodeset = NodeSet("example[1-100]", resolver=res)
            self.assertEqual(str(nodeset), "example[1-100]")
            self.assertEqual(nodeset.regroup(), "@bar")
            self.assertEqual(str(NodeSet("@bar", resolver=res)), "example[1-100]")
        finally:
            f2.close()
            f.close()
            os.rmdir(dname1)
            os.rmdir(dname2)

    def testConfigGroupsDirNotADirectory(self):
        """test groups with groupsdir defined (not a directory)"""
        dname = make_temp_dir()
        fdummy = make_temp_file(b"wrong")
        f = make_temp_file(dedent("""

            [Main]
            default: new_local
            groupsdir: %s
            """ % fdummy.name).encode('ascii'))
        try:
            resolver = GroupResolverConfig(f.name)
            self.assertRaises(GroupResolverConfigError, resolver.grouplist)
        finally:
            fdummy.close()
            f.close()
            os.rmdir(dname)

    def testConfigIllegalChars(self):
        """test groups with illegal characters"""
        f = make_temp_file(dedent("""
            # A comment

            [Main]
            default: local

            [local]
            map: echo example[1-100]
            #all:
            list: echo 'foo *'
            reverse: echo f^oo
            """).encode('ascii'))
        res = GroupResolverConfig(f.name, illegal_chars=set("@,&!&^*"))
        nodeset = NodeSet("example[1-100]", resolver=res)
        self.assertRaises(GroupResolverIllegalCharError, nodeset.groups)
        self.assertRaises(GroupResolverIllegalCharError, nodeset.regroup)

    def testConfigMaxRecursionError(self):
        """test groups maximum recursion depth exceeded error"""
        f = make_temp_file(dedent("""
            # A comment

            [Main]
            default: local

            [local]
            map: echo @deep
            list: echo deep
            """).encode('ascii'))
        res = GroupResolverConfig(f.name)
        self.assertRaises(NodeSetParseError, NodeSet, "@deep", resolver=res)

    def testGroupResolverND(self):
        """test NodeSet with simple custom GroupResolver (nD)"""

        test_groups4 = makeTestG4()

        source = UpcallGroupSource("simple",
                                   "sed -n 's/^$GROUP:\(.*\)/\\1/p' %s" % test_groups4.name,
                                   "sed -n 's/^all:\(.*\)/\\1/p' %s" % test_groups4.name,
                                   "sed -n 's/^\([0-9A-Za-z_-]*\):.*/\\1/p' %s" % test_groups4.name,
                                   None)

        # create custom resolver with default source
        res = GroupResolver(source)
        self.assertFalse(res.has_node_groups())
        self.assertFalse(res.has_node_groups("dummy_namespace"))

        nodeset = NodeSet("@rack-x1y2", resolver=res)
        self.assertEqual(nodeset, NodeSet("idaho[2-3]z1"))
        self.assertEqual(str(nodeset), "idaho[2-3]z1")

        nodeset = NodeSet("@rack-y1", resolver=res)
        self.assertEqual(str(nodeset), "idaho[1-2,4-5]z1")

        nodeset = NodeSet("@rack-all", resolver=res)
        self.assertEqual(str(nodeset), "idaho[1-7]z1")

        # test NESTED nD groups()
        self.assertEqual(sorted(nodeset.groups().keys()),
                         ['@rack-all', '@rack-x1', '@rack-x1y1', '@rack-x1y2',
                          '@rack-x2', '@rack-x2y1', '@rack-x2y2', '@rack-y1',
                          '@rack-y2'])
        self.assertEqual(sorted(nodeset.groups(groupsource="simple").keys()),
                         ['@simple:rack-all', '@simple:rack-x1',
                          '@simple:rack-x1y1', '@simple:rack-x1y2',
                          '@simple:rack-x2', '@simple:rack-x2y1',
                          '@simple:rack-x2y2', '@simple:rack-y1',
                          '@simple:rack-y2'])
        self.assertEqual(sorted(nodeset.groups(groupsource="simple",
                                               noprefix=True).keys()),
                         ['@rack-all', '@rack-x1', '@rack-x1y1', '@rack-x1y2',
                          '@rack-x2', '@rack-x2y1', '@rack-x2y2', '@rack-y1',
                          '@rack-y2'])
        testns = NodeSet()
        for gnodes, inodes in nodeset.groups().values():
            testns.update(inodes)
        self.assertEqual(testns, nodeset)

        # more tests with nested groups
        nodeset = NodeSet("idaho5z1", resolver=res)
        self.assertEqual(sorted(nodeset.groups().keys()),
                         ['@rack-all', '@rack-x2', '@rack-x2y1', '@rack-y1'])
        nodeset = NodeSet("idaho5z1,idaho4z1", resolver=res)
        self.assertEqual(sorted(nodeset.groups().keys()),
                         ['@rack-all', '@rack-x2', '@rack-x2y1', '@rack-y1'])
        nodeset = NodeSet("idaho5z1,idaho7z1", resolver=res)
        self.assertEqual(sorted(nodeset.groups().keys()),
                         ['@rack-all', '@rack-x2', '@rack-x2y1', '@rack-x2y2',
                          '@rack-y1', '@rack-y2'])

    def testConfigCFGDIR(self):
        """test groups with $CFGDIR use in upcalls"""
        f = make_temp_file(dedent("""
            [Main]
            default: local

            [local]
            map: echo example[1-100]
            list: basename $CFGDIR
            """).encode('ascii'))
        res = GroupResolverConfig(f.name)
        nodeset = NodeSet("example[1-100]", resolver=res)
        # just a trick to check $CFGDIR resolution...
        tmpgroup = os.path.basename(os.path.dirname(f.name))
        self.assertEqual(list(nodeset.groups().keys()), ['@%s' % tmpgroup])
        self.assertEqual(str(nodeset), "example[1-100]")
        self.assertEqual(nodeset.regroup(), "@%s" % tmpgroup)
        self.assertEqual(str(NodeSet("@%s" % tmpgroup, resolver=res)),
                         "example[1-100]")

    def test_fromall_grouplist(self):
        """test NodeSet.fromall() without all upcall"""
        # Group Source that has no all upcall and that can handle special char
        test_groups2 = makeTestG2()

        source = UpcallGroupSource("simple",
                                   "sed -n 's/^$GROUP:\(.*\)/\\1/p' %s" % test_groups2.name,
                                   None,
                                   "sed -n 's/^\([0-9A-Za-z_-\%%]*\):.*/\\1/p' %s"
                                   % test_groups2.name,
                                   None)
        res = GroupResolver(source)

        # fromall will trigger ParserEngine.grouplist() that we want to test here
        nsall = NodeSet.fromall(resolver=res)

        # if working, group resolution worked with % char
        self.assertEqual(str(NodeSet.fromall(resolver=res)), "montana[32-55,87-90]")
        self.assertEqual(len(nsall), 28)

        # btw explicitly check escaped char
        nsesc = NodeSet('@escape%test', resolver=res)
        self.assertEqual(str(nsesc), 'montana[87-90]')
        self.assertEqual(len(nsesc), 4)
        nsesc2 = NodeSet('@esc%test2', resolver=res)
        self.assertEqual(nsesc, nsesc2)
        ns = NodeSet('montana[87-90]', resolver=res)
        # could also result in escape%test?
        self.assertEqual(ns.regroup(), '@esc%test2')

    def test_nodeset_wildcard_support(self):
        """test NodeSet wildcard support"""
        f = make_temp_file(dedent("""
            [local]
            map: echo blargh
            all: echo foo1 foo2 foo3 bar bar1 bar2 foobar foobar1
            list: echo g1 g2 g3
            """).encode('ascii'))
        res = GroupResolverConfig(f.name)
        self.assertEqual(res.grouplist(), ['g1', 'g2', 'g3'])
        # wildcard expansion computes against 'all'
        nodeset = NodeSet("*foo*", resolver=res)
        self.assertEqual(str(nodeset), "foo[1-3],foobar,foobar1")
        self.assertEqual(len(nodeset), 5)
        nodeset = NodeSet("foo?", resolver=res)
        self.assertEqual(str(nodeset), "foo[1-3]")
        nodeset = NodeSet("*bar", resolver=res)
        self.assertEqual(str(nodeset), "bar,foobar")
        # to exercise 'all nodes' caching
        nodeset = NodeSet("foo*,bar1,*bar", resolver=res)
        self.assertEqual(str(nodeset), "bar,bar1,foo[1-3],foobar,foobar1")
        nodeset = NodeSet("*", resolver=res)
        self.assertEqual(str(nodeset), "bar,bar[1-2],foo[1-3],foobar,foobar1")
        # wildcard matching is done with fnmatch, which is always case
        # sensitive on UNIX-like systems, the only supported systems
        self.assertEqual(os.path, posixpath)
        nodeset = NodeSet("*Foo*", resolver=res)  # case sensitive
        self.assertEqual(str(nodeset), "")

    def test_nodeset_wildcard_support_noall(self):
        """test NodeSet wildcard support (without all upcall)"""
        f = make_temp_file(dedent("""
            [local]
            map: echo foo1 foo2 foo3 bar bar1 bar2 foobar foobar1
            list: echo g1 g2 g3
            """).encode('ascii'))
        res = GroupResolverConfig(f.name)
        # wildcard expansion computes against 'all', which if absent
        # is resolved using list+map
        nodeset = NodeSet("*foo*", resolver=res)
        self.assertEqual(str(nodeset), "foo[1-3],foobar,foobar1")
        nodeset = NodeSet("foo?", resolver=res)
        self.assertEqual(str(nodeset), "foo[1-3]")
        nodeset = NodeSet("*bar", resolver=res)
        self.assertEqual(str(nodeset), "bar,foobar")
        nodeset = NodeSet("*", resolver=res)
        self.assertEqual(str(nodeset), "bar,bar[1-2],foo[1-3],foobar,foobar1")

    def test_nodeset_wildcard_infinite_recursion(self):
        """test NodeSet wildcard infinite recursion protection"""
        f = make_temp_file(dedent(r"""
            [local]
            map: echo foo1 foo2 foo3
            all: echo foo1 foo2 foo\*
            list: echo g1
            """).encode('ascii'))
        res = GroupResolverConfig(f.name)
        nodeset = NodeSet("*foo*", resolver=res)
        # wildcard mask should be automatically ignored on foo* due to
        # infinite recursion
        self.assertEqual(str(nodeset), "foo[1-2],foo*")
        self.assertEqual(len(nodeset), 3)

    def test_nodeset_wildcard_grouplist(self):
        """test NodeSet wildcard support and grouplist()"""
        f = make_temp_file(dedent(r"""
            [local]
            map: echo other
            all: echo foo1 foo2 foo3 bar bar1 bar2 foobar foobar1
            list: echo a b\* c d e
            """).encode('ascii'))
        res = GroupResolverConfig(f.name)
        # grouplist() shouldn't trigger wildcard expansion
        self.assertEqual(grouplist(resolver=res), ['a', 'b*', 'c', 'd', 'e'])
        nodeset = NodeSet("*foo*", resolver=res)
        self.assertEqual(str(nodeset), "foo[1-3],foobar,foobar1")

    def test_nodeset_wildcard_support_ranges(self):
        """test NodeSet wildcard support with ranges"""
        f = make_temp_file(dedent("""
            [local]
            map: echo blargh
            all: echo foo1 foo2 foo3 foo1-ib0 foo2-ib0 foo1-ib1 foo2-ib1 bar10 foobar foobar1
            list: echo g1 g2 g3
            """).encode('ascii'))
        res = GroupResolverConfig(f.name)
        nodeset = NodeSet("*foo[1-2]", resolver=res)
        self.assertEqual(str(nodeset), "foo[1-2]")
        nodeset = NodeSet("f?o[1]", resolver=res)
        self.assertEqual(str(nodeset), "foo1")
        nodeset = NodeSet("foo*", resolver=res)
        self.assertEqual(str(nodeset),
                         "foo[1-3],foo[1-2]-ib[0-1],foobar,foobar1")
        nodeset = NodeSet("foo[1-2]*[0]", resolver=res)
        self.assertEqual(str(nodeset), "foo[1-2]-ib0")
        nodeset = NodeSet("foo[1-2]*[0-1]", resolver=res)
        self.assertEqual(str(nodeset), "foo[1-2]-ib[0-1]")
        nodeset = NodeSet("*[1-2]*[0-1]", resolver=res)  # we do it all :)
        self.assertEqual(str(nodeset), "bar10,foo[1-2]-ib[0-1]")  # bar10 too
        nodeset = NodeSet("*[1-2]*", resolver=res)
        self.assertEqual(str(nodeset),
                         "bar10,foo[1-2],foo[1-2]-ib[0-1],foobar1")

    def test_nodeset_wildcard_precedence(self):
        """test NodeSet wildcard support precedence"""
        f = make_temp_file(dedent("""
            [local]
            map: echo blargh
            all: echo foo1-ib0 foo2-ib0 foo1-ib1 foo2-ib1 bar001 bar002
            list: echo g1 g2 g3
            """).encode('ascii'))
        res = GroupResolverConfig(f.name)
        nodeset = NodeSet("foo*!foo[1-2]-ib0", resolver=res)
        self.assertEqual(str(nodeset), "foo[1-2]-ib1")
        nodeset = NodeSet("foo2-ib0!*", resolver=res)
        self.assertEqual(str(nodeset), "")
        nodeset = NodeSet("bar[001-002],foo[1-2]-ib[0-1]!*foo*", resolver=res)
        self.assertEqual(str(nodeset), "bar[001-002]")
        nodeset = NodeSet("bar0*,foo[1-2]-ib[0-1]!*foo*", resolver=res)
        self.assertEqual(str(nodeset), "bar[001-002]")
        nodeset = NodeSet("bar??1,foo[1-2]-ib[0-1]!*foo*", resolver=res)
        self.assertEqual(str(nodeset), "bar001")
        nodeset = NodeSet("*,*", resolver=res)
        self.assertEqual(str(nodeset), "bar[001-002],foo[1-2]-ib[0-1]")
        nodeset = NodeSet("*!*", resolver=res)
        self.assertEqual(str(nodeset), "")
        nodeset = NodeSet("*&*", resolver=res)
        self.assertEqual(str(nodeset), "bar[001-002],foo[1-2]-ib[0-1]")
        nodeset = NodeSet("*^*", resolver=res)
        self.assertEqual(str(nodeset), "")

    def test_nodeset_wildcard_no_resolver(self):
        """test NodeSet wildcard without resolver"""
        nodeset = NodeSet("foo*", resolver=RESOLVER_NOGROUP)
        self.assertEqual(str(nodeset), "foo*")


class NodeSetGroup2GSTest(unittest.TestCase):

    def setUp(self):
        """configure simple RESOLVER_STD_GROUP"""

        # create temporary groups file and keep a reference to avoid file closing
        self.test_groups1 = makeTestG1()
        self.test_groups2 = makeTestG2()

        # create 2 GroupSource objects
        default = UpcallGroupSource("default",
                                    "sed -n 's/^$GROUP:\(.*\)/\\1/p' %s" % self.test_groups1.name,
                                    "sed -n 's/^all:\(.*\)/\\1/p' %s" % self.test_groups1.name,
                                    "sed -n 's/^\([0-9A-Za-z_-]*\):.*/\\1/p' %s" % self.test_groups1.name,
                                    None)

        source2 = UpcallGroupSource("source2",
                                    "sed -n 's/^$GROUP:\(.*\)/\\1/p' %s" % self.test_groups2.name,
                                    "sed -n 's/^all:\(.*\)/\\1/p' %s" % self.test_groups2.name,
                                    "sed -n 's/^\([0-9A-Za-z_-]*\):.*/\\1/p' %s" % self.test_groups2.name,
                                    None)

        resolver = GroupResolver(default)
        resolver.add_source(source2)
        set_std_group_resolver(resolver)

    def tearDown(self):
        """restore default RESOLVER_STD_GROUP"""
        set_std_group_resolver(None)
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
        groups = std_group_resolver().grouplist()
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
        groups = std_group_resolver().grouplist("source2")
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
        self.assertEqual(sorted(nodeset.groups().keys()),
                         ['@all', '@chassis1', '@chassis10', '@chassis11',
                          '@chassis12', '@chassis2', '@chassis3', '@chassis6',
                          '@chassis7', '@chassis8', '@chassis9', '@compute'])
        testns = NodeSet()
        for gnodes, inodes in nodeset.groups().values():
            testns.update(inodes)
        self.assertEqual(testns, nodeset)


class NodeSetRegroupTest(unittest.TestCase):

    def setUp(self):
        """setUp test reproducibility: change standard group resolver
        to ensure that no local group source is used during tests"""
        set_std_group_resolver(GroupResolver()) # dummy resolver

    def tearDown(self):
        """tearDown: restore standard group resolver"""
        set_std_group_resolver(None) # restore std resolver

    def testGroupResolverReverse(self):
        """test NodeSet GroupResolver with reverse upcall"""

        test_groups3 = makeTestG3()
        test_reverse3 = makeTestR3()

        source = UpcallGroupSource("test",
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
        self.assertEqual(str(nodeset), "montana[38-42]")
        self.assertEqual(nodeset, NodeSet("montana[38-42]"))
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

class StaticGroupSource(UpcallGroupSource):
    """
    A memory only group source based on a provided dict.
    """

    def __init__(self, name, data):
        all_upcall = None
        if 'all' in data:
            all_upcall = 'fake_all'
        list_upcall = None
        if 'list' in data:
            list_upcall = 'fake_list'
        reverse_upcall = None
        if 'reverse' in data:
            reverse_upcall = 'fake_reverse'
        UpcallGroupSource.__init__(self, name, "fake_map", all_upcall,
                                   list_upcall, reverse_upcall)
        self._data = data

    def _upcall_read(self, cmdtpl, args=dict()):
        if cmdtpl == 'map':
            return self._data[cmdtpl].get(args['GROUP'])
        elif cmdtpl == 'reverse':
            return self._data[cmdtpl].get(args['NODE'])
        else:
            return self._data[cmdtpl]

class GroupSourceCacheTest(unittest.TestCase):

    def test_clear_cache(self):
        """test GroupSource.clear_cache()"""
        source = StaticGroupSource('cache', {'map': {'a': 'foo1', 'b': 'foo2'} })

        # create custom resolver with default source
        res = GroupResolver(source)

        # Populate map cache
        self.assertEqual("foo1", str(NodeSet("@a", resolver=res)))
        self.assertEqual("foo2", str(NodeSet("@b", resolver=res)))
        self.assertEqual(len(source._cache['map']), 2)

        # Clear cache
        source.clear_cache()
        self.assertEqual(len(source._cache['map']), 0)

    def test_expired_cache(self):
        """test UpcallGroupSource expired cache entries"""
        # create custom resolver with default source
        source = StaticGroupSource('cache', {'map': {'a': 'foo1', 'b': 'foo2'} })
        source.cache_time = 0.2
        res = GroupResolver(source)

        # Populate map cache
        self.assertEqual("foo1", str(NodeSet("@a", resolver=res)))
        self.assertEqual("foo2", str(NodeSet("@b", resolver=res)))
        # Query one more time to check that cache key is unique
        self.assertEqual("foo2", str(NodeSet("@b", resolver=res)))
        self.assertEqual(len(source._cache['map']), 2)

        # Be sure 0.2 cache time is expired (especially for old Python version)
        time.sleep(0.25)

        source._data['map']['a'] = 'something_else'
        self.assertEqual('something_else', str(NodeSet("@a", resolver=res)))
        self.assertEqual(len(source._cache['map']), 2)

    def test_expired_cache_reverse(self):
        """test UpcallGroupSource expired cache entries (reverse)"""
        source = StaticGroupSource('cache',
                                   {'map': {'a': 'foo1', 'b': 'foo2'},
                                    'reverse': {'foo1': 'a', 'foo2': 'b'} })
        source.cache_time = 0.2
        res = GroupResolver(source)

        # Populate reverse cache
        self.assertEqual("@a", str(NodeSet("foo1", resolver=res).regroup()))
        self.assertEqual("@b", str(NodeSet("foo2", resolver=res).regroup()))
        # Query one more time to check that cache key is unique
        self.assertEqual("@b", str(NodeSet("foo2", resolver=res).regroup()))
        self.assertEqual(len(source._cache['reverse']), 2)

        # Be sure 0.2 cache time is expired (especially for old Python version)
        time.sleep(0.25)

        source._data['map']['c'] = 'foo1'
        source._data['reverse']['foo1'] = 'c'
        self.assertEqual('@c', NodeSet("foo1", resolver=res).regroup())
        self.assertEqual(len(source._cache['reverse']), 2)

    def test_config_cache_time(self):
        """test group config cache_time options"""
        f = make_temp_file(dedent("""
            [local]
            cache_time: 0.2
            map: echo foo1
            """).encode('ascii'))
        res = GroupResolverConfig(f.name)
        dummy = res.group_nodes('dummy')  # init res to access res._sources
        self.assertEqual(res._sources['local'].cache_time, 0.2)
        self.assertEqual("foo1", str(NodeSet("@local:foo", resolver=res)))


class GroupSourceTest(unittest.TestCase):
    """Test class for 1.7 dict-based GroupSource"""

    def test_base_class0(self):
        """test base GroupSource class (empty)"""
        gs = GroupSource("emptysrc")
        self.assertEqual(gs.resolv_map('gr1'), '')
        self.assertEqual(gs.resolv_map('gr2'), '')
        self.assertEqual(gs.resolv_list(), [])
        self.assertRaises(GroupSourceNoUpcall, gs.resolv_all)
        self.assertRaises(GroupSourceNoUpcall, gs.resolv_reverse, 'n4')

    def test_base_class1(self):
        """test base GroupSource class (map and list)"""
        gs = GroupSource("testsrc", { 'gr1': ['n1', 'n4', 'n3', 'n2'],
                                      'gr2': ['n9', 'n4'] })
        self.assertEqual(gs.resolv_map('gr1'), ['n1', 'n4', 'n3', 'n2'])
        self.assertEqual(gs.resolv_map('gr2'), ['n9', 'n4'])
        self.assertEqual(sorted(gs.resolv_list()), ['gr1', 'gr2'])
        self.assertRaises(GroupSourceNoUpcall, gs.resolv_all)
        self.assertRaises(GroupSourceNoUpcall, gs.resolv_reverse, 'n4')

    def test_base_class2(self):
        """test base GroupSource class (all)"""
        gs = GroupSource("testsrc", { 'gr1': ['n1', 'n4', 'n3', 'n2'],
                                      'gr2': ['n9', 'n4'] },
                         'n[1-9]')
        self.assertEqual(gs.resolv_all(), 'n[1-9]')


class YAMLGroupLoaderTest(unittest.TestCase):

    def test_missing_pyyaml(self):
        """test YAMLGroupLoader with missing PyYAML"""
        sys_path_saved = sys.path
        try:
            sys.path = [] # make import yaml failed
            if 'yaml' in sys.modules:
                # forget about previous yaml import
                del sys.modules['yaml']
            f = make_temp_file(dedent("""
                vendors:
                    apricot: node""").encode('ascii'))
            self.assertRaises(GroupResolverConfigError, YAMLGroupLoader,
                              f.name)
        finally:
            sys.path = sys_path_saved

    def test_one_source(self):
        """test YAMLGroupLoader one source"""
        f = make_temp_file(dedent("""
            vendors:
                apricot: node""").encode('ascii'))
        loader = YAMLGroupLoader(f.name)
        sources = list(loader)
        self.assertEqual(len(sources), 1)
        self.assertEqual(loader.groups("vendors"),
                         { 'apricot': 'node' })

    def test_multi_sources(self):
        """test YAMLGroupLoader multi sources"""
        f = make_temp_file(dedent("""
            vendors:
                apricot: node

            customers:
                cherry: client-4-2""").encode('ascii'))
        loader = YAMLGroupLoader(f.name)
        sources = list(loader)
        self.assertEqual(len(sources), 2)
        self.assertEqual(loader.groups("vendors"),
                         { 'apricot': 'node' })
        self.assertEqual(loader.groups("customers"),
                         { 'cherry': 'client-4-2' })

    def test_reload(self):
        """test YAMLGroupLoader cache_time"""
        f = make_temp_file(dedent("""
            vendors:
                apricot: "node[1-10]"
                avocado: 'node[11-20]'
                banana: node[21-30]
            customers:
                cherry: client-4-2""").encode('ascii'))
        loader = YAMLGroupLoader(f.name, cache_time=1)
        self.assertEqual(loader.groups("vendors"),
                         { 'apricot': 'node[1-10]',
                           'avocado': 'node[11-20]',
                           'banana': 'node[21-30]' })

        # modify YAML file and check that it is reloaded after cache_time
        f.write(b"\n    nut: node42\n")
        # oh and BTW for ultimate code coverage, test if we add a new source
        # on-the-fly, this is not supported but should be ignored
        f.write(b"thieves:\n    pomegranate: node100\n")
        f.flush()
        time.sleep(0.1)
        # too soon
        self.assertEqual(loader.groups("customers"),
                         { 'cherry': 'client-4-2' })
        time.sleep(1.0)
        self.assertEqual(loader.groups("vendors"),
                         { 'apricot': 'node[1-10]',
                           'avocado': 'node[11-20]',
                           'banana': 'node[21-30]' })
        self.assertEqual(loader.groups("customers"),
                         { 'cherry': 'client-4-2',
                           'nut': 'node42' })

    def test_iter(self):
        """test YAMLGroupLoader iterator"""
        f = make_temp_file(dedent("""
            src1:
                src1grp1: node11
                src1grp2: node12

            src2:
                src2grp1: node21
                src2grp2: node22

            src3:
                src3grp1: node31
                src3grp2: node32""").encode('ascii'))
        loader = YAMLGroupLoader(f.name, cache_time = 0.1)
        # iterate sources with cache expired
        for source in loader:
            time.sleep(0.5) # force reload
            self.assertEqual(len(source.groups), 2)

    def test_numeric_sources(self):
        """test YAMLGroupLoader with numeric sources"""
        # good
        f = make_temp_file(b"'111': { compute: 'sgisummit-rcf-111-[08,10]' }")
        loader = YAMLGroupLoader(f.name)
        sources = list(loader)
        self.assertEqual(len(sources), 1)
        self.assertEqual(loader.groups("111"),
                         {'compute': 'sgisummit-rcf-111-[08,10]'})
        # bad
        f = make_temp_file(b"111: { compute: 'sgisummit-rcf-111-[08,10]' }")
        self.assertRaises(GroupResolverConfigError, YAMLGroupLoader, f.name)

    def test_numeric_group(self):
        """test YAMLGroupLoader with numeric group"""
        # good
        f = make_temp_file(b"courses: { '101': 'workstation-[1-10]' }")
        loader = YAMLGroupLoader(f.name)
        sources = list(loader)
        self.assertEqual(len(sources), 1)
        self.assertEqual(loader.groups("courses"),
                         {'101': 'workstation-[1-10]'})
        # bad
        f = make_temp_file(b"courses: { 101: 'workstation-[1-10]' }")
        self.assertRaises(GroupResolverConfigError, YAMLGroupLoader, f.name)


class GroupResolverYAMLTest(unittest.TestCase):

    def setUp(self):
        """setUp test reproducibility: change standard group resolver
        to ensure that no local group source is used during tests"""
        set_std_group_resolver(GroupResolver()) # dummy resolver

    def tearDown(self):
        """tearDown: restore standard group resolver"""
        set_std_group_resolver(None) # restore std resolver

    def test_yaml_basic(self):
        """test groups with a basic YAML config file"""
        dname = make_temp_dir()
        f = make_temp_file(dedent("""
            # A comment

            [Main]
            default: yaml
            autodir: %s
            """ % dname).encode('ascii'))
        yamlfile = make_temp_file(dedent("""
            yaml:
                foo: example[1-4,91-100],example90
                bar: example[5-89]
            """).encode('ascii'), suffix=".yaml", dir=dname)
        try:
            res = GroupResolverConfig(f.name)

            # Group resolution
            nodeset = NodeSet("@foo", resolver=res)
            self.assertEqual(str(nodeset), "example[1-4,90-100]")
            nodeset = NodeSet("@bar", resolver=res)
            self.assertEqual(str(nodeset), "example[5-89]")
            nodeset = NodeSet("@foo,@bar", resolver=res)
            self.assertEqual(str(nodeset), "example[1-100]")
            nodeset = NodeSet("@unknown", resolver=res)
            self.assertEqual(len(nodeset), 0)

            # Regroup
            nodeset = NodeSet("example[1-4,90-100]", resolver=res)
            self.assertEqual(str(nodeset), "example[1-4,90-100]")
            self.assertEqual(nodeset.regroup(), "@foo")
            self.assertEqual(list(nodeset.groups().keys()), ["@foo"])
            self.assertEqual(str(NodeSet("@foo", resolver=res)),
                             "example[1-4,90-100]")

            # No 'all' defined: all_nodes() should raise an error
            self.assertRaises(GroupSourceError, res.all_nodes)
            # but then NodeSet falls back to the union of all groups
            nodeset = NodeSet.fromall(resolver=res)
            self.assertEqual(str(nodeset), "example[1-100]")
            # regroup doesn't use @all in that case
            self.assertEqual(nodeset.regroup(), "@bar,@foo")

            # No 'reverse' defined: node_groups() should raise an error
            self.assertRaises(GroupSourceError, res.node_groups, "example1")

            # regroup with rest
            nodeset = NodeSet("example[1-101]", resolver=res)
            self.assertEqual(nodeset.regroup(), "@bar,@foo,example101")

            # regroup incomplete
            nodeset = NodeSet("example[50-200]", resolver=res)
            self.assertEqual(nodeset.regroup(), "example[50-200]")

            # regroup no matching
            nodeset = NodeSet("example[102-200]", resolver=res)
            self.assertEqual(nodeset.regroup(), "example[102-200]")
        finally:
            yamlfile.close()
            os.rmdir(dname)

    def test_yaml_fromall(self):
        """test groups special all group"""
        dname = make_temp_dir()
        f = make_temp_file(dedent("""
            [Main]
            default: yaml
            autodir: %s
            """ % dname).encode('ascii'))
        yamlfile = make_temp_file(dedent("""
            yaml:
                foo: example[1-4,91-100],example90
                bar: example[5-89]
                all: example[90-100]
            """).encode('ascii'), suffix=".yaml", dir=dname)
        try:
            res = GroupResolverConfig(f.name)
            nodeset = NodeSet.fromall(resolver=res)
            self.assertEqual(str(nodeset), "example[90-100]")
            # regroup uses @all if it is defined
            self.assertEqual(nodeset.regroup(), "@all")
        finally:
            yamlfile.close()
            os.rmdir(dname)

    def test_yaml_invalid_groups_not_dict(self):
        """test groups with an invalid YAML config file (1)"""
        dname = make_temp_dir()
        f = make_temp_file(dedent("""
            [Main]
            default: yaml
            autodir: %s
            """ % dname).encode('ascii'))
        yamlfile = make_temp_file(b"""
yaml: bar
        """, suffix=".yaml", dir=dname)
        try:
            resolver = GroupResolverConfig(f.name)
            self.assertRaises(GroupResolverConfigError, resolver.grouplist)
        finally:
            yamlfile.close()
            os.rmdir(dname)

    def test_yaml_invalid_root_dict(self):
        """test groups with an invalid YAML config file (2)"""
        dname = make_temp_dir()
        f = make_temp_file(dedent("""
            [Main]
            default: yaml
            autodir: %s
            """ % dname).encode('ascii'))
        yamlfile = make_temp_file(b"""
- Casablanca
- North by Northwest
- The Man Who Wasn't There
        """, suffix=".yaml", dir=dname)
        try:
            resolver = GroupResolverConfig(f.name)
            self.assertRaises(GroupResolverConfigError, resolver.grouplist)
        finally:
            yamlfile.close()
            os.rmdir(dname)

    def test_yaml_invalid_not_yaml(self):
        """test groups with an invalid YAML config file (3)"""
        dname = make_temp_dir()
        f = make_temp_file(dedent("""
            [Main]
            default: yaml
            autodir: %s
            """ % dname).encode('ascii'))
        yamlfile = make_temp_file(b"""
[Dummy]
one: un
two: deux
three: trois
        """, suffix=".yaml", dir=dname)
        try:
            resolver = GroupResolverConfig(f.name)
            self.assertRaises(GroupResolverConfigError, resolver.grouplist)
        finally:
            yamlfile.close()
            os.rmdir(dname)

    def test_wrong_autodir(self):
        """test wrong autodir (doesn't exist)"""
        f = make_temp_file(dedent("""
                [Main]
                autodir: /i/do/not/=exist=
                default: local
                """).encode('ascii'))

        # absent autodir itself doesn't raise any exception, but default
        # pointing to nothing does...
        resolver = GroupResolverConfig(f.name)
        self.assertRaises(GroupResolverConfigError, resolver.grouplist)

    def test_wrong_autodir_is_file(self):
        """test wrong autodir (is a file)"""
        fe = make_temp_file(b"")
        f = make_temp_file(dedent("""
            [Main]
            autodir: %s
            default: local

            [local]
            map: node
            """ % fe.name).encode('ascii'))
        resolver = GroupResolverConfig(f.name)
        self.assertRaises(GroupResolverConfigError, resolver.grouplist)

    def test_yaml_permission_denied(self):
        """test groups when not allowed to read some YAML config file"""

        # This test doesn't work if run as root, as root can read the
        # yaml group file even with restricted file permissions...
        if os.geteuid() == 0:
            return

        dname = make_temp_dir()
        f = make_temp_file(dedent("""
            [Main]
            default: yaml1
            autodir: %s
            """ % dname).encode('ascii'))

        yamlfile1 = make_temp_file(b'yaml1: {foo: "example[1-4]"}',
                                   suffix=".yaml", dir=dname)
        yamlfile2 = make_temp_file(b'yaml2: {bar: "example[5-8]"}',
                                   suffix=".yaml", dir=dname)

        try:
            # do not allow read access to yamlfile2
            os.chmod(yamlfile2.name, 0)
            self.assertFalse(os.access(yamlfile2.name, os.R_OK))

            res = GroupResolverConfig(f.name)

            # using yaml1 should work
            nodeset = NodeSet("@foo", resolver=res)
            self.assertEqual(str(nodeset), "example[1-4]")

            # using yaml2 won't, of course
            self.assertRaises(GroupResolverSourceError, NodeSet, "@yaml2:bar",
                              resolver=res)
        finally:
            yamlfile1.close()
            yamlfile2.close()
            os.rmdir(dname)
