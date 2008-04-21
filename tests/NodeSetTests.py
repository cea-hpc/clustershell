#!/usr/bin/env python
# Cluster.NodeSet test suite
# Written by S. Thiell 2007-12-05
# $Id: NodeSetTests.py 24 2008-03-19 14:02:13Z st-cea $


"""Unit test for NodeSet"""

import copy
import sys
import unittest

sys.path.append('../lib')

from ClusterShell.NodeSet import NodeSet


class NodeSetTests(unittest.TestCase):

    def testUnnumberedNode(self):
        nodes = NodeSet("cws-cors")
        assert nodes.as_ranges() == "cws-cors"
        assert list(nodes) == [ "cws-cors" ]

    def testNodeZero(self):
        nodes = NodeSet("fortoy0")
        assert nodes.as_ranges() == "fortoy0"
        assert list(nodes) == [ "fortoy0" ]

    def testNodeEightPad(self):
        nodes = NodeSet("fortoy008")
        assert nodes.as_ranges() == "fortoy008"
        assert list(nodes) == [ "fortoy008" ]

    def testNodeRangeIncludingZero(self):
        nodes = NodeSet("fortoy[0-10]")
        assert nodes.as_ranges() == "fortoy[0-10]"
        assert list(nodes) == [ "fortoy0", "fortoy1", "fortoy2", "fortoy3", "fortoy4", "fortoy5", "fortoy6", "fortoy7", "fortoy8", "fortoy9", "fortoy10" ]

    def testSingle(self):
        nodes = NodeSet("cors115")
        assert nodes.as_ranges() == "cors115"
        assert list(nodes) == [ "cors115" ]

    def testSingleNodeInRange(self):
        nodes = NodeSet("cors[115]")
        assert nodes.as_ranges() == "cors115"
        assert list(nodes) == [ "cors115" ]

    def testRange(self):
        nodes = NodeSet("triton[1-100]")
        assert nodes.as_ranges() == "triton[1-100]"
        lst = copy.deepcopy(list(nodes))
        i = 1
        for n in lst:
            assert n == "triton%d" % i
            i += 1

    def testRangeWithPadding1(self):
        nodes = NodeSet("paris[0001-0100]")
        assert nodes.as_ranges() == "paris[0001-0100]"
        i = 1
        for n in nodes:
            assert n == "paris%04d" % i
            i += 1
        assert i == 101

    def testRangeWithPadding2(self):
        nodes = NodeSet("latour[0034-8127]")
        assert nodes.as_ranges() == "latour[0034-8127]"
        i = 34
        for n in nodes:
            assert n == "latour%04d" % i
            i += 1
        assert i == 8128

    def testRangeWithSuffix(self):
        nodes = NodeSet("roma[50-99]-ipmi")
        assert nodes.as_ranges() == "roma[50-99]-ipmi"
        i = 50
        for n in nodes:
            assert n == "roma%d-ipmi" % i
            i += 1
        assert i == 100

    def testCommadSeparatedAndRangeWithPadding(self):
        nodes = NodeSet("tigrou[0001,0002,1555-1559]")
        assert nodes.as_ranges() == "tigrou[0001-0002,1555-1559]"
        lst = list(nodes)
        assert lst[0] == "tigrou0001"
        assert lst[1] == "tigrou0002"
        assert lst[2] == "tigrou1555"
        assert lst[3] == "tigrou1556"
        assert lst[4] == "tigrou1557"
        assert lst[5] == "tigrou1558"
        assert lst[6] == "tigrou1559"

    def testVeryBigRange(self):
        nodes = NodeSet("bigmac[1-1000000]")
        assert nodes.as_ranges() == "bigmac[1-1000000]"
        i = 1
        for n in nodes:
            assert n == "bigmac%d" % i
            i += 1

    def testCommaSeparated(self):
        """Comma separated nodelist to range"""
        nodes = NodeSet("cors115,cors116,cors117,cors130,cors166")
        assert nodes.as_ranges() == "cors[115-117,130,166]"

    def testCommaSeparatedAndRange(self):
        """Comma separated nodelist and ranges to ranges"""
        nodes = NodeSet("cors115,cors116,cors117,cors130,cors[166-169],cors170")
        assert nodes.as_ranges() == "cors[115-117,130,166-170]"

    def testCommaSeparatedAndRanges(self):
        nodes = NodeSet("cors[115-117],cors130,cors[166-169],cors170")
        assert nodes.as_ranges() == "cors[115-117,130,166-170]"

    def testAdds(self):
        nodes = NodeSet("cors[115-117,130,166-170]")
        assert nodes.as_ranges() == "cors[115-117,130,166-170]"
        nodes.add("cors171")
        assert nodes.as_ranges() == "cors[115-117,130,166-171]"
        nodes.add("cors172")
        assert nodes.as_ranges() == "cors[115-117,130,166-172]"
        nodes.add("cors113")
        assert nodes.as_ranges() == "cors[113,115-117,130,166-172]"
        nodes.add("cors114")
        assert nodes.as_ranges() == "cors[113-117,130,166-172]"

    def testAddsFromEmptyNodeSet(self):
        nodes = NodeSet()
        assert nodes.as_ranges() == ""
        nodes.add("cors115")
        assert nodes.as_ranges() == "cors115"
        nodes.add("cors118")
        assert nodes.as_ranges() == "cors[115,118]"
        nodes.add("cors[116,117]")
        assert nodes.as_ranges() == "cors[115-118]"

    def testAddsWithSeveralPrefixes(self):
        nodes = NodeSet("tigrou3")
        assert nodes.as_ranges() == "tigrou3"
        nodes.add("tigrou4")
        assert nodes.as_ranges() == "tigrou[3-4]"
        nodes.add("tigron5")
        assert nodes.as_ranges() == "tigron5,tigrou[3-4]" or nodes.as_ranges() == "tigrou[3-4],tigron5"
        nodes.add("tigron7")
        assert nodes.as_ranges() == "tigron[5,7],tigrou[3-4]" or nodes.as_ranges() == "tigrou[3-4],tigron[5,7]"
        nodes.add("tigron6")
        assert nodes.as_ranges() == "tigron[5-7],tigrou[3-4]" or nodes.as_ranges() == "tigrou[3-4],tigron[5-7]"

    def testOperatorStrAdds(self):
        nodes = NodeSet("cors[115-117,130,166-170]")
        assert nodes.as_ranges() == "cors[115-117,130,166-170]"
        nodes += "cors171"
        assert nodes.as_ranges() == "cors[115-117,130,166-171]"
        nodes += "cors172"
        assert nodes.as_ranges() == "cors[115-117,130,166-172]"
        nodes += "cors113"
        assert nodes.as_ranges() == "cors[113,115-117,130,166-172]"
        nodes += "cors114"
        assert nodes.as_ranges() == "cors[113-117,130,166-172]"

    def testOperatorStrAddsFromEmptyNodeSet(self):
        nodes = NodeSet()
        assert nodes.as_ranges() == ""
        nodes += "cors115"
        assert nodes.as_ranges() == "cors115"
        nodes += "cors118"
        assert nodes.as_ranges() == "cors[115,118]"
        nodes += "cors[116,117]"
        assert nodes.as_ranges() == "cors[115-118]"

    def testOperatorStrAddsWithSeveralPrefixes(self):
        nodes = NodeSet("tigrou3")
        assert nodes.as_ranges() == "tigrou3"
        nodes += "tigrou4"
        assert nodes.as_ranges() == "tigrou[3-4]"
        nodes += "tigron5"
        assert nodes.as_ranges() == "tigron5,tigrou[3-4]" or nodes.as_ranges() == "tigrou[3-4],tigron5"
        nodes += "tigron7"
        assert nodes.as_ranges() == "tigron[5,7],tigrou[3-4]" or nodes.as_ranges() == "tigrou[3-4],tigron[5,7]"
        nodes += "tigron6"
        assert nodes.as_ranges() == "tigron[5-7],tigrou[3-4]" or nodes.as_ranges() == "tigrou[3-4],tigron[5-7]"

    def testOperatorAdds(self):
        nodes = NodeSet("cors[115-117,130,166-170]")
        assert nodes.as_ranges() == "cors[115-117,130,166-170]"
        nodes += NodeSet("cors171")
        assert nodes.as_ranges() == "cors[115-117,130,166-171]"
        nodes += NodeSet("cors172")
        assert nodes.as_ranges() == "cors[115-117,130,166-172]"
        nodes += NodeSet("cors113")
        assert nodes.as_ranges() == "cors[113,115-117,130,166-172]"
        nodes += NodeSet("cors114")
        assert nodes.as_ranges() == "cors[113-117,130,166-172]"

    def testOperatorAddsFromEmptyNodeSet(self):
        """test + operator from empty NodeSet"""
        nodes = NodeSet()
        assert nodes.as_ranges() == ""
        nodes += NodeSet("cors115")
        assert nodes.as_ranges() == "cors115"
        nodes += NodeSet("cors118")
        assert nodes.as_ranges() == "cors[115,118]"
        nodes += NodeSet("cors[116,117]")
        assert nodes.as_ranges() == "cors[115-118]"

    def testOperatorAddsWithSeveralPrefixes(self):
        """test + operator with several prefixes"""
        nodes = NodeSet("tigrou3")
        assert nodes.as_ranges() == "tigrou3"
        nodes += NodeSet("tigrou4")
        assert nodes.as_ranges() == "tigrou[3-4]"
        nodes += NodeSet("tigron5")
        assert nodes.as_ranges() == "tigron5,tigrou[3-4]" or nodes.as_ranges() == "tigrou[3-4],tigron5"
        nodes += NodeSet("tigron7")
        assert nodes.as_ranges() == "tigron[5,7],tigrou[3-4]" or nodes.as_ranges() == "tigrou[3-4],tigron[5,7]"
        nodes += NodeSet("tigron6")
        assert nodes.as_ranges() == "tigron[5-7],tigrou[3-4]" or nodes.as_ranges() == "tigrou[3-4],tigron[5-7]"

    def testLen(self):
        """test len(nodes)"""
        nodes = NodeSet()
        assert len(nodes) == 0
        nodes.add("cors[116-120]")
        assert len(nodes) == 5
        nodes = NodeSet("roma[50-99]-ipmi,cors[113,115-117,130,166-172],cws-tigrou,tigrou3")
        assert len(nodes) == (50+12+1+1)
        nodes = NodeSet("roma[50-99]-ipmi,cors[113,115-117,130,166-172],cws-tigrou,tigrou3,tigrou3,tigrou3,cors116")
        assert len(nodes) == (50+12+1+1)


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(NodeSetTests)
    unittest.TextTestRunner(verbosity=2).run(suite)
