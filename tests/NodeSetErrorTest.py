#!/usr/bin/env python
# ClusterShell.NodeSet.NodeSet error handling test suite
# Written by S. Thiell 2008-09-28
# $Id$


"""Unit test for RangeSet errors"""

import copy
import sys
import unittest

sys.path.append('../lib')

from ClusterShell.NodeSet import NodeSet
from ClusterShell.NodeSet import NodeSetParseError


class NodeSetErrorTest(unittest.TestCase):

    def _testNS(self, pattern, exc):
        try:
            nodeset = NodeSet(pattern)
            print nodeset
        except NodeSetParseError, e:
            self.assertEqual(NodeSetParseError, exc)
            return
        except:
            raise
        self.assert_(0, "error not detected/no exception raised [pattern=%s]" % pattern)
            

    def testBadRangeUsages(self):
        """test parse errors in range"""
        self._testNS("", NodeSetParseError)
        self._testNS("nova[]", NodeSetParseError)
        self._testNS("nova[-]", NodeSetParseError)
        self._testNS("nova[A]", NodeSetParseError)
        self._testNS("nova[2-5/a]", NodeSetParseError)
        self._testNS("nova[3/2]", NodeSetParseError)
        self._testNS("nova[3-/2]", NodeSetParseError)
        self._testNS("nova[-3/2]", NodeSetParseError)
        self._testNS("nova[-/2]", NodeSetParseError)
        self._testNS("nova[4-a/2]", NodeSetParseError)
        self._testNS("nova[4-3/2]", NodeSetParseError)
        self._testNS("nova[4-5/-2]", NodeSetParseError)
        self._testNS("nova[4-2/-2]", NodeSetParseError)
        self._testNS("nova[004-002]", NodeSetParseError)
        self._testNS("nova[3-59/2,102a]", NodeSetParseError)
        self._testNS("nova[3-59/2,,102]", NodeSetParseError)

    def testBadUsages(self):
        """test other parse errors"""
        self._testNS("nova[3-59/2,102", NodeSetParseError)
        self._testNS("nova3,nova4,,nova6", NodeSetParseError)
        self._testNS("nova3,nova4,5,nova6", NodeSetParseError)
        self._testNS("nova3,nova4,[5-8],nova6", NodeSetParseError)
        self._testNS("nova6,", NodeSetParseError)
        self._testNS("nova6[", NodeSetParseError)
        #self._testNS("nova6]", NodeSetParseError)
        #self._testNS("nova%s", NodeSetParseError)


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(NodeSetErrorTest)
    unittest.TextTestRunner(verbosity=2).run(suite)
