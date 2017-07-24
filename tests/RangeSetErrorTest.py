#!/usr/bin/env python
# ClusterShell.NodeSet.RangeSet error handling test suite
# Written by S. Thiell


"""Unit test for RangeSet errors"""

import copy
import sys
import unittest

sys.path.insert(0, '../lib')

from ClusterShell.NodeSet import RangeSet
from ClusterShell.NodeSet import RangeSetParseError


class RangeSetErrorTest(unittest.TestCase):

    def _testRS(self, r, exc):
        try:
            rset = RangeSet(r)
        except RangeSetParseError as e:
            self.assertEqual(RangeSetParseError, exc)
            return
        except:
            raise
        self.assert_(0, "error not detected/no exception raised")

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
        self._testRS("3-59/2,102a", RangeSetParseError)
