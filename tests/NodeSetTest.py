#!/usr/bin/env python
# ClusterShell.NodeSet test suite
# Written by S. Thiell 2007-12-05


"""Unit test for NodeSet"""

import binascii
import copy
import pickle
import sys
import unittest

sys.path.insert(0, '../lib')

from ClusterShell.NodeSet import RangeSet, NodeSet, fold, expand
from ClusterShell.NodeSet import NodeGroupBase, NodeSetBase


class NodeSetTest(unittest.TestCase):

    def _assertNode(self, nodeset, nodename):
        self.assertEqual(str(nodeset), nodename)
        self.assertEqual(list(nodeset), [ nodename ])
        self.assertEqual(len(nodeset), 1)

    def testUnnumberedNode(self):
        """test NodeSet with unnumbered node"""
        nodeset = NodeSet("cws-machin")
        self._assertNode(nodeset, "cws-machin")

    def testNodeZero(self):
        """test NodeSet with node0"""
        nodeset = NodeSet("supercluster0")
        self._assertNode(nodeset, "supercluster0")

    def testNoPrefix(self):
        """test NodeSet with node without prefix"""
        nodeset = NodeSet("0cluster")
        self._assertNode(nodeset, "0cluster")
        nodeset = NodeSet("[0]cluster")
        self._assertNode(nodeset, "0cluster")

    def testWhitespacePrefix(self):
        """test NodeSet parsing ignoring whitespace"""
        nodeset = NodeSet(" tigrou2 , tigrou7 , tigrou[5,9-11] ")
        self.assertEqual(str(nodeset), "tigrou[2,5,7,9-11]")
        nodeset = NodeSet("   tigrou2 ,    tigrou5,tigrou7 , tigrou[ 9   - 11 ]    ")
        self.assertEqual(str(nodeset), "tigrou[2,5,7,9-11]")

    def testFromListConstructor(self):
        """test NodeSet.fromlist() constructor"""
        nodeset = NodeSet.fromlist([ "cluster33" ])
        self._assertNode(nodeset, "cluster33")
        nodeset = NodeSet.fromlist([ "cluster0", "cluster1", "cluster2", "cluster5", "cluster8", "cluster4", "cluster3" ])
        self.assertEqual(str(nodeset), "cluster[0-5,8]")
        self.assertEqual(len(nodeset), 7)
        # updaten() test
        nodeset.updaten(["cluster10", "cluster9"])
        self.assertEqual(str(nodeset), "cluster[0-5,8-10]")
        self.assertEqual(len(nodeset), 9)
        # single nodes test
        nodeset = NodeSet.fromlist([ "cluster0", "cluster1", "cluster", "wool", "cluster3" ])
        self.assertEqual(str(nodeset), "cluster,cluster[0-1,3],wool")
        self.assertEqual(len(nodeset), 5)

    def testDigitInPrefix(self):
        """test NodeSet digit in prefix"""
        nodeset = NodeSet("clu-0-3")
        self._assertNode(nodeset, "clu-0-3")
        nodeset = NodeSet("clu-0-[3-23]")
        self.assertEqual(str(nodeset), "clu-0-[3-23]")

    def testNodeWithPercent(self):
        """test NodeSet on nodename with % character"""
        nodeset = NodeSet("cluster%s3")
        self._assertNode(nodeset, "cluster%s3")
        nodeset = NodeSet("clust%ser[3-30]")
        self.assertEqual(str(nodeset), "clust%ser[3-30]")

    def testNodeEightPad(self):
        """test NodeSet padding feature"""
        nodeset = NodeSet("cluster008")
        self._assertNode(nodeset, "cluster008")

    def testNodeRangeIncludingZero(self):
        """test NodeSet with node range including zero"""
        nodeset = NodeSet("cluster[0-10]")
        self.assertEqual(str(nodeset), "cluster[0-10]")
        self.assertEqual(list(nodeset), [ "cluster0", "cluster1", "cluster2", "cluster3", "cluster4", "cluster5", "cluster6", "cluster7", "cluster8", "cluster9", "cluster10" ])
        self.assertEqual(len(nodeset), 11)

    def testSingle(self):
        """test NodeSet single cluster node"""
        nodeset = NodeSet("cluster115")
        self._assertNode(nodeset, "cluster115")

    def testSingleNodeInRange(self):
        """test NodeSet single cluster node in range"""
        nodeset = NodeSet("cluster[115]")
        self._assertNode(nodeset, "cluster115")

    def testRange(self):
        """test NodeSet with simple range"""
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
        """test NodeSet with range with padding (1)"""
        nodeset = NodeSet("cluster[0001-0100]")
        self.assertEqual(str(nodeset), "cluster[0001-0100]")
        self.assertEqual(len(nodeset), 100)
        i = 1
        for n in nodeset:
            self.assertEqual(n, "cluster%04d" % i)
            i += 1
        self.assertEqual(i, 101)

    def testRangeWithPadding2(self):
        """test NodeSet with range with padding (2)"""
        nodeset = NodeSet("cluster[0034-8127]")
        self.assertEqual(str(nodeset), "cluster[0034-8127]")
        self.assertEqual(len(nodeset), 8094)

        i = 34
        for n in nodeset:
            self.assertEqual(n, "cluster%04d" % i)
            i += 1
        self.assertEqual(i, 8128)

    def testRangeWithSuffix(self):
        """test NodeSet with simple range with suffix"""
        nodeset = NodeSet("cluster[50-99]-ipmi")
        self.assertEqual(str(nodeset), "cluster[50-99]-ipmi")
        i = 50
        for n in nodeset:
            self.assertEqual(n, "cluster%d-ipmi" % i)
            i += 1
        self.assertEqual(i, 100)

    def testCommaSeparatedAndRangeWithPadding(self):
        """test NodeSet comma separated, range and padding"""
        nodeset = NodeSet("cluster[0001,0002,1555-1559]")
        self.assertEqual(str(nodeset), "cluster[0001-0002,1555-1559]")
        self.assertEqual(list(nodeset), [ "cluster0001", "cluster0002", "cluster1555", "cluster1556", "cluster1557", "cluster1558", "cluster1559" ])

    def testCommaSeparatedAndRangeWithPaddingWithSuffix(self):
        """test NodeSet comma separated, range and padding with suffix"""
        nodeset = NodeSet("cluster[0001,0002,1555-1559]-ipmi")
        self.assertEqual(str(nodeset), "cluster[0001-0002,1555-1559]-ipmi")
        self.assertEqual(list(nodeset), [ "cluster0001-ipmi", "cluster0002-ipmi", "cluster1555-ipmi", "cluster1556-ipmi", "cluster1557-ipmi", "cluster1558-ipmi", "cluster1559-ipmi" ])

    def testVeryBigRange(self):
        """test NodeSet iterations with big range size"""
        nodeset = NodeSet("bigcluster[1-1000000]")
        self.assertEqual(str(nodeset), "bigcluster[1-1000000]")
        self.assertEqual(len(nodeset), 1000000)
        i = 1
        for n in nodeset:
            assert n == "bigcluster%d" % i
            i += 1

    def testCommaSeparated(self):
        """test NodeSet comma separated to ranges (folding)"""
        nodeset = NodeSet("cluster115,cluster116,cluster117,cluster130,cluster166")
        self.assertEqual(str(nodeset), "cluster[115-117,130,166]")
        self.assertEqual(len(nodeset), 5)

    def testCommaSeparatedAndRange(self):
        """test NodeSet comma separated and range to ranges (folding)"""
        nodeset = NodeSet("cluster115,cluster116,cluster117,cluster130,cluster[166-169],cluster170")
        self.assertEqual(str(nodeset), "cluster[115-117,130,166-170]")

    def testCommaSeparatedAndRanges(self):
        """test NodeSet comma separated and ranges to ranges (folding)"""
        nodeset = NodeSet("cluster[115-117],cluster130,cluster[166-169],cluster170")
        self.assertEqual(str(nodeset), "cluster[115-117,130,166-170]")

    def testSimpleStringUpdates(self):
        """test NodeSet simple string-based update()"""
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
        """test NodeSet simple nodeset-based update()"""
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
        """test NodeSet string-based NodeSet.update() from empty nodeset"""
        nodeset = NodeSet()
        self.assertEqual(str(nodeset), "")
        nodeset.update("cluster115")
        self.assertEqual(str(nodeset), "cluster115")
        nodeset.update("cluster118")
        self.assertEqual(str(nodeset), "cluster[115,118]")
        nodeset.update("cluster[116-117]")
        self.assertEqual(str(nodeset), "cluster[115-118]")

    def testNodeSetUpdatesFromEmptyNodeSet(self):
        """test NodeSet-based update() method from empty nodeset"""
        nodeset = NodeSet()
        self.assertEqual(str(nodeset), "")
        nodeset.update(NodeSet("cluster115"))
        self.assertEqual(str(nodeset), "cluster115")
        nodeset.update(NodeSet("cluster118"))
        self.assertEqual(str(nodeset), "cluster[115,118]")
        nodeset.update(NodeSet("cluster[116-117]"))
        self.assertEqual(str(nodeset), "cluster[115-118]")

    def testUpdatesWithSeveralPrefixes(self):
        """test NodeSet.update() using several prefixes"""
        nodeset = NodeSet("cluster3")
        self.assertEqual(str(nodeset), "cluster3")
        nodeset.update("cluster5")
        self.assertEqual(str(nodeset), "cluster[3,5]")
        nodeset.update("tiger5")
        self.assertEqual(str(nodeset), "cluster[3,5],tiger5")
        nodeset.update("tiger7")
        self.assertEqual(str(nodeset), "cluster[3,5],tiger[5,7]")
        nodeset.update("tiger6")
        self.assertEqual(str(nodeset), "cluster[3,5],tiger[5-7]")
        nodeset.update("cluster4")
        self.assertEqual(str(nodeset), "cluster[3-5],tiger[5-7]")

    def testOperatorUnion(self):
        """test NodeSet union | operator"""
        nodeset = NodeSet("cluster[115-117,130,166-170]")
        self.assertEqual(str(nodeset), "cluster[115-117,130,166-170]")
        # 1
        n_test1 = nodeset | NodeSet("cluster171")
        self.assertEqual(str(n_test1), "cluster[115-117,130,166-171]")
        nodeset2 = nodeset.copy()
        self.assertEqual(str(nodeset), "cluster[115-117,130,166-170]")
        nodeset2 |= NodeSet("cluster171")
        self.assertEqual(str(nodeset2), "cluster[115-117,130,166-171]")
        # btw validate modifying a copy did not change original
        self.assertEqual(str(nodeset), "cluster[115-117,130,166-170]")
        # 2
        n_test2 = n_test1 | NodeSet("cluster172")
        self.assertEqual(str(n_test2), "cluster[115-117,130,166-172]")
        nodeset2 |= NodeSet("cluster172")
        self.assertEqual(str(nodeset2), "cluster[115-117,130,166-172]")
        self.assertEqual(str(nodeset), "cluster[115-117,130,166-170]")
        # 3
        n_test1 = n_test2 | NodeSet("cluster113")
        self.assertEqual(str(n_test1), "cluster[113,115-117,130,166-172]")
        nodeset2 |= NodeSet("cluster113")
        self.assertEqual(str(nodeset2), "cluster[113,115-117,130,166-172]")
        self.assertEqual(str(nodeset), "cluster[115-117,130,166-170]")
        # 4
        n_test2 = n_test1 | NodeSet("cluster114")
        self.assertEqual(str(n_test2), "cluster[113-117,130,166-172]")
        nodeset2 |= NodeSet("cluster114")
        self.assertEqual(str(nodeset2), "cluster[113-117,130,166-172]")
        self.assertEqual(nodeset2, NodeSet("cluster[113-117,130,166-172]"))
        self.assertEqual(str(nodeset), "cluster[115-117,130,166-170]")
        # more
        original = NodeSet("cluster0")
        nodeset = original.copy()
        for i in xrange(1, 3000):
            nodeset = nodeset | NodeSet("cluster%d" % i)
        self.assertEqual(len(nodeset), 3000)
        self.assertEqual(str(nodeset), "cluster[0-2999]")
        self.assertEqual(len(original), 1)
        self.assertEqual(str(original), "cluster0")
        nodeset2 = original.copy()
        for i in xrange(1, 3000):
            nodeset2 |= NodeSet("cluster%d" % i)
        self.assertEqual(nodeset, nodeset2)
        for i in xrange(3000, 5000):
            nodeset2 |= NodeSet("cluster%d" % i)
        self.assertEqual(len(nodeset2), 5000)
        self.assertEqual(str(nodeset2), "cluster[0-4999]")
        self.assertEqual(len(nodeset), 3000)
        self.assertEqual(str(nodeset), "cluster[0-2999]")
        self.assertEqual(len(original), 1)
        self.assertEqual(str(original), "cluster0")

    def testOperatorUnionFromEmptyNodeSet(self):
        """test NodeSet union | operator from empty nodeset"""
        nodeset = NodeSet()
        self.assertEqual(str(nodeset), "")
        n_test1 = nodeset | NodeSet("cluster115")
        self.assertEqual(str(n_test1), "cluster115")
        n_test2 = n_test1 | NodeSet("cluster118")
        self.assertEqual(str(n_test2), "cluster[115,118]")
        n_test1 = n_test2 | NodeSet("cluster[116,117]")
        self.assertEqual(str(n_test1), "cluster[115-118]")

    def testOperatorUnionWithSeveralPrefixes(self):
        """test NodeSet union | operator using several prefixes"""
        nodeset = NodeSet("cluster3")
        self.assertEqual(str(nodeset), "cluster3")
        n_test1 = nodeset |  NodeSet("cluster5") 
        self.assertEqual(str(n_test1), "cluster[3,5]")
        n_test2 = n_test1 | NodeSet("tiger5") 
        self.assertEqual(str(n_test2), "cluster[3,5],tiger5")
        n_test1 = n_test2 | NodeSet("tiger7") 
        self.assertEqual(str(n_test1), "cluster[3,5],tiger[5,7]")
        n_test2 = n_test1 | NodeSet("tiger6")
        self.assertEqual(str(n_test2), "cluster[3,5],tiger[5-7]")
        n_test1 = n_test2 | NodeSet("cluster4")
        self.assertEqual(str(n_test1), "cluster[3-5],tiger[5-7]")

    def testOperatorSub(self):
        """test NodeSet difference/sub - operator"""
        nodeset = NodeSet("cluster[115-117,130,166-170]")
        self.assertEqual(str(nodeset), "cluster[115-117,130,166-170]")
        # __sub__
        n_test1 = nodeset - NodeSet("cluster[115,130]")
        self.assertEqual(str(n_test1), "cluster[116-117,166-170]")
        nodeset2 = copy.copy(nodeset)
        nodeset2 -= NodeSet("cluster[115,130]")
        self.assertEqual(str(nodeset2), "cluster[116-117,166-170]")
        self.assertEqual(nodeset2, NodeSet("cluster[116-117,166-170]"))

    def testOperatorAnd(self):
        """test NodeSet intersection/and & operator"""
        nodeset = NodeSet("cluster[115-117,130,166-170]")
        self.assertEqual(str(nodeset), "cluster[115-117,130,166-170]")
        # __and__
        n_test1 = nodeset & NodeSet("cluster[115-167]")
        self.assertEqual(str(n_test1), "cluster[115-117,130,166-167]")
        nodeset2 = copy.copy(nodeset)
        nodeset2 &= NodeSet("cluster[115-167]")
        self.assertEqual(str(nodeset2), "cluster[115-117,130,166-167]")
        self.assertEqual(nodeset2, NodeSet("cluster[115-117,130,166-167]"))

    def testOperatorXor(self):
        """test NodeSet symmetric_difference/xor & operator"""
        nodeset = NodeSet("cluster[115-117,130,166-170]")
        self.assertEqual(str(nodeset), "cluster[115-117,130,166-170]")
        # __xor__
        n_test1 = nodeset ^ NodeSet("cluster[115-167]")
        self.assertEqual(str(n_test1), "cluster[118-129,131-165,168-170]")
        nodeset2 = copy.copy(nodeset)
        nodeset2 ^= NodeSet("cluster[115-167]")
        self.assertEqual(str(nodeset2), "cluster[118-129,131-165,168-170]")
        self.assertEqual(nodeset2, NodeSet("cluster[118-129,131-165,168-170]"))

    def testLen(self):
        """test NodeSet len() results"""
        nodeset = NodeSet()
        self.assertEqual(len(nodeset), 0)
        nodeset.update("cluster[116-120]")
        self.assertEqual(len(nodeset), 5)
        nodeset = NodeSet("roma[50-99]-ipmi,cors[113,115-117,130,166-172],cws-tigrou,tigrou3")
        self.assertEqual(len(nodeset), 50+12+1+1) 
        nodeset = NodeSet("roma[50-99]-ipmi,cors[113,115-117,130,166-172],cws-tigrou,tigrou3,tigrou3,tigrou3,cors116")
        self.assertEqual(len(nodeset), 50+12+1+1) 

    def testIntersection(self):
        """test NodeSet.intersection()"""
        nsstr = "red[34-55,76-249,300-403],blue,green"
        nodeset = NodeSet(nsstr)
        self.assertEqual(len(nodeset), 302)

        nsstr2 = "red[32-57,72-249,300-341],blue,yellow"
        nodeset2 = NodeSet(nsstr2)
        self.assertEqual(len(nodeset2), 248)

        inodeset = nodeset.intersection(nodeset2)
        # originals should not change
        self.assertEqual(len(nodeset), 302)
        self.assertEqual(len(nodeset2), 248)
        self.assertEqual(str(nodeset), "blue,green,red[34-55,76-249,300-403]")
        self.assertEqual(str(nodeset2), "blue,red[32-57,72-249,300-341],yellow")
        # result
        self.assertEqual(len(inodeset), 239)
        self.assertEqual(str(inodeset), "blue,red[34-55,76-249,300-341]")

    def testIntersectUpdate(self):
        """test NodeSet.intersection_update()"""
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

        # single nodes test
        nodeset = NodeSet("red,blue,yellow")
        nodeset.intersection_update("blue,green,yellow")
        self.assertEqual(len(nodeset), 2)
        self.assertEqual(str(nodeset), "blue,yellow")

    def testIntersectSelf(self):
        """test Nodeset.intersection_update(self)"""
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

        nodeset = NodeSet("red")
        self.assertEqual(len(nodeset), 1)
        nodeset.intersection_update("red")
        self.assertEqual(len(nodeset), 1)
        self.assertEqual(str(nodeset), "red")

        nodeset = NodeSet("red")
        self.assertEqual(len(nodeset), 1)
        nodeset.intersection_update("blue")
        self.assertEqual(len(nodeset), 0)

        nodeset = NodeSet("red[78-149]")
        self.assertEqual(len(nodeset), 72)
        nodeset.intersection_update(nodeset)
        self.assertEqual(len(nodeset), 72)
        self.assertEqual(str(nodeset), "red[78-149]")

    def testIntersectReturnNothing(self):
        """test NodeSet intersect that returns empty NodeSet"""
        nodeset = NodeSet("blue43")
        self.assertEqual(len(nodeset), 1)
        nodeset.intersection_update("blue42")
        self.assertEqual(len(nodeset), 0)

    def testDifference(self):
        """test NodeSet.difference()"""
        nsstr = "red[34-55,76-249,300-403],blue,green"
        nodeset = NodeSet(nsstr)
        self.assertEqual(len(nodeset), 302)

        nsstr2 = "red[32-57,72-249,300-341],blue,yellow"
        nodeset2 = NodeSet(nsstr2)
        self.assertEqual(len(nodeset2), 248)

        inodeset = nodeset.difference(nodeset2)
        # originals should not change
        self.assertEqual(len(nodeset), 302)
        self.assertEqual(len(nodeset2), 248)
        self.assertEqual(str(nodeset), "blue,green,red[34-55,76-249,300-403]")
        self.assertEqual(str(nodeset2), "blue,red[32-57,72-249,300-341],yellow")
        # result
        self.assertEqual(len(inodeset), 63)
        self.assertEqual(str(inodeset), "green,red[342-403]")

    def testDifferenceUpdate(self):
        """test NodeSet.difference_update()"""
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
        """test NodeSet.difference_update() method (self)"""
        nodeset = NodeSet("yellow[120-148,167]")
        nodeset.difference_update(nodeset)
        self.assertEqual(len(nodeset), 0)

    def testSubMore(self):
        """test NodeSet.difference_update() method (more)"""
        nodeset = NodeSet("yellow[120-160]")
        self.assertEqual(len(nodeset), 41)
        for i in range(120, 161):
            nodeset.difference_update(NodeSet("yellow%d" % i))
        self.assertEqual(len(nodeset), 0)

    def testSubsAndAdds(self):
        """test NodeSet.update() and difference_update() together"""
        nodeset = NodeSet("yellow[120-160]")
        self.assertEqual(len(nodeset), 41)
        for i in range(120, 131):
            nodeset.difference_update(NodeSet("yellow%d" % i))
        self.assertEqual(len(nodeset), 30)
        for i in range(1940, 2040):
            nodeset.update(NodeSet("yellow%d" % i))
        self.assertEqual(len(nodeset), 130)

    def testSubsAndAddsMore(self):
        """test NodeSet.update() and difference_update() together (more)"""
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

    def testSubsAndAddsMoreDigit(self):
        """test NodeSet.update() and difference_update() together (with other digit in prefix)"""
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
        """test NodeSet.difference_update() with unknown nodes"""
        nodeset = NodeSet("yellow[120-160]")
        self.assertEqual(len(nodeset), 41)
        nodeset.difference_update("red[35-49]")
        self.assertEqual(len(nodeset), 41)
        self.assertEqual(str(nodeset), "yellow[120-160]")

    def testSubMultiplePrefix(self):
        """test NodeSet.difference_update() with multiple prefixes"""
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

    def testGetItem(self):
        """test NodeSet getitem()"""
        nodeset = NodeSet("yeti[30,34-51,59-60]")
        self.assertEqual(len(nodeset), 21)
        self.assertEqual(nodeset[0], "yeti30")
        self.assertEqual(nodeset[1], "yeti34")
        self.assertEqual(nodeset[2], "yeti35")
        self.assertEqual(nodeset[3], "yeti36")
        self.assertEqual(nodeset[18], "yeti51")
        self.assertEqual(nodeset[19], "yeti59")
        self.assertEqual(nodeset[20], "yeti60")
        self.assertRaises(IndexError, nodeset.__getitem__, 21)
        # negative indices
        self.assertEqual(nodeset[-1], "yeti60")
        for n in range(1, len(nodeset)):
            self.assertEqual(nodeset[-n], nodeset[len(nodeset)-n])

        # test getitem with some nodes without range
        nodeset = NodeSet("abc,cde[3-9,11],fgh")
        self.assertEqual(len(nodeset), 10)
        self.assertEqual(nodeset[0], "abc")
        self.assertEqual(nodeset[1], "cde3")
        self.assertEqual(nodeset[2], "cde4")
        self.assertEqual(nodeset[3], "cde5")
        self.assertEqual(nodeset[7], "cde9")
        self.assertEqual(nodeset[8], "cde11")
        self.assertEqual(nodeset[9], "fgh")
        self.assertRaises(IndexError, nodeset.__getitem__, 10)
        # test getitem with rangeset padding
        nodeset = NodeSet("prune[003-034,349-353/2]")
        self.assertEqual(len(nodeset), 35)
        self.assertEqual(nodeset[0], "prune003")
        self.assertEqual(nodeset[1], "prune004")
        self.assertEqual(nodeset[31], "prune034")
        self.assertEqual(nodeset[32], "prune349")
        self.assertEqual(nodeset[33], "prune351")
        self.assertEqual(nodeset[34], "prune353")
        self.assertRaises(IndexError, nodeset.__getitem__, 35)

    def testGetSlice(self):
        """test NodeSet getitem() with slice"""
        nodeset = NodeSet("yeti[30,34-51,59-60]")
        self.assertEqual(len(nodeset), 21)
        self.assertEqual(len(nodeset[0:2]), 2)
        self.assertEqual(str(nodeset[0:2]), "yeti[30,34]")
        self.assertEqual(len(nodeset[1:3]), 2)
        self.assertEqual(str(nodeset[1:3]), "yeti[34-35]")
        self.assertEqual(len(nodeset[19:21]), 2)
        self.assertEqual(str(nodeset[19:21]), "yeti[59-60]")
        self.assertEqual(len(nodeset[20:22]), 1)
        self.assertEqual(str(nodeset[20:22]), "yeti60")
        self.assertEqual(len(nodeset[21:24]), 0)
        self.assertEqual(str(nodeset[21:24]), "")
        # negative indices
        self.assertEqual(str(nodeset[:-1]), "yeti[30,34-51,59]")
        self.assertEqual(str(nodeset[:-2]), "yeti[30,34-51]")
        self.assertEqual(str(nodeset[1:-2]), "yeti[34-51]")
        self.assertEqual(str(nodeset[2:-2]), "yeti[35-51]")
        self.assertEqual(str(nodeset[9:-3]), "yeti[42-50]")
        self.assertEqual(str(nodeset[10:-9]), "yeti[43-44]")
        self.assertEqual(str(nodeset[10:-10]), "yeti43")
        self.assertEqual(str(nodeset[11:-10]), "")
        self.assertEqual(str(nodeset[11:-11]), "")
        self.assertEqual(str(nodeset[::-2]), "yeti[30,35,37,39,41,43,45,47,49,51,60]")
        self.assertEqual(str(nodeset[::-3]), "yeti[35,38,41,44,47,50,60]")
        # advanced
        self.assertEqual(str(nodeset[0:10:2]), "yeti[30,35,37,39,41]")
        self.assertEqual(str(nodeset[1:11:2]), "yeti[34,36,38,40,42]")
        self.assertEqual(str(nodeset[:11:3]), "yeti[30,36,39,42]")
        self.assertEqual(str(nodeset[11::4]), "yeti[44,48,59]")
        self.assertEqual(str(nodeset[14:]), "yeti[47-51,59-60]")
        self.assertEqual(str(nodeset[:]), "yeti[30,34-51,59-60]")
        self.assertEqual(str(nodeset[::5]), "yeti[30,38,43,48,60]")
        # with unindexed nodes
        nodeset = NodeSet("foo,bar,bur")
        self.assertEqual(len(nodeset), 3)
        self.assertEqual(len(nodeset[0:2]), 2)
        self.assertEqual(str(nodeset[0:2]), "bar,bur")
        self.assertEqual(str(nodeset[1:2]), "bur")
        self.assertEqual(str(nodeset[1:3]), "bur,foo")
        self.assertEqual(str(nodeset[2:4]), "foo")
        nodeset = NodeSet("foo,bar,bur3,bur1")
        self.assertEqual(len(nodeset), 4)
        self.assertEqual(len(nodeset[0:2]), 2)
        self.assertEqual(len(nodeset[1:3]), 2)
        self.assertEqual(len(nodeset[2:4]), 2)
        self.assertEqual(len(nodeset[3:5]), 1)
        self.assertEqual(str(nodeset[2:3]), "bur3")
        self.assertEqual(str(nodeset[3:4]), "foo")
        self.assertEqual(str(nodeset[0:2]), "bar,bur1")
        self.assertEqual(str(nodeset[1:3]), "bur[1,3]")
        # using range step
        nodeset = NodeSet("yeti[10-98/2]")
        self.assertEqual(str(nodeset[1:9:3]), "yeti[12,18,24]")
        self.assertEqual(str(nodeset[::17]), "yeti[10,44,78]")
        nodeset = NodeSet("yeti[10-98/2]", autostep=2)
        self.assertEqual(str(nodeset[22:29]), "yeti[54-66/2]")
        # stepping scalability
        nodeset = NodeSet("yeti[10-9800/2]", autostep=2)
        self.assertEqual(str(nodeset[22:2900]), "yeti[54-5808/2]")
        self.assertEqual(str(nodeset[22:2900:3]), "yeti[54-5808/6]")
        nodeset = NodeSet("yeti[10-14,20-26,30-33]")
        self.assertEqual(str(nodeset[2:6]), "yeti[12-14,20]")
        # multiple patterns
        nodeset = NodeSet("stone[1-9],wood[1-9]")
        self.assertEqual(str(nodeset[:]), "stone[1-9],wood[1-9]")
        self.assertEqual(str(nodeset[1:2]), "stone2")
        self.assertEqual(str(nodeset[8:9]), "stone9")
        self.assertEqual(str(nodeset[8:10]), "stone9,wood1")
        self.assertEqual(str(nodeset[9:10]), "wood1")
        self.assertEqual(str(nodeset[9:]), "wood[1-9]")
        nodeset = NodeSet("stone[1-9],water[10-12],wood[1-9]")
        self.assertEqual(str(nodeset[8:10]), "stone9,water10")
        self.assertEqual(str(nodeset[11:15]), "water12,wood[1-3]")
        nodeset = NodeSet("stone[1-9],water,wood[1-9]")
        self.assertEqual(str(nodeset[8:10]), "stone9,water")
        self.assertEqual(str(nodeset[8:11]), "stone9,water,wood1")
        self.assertEqual(str(nodeset[9:11]), "water,wood1")
        self.assertEqual(str(nodeset[9:12]), "water,wood[1-2]")

    def testSplit(self):
        """test NodeSet split()"""
        # Empty nodeset
        nodeset = NodeSet()
        self.assertEqual((), tuple(nodeset.split(2)))
        # Not enough element
        nodeset = NodeSet("foo[1]")
        self.assertEqual((NodeSet("foo[1]"),), \
                         tuple(nodeset.split(2)))
        # Exact number of elements
        nodeset = NodeSet("foo[1-6]")
        self.assertEqual((NodeSet("foo[1-2]"), NodeSet("foo[3-4]"), \
                         NodeSet("foo[5-6]")), tuple(nodeset.split(3)))
        # Check limit results
        nodeset = NodeSet("bar[2-4]")
        for i in (3, 4):
            self.assertEqual((NodeSet("bar2"), NodeSet("bar3"), \
                             NodeSet("bar4")), tuple(nodeset.split(i)))
        
    def testAdd(self):
        """test NodeSet add()"""
        nodeset = NodeSet()
        nodeset.add("green")
        self.assertEqual(len(nodeset), 1)
        self.assertEqual(str(nodeset), "green")
        self.assertEqual(nodeset[0], "green")
        nodeset = NodeSet()
        nodeset.add("green35")
        self.assertEqual(len(nodeset), 1)
        self.assertEqual(str(nodeset), "green35")
        self.assertEqual(nodeset[0], "green35")
        nodeset = NodeSet()
        nodeset.add("green[3,5-46]")
        self.assertEqual(len(nodeset), 43)
        self.assertEqual(nodeset[0], "green3")
        nodeset = NodeSet()
        nodeset.add("green[3,5-46],black64,orange[045-148]")
        self.assertEqual(len(nodeset), 148)
        self.assert_("green5" in nodeset)
        self.assert_("black64" in nodeset)
        self.assert_("orange046" in nodeset)

    def testAddAdjust(self):
        """test NodeSet adjusting add()"""
        # autostep OFF
        nodeset = NodeSet()
        nodeset.add("green[1-8/2]")
        self.assertEqual(str(nodeset), "green[1,3,5,7]")
        self.assertEqual(len(nodeset), 4)
        nodeset.add("green[6-17/2]")
        self.assertEqual(str(nodeset), "green[1,3,5-8,10,12,14,16]")
        self.assertEqual(len(nodeset), 10)
        # autostep ON
        nodeset = NodeSet(autostep=2)
        nodeset.add("green[1-8/2]")
        self.assertEqual(str(nodeset), "green[1-7/2]")
        self.assertEqual(len(nodeset), 4)
        nodeset.add("green[6-17/2]")
        self.assertEqual(str(nodeset), "green[1-5/2,6-7,8-16/2]")
        self.assertEqual(len(nodeset), 10)

    def testRemove(self):
        """test NodeSet remove()"""
        # from empty nodeset
        nodeset = NodeSet()
        self.assertEqual(len(nodeset), 0)
        self.assertRaises(KeyError, nodeset.remove, "tintin23")
        self.assertRaises(KeyError, nodeset.remove, "tintin[35-36]")
        nodeset.update("milou36")
        self.assertEqual(len(nodeset), 1)
        self.assertRaises(KeyError, nodeset.remove, "tintin23")
        self.assert_("milou36" in nodeset)
        nodeset.remove("milou36")
        self.assertEqual(len(nodeset), 0)
        nodeset.update("milou[36-60,76,95],haddock[1-12],tournesol")
        self.assertEqual(len(nodeset), 40)
        nodeset.remove("milou76")
        self.assertEqual(len(nodeset), 39)
        nodeset.remove("milou[36-39]")
        self.assertEqual(len(nodeset), 35)
        self.assertRaises(KeyError, nodeset.remove, "haddock13")
        self.assertEqual(len(nodeset), 35)
        self.assertRaises(KeyError, nodeset.remove, "haddock[1-15]")
        self.assertEqual(len(nodeset), 35)
        self.assertRaises(KeyError, nodeset.remove, "tutu")
        self.assertEqual(len(nodeset), 35)
        nodeset.remove("tournesol")
        self.assertEqual(len(nodeset), 34)
        nodeset.remove("haddock[1-12]")
        self.assertEqual(len(nodeset), 22)
        nodeset.remove("milou[40-60,95]")
        self.assertEqual(len(nodeset), 0)
        self.assertRaises(KeyError, nodeset.remove, "tournesol")
        self.assertRaises(KeyError, nodeset.remove, "milou40")
        # from non-empty nodeset
        nodeset = NodeSet("haddock[16-3045]")
        self.assertEqual(len(nodeset), 3030)
        self.assertRaises(KeyError, nodeset.remove, "haddock15")
        self.assert_("haddock16" in nodeset)
        self.assertEqual(len(nodeset), 3030)
        nodeset.remove("haddock[16,18-3044]")
        self.assertEqual(len(nodeset), 2)
        self.assertRaises(KeyError, nodeset.remove, "haddock3046")
        self.assertRaises(KeyError, nodeset.remove, "haddock[16,3060]")
        self.assertRaises(KeyError, nodeset.remove, "haddock[3045-3046]")
        self.assertRaises(KeyError, nodeset.remove, "haddock[3045,3049-3051/2]")
        nodeset.remove("haddock3045")
        self.assertEqual(len(nodeset), 1)
        self.assertRaises(KeyError, nodeset.remove, "haddock[3045]")
        self.assertEqual(len(nodeset), 1)
        nodeset.remove("haddock17")
        self.assertEqual(len(nodeset), 0)

    def testClear(self):
        """test NodeSet clear()"""
        nodeset = NodeSet("purple[35-39]")
        self.assertEqual(len(nodeset), 5)
        nodeset.clear()
        self.assertEqual(len(nodeset), 0)
    
    def testContains(self):
        """test NodeSet contains()"""
        nodeset = NodeSet()
        self.assertEqual(len(nodeset), 0)
        self.assert_("foo" not in nodeset)
        nodeset.update("bar")
        self.assertEqual(len(nodeset), 1)
        self.assertEqual(str(nodeset), "bar")
        self.assert_("bar" in nodeset)
        nodeset.update("foo[20-40]")
        self.assert_("foo" not in nodeset)
        self.assert_("foo39" in nodeset)
        for node in nodeset:
            self.assert_(node in nodeset)
        nodeset.update("dark[2000-4000/4]")
        self.assert_("dark3000" in nodeset)
        self.assert_("dark3002" not in nodeset)
        for node in nodeset:
            self.assert_(node in nodeset)
        nodeset = NodeSet("scale[0-10000]")
        self.assert_("black64" not in nodeset)
        self.assert_("scale9346" in nodeset)
        nodeset = NodeSet("scale[0-10000]", autostep=2)
        self.assert_("scale9346" in nodeset[::2])
        self.assert_("scale9347" not in nodeset[::2])

    def testContainsUsingPadding(self):
        """test NodeSet contains() when using padding"""
        nodeset = NodeSet("white[001,030]")
        nodeset.add("white113")
        self.assertTrue(NodeSet("white30") in nodeset)
        self.assertTrue(NodeSet("white030") in nodeset)
        # case: nodeset without padding info is compared to a
        # padding-initialized range
        self.assert_(NodeSet("white113") in nodeset)
        self.assert_(NodeSet("white[001,113]") in nodeset)
        self.assert_(NodeSet("gene0113") in NodeSet("gene[001,030,113]"))
        self.assert_(NodeSet("gene0113") in NodeSet("gene[0001,0030,0113]"))
        self.assert_(NodeSet("gene0113") in NodeSet("gene[098-113]"))
        self.assert_(NodeSet("gene0113") in NodeSet("gene[0098-0113]"))
        # case: len(str(ielem)) >= rgpad
        nodeset = NodeSet("white[001,099]")
        nodeset.add("white100")
        nodeset.add("white1000")
        self.assert_(NodeSet("white1000") in nodeset)

    def testIsSuperSet(self):
        """test NodeSet issuperset()"""
        nodeset = NodeSet("tronic[0036-1630]")
        self.assertEqual(len(nodeset), 1595)
        self.assert_(nodeset.issuperset("tronic[0036-1630]"))
        self.assert_(nodeset.issuperset("tronic[0140-0200]"))
        self.assert_(nodeset.issuperset(NodeSet("tronic[0140-0200]")))
        self.assert_(nodeset.issuperset("tronic0070"))
        self.assert_(not nodeset.issuperset("tronic0034"))
        # check padding issue - since 1.6 padding is ignored in this case
        self.assert_(nodeset.issuperset("tronic36"))
        self.assert_(nodeset.issuperset("tronic[36-40]"))
        self.assert_(nodeset.issuperset(NodeSet("tronic[36-40]")))
        # check gt
        self.assert_(nodeset > NodeSet("tronic[0100-0200]"))
        self.assert_(not nodeset > NodeSet("tronic[0036-1630]"))
        self.assert_(not nodeset > NodeSet("tronic[0036-1631]"))
        self.assert_(nodeset >= NodeSet("tronic[0100-0200]"))
        self.assert_(nodeset >= NodeSet("tronic[0036-1630]"))
        self.assert_(not nodeset >= NodeSet("tronic[0036-1631]"))
        # multiple patterns case
        nodeset = NodeSet("tronic[0036-1630],lounge[20-660/2]")
        self.assert_(nodeset > NodeSet("tronic[0100-0200]"))
        self.assert_(nodeset > NodeSet("lounge[36-400/2]"))
        self.assert_(nodeset.issuperset(NodeSet("lounge[36-400/2],tronic[0100-660]")))
        self.assert_(nodeset > NodeSet("lounge[36-400/2],tronic[0100-660]"))

    def testIsSubSet(self):
        """test NodeSet issubset()"""
        nodeset = NodeSet("artcore[3-999]")
        self.assertEqual(len(nodeset), 997)
        self.assert_(nodeset.issubset("artcore[3-999]"))
        self.assert_(nodeset.issubset("artcore[1-1000]"))
        self.assert_(not nodeset.issubset("artcore[350-427]"))
        # check lt
        self.assert_(nodeset < NodeSet("artcore[2-32000]"))
        self.assert_(nodeset < NodeSet("artcore[2-32000],lounge[35-65/2]"))
        self.assert_(not nodeset < NodeSet("artcore[3-999]"))
        self.assert_(not nodeset < NodeSet("artcore[3-980]"))
        self.assert_(not nodeset < NodeSet("artcore[2-998]"))
        self.assert_(nodeset <= NodeSet("artcore[2-32000]"))
        self.assert_(nodeset <= NodeSet("artcore[2-32000],lounge[35-65/2]"))
        self.assert_(nodeset <= NodeSet("artcore[3-999]"))
        self.assert_(not nodeset <= NodeSet("artcore[3-980]"))
        self.assert_(not nodeset <= NodeSet("artcore[2-998]"))
        self.assertEqual(len(nodeset), 997)
        # check padding issue - since 1.6 padding is ignored in this case
        self.assert_(nodeset.issubset("artcore[0001-1000]"))
        self.assert_(not nodeset.issubset("artcore030"))
        # multiple patterns case
        nodeset = NodeSet("tronic[0036-1630],lounge[20-660/2]")
        self.assert_(nodeset < NodeSet("tronic[0036-1630],lounge[20-662/2]"))
        self.assert_(nodeset < NodeSet("tronic[0035-1630],lounge[20-660/2]"))
        self.assert_(not nodeset < NodeSet("tronic[0035-1630],lounge[22-660/2]"))
        self.assert_(nodeset < NodeSet("tronic[0036-1630],lounge[20-660/2],artcore[034-070]"))
        self.assert_(nodeset < NodeSet("tronic[0032-1880],lounge[2-700/2],artcore[039-040]"))
        self.assert_(nodeset.issubset("tronic[0032-1880],lounge[2-700/2],artcore[039-040]"))
        self.assert_(nodeset.issubset(NodeSet("tronic[0032-1880],lounge[2-700/2],artcore[039-040]")))

    def testSymmetricDifference(self):
        """test NodeSet symmetric_difference()"""
        nsstr = "red[34-55,76-249,300-403],blue,green"
        nodeset = NodeSet(nsstr)
        self.assertEqual(len(nodeset), 302)

        nsstr2 = "red[32-57,72-249,300-341],blue,yellow"
        nodeset2 = NodeSet(nsstr2)
        self.assertEqual(len(nodeset2), 248)

        inodeset = nodeset.symmetric_difference(nodeset2)
        # originals should not change
        self.assertEqual(len(nodeset), 302)
        self.assertEqual(len(nodeset2), 248)
        self.assertEqual(str(nodeset), "blue,green,red[34-55,76-249,300-403]")
        self.assertEqual(str(nodeset2), "blue,red[32-57,72-249,300-341],yellow")
        # result
        self.assertEqual(len(inodeset), 72)
        self.assertEqual(str(inodeset), \
            "green,red[32-33,56-57,72-75,342-403],yellow")

    def testSymmetricDifferenceUpdate(self):
        """test NodeSet symmetric_difference_update()"""
        nodeset = NodeSet("artcore[3-999]")
        self.assertEqual(len(nodeset), 997)
        nodeset.symmetric_difference_update("artcore[1-2000]")
        self.assertEqual(len(nodeset), 1003)
        self.assertEqual(str(nodeset), "artcore[1-2,1000-2000]")
        nodeset = NodeSet("artcore[3-999],lounge")
        self.assertEqual(len(nodeset), 998)
        nodeset.symmetric_difference_update("artcore[1-2000]")
        self.assertEqual(len(nodeset), 1004)
        self.assertEqual(str(nodeset), "artcore[1-2,1000-2000],lounge")
        nodeset = NodeSet("artcore[3-999],lounge")
        self.assertEqual(len(nodeset), 998)
        nodeset.symmetric_difference_update("artcore[1-2000],lounge")
        self.assertEqual(len(nodeset), 1003)
        self.assertEqual(str(nodeset), "artcore[1-2,1000-2000]")
        nodeset = NodeSet("artcore[3-999],lounge")
        self.assertEqual(len(nodeset), 998)
        nodeset2 = NodeSet("artcore[1-2000],lounge")
        nodeset.symmetric_difference_update(nodeset2)
        self.assertEqual(len(nodeset), 1003)
        self.assertEqual(str(nodeset), "artcore[1-2,1000-2000]")
        self.assertEqual(len(nodeset2), 2001) # check const argument
        nodeset.symmetric_difference_update("artcore[1-2000],lounge")
        self.assertEqual(len(nodeset), 998)
        self.assertEqual(str(nodeset), "artcore[3-999],lounge")

    def testOperatorSymmetricDifference(self):
        """test NodeSet symmetric_difference() and ^ operator"""
        nodeset = NodeSet("artcore[3-999]")
        self.assertEqual(len(nodeset), 997)
        result = nodeset.symmetric_difference("artcore[1-2000]")
        self.assertEqual(len(result), 1003)
        self.assertEqual(str(result), "artcore[1-2,1000-2000]")
        self.assertEqual(len(nodeset), 997)

        # test ^ operator
        nodeset = NodeSet("artcore[3-999]")
        self.assertEqual(len(nodeset), 997)
        nodeset2 = NodeSet("artcore[1-2000]")
        result = nodeset ^ nodeset2
        self.assertEqual(len(result), 1003)
        self.assertEqual(str(result), "artcore[1-2,1000-2000]")
        self.assertEqual(len(nodeset), 997)
        self.assertEqual(len(nodeset2), 2000)

        # check that n ^ n returns empty NodeSet
        nodeset = NodeSet("lounge[3-999]")
        self.assertEqual(len(nodeset), 997)
        result = nodeset ^ nodeset
        self.assertEqual(len(result), 0)

    def testBinarySanityCheck(self):
        """test NodeSet binary sanity check"""
        ns1 = NodeSet("1-5")
        ns2 = "4-6"
        self.assertRaises(TypeError, ns1.__gt__, ns2)
        self.assertRaises(TypeError, ns1.__lt__, ns2)

    def testBinarySanityCheckNotImplementedSubtle(self):
        """test NodeSet binary sanity check (NotImplemented subtle)"""
        ns1 = NodeSet("1-5")
        ns2 = "4-6"
        self.assertEqual(ns1.__and__(ns2), NotImplemented)
        self.assertEqual(ns1.__or__(ns2), NotImplemented)
        self.assertEqual(ns1.__sub__(ns2), NotImplemented)
        self.assertEqual(ns1.__xor__(ns2), NotImplemented)
        # Should implicitely raises TypeError if the real operator
        # version is invoked. To test that, we perform a manual check
        # as an additional function would be needed to check with
        # assertRaises():
        good_error = False
        try:
            ns3 = ns1 & ns2
        except TypeError:
            good_error = True
        self.assert_(good_error, "TypeError not raised for &")
        good_error = False
        try:
            ns3 = ns1 | ns2
        except TypeError:
            good_error = True
        self.assert_(good_error, "TypeError not raised for |")
        good_error = False
        try:
            ns3 = ns1 - ns2
        except TypeError:
            good_error = True
        self.assert_(good_error, "TypeError not raised for -")
        good_error = False
        try:
            ns3 = ns1 ^ ns2
        except TypeError:
            good_error = True
        self.assert_(good_error, "TypeError not raised for ^")

    def testIsSubSetError(self):
        """test NodeSet issubset type error"""
        ns1 = NodeSet("1-5")
        ns2 = 4
        self.assertRaises(TypeError, ns1.issubset, ns2)

    def testExpandFunction(self):
        """test NodeSet expand() utility function"""
        self.assertEqual(expand("purple[1-3]"), [ "purple1", "purple2", "purple3" ])

    def testFoldFunction(self):
        """test NodeSet fold() utility function"""
        self.assertEqual(fold("purple1,purple2,purple3"), "purple[1-3]")

    def testEquality(self):
        """test NodeSet equality"""
        ns0_1 = NodeSet()
        ns0_2 = NodeSet()
        self.assertEqual(ns0_1, ns0_2)
        ns1 = NodeSet("roma[50-99]-ipmi,cors[113,115-117,130,166-172],cws-tigrou,tigrou3")
        ns2 = NodeSet("roma[50-99]-ipmi,cors[113,115-117,130,166-172],cws-tigrou,tigrou3")
        self.assertEqual(ns1, ns2)
        ns3 = NodeSet("cws-tigrou,tigrou3,cors[113,115-117,166-172],roma[50-99]-ipmi,cors130")
        self.assertEqual(ns1, ns3)
        ns4 = NodeSet("roma[50-99]-ipmi,cors[113,115-117,130,166-171],cws-tigrou,tigrou[3-4]")
        self.assertNotEqual(ns1, ns4)

    def testIterOrder(self):
        """test NodeSet nodes name order in iter and str"""
        ns_b = NodeSet("bcluster25")
        ns_c = NodeSet("ccluster12")
        ns_a1 = NodeSet("acluster4")
        ns_a2 = NodeSet("acluster39")
        ns_a3 = NodeSet("acluster41")
        ns = ns_c | ns_a1 | ns_b | ns_a2 | ns_a3
        self.assertEqual(str(ns), "acluster[4,39,41],bcluster25,ccluster12")
        nodelist = list(iter(ns))
        self.assertEqual(nodelist, ['acluster4', 'acluster39', 'acluster41', \
            'bcluster25', 'ccluster12'])

    def test_nsiter(self):
        """test NodeSet.nsiter() iterator"""
        ns1 = NodeSet("roma[50-61]-ipmi,cors[113,115-117,130,166-169],cws-tigrou,tigrou3")
        self.assertEqual(list(ns1), ['cors113', 'cors115', 'cors116', 'cors117', 'cors130', 'cors166', 'cors167', 'cors168', 'cors169', 'cws-tigrou', 'roma50-ipmi', 'roma51-ipmi', 'roma52-ipmi', 'roma53-ipmi', 'roma54-ipmi', 'roma55-ipmi', 'roma56-ipmi', 'roma57-ipmi', 'roma58-ipmi', 'roma59-ipmi', 'roma60-ipmi', 'roma61-ipmi', 'tigrou3'])
        self.assertEqual(list(ns1), [str(ns) for ns in ns1.nsiter()])

    def test_contiguous(self):
        """test NodeSet.contiguous() iterator"""
        ns1 = NodeSet("cors,roma[50-61]-ipmi,cors[113,115-117,130,166-169],cws-tigrou,tigrou3")
        self.assertEqual(['cors', 'cors113', 'cors[115-117]', 'cors130', 'cors[166-169]', 'cws-tigrou', 'roma[50-61]-ipmi', 'tigrou3'], [str(ns) for ns in ns1.contiguous()])

    def testEqualityMore(self):
        """test NodeSet equality (more)"""
        self.assertEqual(NodeSet(), NodeSet())
        ns1 = NodeSet("nodealone")
        ns2 = NodeSet("nodealone")
        self.assertEqual(ns1, ns2)
        ns1 = NodeSet("clu3,clu[4-9],clu11")
        ns2 = NodeSet("clu[3-9,11]")
        self.assertEqual(ns1, ns2)
        if ns1 == None:
            self.fail("ns1 == None succeeded")
        if ns1 != None:
            pass
        else:
            self.fail("ns1 != None failed")

    def testNodeSetNone(self):
        """test NodeSet methods behavior with None argument"""
        nodeset = NodeSet(None)
        self.assertEqual(len(nodeset), 0)
        self.assertEqual(list(nodeset), [])
        nodeset.update(None)
        self.assertEqual(list(nodeset), [])
        nodeset.intersection_update(None)
        self.assertEqual(list(nodeset), [])
        nodeset.difference_update(None)
        self.assertEqual(list(nodeset), [])
        nodeset.symmetric_difference_update(None)
        self.assertEqual(list(nodeset), [])
        n = nodeset.union(None)
        self.assertEqual(list(n), [])
        self.assertEqual(len(n), 0)
        n = nodeset.intersection(None)
        self.assertEqual(list(n), [])
        n = nodeset.difference(None)
        self.assertEqual(list(n), [])
        n = nodeset.symmetric_difference(None)
        self.assertEqual(list(n), [])
        nodeset = NodeSet("abc[3,6-89],def[3-98,104,128-133]")
        self.assertEqual(len(nodeset), 188)
        nodeset.update(None)
        self.assertEqual(len(nodeset), 188)
        nodeset.intersection_update(None)
        self.assertEqual(len(nodeset), 0)
        self.assertEqual(list(nodeset), [])
        nodeset = NodeSet("abc[3,6-89],def[3-98,104,128-133]")
        self.assertEqual(len(nodeset), 188)
        nodeset.difference_update(None)
        self.assertEqual(len(nodeset), 188)
        nodeset.symmetric_difference_update(None)
        self.assertEqual(len(nodeset), 188)
        n = nodeset.union(None)
        self.assertEqual(len(nodeset), 188)
        n = nodeset.intersection(None)
        self.assertEqual(list(n), [])
        self.assertEqual(len(n), 0)
        n = nodeset.difference(None)
        self.assertEqual(len(n), 188)
        n = nodeset.symmetric_difference(None)
        self.assertEqual(len(n), 188)
        self.assertFalse(n.issubset(None))
        self.assertTrue(n.issuperset(None))
        n = NodeSet(None)
        n.clear()
        self.assertEqual(len(n), 0)

    def testCopy(self):
        """test NodeSet.copy()"""
        nodeset = NodeSet("zclu[115-117,130,166-170],glycine[68,4780-4999]")
        self.assertEqual(str(nodeset), \
            "glycine[68,4780-4999],zclu[115-117,130,166-170]")
        nodeset2 = nodeset.copy()
        nodeset3 = nodeset.copy()
        self.assertEqual(nodeset, nodeset2) # content equality
        self.assertTrue(isinstance(nodeset, NodeSet))
        self.assertTrue(isinstance(nodeset2, NodeSet))
        self.assertTrue(isinstance(nodeset3, NodeSet))
        nodeset2.remove("glycine68")
        self.assertEqual(len(nodeset), len(nodeset2) + 1)
        self.assertNotEqual(nodeset, nodeset2)
        self.assertEqual(str(nodeset2), \
            "glycine[4780-4999],zclu[115-117,130,166-170]")
        self.assertEqual(str(nodeset), \
            "glycine[68,4780-4999],zclu[115-117,130,166-170]")
        nodeset2.add("glycine68")
        self.assertEqual(str(nodeset2), \
            "glycine[68,4780-4999],zclu[115-117,130,166-170]")
        self.assertEqual(nodeset, nodeset3)
        nodeset3.update(NodeSet("zclu118"))
        self.assertNotEqual(nodeset, nodeset3)
        self.assertEqual(len(nodeset) + 1, len(nodeset3))
        self.assertEqual(str(nodeset), \
            "glycine[68,4780-4999],zclu[115-117,130,166-170]")
        self.assertEqual(str(nodeset3), \
            "glycine[68,4780-4999],zclu[115-118,130,166-170]")

    def test_unpickle_v1_3_py24(self):
        """test NodeSet unpickling (against v1.3/py24)"""
        nodeset = pickle.loads(binascii.a2b_base64("gAJjQ2x1c3RlclNoZWxsLk5vZGVTZXQKTm9kZVNldApxACmBcQF9cQIoVQdfbGVuZ3RocQNLAFUJX3BhdHRlcm5zcQR9cQUoVQh5ZWxsb3clc3EGKGNDbHVzdGVyU2hlbGwuTm9kZVNldApSYW5nZVNldApxB29xCH1xCShoA0sBVQlfYXV0b3N0ZXBxCkdUskmtJZTDfVUHX3Jhbmdlc3ELXXEMKEsESwRLAUsAdHENYXViVQZibHVlJXNxDihoB29xD31xEChoA0sIaApHVLJJrSWUw31oC11xESgoSwZLCksBSwB0cRIoSw1LDUsBSwB0cRMoSw9LD0sBSwB0cRQoSxFLEUsBSwB0cRVldWJVB2dyZWVuJXNxFihoB29xF31xGChoA0tlaApHVLJJrSWUw31oC11xGShLAEtkSwFLAHRxGmF1YlUDcmVkcRtOdWgKTnViLg=="))
        self.assertEqual(nodeset, NodeSet("blue[6-10,13,15,17],green[0-100],red,yellow4"))
        self.assertEqual(str(nodeset), "blue[6-10,13,15,17],green[0-100],red,yellow4")
        self.assertEqual(len(nodeset), 111)
        self.assertEqual(nodeset[0], "blue6")
        self.assertEqual(nodeset[1], "blue7")
        self.assertEqual(nodeset[-1], "yellow4")

    # unpickle_v1_4_py24 : unpickling fails as v1.4 does not have slice pickling workaround
    def test_unpickle_v1_3_py26(self):
        """test NodeSet unpickling (against v1.3/py26)"""
        nodeset = pickle.loads(binascii.a2b_base64("gAJjQ2x1c3RlclNoZWxsLk5vZGVTZXQKTm9kZVNldApxACmBcQF9cQIoVQdfbGVuZ3RocQNLAFUJX3BhdHRlcm5zcQR9cQUoVQh5ZWxsb3clc3EGKGNDbHVzdGVyU2hlbGwuTm9kZVNldApSYW5nZVNldApxB29xCH1xCShoA0sBVQlfYXV0b3N0ZXBxCkdUskmtJZTDfVUHX3Jhbmdlc3ELXXEMKEsESwRLAUsAdHENYXViVQZibHVlJXNxDihoB29xD31xEChoA0sIaApHVLJJrSWUw31oC11xESgoSwZLCksBSwB0cRIoSw1LDUsBSwB0cRMoSw9LD0sBSwB0cRQoSxFLEUsBSwB0cRVldWJVB2dyZWVuJXNxFihoB29xF31xGChoA0tlaApHVLJJrSWUw31oC11xGShLAEtkSwFLAHRxGmF1YlUDcmVkcRtOdWgKTnViLg=="))
        self.assertEqual(nodeset, NodeSet("blue[6-10,13,15,17],green[0-100],red,yellow4"))
        self.assertEqual(str(nodeset), "blue[6-10,13,15,17],green[0-100],red,yellow4")
        self.assertEqual(len(nodeset), 111)
        self.assertEqual(nodeset[0], "blue6")
        self.assertEqual(nodeset[1], "blue7")
        self.assertEqual(nodeset[-1], "yellow4")

    # unpickle_v1_4_py24 : unpickling fails as v1.4 does not have slice pickling workaround

    def test_unpickle_v1_4_py26(self):
        """test NodeSet unpickling (against v1.4/py26)"""
        nodeset = pickle.loads(binascii.a2b_base64("gAJjQ2x1c3RlclNoZWxsLk5vZGVTZXQKTm9kZVNldApxACmBcQF9cQIoVQdfbGVuZ3RocQNLAFUJX3BhdHRlcm5zcQR9cQUoVQh5ZWxsb3clc3EGKGNDbHVzdGVyU2hlbGwuTm9kZVNldApSYW5nZVNldApxB29xCH1xCihoA0sBVQlfYXV0b3N0ZXBxC0dUskmtJZTDfVUHX3Jhbmdlc3EMXXENY19fYnVpbHRpbl9fCnNsaWNlCnEOSwRLBUsBh3EPUnEQSwCGcRFhVQhfdmVyc2lvbnESSwJ1YlUGYmx1ZSVzcRMoaAdvcRR9cRUoaANLCGgLR1SySa0llMN9aAxdcRYoaA5LBksLSwGHcRdScRhLAIZxGWgOSw1LDksBh3EaUnEbSwCGcRxoDksPSxBLAYdxHVJxHksAhnEfaA5LEUsSSwGHcSBScSFLAIZxImVoEksCdWJVB2dyZWVuJXNxIyhoB29xJH1xJShoA0tlaAtHVLJJrSWUw31oDF1xJmgOSwBLZUsBh3EnUnEoSwCGcSlhaBJLAnViVQNyZWRxKk51aAtOdWIu"))
        self.assertEqual(nodeset, NodeSet("blue[6-10,13,15,17],green[0-100],red,yellow4"))
        self.assertEqual(str(nodeset), "blue[6-10,13,15,17],green[0-100],red,yellow4")
        self.assertEqual(len(nodeset), 111)
        self.assertEqual(nodeset[0], "blue6")
        self.assertEqual(nodeset[1], "blue7")
        self.assertEqual(nodeset[-1], "yellow4")

    def test_unpickle_v1_5_py24(self):
        """test NodeSet unpickling (against v1.5/py24)"""
        nodeset = pickle.loads(binascii.a2b_base64("gAJjQ2x1c3RlclNoZWxsLk5vZGVTZXQKTm9kZVNldApxACmBcQF9cQIoVQdfbGVuZ3RocQNLAFUJX3BhdHRlcm5zcQR9cQUoVQh5ZWxsb3clc3EGKGNDbHVzdGVyU2hlbGwuTm9kZVNldApSYW5nZVNldApxB29xCH1xCihoA0sBVQlfYXV0b3N0ZXBxC0dUskmtJZTDfVUHX3Jhbmdlc3EMXXENSwRLBUsBh3EOSwCGcQ9hVQhfdmVyc2lvbnEQSwJ1YlUGYmx1ZSVzcREoaAdvcRJ9cRMoaANLCGgLR1SySa0llMN9aAxdcRQoSwZLC0sBh3EVSwCGcRZLDUsOSwGHcRdLAIZxGEsPSxBLAYdxGUsAhnEaSxFLEksBh3EbSwCGcRxlaBBLAnViVQdncmVlbiVzcR0oaAdvcR59cR8oaANLZWgLR1SySa0llMN9aAxdcSBLAEtlSwGHcSFLAIZxImFoEEsCdWJVA3JlZHEjTnVoC051Yi4="))
        self.assertEqual(nodeset, NodeSet("blue[6-10,13,15,17],green[0-100],red,yellow4"))
        self.assertEqual(str(nodeset), "blue[6-10,13,15,17],green[0-100],red,yellow4")
        self.assertEqual(len(nodeset), 111)
        self.assertEqual(nodeset[0], "blue6")
        self.assertEqual(nodeset[1], "blue7")
        self.assertEqual(nodeset[-1], "yellow4")

    def test_unpickle_v1_5_py26(self):
        """test NodeSet unpickling (against v1.5/py26)"""
        nodeset = pickle.loads(binascii.a2b_base64("gAJjQ2x1c3RlclNoZWxsLk5vZGVTZXQKTm9kZVNldApxACmBcQF9cQIoVQdfbGVuZ3RocQNLAFUJX3BhdHRlcm5zcQR9cQUoVQh5ZWxsb3clc3EGKGNDbHVzdGVyU2hlbGwuTm9kZVNldApSYW5nZVNldApxB29xCH1xCihoA0sBVQlfYXV0b3N0ZXBxC0dUskmtJZTDfVUHX3Jhbmdlc3EMXXENY19fYnVpbHRpbl9fCnNsaWNlCnEOSwRLBUsBh3EPUnEQSwCGcRFhVQhfdmVyc2lvbnESSwJ1YlUGYmx1ZSVzcRMoaAdvcRR9cRUoaANLCGgLR1SySa0llMN9aAxdcRYoaA5LBksLSwGHcRdScRhLAIZxGWgOSw1LDksBh3EaUnEbSwCGcRxoDksPSxBLAYdxHVJxHksAhnEfaA5LEUsSSwGHcSBScSFLAIZxImVoEksCdWJVB2dyZWVuJXNxIyhoB29xJH1xJShoA0tlaAtHVLJJrSWUw31oDF1xJmgOSwBLZUsBh3EnUnEoSwCGcSlhaBJLAnViVQNyZWRxKk51aAtOdWIu"))
        self.assertEqual(nodeset, NodeSet("blue[6-10,13,15,17],green[0-100],red,yellow4"))
        self.assertEqual(str(nodeset), "blue[6-10,13,15,17],green[0-100],red,yellow4")
        self.assertEqual(len(nodeset), 111)
        self.assertEqual(nodeset[0], "blue6")
        self.assertEqual(nodeset[1], "blue7")
        self.assertEqual(nodeset[-1], "yellow4")

    def test_unpickle_v1_6_py24(self):
        """test NodeSet unpickling (against v1.6/py24)"""
        nodeset = pickle.loads(binascii.a2b_base64("gAJjQ2x1c3RlclNoZWxsLk5vZGVTZXQKTm9kZVNldApxACmBcQF9cQIoVQdfbGVuZ3RocQNLAFUJX3BhdHRlcm5zcQR9cQUoVQh5ZWxsb3clc3EGY0NsdXN0ZXJTaGVsbC5SYW5nZVNldApSYW5nZVNldApxB1UBNHEIhXEJUnEKfXELKFUHcGFkZGluZ3EMTlUJX2F1dG9zdGVwcQ1HVLJJrSWUw31VCF92ZXJzaW9ucQ5LA3ViVQZibHVlJXNxD2gHVQ02LTEwLDEzLDE1LDE3cRCFcRFScRJ9cRMoaAxOaA1HVLJJrSWUw31oDksDdWJVB2dyZWVuJXNxFGgHVQUwLTEwMHEVhXEWUnEXfXEYKGgMTmgNR1SySa0llMN9aA5LA3ViVQNyZWRxGU51aA1OdWIu"))
        self.assertEqual(nodeset, NodeSet("blue[6-10,13,15,17],green[0-100],red,yellow4"))
        self.assertEqual(str(nodeset), "blue[6-10,13,15,17],green[0-100],red,yellow4")
        self.assertEqual(len(nodeset), 111)
        self.assertEqual(nodeset[0], "blue6")
        self.assertEqual(nodeset[1], "blue7")
        self.assertEqual(nodeset[-1], "yellow4")

    def test_unpickle_v1_6_py26(self):
        """test NodeSet unpickling (against v1.6/py26)"""
        nodeset = pickle.loads(binascii.a2b_base64("gAJjQ2x1c3RlclNoZWxsLk5vZGVTZXQKTm9kZVNldApxACmBcQF9cQIoVQdfbGVuZ3RocQNLAFUJX3BhdHRlcm5zcQR9cQUoVQh5ZWxsb3clc3EGY0NsdXN0ZXJTaGVsbC5SYW5nZVNldApSYW5nZVNldApxB1UBNHEIhXEJUnEKfXELKFUHcGFkZGluZ3EMTlUJX2F1dG9zdGVwcQ1HVLJJrSWUw31VCF92ZXJzaW9ucQ5LA3ViVQZibHVlJXNxD2gHVQ02LTEwLDEzLDE1LDE3cRCFcRFScRJ9cRMoaAxOaA1HVLJJrSWUw31oDksDdWJVB2dyZWVuJXNxFGgHVQUwLTEwMHEVhXEWUnEXfXEYKGgMTmgNR1SySa0llMN9aA5LA3ViVQNyZWRxGU51aA1OdWIu"))
        self.assertEqual(nodeset, NodeSet("blue[6-10,13,15,17],green[0-100],red,yellow4"))
        self.assertEqual(str(nodeset), "blue[6-10,13,15,17],green[0-100],red,yellow4")
        self.assertEqual(len(nodeset), 111)
        self.assertEqual(nodeset[0], "blue6")
        self.assertEqual(nodeset[1], "blue7")
        self.assertEqual(nodeset[-1], "yellow4")

    def test_pickle_current(self):
        """test NodeSet pickling (current version)"""
        dump = pickle.dumps(NodeSet("foo[1-100]"))
        self.assertNotEqual(dump, None)
        nodeset = pickle.loads(dump)
        self.assertEqual(nodeset, NodeSet("foo[1-100]"))
        self.assertEqual(str(nodeset), "foo[1-100]")
        self.assertEqual(nodeset[0], "foo1")
        self.assertEqual(nodeset[1], "foo2")
        self.assertEqual(nodeset[-1], "foo100")

    def testNodeSetBase(self):
        """test underlying NodeSetBase class"""
        rset = RangeSet("1-100,200")
        self.assertEqual(len(rset), 101)
        nsb = NodeSetBase("foo%sbar", rset) 
        self.assertEqual(len(nsb), len(rset))
        self.assertEqual(str(nsb), "foo[1-100,200]bar")
        nsbcpy = nsb.copy()
        self.assertEqual(len(nsbcpy), 101)
        self.assertEqual(str(nsbcpy), "foo[1-100,200]bar")
        other = NodeSetBase("foo%sbar", RangeSet("201"))
        nsbcpy.add(other)
        self.assertEqual(len(nsb), 101)
        self.assertEqual(str(nsb), "foo[1-100,200]bar")
        self.assertEqual(len(nsbcpy), 102)
        self.assertEqual(str(nsbcpy), "foo[1-100,200-201]bar")

    def testNodeGroupBase(self):
        """test underlying NodeGroupBase class"""
        ngb = NodeGroupBase("@group")
        self.assertEqual(len(ngb), 1)
        self.assertEqual(str(ngb), "@group")
        self.assertRaises(ValueError, NodeGroupBase, "badgroup")


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(NodeSetTest)
    unittest.TextTestRunner(verbosity=2).run(suite)
