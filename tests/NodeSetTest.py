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


class NodeSetTest(unittest.TestCase):

    def _assertNode(self, nodeset, nodename):
        self.assertEqual(str(nodeset), nodename)
        self.assertEqual(list(nodeset), [ nodename ])
        self.assertEqual(len(nodeset), 1)

    def testUnnumberedNode(self):
        """test unnumbered node"""
        nodeset = NodeSet("cws-machin")
        self._assertNode(nodeset, "cws-machin")

    def testNodeZero(self):
        """test node0"""
        nodeset = NodeSet("supercluster0")
        self._assertNode(nodeset, "supercluster0")

    def testNoPrefix(self):
        """test node without prefix"""
        nodeset = NodeSet("0cluster")
        self._assertNode(nodeset, "0cluster")
        nodeset = NodeSet("[0]cluster")
        self._assertNode(nodeset, "0cluster")

    def testFromListConstructor(self):
        """test NodeSet.fromlist constructor"""
        nodeset = NodeSet.fromlist([ "cluster33" ])
        self._assertNode(nodeset, "cluster33")
        nodeset = NodeSet.fromlist([ "cluster0", "cluster1", "cluster2", "cluster5", "cluster8", "cluster4", "cluster3" ])
        self.assertEqual(str(nodeset), "cluster[0-5,8]")
        self.assertEqual(len(nodeset), 7)

    def testDigitInPrefix(self):
        """test digit in prefix"""
        nodeset = NodeSet("clu-0-3")
        self._assertNode(nodeset, "clu-0-3")
        nodeset = NodeSet("clu-0-[3-23]")
        self.assertEqual(str(nodeset), "clu-0-[3-23]")

    def testNodeWithPercent(self):
        """test nodename with % character"""
        nodeset = NodeSet("cluster%s3")
        self._assertNode(nodeset, "cluster%s3")
        nodeset = NodeSet("clust%ser[3-30]")
        self.assertEqual(str(nodeset), "clust%ser[3-30]")

    def testNodeEightPad(self):
        """test padding feature"""
        nodeset = NodeSet("cluster008")
        self._assertNode(nodeset, "cluster008")

    def testNodeRangeIncludingZero(self):
        """test node range including zero"""
        nodeset = NodeSet("cluster[0-10]")
        self.assertEqual(str(nodeset), "cluster[0-10]")
        self.assertEqual(list(nodeset), [ "cluster0", "cluster1", "cluster2", "cluster3", "cluster4", "cluster5", "cluster6", "cluster7", "cluster8", "cluster9", "cluster10" ])
        self.assertEqual(len(nodeset), 11)

    def testSingle(self):
        """test single cluster node"""
        nodeset = NodeSet("cluster115")
        self._assertNode(nodeset, "cluster115")

    def testSingleNodeInRange(self):
        """test single cluster node in range"""
        nodeset = NodeSet("cluster[115]")
        self._assertNode(nodeset, "cluster115")

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

    def testSimpleStringUpdates(self):
        """test simple string-based update() method"""
        nodeset = NodeSet("cluster[115-117,130,166-170]")
        self.assertEqual(str(nodeset), "cluster[115-117,130,166-170]")
        nodeset.update("cluster171")
        self.assertEqual(str(nodeset), "cluster[115-117,130,166-171]")
        nodeset.update("cluster172")
        self.assertEqual(str(nodeset), "cluster[115-117,130,166-172]")
        nodeset.update("cluster174")
        self.assertEqual(str(nodeset), "cluster[115-117,130,166-172,174]")
        nodeset.update("cluster113")
        self.assertEqual(str(nodeset), "cluster[113,115-117,130,166-172,174]")
        nodeset.update("cluster173")
        self.assertEqual(str(nodeset), "cluster[113,115-117,130,166-174]")
        nodeset.update("cluster114")
        self.assertEqual(str(nodeset), "cluster[113-117,130,166-174]")

    def testSimpleNodeSetUpdates(self):
        """test simple nodeset-based update() method"""
        nodeset = NodeSet("cluster[115-117,130,166-170]")
        self.assertEqual(str(nodeset), "cluster[115-117,130,166-170]")
        nodeset.update(NodeSet("cluster171"))
        self.assertEqual(str(nodeset), "cluster[115-117,130,166-171]")
        nodeset.update(NodeSet("cluster172"))
        self.assertEqual(str(nodeset), "cluster[115-117,130,166-172]")
        nodeset.update(NodeSet("cluster174"))
        self.assertEqual(str(nodeset), "cluster[115-117,130,166-172,174]")
        nodeset.update(NodeSet("cluster113"))
        self.assertEqual(str(nodeset), "cluster[113,115-117,130,166-172,174]")
        nodeset.update(NodeSet("cluster173"))
        self.assertEqual(str(nodeset), "cluster[113,115-117,130,166-174]")
        nodeset.update(NodeSet("cluster114"))
        self.assertEqual(str(nodeset), "cluster[113-117,130,166-174]")

    def testStringUpdatesFromEmptyNodeSet(self):
        """test string-based update() method from empty nodeset"""
        nodeset = NodeSet()
        self.assertEqual(str(nodeset), "")
        nodeset.update("cluster115")
        self.assertEqual(str(nodeset), "cluster115")
        nodeset.update("cluster118")
        self.assertEqual(str(nodeset), "cluster[115,118]")
        nodeset.update("cluster[116-117]")
        self.assertEqual(str(nodeset), "cluster[115-118]")

    def testNodeSetUpdatesFromEmptyNodeSet(self):
        """test nodeset-based update() method from empty nodeset"""
        nodeset = NodeSet()
        self.assertEqual(str(nodeset), "")
        nodeset.update(NodeSet("cluster115"))
        self.assertEqual(str(nodeset), "cluster115")
        nodeset.update(NodeSet("cluster118"))
        self.assertEqual(str(nodeset), "cluster[115,118]")
        nodeset.update(NodeSet("cluster[116-117]"))
        self.assertEqual(str(nodeset), "cluster[115-118]")

    def testUpdatesWithSeveralPrefixes(self):
        """test update() method using several prefixes"""
        nodeset = NodeSet("cluster3")
        self.assertEqual(str(nodeset), "cluster3")
        nodeset.update("cluster5")
        self.assertEqual(str(nodeset), "cluster[3,5]")
        nodeset.update("tiger5")
        self.assert_(str(nodeset) == "cluster[3,5],tiger5" or str(nodeset) == "tiger5,cluster[3,5]")
        nodeset.update("tiger7")
        self.assert_(str(nodeset) == "cluster[3,5],tiger[5,7]" or str(nodeset) == "tiger[5,7],cluster[3,5]")
        nodeset.update("tiger6")
        self.assert_(str(nodeset) == "cluster[3,5],tiger[5-7]" or str(nodeset) == "tiger[5-7],cluster[3,5]")
        nodeset.update("cluster4")
        self.assert_(str(nodeset) == "cluster[3-5],tiger[5-7]" or str(nodeset) == "tiger[5-7],cluster[3-5]")

    def testOperatorUnion(self):
        """test union | operator"""
        nodeset = NodeSet("cluster[115-117,130,166-170]")
        self.assertEqual(str(nodeset), "cluster[115-117,130,166-170]")
        n_test1 = nodeset | NodeSet("cluster171")
        self.assertEqual(str(n_test1), "cluster[115-117,130,166-171]")
        n_test2 = n_test1 | NodeSet("cluster172")
        self.assertEqual(str(n_test2), "cluster[115-117,130,166-172]")
        n_test1 = n_test2 | NodeSet("cluster113")
        self.assertEqual(str(n_test1), "cluster[113,115-117,130,166-172]")
        n_test2 = n_test1 | NodeSet("cluster114")
        self.assertEqual(str(n_test2), "cluster[113-117,130,166-172]")

    def testOperatorUnionFromEmptyNodeSet(self):
        """test union | operator from empty nodeset"""
        nodeset = NodeSet()
        self.assertEqual(str(nodeset), "")
        n_test1 = nodeset | NodeSet("cluster115")
        self.assertEqual(str(n_test1), "cluster115")
        n_test2 = n_test1 | NodeSet("cluster118")
        self.assertEqual(str(n_test2), "cluster[115,118]")
        n_test1 = n_test2 | NodeSet("cluster[116,117]")
        self.assertEqual(str(n_test1), "cluster[115-118]")

    def testOperatorUnionWithSeveralPrefixes(self):
        """test union | operator using several prefixes"""
        nodeset = NodeSet("cluster3")
        self.assertEqual(str(nodeset), "cluster3")
        n_test1 = nodeset |  NodeSet("cluster5") 
        self.assertEqual(str(n_test1), "cluster[3,5]")
        n_test2 = n_test1 | NodeSet("tiger5") 
        self.assert_(str(n_test2) == "cluster[3,5],tiger5" or str(n_test2) == "tiger5,cluster[3,5]")
        n_test1 = n_test2 | NodeSet("tiger7") 
        self.assert_(str(n_test1) == "cluster[3,5],tiger[5,7]" or str(n_test1) == "tiger[5,7],cluster[3,5]")
        n_test2 = n_test1 | NodeSet("tiger6")
        self.assert_(str(n_test2) == "cluster[3,5],tiger[5-7]" or str(n_test2) == "tiger[5-7],cluster[3,5]")
        n_test1 = n_test2 | NodeSet("cluster4")
        self.assert_(str(n_test1) == "cluster[3-5],tiger[5-7]" or str(n_test1) == "tiger[5-7],cluster[3-5]")

    def testLen(self):
        """test len() results"""
        nodeset = NodeSet()
        self.assertEqual(len(nodeset), 0)
        nodeset.update("cluster[116-120]")
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
        nodeset.intersection_update("red[78-80]")
        self.assertEqual(str(nodeset), "red[78-80]")

        nodeset = NodeSet(nsstr)
        nodeset.intersection_update("red[54-249]")
        self.assertEqual(str(nodeset), "red[54-55,76-249]")

        nodeset = NodeSet(nsstr)
        nodeset.intersection_update("red[55-249]")
        self.assertEqual(str(nodeset), "red[55,76-249]")

        nodeset = NodeSet(nsstr)
        nodeset.intersection_update("red[55-100]")
        self.assertEqual(str(nodeset), "red[55,76-100]")

        nodeset = NodeSet(nsstr)
        nodeset.intersection_update("red[55-76]")
        self.assertEqual(str(nodeset), "red[55,76]")

        nodeset = NodeSet(nsstr)
        nodeset.intersection_update("red[55,76]")
        self.assertEqual(str(nodeset), "red[55,76]")

        nodeset = NodeSet(nsstr)
        nodeset.intersection_update("red55,red76")
        self.assertEqual(str(nodeset), "red[55,76]")

        # same with intersect(NodeSet)
        nodeset = NodeSet(nsstr)
        nodeset.intersection_update(NodeSet("red[78-80]"))
        self.assertEqual(str(nodeset), "red[78-80]")

        nodeset = NodeSet(nsstr)
        nodeset.intersection_update(NodeSet("red[54-249]"))
        self.assertEqual(str(nodeset), "red[54-55,76-249]")

        nodeset = NodeSet(nsstr)
        nodeset.intersection_update(NodeSet("red[55-249]"))
        self.assertEqual(str(nodeset), "red[55,76-249]")

        nodeset = NodeSet(nsstr)
        nodeset.intersection_update(NodeSet("red[55-100]"))
        self.assertEqual(str(nodeset), "red[55,76-100]")

        nodeset = NodeSet(nsstr)
        nodeset.intersection_update(NodeSet("red[55-76]"))
        self.assertEqual(str(nodeset), "red[55,76]")

        nodeset = NodeSet(nsstr)
        nodeset.intersection_update(NodeSet("red[55,76]"))
        self.assertEqual(str(nodeset), "red[55,76]")

        nodeset = NodeSet(nsstr)
        nodeset.intersection_update(NodeSet("red55,red76"))
        self.assertEqual(str(nodeset), "red[55,76]")

    def testIntersectSelf(self):
        """test nodes intersect (self)"""
        nodeset = NodeSet("red4955")
        self.assertEqual(len(nodeset), 1)
        nodeset.intersection_update(nodeset)
        self.assertEqual(len(nodeset), 1)
        self.assertEqual(str(nodeset), "red4955")

        nodeset = NodeSet("red")
        self.assertEqual(len(nodeset), 1)
        nodeset.intersection_update(nodeset)
        self.assertEqual(len(nodeset), 1)
        self.assertEqual(str(nodeset), "red")

        nodeset = NodeSet("red[78-149]")
        self.assertEqual(len(nodeset), 72)
        nodeset.intersection_update(nodeset)
        self.assertEqual(len(nodeset), 72)
        self.assertEqual(str(nodeset), "red[78-149]")

    def testSimpleDifferences(self):
        """test difference_update() method (simple)"""
        # nodeset-based subs
        nodeset = NodeSet("yellow120")
        self.assertEqual(len(nodeset), 1)
        nodeset.difference_update(NodeSet("yellow120"))
        self.assertEqual(len(nodeset), 0)

        nodeset = NodeSet("yellow")
        self.assertEqual(len(nodeset), 1)
        nodeset.difference_update(NodeSet("yellow"))
        self.assertEqual(len(nodeset), 0)

        nodeset = NodeSet("yellow")
        self.assertEqual(len(nodeset), 1)
        nodeset.difference_update(NodeSet("blue"))
        self.assertEqual(len(nodeset), 1)
        self.assertEqual(str(nodeset), "yellow")

        nodeset = NodeSet("yellow[45-240,570-764,800]")
        self.assertEqual(len(nodeset), 392)
        nodeset.difference_update(NodeSet("yellow[45-240,570-764,800]"))
        self.assertEqual(len(nodeset), 0)

        # same with string-based subs
        nodeset = NodeSet("yellow120")
        self.assertEqual(len(nodeset), 1)
        nodeset.difference_update("yellow120")
        self.assertEqual(len(nodeset), 0)

        nodeset = NodeSet("yellow")
        self.assertEqual(len(nodeset), 1)
        nodeset.difference_update("yellow")
        self.assertEqual(len(nodeset), 0)

        nodeset = NodeSet("yellow")
        self.assertEqual(len(nodeset), 1)
        nodeset.difference_update("blue")
        self.assertEqual(len(nodeset), 1)
        self.assertEqual(str(nodeset), "yellow")

        nodeset = NodeSet("yellow[45-240,570-764,800]")
        self.assertEqual(len(nodeset), 392)
        nodeset.difference_update("yellow[45-240,570-764,800]")
        self.assertEqual(len(nodeset), 0)

    def testSubSelf(self):
        """test difference_update() method (self)"""
        nodeset = NodeSet("yellow[120-148,167]")
        nodeset.difference_update(nodeset)
        self.assertEqual(len(nodeset), 0)

    def testSubMore(self):
        """test difference_update() method (more)"""
        nodeset = NodeSet("yellow[120-160]")
        self.assertEqual(len(nodeset), 41)
        for i in range(120, 161):
            nodeset.difference_update(NodeSet("yellow%d" % i))
        self.assertEqual(len(nodeset), 0)

    def testSubsAndAdds(self):
        """test update() and difference_update() methods together"""
        nodeset = NodeSet("yellow[120-160]")
        self.assertEqual(len(nodeset), 41)
        for i in range(120, 131):
            nodeset.difference_update(NodeSet("yellow%d" % i))
        self.assertEqual(len(nodeset), 30)
        for i in range(1940, 2040):
            nodeset.update(NodeSet("yellow%d" % i))
        self.assertEqual(len(nodeset), 130)

    def testSubsAndAddsMore(self):
        """test update() and difference_update() methods together (more)"""
        nodeset = NodeSet("yellow[120-160]")
        self.assertEqual(len(nodeset), 41)
        for i in range(120, 131):
            nodeset.difference_update(NodeSet("yellow%d" % i))
            nodeset.update(NodeSet("yellow%d" % (i + 1000)))
        self.assertEqual(len(nodeset), 41)
        for i in range(1120, 1131):
            nodeset.difference_update(NodeSet("yellow%d" % i))
        nodeset.difference_update(NodeSet("yellow[131-160]"))
        self.assertEqual(len(nodeset), 0)

    def testSubsAndAddsMore(self):
        """test update() and difference_update() methods together (with other digit in prefix)"""
        nodeset = NodeSet("clu-3-[120-160]")
        self.assertEqual(len(nodeset), 41)
        for i in range(120, 131):
            nodeset.difference_update(NodeSet("clu-3-[%d]" % i))
            nodeset.update(NodeSet("clu-3-[%d]" % (i + 1000)))
        self.assertEqual(len(nodeset), 41)
        for i in range(1120, 1131):
            nodeset.difference_update(NodeSet("clu-3-[%d]" % i))
        nodeset.difference_update(NodeSet("clu-3-[131-160]"))
        self.assertEqual(len(nodeset), 0)

    def testSubUnknownNodes(self):
        """test difference_update() method (with unknown nodes)"""
        nodeset = NodeSet("yellow[120-160]")
        self.assertEqual(len(nodeset), 41)
        nodeset.difference_update("red[35-49]")
        self.assertEqual(len(nodeset), 41)
        self.assertEqual(str(nodeset), "yellow[120-160]")

    def testSubMultiplePrefix(self):
        """test difference_update() method with multiple prefixes"""
        nodeset = NodeSet("yellow[120-160],red[32-147],blue3,green,white[2-3940],blue4,blue303")
        self.assertEqual(len(nodeset), 4100)
        for i in range(120, 131):
            nodeset.difference_update(NodeSet("red%d" % i))
            nodeset.update(NodeSet("red%d" % (i + 1000)))
            nodeset.update(NodeSet("yellow%d" % (i + 1000)))
        self.assertEqual(len(nodeset), 4111)
        for i in range(1120, 1131):
            nodeset.difference_update(NodeSet("red%d" % i))
            nodeset.difference_update(NodeSet("white%d" %i))
        nodeset.difference_update(NodeSet("yellow[131-160]"))
        self.assertEqual(len(nodeset), 4059)
        nodeset.difference_update(NodeSet("green"))
        self.assertEqual(len(nodeset), 4058)



if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(NodeSetTest)
    unittest.TextTestRunner(verbosity=2).run(suite)
