#!/usr/bin/env python
# ClusterShell.NodeSet test suite
# Written by S. Thiell 2007-12-05
# $Id$


"""Unit test for NodeSet"""

import copy
import sys
import unittest

sys.path.append('../lib')

from ClusterShell.NodeSet import NodeSet


class NodeSetTests(unittest.TestCase):

    def _assertNode(self, nodeset, nodename, length):
        self.assertEqual(str(nodeset), nodename)
        self.assertEqual(list(nodeset), [ nodename ])
        self.assertEqual(len(nodeset), length)

    def testUnnumberedNode(self):
        """test unnumbered node"""
        nodeset = NodeSet("cws-machin")
        self._assertNode(nodeset, "cws-machin", 1)

    def testNodeZero(self):
        """test node0"""
        nodeset = NodeSet("supercluster0")
        self._assertNode(nodeset, "supercluster0", 1)

    def testNodeEightPad(self):
        """test padding feature"""
        nodeset = NodeSet("cluster008")
        self._assertNode(nodeset, "cluster008", 1)

    def testNodeRangeIncludingZero(self):
        """test node range including zero"""
        nodeset = NodeSet("cluster[0-10]")
        self.assertEqual(str(nodeset), "cluster[0-10]")
        self.assertEqual(list(nodeset), [ "cluster0", "cluster1", "cluster2", "cluster3", "cluster4", "cluster5", "cluster6", "cluster7", "cluster8", "cluster9", "cluster10" ])
        self.assertEqual(len(nodeset), 11)

    def testSingle(self):
        """test single cluster node"""
        nodeset = NodeSet("cluster115")
        self._assertNode(nodeset, "cluster115", 1)

    def testSingleNodeInRange(self):
        """test single cluster node in range"""
        nodeset = NodeSet("cluster[115]")
        self._assertNode(nodeset, "cluster115", 1)

    def testRange(self):
        """test simple range"""
        nodeset = NodeSet("cluster[1-100]")
        self.assertEqual(str(nodeset), "cluster[1-100]")
        self.assertEqual(len(nodeset), 100)

        i = 1
        for n in nodeset:
            self.assertEqual(n, "cluster%d" % i)
            i += 1
        self.assertEqual(i, 101)

        lst = copy.deepcopy(list(nodeset))
        i = 1
        for n in lst:
            self.assertEqual(n, "cluster%d" % i)
            i += 1
        self.assertEqual(i, 101)

    def testRangeWithPadding1(self):
        """test range with padding (1)"""
        nodeset = NodeSet("cluster[0001-0100]")
        self.assertEqual(str(nodeset), "cluster[0001-0100]")
        self.assertEqual(len(nodeset), 100)
        i = 1
        for n in nodeset:
            self.assertEqual(n, "cluster%04d" % i)
            i += 1
        self.assertEqual(i, 101)

    def testRangeWithPadding2(self):
        """test range with padding (2)"""
        nodeset = NodeSet("cluster[0034-8127]")
        self.assertEqual(str(nodeset), "cluster[0034-8127]")
        self.assertEqual(len(nodeset), 8094)

        i = 34
        for n in nodeset:
            self.assertEqual(n, "cluster%04d" % i)
            i += 1
        self.assertEqual(i, 8128)

    def testRangeWithSuffix(self):
        """test simple range with suffix"""
        nodeset = NodeSet("cluster[50-99]-ipmi")
        self.assertEqual(str(nodeset), "cluster[50-99]-ipmi")
        i = 50
        for n in nodeset:
            self.assertEqual(n, "cluster%d-ipmi" % i)
            i += 1
        self.assertEqual(i, 100)

    def testCommaSeparatedAndRangeWithPadding(self):
        """test comma separated, range and padding"""
        nodeset = NodeSet("cluster[0001,0002,1555-1559]")
        self.assertEqual(str(nodeset), "cluster[0001-0002,1555-1559]")
        self.assertEqual(list(nodeset), [ "cluster0001", "cluster0002", "cluster1555", "cluster1556", "cluster1557", "cluster1558", "cluster1559" ])

    def testCommaSeparatedAndRangeWithPaddingWithSuffix(self):
        """test comma separated, range and padding with suffix"""
        nodeset = NodeSet("cluster[0001,0002,1555-1559]-ipmi")
        self.assertEqual(str(nodeset), "cluster[0001-0002,1555-1559]-ipmi")
        self.assertEqual(list(nodeset), [ "cluster0001-ipmi", "cluster0002-ipmi", "cluster1555-ipmi", "cluster1556-ipmi", "cluster1557-ipmi", "cluster1558-ipmi", "cluster1559-ipmi" ])

    def testVeryBigRange(self):
        """test iterations with big range size"""
        nodeset = NodeSet("bigcluster[1-1000000]")
        self.assertEqual(str(nodeset), "bigcluster[1-1000000]")
        self.assertEqual(len(nodeset), 1000000)
        i = 1
        for n in nodeset:
            assert n == "bigcluster%d" % i
            i += 1

    def testCommaSeparated(self):
        """test comma separated to ranges (folding)"""
        nodeset = NodeSet("cluster115,cluster116,cluster117,cluster130,cluster166")
        self.assertEqual(str(nodeset), "cluster[115-117,130,166]")
        self.assertEqual(len(nodeset), 5)

    def testCommaSeparatedAndRange(self):
        """test comma separated and range to ranges (folding)"""
        nodeset = NodeSet("cluster115,cluster116,cluster117,cluster130,cluster[166-169],cluster170")
        self.assertEqual(str(nodeset), "cluster[115-117,130,166-170]")

    def testCommaSeparatedAndRanges(self):
        """test comma separated and ranges to ranges (folding)"""
        nodeset = NodeSet("cluster[115-117],cluster130,cluster[166-169],cluster170")
        self.assertEqual(str(nodeset), "cluster[115-117,130,166-170]")

    def testSimpleStringAdds(self):
        """test simple string-based add() method"""
        nodeset = NodeSet("cluster[115-117,130,166-170]")
        self.assertEqual(str(nodeset), "cluster[115-117,130,166-170]")
        nodeset.add("cluster171")
        self.assertEqual(str(nodeset), "cluster[115-117,130,166-171]")
        nodeset.add("cluster172")
        self.assertEqual(str(nodeset), "cluster[115-117,130,166-172]")
        nodeset.add("cluster174")
        self.assertEqual(str(nodeset), "cluster[115-117,130,166-172,174]")
        nodeset.add("cluster113")
        self.assertEqual(str(nodeset), "cluster[113,115-117,130,166-172,174]")
        nodeset.add("cluster173")
        self.assertEqual(str(nodeset), "cluster[113,115-117,130,166-174]")
        nodeset.add("cluster114")
        self.assertEqual(str(nodeset), "cluster[113-117,130,166-174]")

    def testSimpleNodeSetAdds(self):
        """test simple nodeset-based add() method"""
        nodeset = NodeSet("cluster[115-117,130,166-170]")
        self.assertEqual(str(nodeset), "cluster[115-117,130,166-170]")
        nodeset.add(NodeSet("cluster171"))
        self.assertEqual(str(nodeset), "cluster[115-117,130,166-171]")
        nodeset.add(NodeSet("cluster172"))
        self.assertEqual(str(nodeset), "cluster[115-117,130,166-172]")
        nodeset.add(NodeSet("cluster174"))
        self.assertEqual(str(nodeset), "cluster[115-117,130,166-172,174]")
        nodeset.add(NodeSet("cluster113"))
        self.assertEqual(str(nodeset), "cluster[113,115-117,130,166-172,174]")
        nodeset.add(NodeSet("cluster173"))
        self.assertEqual(str(nodeset), "cluster[113,115-117,130,166-174]")
        nodeset.add(NodeSet("cluster114"))
        self.assertEqual(str(nodeset), "cluster[113-117,130,166-174]")

    def testStringAddsFromEmptyNodeSet(self):
        """test string-based add() method from empty nodeset"""
        nodeset = NodeSet()
        self.assertEqual(str(nodeset), "")
        nodeset.add("cluster115")
        self.assertEqual(str(nodeset), "cluster115")
        nodeset.add("cluster118")
        self.assertEqual(str(nodeset), "cluster[115,118]")
        nodeset.add("cluster[116-117]")
        self.assertEqual(str(nodeset), "cluster[115-118]")

    def testNodeSetAddsFromEmptyNodeSet(self):
        """test nodeset-based add() method from empty nodeset"""
        nodeset = NodeSet()
        self.assertEqual(str(nodeset), "")
        nodeset.add(NodeSet("cluster115"))
        self.assertEqual(str(nodeset), "cluster115")
        nodeset.add(NodeSet("cluster118"))
        self.assertEqual(str(nodeset), "cluster[115,118]")
        nodeset.add(NodeSet("cluster[116-117]"))
        self.assertEqual(str(nodeset), "cluster[115-118]")

    def testAddsWithSeveralPrefixes(self):
        """test add() method using several prefixes"""
        nodeset = NodeSet("cluster3")
        self.assertEqual(str(nodeset), "cluster3")
        nodeset.add("cluster5")
        self.assertEqual(str(nodeset), "cluster[3,5]")
        nodeset.add("tiger5")
        self.assert_(str(nodeset) == "cluster[3,5],tiger5" or str(nodeset) == "tiger5,cluster[3,5]")
        nodeset.add("tiger7")
        self.assert_(str(nodeset) == "cluster[3,5],tiger[5,7]" or str(nodeset) == "tiger[5,7],cluster[3,5]")
        nodeset.add("tiger6")
        self.assert_(str(nodeset) == "cluster[3,5],tiger[5-7]" or str(nodeset) == "tiger[5-7],cluster[3,5]")
        nodeset.add("cluster4")
        self.assert_(str(nodeset) == "cluster[3-5],tiger[5-7]" or str(nodeset) == "tiger[5-7],cluster[3-5]")

    def testOperatorStrAdds(self):
        """test + operator"""
        nodeset = NodeSet("cluster[115-117,130,166-170]")
        self.assertEqual(str(nodeset), "cluster[115-117,130,166-170]")
        nodeset += "cluster171"
        self.assertEqual(str(nodeset), "cluster[115-117,130,166-171]")
        nodeset += "cluster172"
        self.assertEqual(str(nodeset), "cluster[115-117,130,166-172]")
        nodeset += "cluster113"
        self.assertEqual(str(nodeset), "cluster[113,115-117,130,166-172]")
        nodeset += "cluster114"
        self.assertEqual(str(nodeset), "cluster[113-117,130,166-172]")

    def testOperatorStrAddsFromEmptyNodeSet(self):
        """test string-based + operator from empty nodeset"""
        nodeset = NodeSet()
        self.assertEqual(str(nodeset), "")
        nodeset += "cluster115"
        self.assertEqual(str(nodeset), "cluster115")
        nodeset += "cluster118"
        self.assertEqual(str(nodeset), "cluster[115,118]")
        nodeset += "cluster[116,117]"
        self.assertEqual(str(nodeset), "cluster[115-118]")

    def testOperatorStrAddsWithSeveralPrefixes(self):
        """test string-based + operator using several prefixes"""
        nodeset = NodeSet("cluster3")
        self.assertEqual(str(nodeset), "cluster3")
        nodeset += "cluster5"
        self.assertEqual(str(nodeset), "cluster[3,5]")
        nodeset += "tiger5"
        self.assert_(str(nodeset) == "cluster[3,5],tiger5" or str(nodeset) == "tiger5,cluster[3,5]")
        nodeset += "tiger7"
        self.assert_(str(nodeset) == "cluster[3,5],tiger[5,7]" or str(nodeset) == "tiger[5,7],cluster[3,5]")
        nodeset += "tiger6"
        self.assert_(str(nodeset) == "cluster[3,5],tiger[5-7]" or str(nodeset) == "tiger[5-7],cluster[3,5]")
        nodeset += "cluster4"
        self.assert_(str(nodeset) == "cluster[3-5],tiger[5-7]" or str(nodeset) == "tiger[5-7],cluster[3-5]")

    def testOperatorAdds(self):
        """test nodeset-based + operator"""
        nodeset = NodeSet("cluster[115-117,130,166-170]")
        self.assertEqual(str(nodeset), "cluster[115-117,130,166-170]")
        nodeset += NodeSet("cluster171")
        self.assertEqual(str(nodeset), "cluster[115-117,130,166-171]")
        nodeset += NodeSet("cluster172")
        self.assertEqual(str(nodeset), "cluster[115-117,130,166-172]")
        nodeset += NodeSet("cluster113")
        self.assertEqual(str(nodeset), "cluster[113,115-117,130,166-172]")
        nodeset += NodeSet("cluster114")
        self.assertEqual(str(nodeset), "cluster[113-117,130,166-172]")

    def testOperatorAddsFromEmptyNodeSet(self):
        """test nodeset-based + operator from empty nodeset"""
        nodeset = NodeSet()
        self.assertEqual(str(nodeset), "")
        nodeset += NodeSet("cluster115")
        self.assertEqual(str(nodeset), "cluster115")
        nodeset += NodeSet("cluster118")
        self.assertEqual(str(nodeset), "cluster[115,118]")
        nodeset += NodeSet("cluster[116,117]")
        self.assertEqual(str(nodeset), "cluster[115-118]")

    def testOperatorAddsWithSeveralPrefixes(self):
        """test nodeset-based + operator using several prefixes"""
        nodeset = NodeSet("cluster3")
        self.assertEqual(str(nodeset), "cluster3")
        nodeset += NodeSet("cluster5")
        self.assertEqual(str(nodeset), "cluster[3,5]")
        nodeset += NodeSet("tiger5")
        self.assert_(str(nodeset) == "cluster[3,5],tiger5" or str(nodeset) == "tiger5,cluster[3,5]")
        nodeset += NodeSet("tiger7")
        self.assert_(str(nodeset) == "cluster[3,5],tiger[5,7]" or str(nodeset) == "tiger[5,7],cluster[3,5]")
        nodeset += NodeSet("tiger6")
        self.assert_(str(nodeset) == "cluster[3,5],tiger[5-7]" or str(nodeset) == "tiger[5-7],cluster[3,5]")
        nodeset += NodeSet("cluster4")
        self.assert_(str(nodeset) == "cluster[3-5],tiger[5-7]" or str(nodeset) == "tiger[5-7],cluster[3-5]")

    def testLen(self):
        """test len() results"""
        nodeset = NodeSet()
        self.assertEqual(len(nodeset), 0)
        nodeset.add("cluster[116-120]")
        self.assertEqual(len(nodeset), 5)
        nodeset = NodeSet("roma[50-99]-ipmi,cors[113,115-117,130,166-172],cws-tigrou,tigrou3")
        self.assertEqual(len(nodeset), 50+12+1+1) 
        nodeset = NodeSet("roma[50-99]-ipmi,cors[113,115-117,130,166-172],cws-tigrou,tigrou3,tigrou3,tigrou3,cors116")
        self.assertEqual(len(nodeset), 50+12+1+1) 

    def testIntersectSimple(self):
        """test nodes intersection (simple)"""
        nsstr = "red[34-55,76-249,300-403]"
        nodeset = NodeSet(nsstr)
        self.assertEqual(len(nodeset), 300)

        nodeset = NodeSet(nsstr)
        nodeset.intersect("red[78-80]")
        self.assertEqual(str(nodeset), "red[78-80]")

        nodeset = NodeSet(nsstr)
        nodeset.intersect("red[54-249]")
        self.assertEqual(str(nodeset), "red[54-55,76-249]")

        nodeset = NodeSet(nsstr)
        nodeset.intersect("red[55-249]")
        self.assertEqual(str(nodeset), "red[55,76-249]")

        nodeset = NodeSet(nsstr)
        nodeset.intersect("red[55-100]")
        self.assertEqual(str(nodeset), "red[55,76-100]")

        nodeset = NodeSet(nsstr)
        nodeset.intersect("red[55-76]")
        self.assertEqual(str(nodeset), "red[55,76]")

        nodeset = NodeSet(nsstr)
        nodeset.intersect("red[55,76]")
        self.assertEqual(str(nodeset), "red[55,76]")

        nodeset = NodeSet(nsstr)
        nodeset.intersect("red55,red76")
        self.assertEqual(str(nodeset), "red[55,76]")

        # same with intersect(NodeSet)
        nodeset = NodeSet(nsstr)
        nodeset.intersect(NodeSet("red[78-80]"))
        self.assertEqual(str(nodeset), "red[78-80]")

        nodeset = NodeSet(nsstr)
        nodeset.intersect(NodeSet("red[54-249]"))
        self.assertEqual(str(nodeset), "red[54-55,76-249]")

        nodeset = NodeSet(nsstr)
        nodeset.intersect(NodeSet("red[55-249]"))
        self.assertEqual(str(nodeset), "red[55,76-249]")

        nodeset = NodeSet(nsstr)
        nodeset.intersect(NodeSet("red[55-100]"))
        self.assertEqual(str(nodeset), "red[55,76-100]")

        nodeset = NodeSet(nsstr)
        nodeset.intersect(NodeSet("red[55-76]"))
        self.assertEqual(str(nodeset), "red[55,76]")

        nodeset = NodeSet(nsstr)
        nodeset.intersect(NodeSet("red[55,76]"))
        self.assertEqual(str(nodeset), "red[55,76]")

        nodeset = NodeSet(nsstr)
        nodeset.intersect(NodeSet("red55,red76"))
        self.assertEqual(str(nodeset), "red[55,76]")

    def testIntersectSelf(self):
        """test nodes intersect (self)"""
        nodeset = NodeSet("red4955")
        self.assertEqual(len(nodeset), 1)
        nodeset.intersect(nodeset)
        self.assertEqual(len(nodeset), 1)
        self.assertEqual(str(nodeset), "red4955")

        nodeset = NodeSet("red")
        self.assertEqual(len(nodeset), 1)
        nodeset.intersect(nodeset)
        self.assertEqual(len(nodeset), 1)
        self.assertEqual(str(nodeset), "red")

        nodeset = NodeSet("red[78-149]")
        self.assertEqual(len(nodeset), 72)
        nodeset.intersect(nodeset)
        self.assertEqual(len(nodeset), 72)
        self.assertEqual(str(nodeset), "red[78-149]")

    def testSimpleSubs(self):
        """test sub() method (simple)"""
        # nodeset-based subs
        nodeset = NodeSet("yellow120")
        self.assertEqual(len(nodeset), 1)
        nodeset.sub(NodeSet("yellow120"))
        self.assertEqual(len(nodeset), 0)

        nodeset = NodeSet("yellow")
        self.assertEqual(len(nodeset), 1)
        nodeset.sub(NodeSet("yellow"))
        self.assertEqual(len(nodeset), 0)

        nodeset = NodeSet("yellow")
        self.assertEqual(len(nodeset), 1)
        nodeset.sub(NodeSet("blue"))
        self.assertEqual(len(nodeset), 1)
        self.assertEqual(str(nodeset), "yellow")

        nodeset = NodeSet("yellow[45-240,570-764,800]")
        self.assertEqual(len(nodeset), 392)
        nodeset.sub(NodeSet("yellow[45-240,570-764,800]"))
        self.assertEqual(len(nodeset), 0)

        # same with string-based subs
        nodeset = NodeSet("yellow120")
        self.assertEqual(len(nodeset), 1)
        nodeset.sub("yellow120")
        self.assertEqual(len(nodeset), 0)

        nodeset = NodeSet("yellow")
        self.assertEqual(len(nodeset), 1)
        nodeset.sub("yellow")
        self.assertEqual(len(nodeset), 0)

        nodeset = NodeSet("yellow")
        self.assertEqual(len(nodeset), 1)
        nodeset.sub("blue")
        self.assertEqual(len(nodeset), 1)
        self.assertEqual(str(nodeset), "yellow")

        nodeset = NodeSet("yellow[45-240,570-764,800]")
        self.assertEqual(len(nodeset), 392)
        nodeset.sub("yellow[45-240,570-764,800]")
        self.assertEqual(len(nodeset), 0)

    def testSubSelf(self):
        """test sub() method (self)"""
        nodeset = NodeSet("yellow[120-148,167]")
        nodeset.sub(nodeset)
        self.assertEqual(len(nodeset), 0)

    def testSubMore(self):
        """test sub() method (more)"""
        nodeset = NodeSet("yellow[120-160]")
        self.assertEqual(len(nodeset), 41)
        for i in range(120, 161):
            nodeset.sub(NodeSet("yellow%d" % i))
        self.assertEqual(len(nodeset), 0)

    def testSubsAndAdds(self):
        """test add() and sub() methods together"""
        nodeset = NodeSet("yellow[120-160]")
        self.assertEqual(len(nodeset), 41)
        for i in range(120, 131):
            nodeset.sub(NodeSet("yellow%d" % i))
        self.assertEqual(len(nodeset), 30)
        for i in range(1940, 2040):
            nodeset.add(NodeSet("yellow%d" % i))
        self.assertEqual(len(nodeset), 130)

    def testSubsAndAddsMore(self):
        """test add() and sub() methods together (more)"""
        nodeset = NodeSet("yellow[120-160]")
        self.assertEqual(len(nodeset), 41)
        for i in range(120, 131):
            nodeset.sub(NodeSet("yellow%d" % i))
            nodeset.add(NodeSet("yellow%d" % (i + 1000)))
        self.assertEqual(len(nodeset), 41)
        for i in range(1120, 1131):
            nodeset.sub(NodeSet("yellow%d" % i))
        nodeset.sub(NodeSet("yellow[131-160]"))
        self.assertEqual(len(nodeset), 0)

    def testSubUnknownNodes(self):
        """test sub() method (with unknown nodes)"""
        nodeset = NodeSet("yellow[120-160]")
        self.assertEqual(len(nodeset), 41)
        nodeset.sub("red[35-49]")
        self.assertEqual(len(nodeset), 41)
        self.assertEqual(str(nodeset), "yellow[120-160]")

    def testSubMultiplePrefix(self):
        """test sub() method with multiple prefixes"""
        nodeset = NodeSet("yellow[120-160],red[32-147],blue3,green,white[2-3940],blue4,blue303")
        self.assertEqual(len(nodeset), 4100)
        for i in range(120, 131):
            nodeset.sub(NodeSet("red%d" % i))
            nodeset.add(NodeSet("red%d" % (i + 1000)))
            nodeset.add(NodeSet("yellow%d" % (i + 1000)))
        self.assertEqual(len(nodeset), 4111)
        for i in range(1120, 1131):
            nodeset.sub(NodeSet("red%d" % i))
            nodeset.sub(NodeSet("white%d" %i))
        nodeset.sub(NodeSet("yellow[131-160]"))
        self.assertEqual(len(nodeset), 4059)
        nodeset.sub(NodeSet("green"))
        self.assertEqual(len(nodeset), 4058)



if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(NodeSetTests)
    unittest.TextTestRunner(verbosity=2).run(suite)
