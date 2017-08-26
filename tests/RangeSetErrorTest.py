"""
Unit test for RangeSet errors
"""

import copy
import sys
import unittest

sys.path.insert(0, '../lib')

from ClusterShell.NodeSet import RangeSet
from ClusterShell.NodeSet import RangeSetParseError


class RangeSetErrorTest(unittest.TestCase):

    def _testRS(self, pattern, expected_exc):
        self.assertRaises(expected_exc, RangeSet, pattern)

    def testBadUsages(self):
        """test parse errors"""
        self._testRS("", RangeSetParseError)
        self._testRS("-", RangeSetParseError)
        self._testRS("A", RangeSetParseError)
        self._testRS("2-5/a", RangeSetParseError)
        self._testRS("3/2", RangeSetParseError)
        self._testRS("3-/2", RangeSetParseError)
        self._testRS("-3/2", RangeSetParseError)
        self._testRS("-/2", RangeSetParseError)
        self._testRS("4-a/2", RangeSetParseError)
        self._testRS("4-3/2", RangeSetParseError)
        self._testRS("4-5/-2", RangeSetParseError)
        self._testRS("4-2/-2", RangeSetParseError)
        self._testRS("004-002", RangeSetParseError)
        self._testRS("3-59/2,102a", RangeSetParseError)
