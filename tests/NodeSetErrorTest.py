#!/usr/bin/env python
# ClusterShell.NodeSet.NodeSet error handling test suite
# Written by S. Thiell 2008-09-28


"""Unit test for RangeSet errors"""

import copy
import sys
import unittest

sys.path.insert(0, '../lib')

from ClusterShell.RangeSet import RangeSet
from ClusterShell.NodeSet import NodeSet
from ClusterShell.NodeSet import NodeSetBase
from ClusterShell.NodeSet import NodeSetError
from ClusterShell.NodeSet import NodeSetParseError
from ClusterShell.NodeSet import NodeSetParseRangeError


class NodeSetErrorTest(unittest.TestCase):

    def _testNS(self, pattern, expected_exc):
        try:
            nodeset = NodeSet(pattern)
            print nodeset
        except NodeSetParseError, e:
            self.assertEqual(e.__class__, expected_exc)
            return
        except NodeSetParseRangeError, e:
            self.assertEqual(e.__class__, expected_exc)
            return
        except:
            raise
        self.assert_(0, "error not detected/no exception raised [pattern=%s]" % pattern)
            

    def testBadRangeUsages(self):
        """test NodeSet parse errors in range"""
        self._testNS("", NodeSetParseError)
        self._testNS("nova[]", NodeSetParseRangeError)
        self._testNS("nova[-]", NodeSetParseRangeError)
        self._testNS("nova[A]", NodeSetParseRangeError)
        self._testNS("nova[2-5/a]", NodeSetParseRangeError)
        self._testNS("nova[3/2]", NodeSetParseRangeError)
        self._testNS("nova[3-/2]", NodeSetParseRangeError)
        self._testNS("nova[-3/2]", NodeSetParseRangeError)
        self._testNS("nova[-/2]", NodeSetParseRangeError)
        self._testNS("nova[4-a/2]", NodeSetParseRangeError)
        self._testNS("nova[4-3/2]", NodeSetParseRangeError)
        self._testNS("nova[4-5/-2]", NodeSetParseRangeError)
        self._testNS("nova[4-2/-2]", NodeSetParseRangeError)
        self._testNS("nova[004-002]", NodeSetParseRangeError)
        self._testNS("nova[3-59/2,102a]", NodeSetParseRangeError)
        self._testNS("nova[3-59/2,,102]", NodeSetParseRangeError)
        self._testNS("nova%s" % ("3" * 101), NodeSetParseRangeError)
        # nD
        self._testNS("nova[]p0", NodeSetParseRangeError)
        self._testNS("nova[-]p0", NodeSetParseRangeError)
        self._testNS("nova[A]p0", NodeSetParseRangeError)
        self._testNS("nova[2-5/a]p0", NodeSetParseRangeError)
        self._testNS("nova[3/2]p0", NodeSetParseRangeError)
        self._testNS("nova[3-/2]p0", NodeSetParseRangeError)
        self._testNS("nova[-3/2]p0", NodeSetParseRangeError)
        self._testNS("nova[-/2]p0", NodeSetParseRangeError)
        self._testNS("nova[4-a/2]p0", NodeSetParseRangeError)
        self._testNS("nova[4-3/2]p0", NodeSetParseRangeError)
        self._testNS("nova[4-5/-2]p0", NodeSetParseRangeError)
        self._testNS("nova[4-2/-2]p0", NodeSetParseRangeError)
        self._testNS("nova[004-002]p0", NodeSetParseRangeError)
        self._testNS("nova[3-59/2,102a]p0", NodeSetParseRangeError)
        self._testNS("nova[3-59/2,,102]p0", NodeSetParseRangeError)
        self._testNS("nova%sp0" % ("3" * 101), NodeSetParseRangeError)
        self._testNS("x4nova[]p0", NodeSetParseRangeError)
        self._testNS("x4nova[-]p0", NodeSetParseRangeError)
        self._testNS("x4nova[A]p0", NodeSetParseRangeError)
        self._testNS("x4nova[2-5/a]p0", NodeSetParseRangeError)
        self._testNS("x4nova[3/2]p0", NodeSetParseRangeError)
        self._testNS("x4nova[3-/2]p0", NodeSetParseRangeError)
        self._testNS("x4nova[-3/2]p0", NodeSetParseRangeError)
        self._testNS("x4nova[-/2]p0", NodeSetParseRangeError)
        self._testNS("x4nova[4-a/2]p0", NodeSetParseRangeError)
        self._testNS("x4nova[4-3/2]p0", NodeSetParseRangeError)
        self._testNS("x4nova[4-5/-2]p0", NodeSetParseRangeError)
        self._testNS("x4nova[4-2/-2]p0", NodeSetParseRangeError)
        self._testNS("x4nova[004-002]p0", NodeSetParseRangeError)
        self._testNS("x4nova[3-59/2,102a]p0", NodeSetParseRangeError)
        self._testNS("x4nova[3-59/2,,102]p0", NodeSetParseRangeError)
        self._testNS("x4nova%sp0" % ("3" * 101), NodeSetParseRangeError)

    def testBadUsages(self):
        """test NodeSet other parse errors"""
        self._testNS("nova[3-59/2,102", NodeSetParseError)
        self._testNS("nova3,nova4,,nova6", NodeSetParseError)
        self._testNS("nova3,nova4,5,nova6", NodeSetParseError)
        self._testNS("nova3,nova4,[5-8],nova6", NodeSetParseError)
        self._testNS("nova6,", NodeSetParseError)
        self._testNS("nova6[", NodeSetParseError)
        self._testNS("nova6]", NodeSetParseError)
        #self._testNS("nova%s", NodeSetParseError)
        # nD more
        self._testNS("[1-30][4-9]", NodeSetParseError)
        self._testNS("[1-30][4-9]p", NodeSetParseError)
        self._testNS("x[1-30][4-9]p", NodeSetParseError)
        self._testNS("x[1-30]p4-9]", NodeSetParseError)
        self._testNS("xazer][1-30]p[4-9]", NodeSetParseError)
        self._testNS("xa[[zer[1-30]p[4-9]", NodeSetParseRangeError)

    def testTypeSanityCheck(self):
        """test NodeSet input type sanity check"""
        self.assertRaises(TypeError, NodeSet, dict())
        self.assertRaises(TypeError, NodeSet, list())
        self.assertRaises(ValueError, NodeSetBase, None, RangeSet("1-10"))

    def testRangeSetEntryMismatch(self):
        """test NodeSet RangeSet entry mismatch"""
        nodeset = NodeSet("toto%s")
        rangeset = RangeSet("5")
        self.assertRaises(NodeSetError, nodeset._add, "toto%%s", rangeset)

    def test_bad_slices(self):
        nodeset = NodeSet("cluster[1-30]c[1-2]")
        self.assertRaises(TypeError, nodeset.__getitem__, slice(1,'foo'))


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(NodeSetErrorTest)
    unittest.TextTestRunner(verbosity=2).run(suite)
