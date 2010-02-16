#!/usr/bin/env python
# ClusterShell.NodeSet.RangeSet test suite
# Written by S. Thiell
# $Id$


"""Unit test for RangeSet"""

import copy
import sys
import unittest

sys.path.insert(0, '../lib')

from ClusterShell.NodeSet import RangeSet


class RangeSetTest(unittest.TestCase):

    def _testRS(self, test, res, length):
        r1 = RangeSet(test, autostep=3)
        self.assertEqual(str(r1), res)
        self.assertEqual(len(r1), length)

    def testSimple(self):
        """test simple ranges"""
        self._testRS("0", "0", 1)
        self._testRS("1", "1", 1)
        self._testRS("0-2", "0-2", 3)
        self._testRS("1-3", "1-3", 3)
        self._testRS("1-3,4-6", "1-6", 6)
        self._testRS("1-3,4-6,7-10", "1-10", 10)

    def testStepSimple(self):
        """test simple step usages"""
        self._testRS("0-4/2", "0-4/2", 3)
        self._testRS("1-4/2", "1,3", 2)
        self._testRS("1-4/3", "1,4", 2)
        self._testRS("1-4/4", "1", 1)

    def testStepAdvanced(self):
        """test advanced step usages"""
        self._testRS("1-4/4,2-6/2", "1-2,4,6", 4)
        self._testRS("6-24/6,9-21/6", "6-24/3", 7)
        self._testRS("0-24/2,9-21/2", "0-8/2,9-22,24", 20)
        self._testRS("3-21/9,6-24/9,9-27/9", "3-27/3", 9)
        self._testRS("101-121/4,1-225/112", "1,101-121/4,225", 8)
        self._testRS("1-32/3,13-28/9", "1-31/3", 11)
        self._testRS("1-32/3,13-22/9", "1-31/3", 11)
        self._testRS("1-32/3,13-31/9", "1-31/3", 11)
        self._testRS("1-32/3,13-40/9", "1-31/3,40", 12)
        self._testRS("1-16/3,13-28/6", "1-19/3,25", 8)
        self._testRS("1-16/3,1-16/6", "1-16/3", 6)
        self._testRS("1-16/6,1-16/3", "1-16/3", 6)
        self._testRS("1-16/3,3-19/6", "1,3-4,7,9-10,13,15-16", 9)
        self._testRS("1-16/3,3-19/4", "1,3-4,7,10-11,13,15-16,19", 10)
        self._testRS("1-17/2,2-18/2", "1-18", 18)
        self._testRS("1-17/2,33-41/2,2-18/2", "1-18,33-41/2", 23)
        self._testRS("1-17/2,33-41/2,2-20/2", "1-18,20,33-41/2", 24)
        self._testRS("1-17/2,33-41/2,2-19/2", "1-18,33-41/2", 23)

    def testIntersectSimple(self):
        """test simple intersections of ranges"""
        r1 = RangeSet("4-34")
        r2 = RangeSet("27-42")
        r1.intersection_update(r2)
        self.assertEqual(str(r1), "27-34")
        self.assertEqual(len(r1), 8)

        r1 = RangeSet("2-450,654-700,800")
        r2 = RangeSet("500-502,690-820,830-840,900")
        r1.intersection_update(r2)
        self.assertEqual(str(r1), "690-700,800")
        self.assertEqual(len(r1), 12)

        r1 = RangeSet("2-450,654-700,800")
        r3 = r1.intersection(r2)
        self.assertEqual(str(r3), "690-700,800")
        self.assertEqual(len(r3), 12)

        r1 = RangeSet("2-450,654-700,800")
        r3 = r1 & r2
        self.assertEqual(str(r3), "690-700,800")
        self.assertEqual(len(r3), 12)


    def testIntersectStep(self):
        """test more intersections of ranges"""
        r1 = RangeSet("4-34/2")
        r2 = RangeSet("28-42/2")
        r1.intersection_update(r2)
        self.assertEqual(str(r1), "28,30,32,34")
        self.assertEqual(len(r1), 4)

        r1 = RangeSet("4-34/2")
        r2 = RangeSet("27-42/2")
        r1.intersection_update(r2)
        self.assertEqual(str(r1), "")
        self.assertEqual(len(r1), 0)

        r1 = RangeSet("2-60/3", autostep=3)
        r2 = RangeSet("3-50/2", autostep=3)
        r1.intersection_update(r2)
        self.assertEqual(str(r1), "5-47/6")
        self.assertEqual(len(r1), 8)

    def testSubSimple(self):
        """test simple difference of ranges"""
        r1 = RangeSet("4,7-33")
        r2 = RangeSet("8-33")
        r1.difference_update(r2)
        self.assertEqual(str(r1), "4,7")
        self.assertEqual(len(r1), 2)

        r1 = RangeSet("4,7-33")
        r3 = r1.difference(r2)
        self.assertEqual(str(r3), "4,7")
        self.assertEqual(len(r3), 2)

        r3 = r1 - r2
        self.assertEqual(str(r3), "4,7")
        self.assertEqual(len(r3), 2)

    def testSymmetricDifference(self):
        """test symmetric difference of ranges"""
        r1 = RangeSet("4,7-33")
        r2 = RangeSet("8-34")
        r1.symmetric_difference_update(r2)
        self.assertEqual(str(r1), "4,7,34")
        self.assertEqual(len(r1), 3)

        r1 = RangeSet("4,7-33")
        r3 = r1.symmetric_difference(r2)
        self.assertEqual(str(r3), "4,7,34")
        self.assertEqual(len(r3), 3)

        r3 = r1 ^ r2
        self.assertEqual(str(r3), "4,7,34")
        self.assertEqual(len(r3), 3)


    def testSubStep(self):
        """test more sub of ranges (with step)"""
        # case 1 no sub
        r1 = RangeSet("4-34/2", autostep=3)
        r2 = RangeSet("3-33/2", autostep=3)
        r1.difference_update(r2)
        self.assertEqual(str(r1), "4-34/2")
        self.assertEqual(len(r1), 16)

        # case 2 diff left
        r1 = RangeSet("4-34/2", autostep=3)
        r2 = RangeSet("2-14/2", autostep=3)
        r1.difference_update(r2)
        self.assertEqual(str(r1), "16-34/2")
        self.assertEqual(len(r1), 10)
        
        # case 3 diff right
        r1 = RangeSet("4-34/2", autostep=3)
        r2 = RangeSet("28-52/2", autostep=3)
        r1.difference_update(r2)
        self.assertEqual(str(r1), "4-26/2")
        self.assertEqual(len(r1), 12)
        
        # case 4 diff with ranges split
        r1 = RangeSet("4-34/2", autostep=3)
        r2 = RangeSet("12-18/2", autostep=3)
        r1.difference_update(r2)
        self.assertEqual(str(r1), "4-10/2,20-34/2")
        self.assertEqual(len(r1), 12)

        # case 5+ more tricky diffs
        r1 = RangeSet("4-34/2", autostep=3)
        r2 = RangeSet("28-55", autostep=3)
        r1.difference_update(r2)
        self.assertEqual(str(r1), "4-26/2")
        self.assertEqual(len(r1), 12)

        r1 = RangeSet("4-34/2", autostep=3)
        r2 = RangeSet("27-55", autostep=3)
        r1.difference_update(r2)
        self.assertEqual(str(r1), "4-26/2")
        self.assertEqual(len(r1), 12)

        r1 = RangeSet("1-100", autostep=3)
        r2 = RangeSet("2-98/2", autostep=3)
        r1.difference_update(r2)
        self.assertEqual(str(r1), "1-99/2,100")
        self.assertEqual(len(r1), 51)

        r1 = RangeSet("1-100,102,105-242,800", autostep=3)
        r2 = RangeSet("1-1000/3", autostep=3)
        r1.difference_update(r2)
        self.assertEqual(str(r1), "2-3,5-6,8-9,11-12,14-15,17-18,20-21,23-24,26-27,29-30,32-33,35-36,38-39,41-42,44-45,47-48,50-51,53-54,56-57,59-60,62-63,65-66,68-69,71-72,74-75,77-78,80-81,83-84,86-87,89-90,92-93,95-96,98-99,102,105,107-108,110-111,113-114,116-117,119-120,122-123,125-126,128-129,131-132,134-135,137-138,140-141,143-144,146-147,149-150,152-153,155-156,158-159,161-162,164-165,167-168,170-171,173-174,176-177,179-180,182-183,185-186,188-189,191-192,194-195,197-198,200-201,203-204,206-207,209-210,212-213,215-216,218-219,221-222,224-225,227-228,230-231,233-234,236-237,239-240,242,800")
        self.assertEqual(len(r1), 160)

        r1 = RangeSet("1-100000", autostep=3)
        r2 = RangeSet("2-99999/2", autostep=3)
        r1.difference_update(r2)
        self.assertEqual(str(r1), "1-99999/2,100000")
        self.assertEqual(len(r1), 50001)

        r1 = RangeSet("1-100/3,40-60/3", autostep=3)
        r2 = RangeSet("31-61/3", autostep=3)
        r1.difference_update(r2)
        self.assertEqual(str(r1), "1-28/3,64-100/3")
        self.assertEqual(len(r1), 23)

        r1 = RangeSet("1-100/3,40-60/3", autostep=3)
        r2 = RangeSet("30-80/5", autostep=3)
        r1.difference_update(r2)
        self.assertEqual(str(r1), "1-37/3,43-52/3,58-67/3,73-100/3")
        self.assertEqual(len(r1), 31)

    def testContains(self):
        """test RangeSet __contains__()"""
        r1 = RangeSet("1-100,102,105-242,800")
        self.assertEqual(len(r1), 240)
        self.assert_(99 in r1)
        self.assert_("99" in r1)
        self.assert_(not "099" in r1)
        self.assertRaises(TypeError, r1.__contains__, object())
        self.assert_(101 not in r1)
        self.assertEqual(len(r1), 240)
        r2 = RangeSet("1-100/3,40-60/3", autostep=3)
        self.assertEqual(len(r2), 34)
        self.assert_(1 in r2)
        self.assert_(4 in r2)
        self.assert_(2 not in r2)
        self.assert_(3 not in r2)
        self.assert_(40 in r2)
        self.assert_(101 not in r2)
        r3 = RangeSet("0003-0143,0360-1000")
        self.assert_(360 in r3)
        self.assert_(not "360" in r3)
        self.assert_("0360" in r3)
        r4 = RangeSet("00-02")
        self.assert_("00" in r4)
        self.assert_(0 in r4)
        self.assert_(not "0" in r4)
        self.assert_("01" in r4)
        self.assert_(1 in r4)
        self.assert_(not "1" in r4)
        self.assert_("02" in r4)
        self.assert_(not "03" in r4)

    def testIsSuperSet(self):
        """test RangeSet issuperset()"""
        r1 = RangeSet("1-100,102,105-242,800")
        self.assertEqual(len(r1), 240)
        r2 = RangeSet("3-98,140-199,800")
        self.assertEqual(len(r2), 157)
        self.assert_(r1.issuperset(r1))
        self.assert_(r1.issuperset(r2))
        self.assert_(r1 >= r1)
        self.assert_(r1 > r2)
        self.assert_(not r2 > r1)
        r2 = RangeSet("3-98,140-199,243,800")
        self.assertEqual(len(r2), 158)
        self.assert_(not r1.issuperset(r2))
        self.assert_(not r1 > r2)

    def testIsSubSet(self):
        """test RangeSet issubset()"""
        r1 = RangeSet("1-100,102,105-242,800-900/2")
        r2 = RangeSet("3,800,802,804,888")
        self.assert_(r2.issubset(r2))
        self.assert_(r2.issubset(r1))
        self.assert_(r2 <= r1)
        self.assert_(r2 < r1)
        self.assert_(not r1 < r2)
        self.assert_(not r1 <= r2)

    def testGetItem(self):
        """test RangeSet __getitem__()"""
        r1 = RangeSet("1-100,102,105-242,800")
        self.assertEqual(len(r1), 240)
        self.assertEqual(r1[0], 1)
        self.assertEqual(r1[1], 2)
        self.assertEqual(r1[2], 3)
        self.assertEqual(r1[99], 100)
        self.assertEqual(r1[100], 102)
        self.assertEqual(r1[101], 105)
        self.assertEqual(r1[102], 106)
        self.assertEqual(r1[103], 107)
        self.assertEqual(r1[237], 241)
        self.assertEqual(r1[238], 242)
        self.assertEqual(r1[239], 800)
        r2 = RangeSet("1-37/3,43-52/3,58-67/3,73-100/3,102-106/2")
        self.assertEqual(len(r2), 34)
        self.assertEqual(r2[0], 1)
        self.assertEqual(r2[1], 4)
        self.assertEqual(r2[2], 7)
        self.assertEqual(r2[12], 37)
        self.assertEqual(r2[13], 43)
        self.assertEqual(r2[14], 46)
        self.assertEqual(r2[16], 52)
        self.assertEqual(r2[17], 58)
        self.assertEqual(r2[29], 97)
        self.assertEqual(r2[30], 100)
        self.assertEqual(r2[31], 102)
        self.assertEqual(r2[32], 104)
        self.assertEqual(r2[33], 106)

    def testGetSlice(self):
        """test RangeSet __getslice__()"""
        r1 = RangeSet("1-2,4,9,10-12")
        self.assertEqual(r1[0:3], RangeSet("1-2,4"))
        self.assertEqual(r1[2:6], RangeSet("4,9,10-11"))
        self.assertEqual(r1[2:4], RangeSet("4,9"))

    def testSplit(self):
        """test RangeSet split()"""

        # Empty nodeset
        rangeset = RangeSet()
        self.assertEqual((RangeSet(), RangeSet()), tuple(rangeset.split(2)))

        # Not enough element
        rangeset = RangeSet("1")
        self.assertEqual((RangeSet("1"), RangeSet()), tuple(rangeset.split(2)))

        # Exact number of elements
        rangeset = RangeSet("1-6")
        self.assertEqual((RangeSet("1-2"), RangeSet("3-4"), RangeSet("5-6")), tuple(rangeset.split(3)))

    def testAdd(self):
        """test RangeSet add()"""
        r1 = RangeSet("1-100,102,105-242,800")
        self.assertEqual(len(r1), 240)
        r1.add(801)
        self.assertEqual(len(r1), 241)
        self.assertEqual(r1[240], 801)
        r1.add(788)
        self.assertEqual(len(r1), 242)
        self.assertEqual(r1[239], 788)
        self.assertEqual(r1[240], 800)

    def testUnion(self):
        """test RangeSet union()"""
        r1 = RangeSet("1-100,102,105-242,800")
        self.assertEqual(len(r1), 240)
        r2 = RangeSet("243-799,1924-1984")
        self.assertEqual(len(r2), 618)
        r3 = r1.union(r2)
        self.assertEqual(len(r3), 240+618) 
        self.assertEqual(str(r3), "1-100,102,105-800,1924-1984")
        r4 = r1 | r2
        self.assertEqual(len(r4), 240+618) 
        self.assertEqual(str(r4), "1-100,102,105-800,1924-1984")
        # test with overlap
        r2 = RangeSet("200-799")
        r3 = r1.union(r2)
        self.assertEqual(len(r3), 797)
        self.assertEqual(str(r3), "1-100,102,105-800")
        r4 = r1 | r2
        self.assertEqual(len(r4), 797)
        self.assertEqual(str(r4), "1-100,102,105-800")

    def testRemove(self):
        """test RangeSet remove()"""
        r1 = RangeSet("1-100,102,105-242,800")
        self.assertEqual(len(r1), 240)
        r1.remove(100)
        self.assertEqual(len(r1), 239)
        self.assertEqual(str(r1), "1-99,102,105-242,800")
        self.assertRaises(KeyError, r1.remove, 101)

    def testClear(self):
        """test RangeSet clear()"""
        r1 = RangeSet("1-100,102,105-242,800")
        self.assertEqual(len(r1), 240)
        self.assertEqual(str(r1), "1-100,102,105-242,800")
        r1.clear()
        self.assertEqual(len(r1), 0)
        self.assertEqual(str(r1), "")
    
    def testFromListConstructor(self):
        """test RangeSet.fromlist constructor"""
        rgs = RangeSet.fromlist([ "3", "5-8", "1" ])
        self.assertEqual(str(rgs), "1,3,5-8")
        self.assertEqual(len(rgs), 6)
        rgs = RangeSet.fromlist([ RangeSet("3"), RangeSet("5-8"), RangeSet("1") ])
        self.assertEqual(str(rgs), "1,3,5-8")
        self.assertEqual(len(rgs), 6)

    def testIterate(self):
        """test RangeSet iterator"""
        rgs = RangeSet.fromlist([ "11", "3", "5-8", "1", "4" ])
        matches = [ 1, 3, 4, 5, 6, 7, 8, 11 ]
        cnt = 0
        for rg in rgs:
            self.assertEqual(rg, str(matches[cnt]))
            cnt += 1
        self.assertEqual(cnt, len(matches))

    def testBinarySanityCheck(self):
        """test RangeSet binary sanity check"""
        rg1 = RangeSet("1-5")
        rg2 = "4-6"
        self.assertRaises(TypeError, rg1.__gt__, rg2)
        self.assertRaises(TypeError, rg1.__lt__, rg2)

    def testBinarySanityCheckNotImplementedSubtle(self):
        """test RangeSet binary sanity check (NotImplemented subtle)"""
        rg1 = RangeSet("1-5")
        rg2 = "4-6"
        self.assertEqual(rg1.__and__(rg2), NotImplemented)
        self.assertEqual(rg1.__or__(rg2), NotImplemented)
        self.assertEqual(rg1.__sub__(rg2), NotImplemented)
        self.assertEqual(rg1.__xor__(rg2), NotImplemented)
        # Should implicitely raises TypeError if the real operator
        # version is invoked. To test that, we perform a manual check
        # as an additional function would be needed to check with
        # assertRaises():
        good_error = False
        try:
            rg3 = rg1 & rg2
        except TypeError:
            good_error = True
        self.assert_(good_error, "TypeError not raised for &")
        good_error = False
        try:
            rg3 = rg1 | rg2
        except TypeError:
            good_error = True
        self.assert_(good_error, "TypeError not raised for |")
        good_error = False
        try:
            rg3 = rg1 - rg2
        except TypeError:
            good_error = True
        self.assert_(good_error, "TypeError not raised for -")
        good_error = False
        try:
            rg3 = rg1 ^ rg2
        except TypeError:
            good_error = True
        self.assert_(good_error, "TypeError not raised for ^")

    def testIsSubSetError(self):
        """test RangeSet issubset error"""
        rg1 = RangeSet("1-5")
        rg2 = "4-6"
        self.assertRaises(TypeError, rg1.issubset, rg2)

    def testEquality(self):
        """test RangeSet equal"""
        rg0_1 = RangeSet()
        rg0_2 = RangeSet()
        self.assertEqual(rg0_1, rg0_2)
        rg1 = RangeSet("1-4")
        rg2 = RangeSet("1-4")
        self.assertEqual(rg1, rg2)
        rg3 = RangeSet("2-5")
        self.assertNotEqual(rg1, rg3)
        rg4 = RangeSet("1,2,3,4")
        self.assertEqual(rg1, rg4)
        rg5 = RangeSet("1,2,4")
        self.assertNotEqual(rg1, rg5)
        if rg1 == None:
            self.fail("rg1 == None succeeded")
        if rg1 != None:
            pass
        else:
            self.fail("rg1 != None failed")


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(RangeSetTest)
    unittest.TextTestRunner(verbosity=2).run(suite)
