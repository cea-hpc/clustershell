#!/usr/bin/env python
# ClusterShell.NodeSet.NodeSet error handling test suite
# Written by S. Thiell 2008-09-28


"""Unit test for RangeSet errors"""

import copy
import sys
import unittest

sys.path.insert(0, '../lib')

from ClusterShell.NodeSet import NodeSet
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

    def testBadUsages(self):
        """test NodeSet other parse errors"""
        self._testNS("nova[3-59/2,102", NodeSetParseError)
        self._testNS("nova3,nova4,,nova6", NodeSetParseError)
        self._testNS("nova3,nova4,5,nova6", NodeSetParseError)
        self._testNS("nova3,nova4,[5-8],nova6", NodeSetParseError)
        self._testNS("nova6,", NodeSetParseError)
        self._testNS("nova6[", NodeSetParseError)
        #self._testNS("nova6]", NodeSetParseError)
        #self._testNS("nova%s", NodeSetParseError)

    def testTypeSanityCheck(self):
        """test NodeSet input type sanity check"""
        self.assertRaises(TypeError, NodeSet, dict())
        self.assertRaises(TypeError, NodeSet, list())


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(NodeSetErrorTest)
    unittest.TextTestRunner(verbosity=2).run(suite)
