# ClusterShell.NodeSet.RangeSet test suite
# Written by S. Thiell

"""Unit test for RangeSet"""

import binascii
import pickle
import unittest
import warnings

from ClusterShell.RangeSet import RangeSet, RangeSetParseError

class RangeSetTest(unittest.TestCase):

    def setUp(self):
        warnings.simplefilter("always")

    def _testRS(self, test, res, length):
        r1 = RangeSet(test, autostep=3)
        self.assertEqual(str(r1), res)
        self.assertEqual(len(r1), length)

    def testSimple(self):
        """test RangeSet simple ranges"""
        self._testRS("0", "0", 1)
        self._testRS("1", "1", 1)
        self._testRS("0-2", "0-2", 3)
        self._testRS("1-3", "1-3", 3)
        self._testRS("1-3,4-6", "1-6", 6)
        self._testRS("1-3,4-6,7-10", "1-10", 10)

    def testStepSimple(self):
        """test RangeSet simple step usages"""
        self._testRS("0-4/2", "0-4/2", 3)
        self._testRS("1-4/2", "1,3", 2)
        self._testRS("1-4/3", "1,4", 2)
        self._testRS("1-4/4", "1", 1)

    def testStepAdvanced(self):
        """test RangeSet advanced step usages"""
        self._testRS("1-4/4,2-6/2", "1-2,4,6", 4)   # 1.9 small behavior change
        self._testRS("6-24/6,9-21/6", "6-24/3", 7)
        self._testRS("0-24/2,9-21/2", "0-8/2,9-22,24", 20)
        self._testRS("0-24/2,9-21/2,100", "0-8/2,9-22,24,100", 21)
        self._testRS("0-24/2,9-21/2,100-101", "0-8/2,9-22,24,100-101", 22)
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
        #self._testRS("1-16/3,3-19/4", "1,3-4,7,10-11,13,15-16,19", 10)  # <1.6
        #self._testRS("1-16/3,3-19/4", "1,3,4-10/3,11-15/2,16,19", 10)   # 1.6+
        self._testRS("1-16/3,3-19/4", "1,3-4,7,10-11,13,15-16,19", 10)   # 1.9+
        self._testRS("1-17/2,2-18/2", "1-18", 18)
        self._testRS("1-17/2,33-41/2,2-18/2", "1-18,33-41/2", 23)
        self._testRS("1-17/2,33-41/2,2-20/2", "1-18,20,33-41/2", 24)
        self._testRS("1-17/2,33-41/2,2-19/2", "1-18,33-41/2", 23)
        self._testRS("1968-1970,1972,1975,1978-1981,1984-1989", "1968-1970,1972-1978/3,1979-1981,1984-1989", 15)
        # use of 0-padding in the step number is ignored
        self._testRS("1-17/01", "1-17", 17)
        self._testRS("1-17/02", "1-17/2", 9)
        self._testRS("1-17/03", "1-16/3", 6)

    def test_bad_syntax(self):
        """test parse errors"""
        self.assertRaises(RangeSetParseError, RangeSet, "")
        self.assertRaises(RangeSetParseError, RangeSet, "-")
        self.assertRaises(RangeSetParseError, RangeSet, "A")
        self.assertRaises(RangeSetParseError, RangeSet, "2-5/a")
        self.assertRaises(RangeSetParseError, RangeSet, "3/2")
        self.assertRaises(RangeSetParseError, RangeSet, "3-/2")
        self.assertRaises(RangeSetParseError, RangeSet, "-3/2")
        self.assertRaises(RangeSetParseError, RangeSet, "-/2")
        self.assertRaises(RangeSetParseError, RangeSet, "4-a/2")
        self.assertRaises(RangeSetParseError, RangeSet, "4-3/2")
        self.assertRaises(RangeSetParseError, RangeSet, "4-5/-2")
        self.assertRaises(RangeSetParseError, RangeSet, "4-2/-2")
        self.assertRaises(RangeSetParseError, RangeSet, "004-002")
        self.assertRaises(RangeSetParseError, RangeSet, "3-59/2,102a")

    def testIntersectSimple(self):
        """test RangeSet with simple intersections of ranges"""
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

        r1 = RangeSet()
        r3 = r1.intersection(r2)
        self.assertEqual(str(r3), "")
        self.assertEqual(len(r3), 0)

    def testIntersectStep(self):
        """test RangeSet with more intersections of ranges"""
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
        """test RangeSet with simple difference of ranges"""
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

        # bounds checking
        r1 = RangeSet("1-10,39-41,50-60")
        r2 = RangeSet("1-10,38-39,50-60")
        r1.difference_update(r2)
        self.assertEqual(len(r1), 2)
        self.assertEqual(str(r1), "40-41")

        r1 = RangeSet("1-20,39-41")
        r2 = RangeSet("1-20,41-42")
        r1.difference_update(r2)
        self.assertEqual(len(r1), 2)
        self.assertEqual(str(r1), "39-40")

        # difference(self) issue
        r1 = RangeSet("1-20,39-41")
        r1.difference_update(r1)
        self.assertEqual(len(r1), 0)
        self.assertEqual(str(r1), "")

        # strict mode
        r1 = RangeSet("4,7-33")
        r2 = RangeSet("8-33")
        r1.difference_update(r2, strict=True)
        self.assertEqual(str(r1), "4,7")
        self.assertEqual(len(r1), 2)

        r3 = RangeSet("4-5")
        self.assertRaises(KeyError, r1.difference_update, r3, True)

    def testSymmetricDifference(self):
        """test RangeSet.symmetric_difference_update()"""
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

        r1 = RangeSet("5,7,10-12,33-50")
        r2 = RangeSet("8-34")
        r1.symmetric_difference_update(r2)
        self.assertEqual(str(r1), "5,7-9,13-32,35-50")
        self.assertEqual(len(r1), 40)

        r1 = RangeSet("8-34")
        r2 = RangeSet("5,7,10-12,33-50")
        r1.symmetric_difference_update(r2)
        self.assertEqual(str(r1), "5,7-9,13-32,35-50")
        self.assertEqual(len(r1), 40)

        r1 = RangeSet("8-30")
        r2 = RangeSet("31-40")
        r1.symmetric_difference_update(r2)
        self.assertEqual(str(r1), "8-40")
        self.assertEqual(len(r1), 33)

        r1 = RangeSet("8-30")
        r2 = RangeSet("8-30")
        r1.symmetric_difference_update(r2)
        self.assertEqual(str(r1), "")
        self.assertEqual(len(r1), 0)

        r1 = RangeSet("8-30")
        r2 = RangeSet("10-13,31-40")
        r1.symmetric_difference_update(r2)
        self.assertEqual(str(r1), "8-9,14-40")
        self.assertEqual(len(r1), 29)

        r1 = RangeSet("10-13,31-40")
        r2 = RangeSet("8-30")
        r1.symmetric_difference_update(r2)
        self.assertEqual(str(r1), "8-9,14-40")
        self.assertEqual(len(r1), 29)

        r1 = RangeSet("1,3,5,7")
        r2 = RangeSet("4-8")
        r1.symmetric_difference_update(r2)
        self.assertEqual(str(r1), "1,3-4,6,8")
        self.assertEqual(len(r1), 5)

        r1 = RangeSet("1-1000")
        r2 = RangeSet("0-40,60-100/4,300,1000,1002")
        r1.symmetric_difference_update(r2)
        self.assertEqual(str(r1), "0,41-59,61-63,65-67,69-71,73-75,77-79,81-83,85-87,89-91,93-95,97-99,101-299,301-999,1002")
        self.assertEqual(len(r1), 949)

        r1 = RangeSet("25,27,29-31,33-35,41-43,48,50-52,55-60,63,66-68,71-78")
        r2 = RangeSet("27-30,35,37-39,42,45-48,50,52-54,56,61,67,69-79,81-82")
        r1.symmetric_difference_update(r2)
        self.assertEqual(str(r1), "25,28,31,33-34,37-39,41,43,45-47,51,53-55,57-61,63,66,68-70,79,81-82")
        self.assertEqual(len(r1), 30)

        r1 = RangeSet("986-987,989,991-992,994-995,997,1002-1008,1010-1011,1015-1018,1021")
        r2 = RangeSet("989-990,992-994,997-1000")
        r1.symmetric_difference_update(r2)
        self.assertEqual(str(r1), "986-987,990-991,993,995,998-1000,1002-1008,1010-1011,1015-1018,1021")
        self.assertEqual(len(r1), 23)

    def testSubStep(self):
        """test RangeSet with more sub of ranges (with step)"""
        # case 1 no sub
        r1 = RangeSet("4-34/2", autostep=3)
        r2 = RangeSet("3-33/2", autostep=3)
        self.assertEqual(r1.autostep, 3)
        self.assertEqual(r2.autostep, 3)
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

        r1 = RangeSet("1-1000", autostep=3)
        r2 = RangeSet("2-999/2", autostep=3)
        r1.difference_update(r2)
        self.assertEqual(str(r1), "1-999/2,1000")
        self.assertEqual(len(r1), 501)

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
        """test RangeSet.__contains__()"""
        r1 = RangeSet("1-100,102,105-242,800")
        self.assertEqual(len(r1), 240)
        self.assertTrue(99 in r1)
        self.assertTrue("99" in r1)
        self.assertFalse("099" in r1)  # fixed in 1.9+
        self.assertFalse(object() in r1)
        self.assertTrue(101 not in r1)
        self.assertEqual(len(r1), 240)
        r2 = RangeSet("1-100/3,40-60/3", autostep=3)
        self.assertEqual(len(r2), 34)
        self.assertTrue(1 in r2)
        self.assertTrue(4 in r2)
        self.assertTrue(2 not in r2)
        self.assertTrue(3 not in r2)
        self.assertTrue(40 in r2)
        self.assertTrue(101 not in r2)
        r3 = RangeSet("0003-0143,0360-1000")
        self.assertFalse(360 in r3)    # fixed in 1.9+
        self.assertFalse("360" in r3)  # fixed in 1.9+
        self.assertTrue("0360" in r3)
        r4 = RangeSet("00-02")
        self.assertTrue("00" in r4)
        self.assertFalse(0 in r4)      # changed in 1.9+
        self.assertFalse("0" in r4)    # fixed in 1.9+
        self.assertTrue("01" in r4)
        self.assertFalse(1 in r4)      # changed in 1.9+
        self.assertFalse("1" in r4)    # fixed in 1.9+
        self.assertTrue("02" in r4)
        self.assertFalse("03" in r4)
        #
        r1 = RangeSet("115-117,130,132,166-170,4780-4999")
        self.assertEqual(len(r1), 230)
        r2 = RangeSet("116-117,130,4781-4999")
        self.assertEqual(len(r2), 222)
        self.assertTrue(r2 in r1)
        self.assertFalse(r1 in r2)
        r2 = RangeSet("5000")
        self.assertFalse(r2 in r1)
        r2 = RangeSet("4999")
        self.assertTrue(r2 in r1)

    def testIsSuperSet(self):
        """test RangeSet.issuperset()"""
        r1 = RangeSet("1-100,102,105-242,800")
        self.assertEqual(len(r1), 240)
        r2 = RangeSet("3-98,140-199,800")
        self.assertEqual(len(r2), 157)
        self.assertTrue(r1.issuperset(r1))
        self.assertTrue(r1.issuperset(r2))
        self.assertTrue(r1 >= r1)
        self.assertTrue(r1 > r2)
        self.assertFalse(r2 > r1)
        r2 = RangeSet("3-98,140-199,243,800")
        self.assertEqual(len(r2), 158)
        self.assertFalse(r1.issuperset(r2))
        self.assertFalse(r1 > r2)

    def testIsSubSet(self):
        """test RangeSet.issubset()"""
        r1 = RangeSet("1-100,102,105-242,800-900/2")
        self.assertTrue(r1.issubset(r1))
        self.assertTrue(r1.issuperset(r1))
        r2 = RangeSet()
        self.assertTrue(r2.issubset(r1))
        self.assertTrue(r1.issuperset(r2))
        self.assertFalse(r1.issubset(r2))
        self.assertFalse(r2.issuperset(r1))
        r1 = RangeSet("1-100,102,105-242,800-900/2")
        r2 = RangeSet("3,800,802,804,888")
        self.assertTrue(r2.issubset(r2))
        self.assertTrue(r2.issubset(r1))
        self.assertTrue(r2 <= r1)
        self.assertTrue(r2 < r1)
        self.assertTrue(r1 > r2)
        self.assertFalse(r1 < r2)
        self.assertFalse(r1 <= r2)
        self.assertFalse(r2 >= r1)
        # fixed in v1.9 where mixed padding is now supported
        r1 = RangeSet("1-100")
        r2 = RangeSet("001-100")
        self.assertFalse(r1.issubset(r2)) # used to be true < v1.9

    def testGetItem(self):
        """test RangeSet.__getitem__()"""
        r1 = RangeSet("1-100,102,105-242,800")
        self.assertEqual(len(r1), 240)
        self.assertEqual(r1[0], '1')
        self.assertEqual(r1[1], '2')
        self.assertEqual(r1[2], '3')
        self.assertEqual(r1[99], '100')
        self.assertEqual(r1[100], '102')
        self.assertEqual(r1[101], '105')
        self.assertEqual(r1[102], '106')
        self.assertEqual(r1[103], '107')
        self.assertEqual(r1[237], '241')
        self.assertEqual(r1[238], '242')
        self.assertEqual(r1[239], '800')
        self.assertRaises(IndexError, r1.__getitem__, 240)
        self.assertRaises(IndexError, r1.__getitem__, 241)
        # negative indices
        self.assertEqual(r1[-1], '800')
        self.assertEqual(r1[-240], '1')
        for n in range(1, len(r1)):
            self.assertEqual(r1[-n], r1[len(r1)-n])
        self.assertRaises(IndexError, r1.__getitem__, -len(r1)-1)
        self.assertRaises(IndexError, r1.__getitem__, -len(r1)-2)

        r2 = RangeSet("1-37/3,43-52/3,58-67/3,73-100/3,102-106/2")
        self.assertEqual(len(r2), 34)
        self.assertEqual(r2[0], '1')
        self.assertEqual(r2[1], '4')
        self.assertEqual(r2[2], '7')
        self.assertEqual(r2[12], '37')
        self.assertEqual(r2[13], '43')
        self.assertEqual(r2[14], '46')
        self.assertEqual(r2[16], '52')
        self.assertEqual(r2[17], '58')
        self.assertEqual(r2[29], '97')
        self.assertEqual(r2[30], '100')
        self.assertEqual(r2[31], '102')
        self.assertEqual(r2[32], '104')
        self.assertEqual(r2[33], '106')
        self.assertRaises(TypeError, r2.__getitem__, "foo")

    def testGetSlice(self):
        """test RangeSet.__getitem__() with slice"""
        r0 = RangeSet("1-12")
        self.assertEqual(r0[0:3], RangeSet("1-3"))
        self.assertEqual(r0[2:7], RangeSet("3-7"))
        # negative indices - sl_start
        self.assertEqual(r0[-1:0], RangeSet())
        self.assertEqual(r0[-2:0], RangeSet())
        self.assertEqual(r0[-11:0], RangeSet())
        self.assertEqual(r0[-12:0], RangeSet())
        self.assertEqual(r0[-13:0], RangeSet())
        self.assertEqual(r0[-1000:0], RangeSet())
        self.assertEqual(r0[-1:], RangeSet("12"))
        self.assertEqual(r0[-2:], RangeSet("11-12"))
        self.assertEqual(r0[-11:], RangeSet("2-12"))
        self.assertEqual(r0[-12:], RangeSet("1-12"))
        self.assertEqual(r0[-13:], RangeSet("1-12"))
        self.assertEqual(r0[-1000:], RangeSet("1-12"))
        self.assertEqual(r0[-13:1], RangeSet("1"))
        self.assertEqual(r0[-13:2], RangeSet("1-2"))
        self.assertEqual(r0[-13:11], RangeSet("1-11"))
        self.assertEqual(r0[-13:12], RangeSet("1-12"))
        self.assertEqual(r0[-13:13], RangeSet("1-12"))
        # negative indices - sl_stop
        self.assertEqual(r0[0:-1], RangeSet("1-11"))
        self.assertEqual(r0[:-1], RangeSet("1-11"))
        self.assertEqual(r0[0:-2], RangeSet("1-10"))
        self.assertEqual(r0[:-2], RangeSet("1-10"))
        self.assertEqual(r0[1:-2], RangeSet("2-10"))
        self.assertEqual(r0[4:-4], RangeSet("5-8"))
        self.assertEqual(r0[5:-5], RangeSet("6-7"))
        self.assertEqual(r0[6:-5], RangeSet("7"))
        self.assertEqual(r0[6:-6], RangeSet())
        self.assertEqual(r0[7:-6], RangeSet())
        self.assertEqual(r0[0:-1000], RangeSet())

        r1 = RangeSet("10-14,16-20")
        self.assertEqual(r1[2:6], RangeSet("12-14,16"))
        self.assertEqual(r1[2:7], RangeSet("12-14,16-17"))

        r1 = RangeSet("1-2,4,9,10-12")
        self.assertEqual(r1[0:3], RangeSet("1-2,4"))
        self.assertEqual(r1[0:4], RangeSet("1-2,4,9"))
        self.assertEqual(r1[2:6], RangeSet("4,9,10-11"))
        self.assertEqual(r1[2:4], RangeSet("4,9"))
        self.assertEqual(r1[5:6], RangeSet("11"))
        self.assertEqual(r1[6:7], RangeSet("12"))
        self.assertEqual(r1[4:7], RangeSet("10-12"))

        # Slice indices are silently truncated to fall in the allowed range
        self.assertEqual(r1[2:100], RangeSet("4,9-12"))
        self.assertEqual(r1[9:10], RangeSet())

        # Slice stepping
        self.assertEqual(r1[0:1:2], RangeSet("1"))
        self.assertEqual(r1[0:2:2], RangeSet("1"))
        self.assertEqual(r1[0:3:2], RangeSet("1,4"))
        self.assertEqual(r1[0:4:2], RangeSet("1,4"))
        self.assertEqual(r1[0:5:2], RangeSet("1,4,10"))
        self.assertEqual(r1[0:6:2], RangeSet("1,4,10"))
        self.assertEqual(r1[0:7:2], RangeSet("1,4,10,12"))
        self.assertEqual(r1[0:8:2], RangeSet("1,4,10,12"))
        self.assertEqual(r1[0:9:2], RangeSet("1,4,10,12"))
        self.assertEqual(r1[0:10:2], RangeSet("1,4,10,12"))

        self.assertEqual(r1[0:7:3], RangeSet("1,9,12"))
        self.assertEqual(r1[0:7:4], RangeSet("1,10"))

        self.assertEqual(len(r1[1:1:2]), 0)
        self.assertEqual(r1[1:2:2], RangeSet("2"))
        self.assertEqual(r1[1:3:2], RangeSet("2"))
        self.assertEqual(r1[1:4:2], RangeSet("2,9"))
        self.assertEqual(r1[1:5:2], RangeSet("2,9"))
        self.assertEqual(r1[1:6:2], RangeSet("2,9,11"))
        self.assertEqual(r1[1:7:2], RangeSet("2,9,11"))

        # negative indices - sl_step
        self.assertEqual(r1[::-2], RangeSet("1,4,10,12"))
        r2 = RangeSet("1-2,4,9,10-13")
        self.assertEqual(r2[::-2], RangeSet("2,9,11,13"))
        self.assertEqual(r2[::-3], RangeSet("2,10,13"))
        self.assertEqual(r2[::-4], RangeSet("9,13"))
        self.assertEqual(r2[::-5], RangeSet("4,13"))
        self.assertEqual(r2[::-6], RangeSet("2,13"))
        self.assertEqual(r2[::-7], RangeSet("1,13"))
        self.assertEqual(r2[::-8], RangeSet("13"))
        self.assertEqual(r2[::-9], RangeSet("13"))

        # Partial slices
        self.assertEqual(r1[2:], RangeSet("4,9-12"))
        self.assertEqual(r1[:3], RangeSet("1-2,4"))
        self.assertEqual(r1[:3:2], RangeSet("1,4"))

        # Twisted
        r2 = RangeSet("1-9/2,12-32/4")
        self.assertEqual(r2[5:10:2], RangeSet("12-28/8"))
        self.assertEqual(r2[5:10:2], RangeSet("12-28/8", autostep=2))
        self.assertEqual(r2[1:12:3], RangeSet("3,9,20,32"))

        # FIXME: use nosetests/@raises to do that...
        self.assertRaises(TypeError, r1.__getitem__, slice('foo', 'bar'))
        self.assertRaises(TypeError, r1.__getitem__, slice(1, 3, 'bar'))

        r3 = RangeSet("0-600")
        self.assertEqual(r3[30:389], RangeSet("30-388"))
        r3 = RangeSet("0-6000")
        self.assertEqual(r3[30:389:2], RangeSet("30-389/2"))
        self.assertEqual(r3[30:389:2], RangeSet("30-389/2", autostep=2))

    def testSplit(self):
        """test RangeSet.split()"""
        # Empty rangeset
        rangeset = RangeSet()
        self.assertEqual(len(list(rangeset.split(2))), 0)
        # Not enough element
        rangeset = RangeSet("1")
        self.assertEqual((RangeSet("1"),), tuple(rangeset.split(2)))
        # Exact number of elements
        rangeset = RangeSet("1-6")
        self.assertEqual((RangeSet("1-2"), RangeSet("3-4"), RangeSet("5-6")), \
                         tuple(rangeset.split(3)))
        # Check limit results
        rangeset = RangeSet("0-3")
        for i in (4, 5):
            self.assertEqual((RangeSet("0"), RangeSet("1"), \
                             RangeSet("2"), RangeSet("3")), \
                             tuple(rangeset.split(i)))

    def testAdd(self):
        """test RangeSet.add()"""
        r1 = RangeSet("1-100,102,105-242,800")
        self.assertEqual(len(r1), 240)
        r1.add(801)
        self.assertEqual(len(r1), 241)
        self.assertEqual(r1[0], '1')
        self.assertEqual(r1[240], '801')
        r1.add(788)
        self.assertEqual(str(r1), "1-100,102,105-242,788,800-801")
        self.assertEqual(len(r1), 242)
        self.assertEqual(r1[0], '1')
        self.assertEqual(r1[239], '788')
        self.assertEqual(r1[240], '800')
        r1.add(812)
        self.assertEqual(len(r1), 243)
        # test forced padding
        r1 = RangeSet("1-100,102,105-242,800")
        r1.add(801, pad=3)
        self.assertEqual(len(r1), 241)
        self.assertEqual(str(r1), "1-100,102,105-242,800-801")
        r1.padding = 4  # 1.8-1.9 compat: adjust padding of the whole set
        self.assertEqual(len(r1), 241)
        self.assertEqual(str(r1), "0001-0100,0102,0105-0242,0800-0801")

    def testUpdate(self):
        """test RangeSet.update()"""
        r1 = RangeSet("1-100,102,105-242,800")
        self.assertEqual(len(r1), 240)
        r2 = RangeSet("243-799,1924-1984")
        self.assertEqual(len(r2), 618)
        r1.update(r2)
        self.assertEqual(type(r1), RangeSet)
        self.assertEqual(r1.padding, None)
        self.assertEqual(len(r1), 240+618) 
        self.assertEqual(str(r1), "1-100,102,105-800,1924-1984")
        r1 = RangeSet("1-100,102,105-242,800")
        r1.union_update(r2)
        self.assertEqual(len(r1), 240+618) 
        self.assertEqual(str(r1), "1-100,102,105-800,1924-1984")

    def testUnion(self):
        """test RangeSet.union()"""
        r1 = RangeSet("1-100,102,105-242,800")
        self.assertEqual(len(r1), 240)
        r2 = RangeSet("243-799,1924-1984")
        self.assertEqual(len(r2), 618)
        r3 = r1.union(r2)
        self.assertEqual(type(r3), RangeSet)
        self.assertEqual(r3.padding, None)
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
        """test RangeSet.remove()"""
        r1 = RangeSet("1-100,102,105-242,800")
        self.assertEqual(len(r1), 240)
        r1.remove(100)
        self.assertEqual(len(r1), 239)
        self.assertEqual(str(r1), "1-99,102,105-242,800")
        self.assertRaises(KeyError, r1.remove, 101)
        self.assertRaises(KeyError, r1.remove, "101")
        r1.remove("106")
        self.assertRaises(KeyError, r1.remove, "foo")

    def testDiscard(self):
        """test RangeSet.discard()"""
        r1 = RangeSet("1-100,102,105-242,800")
        self.assertEqual(len(r1), 240)
        r1.discard(100)
        self.assertEqual(len(r1), 239)
        self.assertEqual(str(r1), "1-99,102,105-242,800")
        r1.discard(101)     # should not raise KeyError
        r1.discard('105')
        self.assertEqual(len(r1), 238)
        self.assertEqual(str(r1), "1-99,102,106-242,800")
        r1.discard("foo")

    def testClear(self):
        """test RangeSet.clear()"""
        r1 = RangeSet("1-100,102,105-242,800")
        self.assertEqual(len(r1), 240)
        self.assertEqual(str(r1), "1-100,102,105-242,800")
        r1.clear()
        self.assertEqual(len(r1), 0)
        self.assertEqual(str(r1), "")

    def testConstructorIterate(self):
        """test RangeSet(iterable) constructor"""
        # from list
        rgs = RangeSet([3,5,6,7,8,1])
        self.assertEqual(str(rgs), "1,3,5-8")
        self.assertEqual(len(rgs), 6)
        rgs.add(10)
        self.assertEqual(str(rgs), "1,3,5-8,10")
        self.assertEqual(len(rgs), 7)
        # from set
        rgs = RangeSet(set([3,5,6,7,8,1]))
        self.assertEqual(str(rgs), "1,3,5-8")
        self.assertEqual(len(rgs), 6)
        # from RangeSet
        r1 = RangeSet("1,3,5-8")
        rgs = RangeSet(r1)
        self.assertEqual(str(rgs), "1,3,5-8")
        self.assertEqual(len(rgs), 6)

    def testFromListConstructor(self):
        """test RangeSet.fromlist() constructor"""
        rgs = RangeSet.fromlist([ "3", "5-8", "1" ])
        self.assertEqual(str(rgs), "1,3,5-8")
        self.assertEqual(len(rgs), 6)
        rgs = RangeSet.fromlist([ RangeSet("3"), RangeSet("5-8"), RangeSet("1") ])
        self.assertEqual(str(rgs), "1,3,5-8")
        self.assertEqual(len(rgs), 6)
        rgs = RangeSet.fromlist([set([3,5,6,7,8,1])])
        self.assertEqual(str(rgs), "1,3,5-8")
        self.assertEqual(len(rgs), 6)

    def testFromOneConstructor(self):
        """test RangeSet.fromone() constructor"""
        rgs = RangeSet.fromone(42)
        self.assertEqual(str(rgs), "42")
        self.assertEqual(len(rgs), 1)
        # also support slice object (v1.6+)
        rgs = RangeSet.fromone(slice(42))
        self.assertEqual(str(rgs), "0-41")
        self.assertEqual(len(rgs), 42)
        self.assertRaises(ValueError, RangeSet.fromone, slice(12, None))
        rgs = RangeSet.fromone(slice(42, 43))
        self.assertEqual(str(rgs), "42")
        self.assertEqual(len(rgs), 1)
        rgs = RangeSet.fromone(slice(42, 48))
        self.assertEqual(str(rgs), "42-47")
        self.assertEqual(len(rgs), 6)
        rgs = RangeSet.fromone(slice(42, 57, 2))
        self.assertEqual(str(rgs), "42,44,46,48,50,52,54,56")
        rgs.autostep = 3
        self.assertEqual(str(rgs), "42-56/2")
        self.assertEqual(len(rgs), 8)

    def testIterator(self):
        """test RangeSet iterator"""
        matches = ['1', '3', '4', '5', '6', '7', '8', '11']
        rgs = RangeSet.fromlist([ "11", "3", "5-8", "1", "4" ])
        cnt = 0
        for rg in rgs:
            self.assertEqual(rg, matches[cnt])
            cnt += 1
        self.assertEqual(cnt, len(matches))
        # with padding
        matches = ['001', '003', '004', '005', '006', '007', '008', '011']
        rgs = RangeSet.fromlist([ "011", "003", "005-008", "001", "004" ])
        cnt = 0
        for rg in rgs:
            self.assertFalse(isinstance(rg, int))  # true prior to v1.9
            self.assertTrue(isinstance(rg, str))   # true since v1.9
            self.assertEqual(rg, matches[cnt])
            cnt += 1
        self.assertEqual(cnt, len(matches))

    def testStringIterator(self):
        """test RangeSet string iterator striter()"""
        matches = [ 1, 3, 4, 5, 6, 7, 8, 11 ]
        rgs = RangeSet.fromlist([ "11", "3", "5-8", "1", "4" ])
        cnt = 0
        for rg in rgs.striter():
            self.assertEqual(rg, str(matches[cnt]))
            cnt += 1
        self.assertEqual(cnt, len(matches))
        # with padding
        rgs = RangeSet.fromlist([ "011", "003", "005-008", "001", "004" ])
        cnt = 0
        for rg in rgs.striter():
            self.assertTrue(isinstance(rg, str))
            self.assertEqual(rg, "%0*d" % (3, matches[cnt]))
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
        self.assertTrue(good_error, "TypeError not raised for &")
        good_error = False
        try:
            rg3 = rg1 | rg2
        except TypeError:
            good_error = True
        self.assertTrue(good_error, "TypeError not raised for |")
        good_error = False
        try:
            rg3 = rg1 - rg2
        except TypeError:
            good_error = True
        self.assertTrue(good_error, "TypeError not raised for -")
        good_error = False
        try:
            rg3 = rg1 ^ rg2
        except TypeError:
            good_error = True
        self.assertTrue(good_error, "TypeError not raised for ^")

    def testIsSubSetError(self):
        """test RangeSet.issubset() error"""
        rg1 = RangeSet("1-5")
        rg2 = "4-6"
        self.assertRaises(TypeError, rg1.issubset, rg2)

    def testEquality(self):
        """test RangeSet equality"""
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

    def testAddRange(self):
        """test RangeSet.add_range()"""
        r1 = RangeSet()
        r1.add_range(1, 100, 1)
        self.assertEqual(len(r1), 99)
        self.assertEqual(str(r1), "1-99")
        r1.add_range(40, 101, 1)
        self.assertEqual(len(r1), 100)
        self.assertEqual(str(r1), "1-100")
        r1.add_range(399, 423, 2)
        self.assertEqual(len(r1), 112)
        self.assertEqual(str(r1), "1-100,399,401,403,405,407,409,411,413,415,417,419,421")
        # With autostep...
        r1 = RangeSet(autostep=3)
        r1.add_range(1, 100, 1)
        self.assertEqual(r1.autostep, 3)
        self.assertEqual(len(r1), 99)
        self.assertEqual(str(r1), "1-99")
        r1.add_range(40, 101, 1)
        self.assertEqual(len(r1), 100)
        self.assertEqual(str(r1), "1-100")
        r1.add_range(399, 423, 2)
        self.assertEqual(len(r1), 112)
        self.assertEqual(str(r1), "1-100,399-421/2")
        # Bound checks
        r1 = RangeSet("1-30", autostep=2)
        self.assertEqual(len(r1), 30)
        self.assertEqual(str(r1), "1-30")
        self.assertEqual(r1.autostep, 2)
        r1.add_range(32, 35, 1)
        self.assertEqual(len(r1), 33)
        self.assertEqual(str(r1), "1-30,32-34")
        r1.add_range(31, 32, 1)
        self.assertEqual(len(r1), 34)
        self.assertEqual(str(r1), "1-34")
        r1 = RangeSet("1-30/4")
        self.assertEqual(len(r1), 8)
        self.assertEqual(str(r1), "1,5,9,13,17,21,25,29")
        r1.add_range(30, 32, 1)
        self.assertEqual(len(r1), 10)
        self.assertEqual(str(r1), "1,5,9,13,17,21,25,29-31")
        r1.add_range(40, 65, 10)
        self.assertEqual(len(r1), 13)
        self.assertEqual(str(r1), "1,5,9,13,17,21,25,29-31,40,50,60")
        r1 = RangeSet("1-30", autostep=3)
        r1.add_range(40, 65, 10)
        self.assertEqual(r1.autostep, 3)
        self.assertEqual(len(r1), 33)
        self.assertEqual(str(r1), "1-30,40-60/10")
        # One
        r1.add_range(103, 104)
        self.assertEqual(len(r1), 34)
        self.assertEqual(str(r1), "1-30,40-60/10,103")
        # Zero
        self.assertRaises(AssertionError, r1.add_range, 103, 103)

    def testSlices(self):
        """test RangeSet.slices()"""
        r1 = RangeSet()
        self.assertEqual(len(r1), 0)
        self.assertEqual(len(list(r1.slices())), 0)
        # Without autostep
        r1 = RangeSet("1-7/2,8-12,3000-3019")
        self.assertEqual(r1.autostep, None)
        self.assertEqual(len(r1), 29)
        self.assertEqual(list(r1.slices()), [slice(1, 2, 1), slice(3, 4, 1), \
            slice(5, 6, 1), slice(7, 13, 1), slice(3000, 3020, 1)])
        # With autostep
        r1 = RangeSet("1-7/2,8-12,3000-3019", autostep=2)
        self.assertEqual(len(r1), 29)
        self.assertEqual(r1.autostep, 2)
        self.assertEqual(list(r1.slices()), [slice(1, 8, 2), slice(8, 13, 1), \
            slice(3000, 3020, 1)])

    def testCopy(self):
        """test RangeSet.copy()"""
        rangeset = RangeSet("115-117,130,166-170,4780-4999")
        self.assertEqual(len(rangeset), 229)
        self.assertEqual(str(rangeset), "115-117,130,166-170,4780-4999")
        r1 = rangeset.copy()
        r2 = rangeset.copy()
        self.assertEqual(rangeset, r1) # content equality
        r1.remove(166)
        self.assertEqual(len(rangeset), len(r1) + 1)
        self.assertNotEqual(rangeset, r1)
        self.assertEqual(str(rangeset), "115-117,130,166-170,4780-4999")
        self.assertEqual(str(r1), "115-117,130,167-170,4780-4999")
        r2.update(RangeSet("118"))
        self.assertNotEqual(rangeset, r2)
        self.assertNotEqual(r1, r2)
        self.assertEqual(len(rangeset) + 1, len(r2))
        self.assertEqual(str(rangeset), "115-117,130,166-170,4780-4999")
        self.assertEqual(str(r1), "115-117,130,167-170,4780-4999")
        self.assertEqual(str(r2), "115-118,130,166-170,4780-4999")

    # unpickling tests; generate data with:
    # rs = RangeSet("5,7-102,104,106-107")
    # print(binascii.b2a_base64(pickle.dumps(rs)))

    def test_unpickle_v1_3_py24(self):
        """test RangeSet unpickling (against v1.3/py24)"""
        rngset = pickle.loads(binascii.a2b_base64("gAIoY0NsdXN0ZXJTaGVsbC5Ob2RlU2V0ClJhbmdlU2V0CnEAb3EBfXECKFUHX2xlbmd0aHEDS2RVCV9hdXRvc3RlcHEER1SySa0llMN9VQdfcmFuZ2VzcQVdcQYoKEsFSwVLAUsAdHEHKEsHS2ZLAUsAdHEIKEtoS2hLAUsAdHEJKEtqS2tLAUsAdHEKZXViLg=="))
        self.assertEqual(rngset, RangeSet("5,7-102,104,106-107"))
        self.assertEqual(str(rngset), "5,7-102,104,106-107")
        self.assertEqual(len(rngset), 100)
        self.assertEqual(rngset[0], '5')
        self.assertEqual(rngset[1], '7')
        self.assertEqual(rngset[-1], '107')

    def test_unpickle_v1_3_py26(self):
        """test RangeSet unpickling (against v1.3/py26)"""
        rngset = pickle.loads(binascii.a2b_base64("gAIoY0NsdXN0ZXJTaGVsbC5Ob2RlU2V0ClJhbmdlU2V0CnEAb3EBfXECKFUHX2xlbmd0aHEDS2RVCV9hdXRvc3RlcHEER1SySa0llMN9VQdfcmFuZ2VzcQVdcQYoKEsFSwVLAUsAdHEHKEsHS2ZLAUsAdHEIKEtoS2hLAUsAdHEJKEtqS2tLAUsAdHEKZXViLg=="))
        self.assertEqual(rngset, RangeSet("5,7-102,104,106-107"))
        self.assertEqual(str(rngset), "5,7-102,104,106-107")
        self.assertEqual(len(rngset), 100)
        self.assertEqual(rngset[0], '5')
        self.assertEqual(rngset[1], '7')
        self.assertEqual(rngset[-1], '107')

    # unpickle_v1_4_py24 : unpickling fails as v1.4 does not have slice pickling workaround

    def test_unpickle_v1_4_py26(self):
        """test RangeSet unpickling (against v1.4/py26)"""
        rngset = pickle.loads(binascii.a2b_base64("gAIoY0NsdXN0ZXJTaGVsbC5Ob2RlU2V0ClJhbmdlU2V0CnEAb3EBfXEDKFUHX2xlbmd0aHEES2RVCV9hdXRvc3RlcHEFR1SySa0llMN9VQdfcmFuZ2VzcQZdcQcoY19fYnVpbHRpbl9fCnNsaWNlCnEISwVLBksBh3EJUnEKSwCGcQtoCEsHS2dLAYdxDFJxDUsAhnEOaAhLaEtpSwGHcQ9ScRBLAIZxEWgIS2pLbEsBh3ESUnETSwCGcRRlVQhfdmVyc2lvbnEVSwJ1Yi4="))
        self.assertEqual(rngset, RangeSet("5,7-102,104,106-107"))
        self.assertEqual(str(rngset), "5,7-102,104,106-107")
        self.assertEqual(len(rngset), 100)
        self.assertEqual(rngset[0], '5')
        self.assertEqual(rngset[1], '7')
        self.assertEqual(rngset[-1], '107')

    def test_unpickle_v1_5_py24(self):
        """test RangeSet unpickling (against v1.5/py24)"""
        rngset = pickle.loads(binascii.a2b_base64("gAIoY0NsdXN0ZXJTaGVsbC5Ob2RlU2V0ClJhbmdlU2V0CnEAb3EBfXEDKFUHX2xlbmd0aHEES2RVCV9hdXRvc3RlcHEFR1SySa0llMN9VQdfcmFuZ2VzcQZdcQcoSwVLBksBh3EISwCGcQlLB0tnSwGHcQpLAIZxC0toS2lLAYdxDEsAhnENS2pLbEsBh3EOSwCGcQ9lVQhfdmVyc2lvbnEQSwJ1Yi4="))
        self.assertEqual(rngset, RangeSet("5,7-102,104,106-107"))
        self.assertEqual(str(rngset), "5,7-102,104,106-107")
        self.assertEqual(len(rngset), 100)
        self.assertEqual(rngset[0], '5')
        self.assertEqual(rngset[1], '7')
        self.assertEqual(rngset[-1], '107')

    def test_unpickle_v1_5_py26(self):
        """test RangeSet unpickling (against v1.5/py26)"""
        rngset = pickle.loads(binascii.a2b_base64("gAIoY0NsdXN0ZXJTaGVsbC5Ob2RlU2V0ClJhbmdlU2V0CnEAb3EBfXEDKFUHX2xlbmd0aHEES2RVCV9hdXRvc3RlcHEFR1SySa0llMN9VQdfcmFuZ2VzcQZdcQcoY19fYnVpbHRpbl9fCnNsaWNlCnEISwVLBksBh3EJUnEKSwCGcQtoCEsHS2dLAYdxDFJxDUsAhnEOaAhLaEtpSwGHcQ9ScRBLAIZxEWgIS2pLbEsBh3ESUnETSwCGcRRlVQhfdmVyc2lvbnEVSwJ1Yi4="))

        self.assertEqual(rngset, RangeSet("5,7-102,104,106-107"))
        self.assertEqual(str(rngset), "5,7-102,104,106-107")
        self.assertEqual(len(rngset), 100)
        self.assertEqual(rngset[0], '5')
        self.assertEqual(rngset[1], '7')
        self.assertEqual(rngset[-1], '107')

    def test_unpickle_v1_6_py24(self):
        """test RangeSet unpickling (against v1.6/py24)"""
        rngset = pickle.loads(binascii.a2b_base64("gAJjQ2x1c3RlclNoZWxsLlJhbmdlU2V0ClJhbmdlU2V0CnEAVRM1LDctMTAyLDEwNCwxMDYtMTA3cQGFcQJScQN9cQQoVQdwYWRkaW5ncQVOVQlfYXV0b3N0ZXBxBkdUskmtJZTDfVUIX3ZlcnNpb25xB0sDdWIu"))
        self.assertEqual(rngset, RangeSet("5,7-102,104,106-107"))
        self.assertEqual(str(rngset), "5,7-102,104,106-107")
        self.assertEqual(len(rngset), 100)
        self.assertEqual(rngset[0], '5')
        self.assertEqual(rngset[1], '7')
        self.assertEqual(rngset[-1], '107')

    def test_unpickle_v1_6_py26(self):
        """test RangeSet unpickling (against v1.6/py26)"""
        rngset = pickle.loads(binascii.a2b_base64("gAJjQ2x1c3RlclNoZWxsLlJhbmdlU2V0ClJhbmdlU2V0CnEAVRM1LDctMTAyLDEwNCwxMDYtMTA3cQGFcQJScQN9cQQoVQdwYWRkaW5ncQVOVQlfYXV0b3N0ZXBxBkdUskmtJZTDfVUIX3ZlcnNpb25xB0sDdWIu"))
        self.assertEqual(rngset, RangeSet("5,7-102,104,106-107"))
        self.assertEqual(str(rngset), "5,7-102,104,106-107")
        self.assertEqual(len(rngset), 100)
        self.assertEqual(rngset[0], '5')
        self.assertEqual(rngset[1], '7')
        self.assertEqual(rngset[-1], '107')

    def test_unpickle_v1_8_4_py27(self):
        """test RangeSet unpickling (against v1.8.4/py27)"""
        rngset = pickle.loads(binascii.a2b_base64("Y0NsdXN0ZXJTaGVsbC5SYW5nZVNldApSYW5nZVNldApwMAooUyc1LDctMTAyLDEwNCwxMDYtMTA3JwpwMQp0cDIKUnAzCihkcDQKUydwYWRkaW5nJwpwNQpOc1MnX2F1dG9zdGVwJwpwNgpGMWUrMTAwCnNTJ192ZXJzaW9uJwpwNwpJMwpzYi4="))
        self.assertEqual(rngset, RangeSet("5,7-102,104,106-107"))
        self.assertEqual(str(rngset), "5,7-102,104,106-107")
        self.assertEqual(len(rngset), 100)
        self.assertEqual(rngset[0], '5')
        self.assertEqual(rngset[1], '7')
        self.assertEqual(rngset[-1], '107')

        rngset = pickle.loads(binascii.a2b_base64("Y0NsdXN0ZXJTaGVsbC5SYW5nZVNldApSYW5nZVNldApwMAooUycwMDAzLTAwNDAsMDA1OS0xNDAwJwpwMQp0cDIKUnAzCihkcDQKUydwYWRkaW5nJwpwNQpJNApzUydfYXV0b3N0ZXAnCnA2CkYxZSsxMDAKc1MnX3ZlcnNpb24nCnA3CkkzCnNiLg=="))
        self.assertEqual(rngset, RangeSet("0003-0040,0059-1400"))
        self.assertEqual(str(rngset), "0003-0040,0059-1400")
        self.assertEqual(len(rngset), 1380)
        self.assertEqual(rngset[0], '0003')
        self.assertEqual(rngset[1], '0004')
        self.assertEqual(rngset[-1], '1400')

    def test_pickle_current(self):
        """test RangeSet pickling (current version)"""
        dump = pickle.dumps(RangeSet("1-100"))
        self.assertNotEqual(dump, None)
        rngset = pickle.loads(dump)
        self.assertEqual(rngset, RangeSet("1-100"))
        self.assertEqual(str(rngset), "1-100")
        self.assertEqual(rngset[0], '1')
        self.assertEqual(rngset[1], '2')
        self.assertEqual(rngset[-1], '100')

    def testIntersectionLength(self):
        """test RangeSet intersection/length"""
        r1 = RangeSet("115-117,130,166-170,4780-4999")
        self.assertEqual(len(r1), 229)
        r2 = RangeSet("116-117,130,4781-4999")
        self.assertEqual(len(r2), 222)
        res = r1.intersection(r2)
        self.assertEqual(len(res), 222)
        r1 = RangeSet("115-200")
        self.assertEqual(len(r1), 86)
        r2 = RangeSet("116-117,119,123-131,133,149,199")
        self.assertEqual(len(r2), 15)
        res = r1.intersection(r2)
        self.assertEqual(len(res), 15)
        # StopIteration test
        r1 = RangeSet("115-117,130,166-170,4780-4999,5003")
        self.assertEqual(len(r1), 230)
        r2 = RangeSet("116-117,130,4781-4999")
        self.assertEqual(len(r2), 222)
        res = r1.intersection(r2)
        self.assertEqual(len(res), 222)
        # StopIteration test2
        r1 = RangeSet("130,166-170,4780-4999")
        self.assertEqual(len(r1), 226)
        r2 = RangeSet("116-117")
        self.assertEqual(len(r2), 2)
        res = r1.intersection(r2)
        self.assertEqual(len(res), 0)

    def testFolding(self):
        """test RangeSet folding conditions"""
        r1 = RangeSet("112,114-117,119,121,130,132,134,136,138,139-141,144,147-148", autostep=6)
        self.assertEqual(str(r1), "112,114-117,119,121,130,132,134,136,138-141,144,147-148")
        r1.autostep = 5
        self.assertEqual(str(r1), "112,114-117,119,121,130-138/2,139-141,144,147-148")

        r1 = RangeSet("1,3-4,6,8")
        self.assertEqual(str(r1), "1,3-4,6,8")
        r1 = RangeSet("1,3-4,6,8", autostep=4)
        self.assertEqual(str(r1), "1,3-4,6,8")
        r1 = RangeSet("1,3-4,6,8", autostep=2)
        self.assertEqual(str(r1), "1-3/2,4,6-8/2")
        r1 = RangeSet("1,3-4,6,8", autostep=3)
        self.assertEqual(str(r1), "1,3-4,6,8")

        # empty set
        r1 = RangeSet(autostep=3)
        self.assertEqual(str(r1), "")

    def test_ior(self):
        """test RangeSet.__ior__()"""
        r1 = RangeSet("1,3-9,14-21,30-39,42")
        r2 = RangeSet("2-5,10-32,35,40-41")
        r1 |= r2
        self.assertEqual(len(r1), 42)
        self.assertEqual(str(r1), "1-42")

    def test_iand(self):
        """test RangeSet.__iand__()"""
        r1 = RangeSet("1,3-9,14-21,30-39,42")
        r2 = RangeSet("2-5,10-32,35,40-41")
        r1 &= r2
        self.assertEqual(len(r1), 15)
        self.assertEqual(str(r1), "3-5,14-21,30-32,35")

    def test_ixor(self):
        """test RangeSet.__ixor__()"""
        r1 = RangeSet("1,3-9,14-21,30-39,42")
        r2 = RangeSet("2-5,10-32,35,40-41")
        r1 ^= r2
        self.assertEqual(len(r1), 27)
        self.assertEqual(str(r1), "1-2,6-13,22-29,33-34,36-42")

    def test_isub(self):
        """test RangeSet.__isub__()"""
        r1 = RangeSet("1,3-9,14-21,30-39,42")
        r2 = RangeSet("2-5,10-32,35,40-41")
        r1 -= r2
        self.assertEqual(len(r1), 12)
        self.assertEqual(str(r1), "1,6-9,33-34,36-39,42")

    def test_contiguous(self):
        r0 = RangeSet()
        self.assertEqual([], [str(ns) for ns in r0.contiguous()])
        r1 = RangeSet("1,3-9,14-21,30-39,42")
        self.assertEqual(['1', '3-9', '14-21', '30-39', '42'], [str(ns) for ns in r1.contiguous()])

    def test_dim(self):
        r0 = RangeSet()
        self.assertEqual(r0.dim(), 0)
        r1 = RangeSet("1-10,15-20")
        self.assertEqual(r1.dim(), 1)

    def test_intiter(self):
        matches = [ 1, 3, 4, 5, 6, 7, 8, 11 ]
        rgs = RangeSet.fromlist([ "11", "3", "5-8", "1", "4" ])
        cnt = 0
        for rg in rgs.intiter():
            self.assertEqual(rg, matches[cnt])
            cnt += 1
        self.assertEqual(cnt, len(matches))
        # with padding
        rgs = RangeSet.fromlist([ "011", "003", "005-008", "001", "004" ])
        cnt = 0
        for rg in rgs.intiter():
            self.assertTrue(isinstance(rg, int))
            self.assertEqual(rg, matches[cnt])
            cnt += 1
        self.assertEqual(cnt, len(matches))
        # with mixed length padding (add 01, 09 and 0001): not supported until 1.9
        matches = [ 1, 9 ] + matches + [ 1 ]
        rgs = RangeSet.fromlist([ "011", "01", "003", "005-008", "001", "0001", "09", "004" ])
        cnt = 0
        for rg in rgs.intiter():
            self.assertTrue(isinstance(rg, int))
            self.assertEqual(rg, matches[cnt])
            cnt += 1
        self.assertEqual(cnt, len(matches))

    def test_mixed_padding(self):
        r0 = RangeSet("030-031,032-100/2,101-489", autostep=3)
        self.assertEqual(str(r0), "030-032,034-100/2,101-489")
        r1 = RangeSet("030-032,033-100/3,102", autostep=3)
        self.assertEqual(str(r1), "030-033,036-102/3")
        r2 = RangeSet("030-032,033-100/3,101", autostep=3)
        self.assertEqual(str(r2), "030-033,036-099/3,101")
        r3 = RangeSet("030-032,033-100/3,100", autostep=3)
        self.assertEqual(str(r3), "030-033,036-099/3,100")
        r5 = RangeSet("030-032,033-100/3,99-105/3,0001", autostep=3)
        self.assertEqual(str(r5), "99,030-033,036-105/3,0001")

    def test_mixed_padding_mismatch(self):
        self.assertRaises(RangeSetParseError, RangeSet, "1-044")
        self.assertRaises(RangeSetParseError, RangeSet, "01-044")
        self.assertRaises(RangeSetParseError, RangeSet, "001-44")

        self.assertRaises(RangeSetParseError, RangeSet, "0-9,1-044")
        self.assertRaises(RangeSetParseError, RangeSet, "0-9,01-044")
        self.assertRaises(RangeSetParseError, RangeSet, "0-9,001-44")

        self.assertRaises(RangeSetParseError, RangeSet, "030-032,033-99/3,100")

    def test_padding_property_compat(self):
        r0 = RangeSet("0-10,15-20")
        self.assertEqual(r0.padding, None)
        r0.padding = 1
        self.assertEqual(r0.padding, None)
        self.assertEqual(str(r0), "0-10,15-20")
        r0.padding = 2
        self.assertEqual(r0.padding, 2)
        self.assertEqual(str(r0), "00-10,15-20")
        r0.padding = 3
        self.assertEqual(r0.padding, 3)
        self.assertEqual(str(r0), "000-010,015-020")
        # reset padding using None is allowed
        r0.padding = None
        self.assertEqual(r0.padding, None)
        self.assertEqual(str(r0), "0-10,15-20")

    def test_strip_whitespaces(self):
        r0 = RangeSet(" 1,5,39-42,100")
        self._testRS(" 1,5,39-42,100", "1,5,39-42,100", 7)
        self._testRS("1 ,5,39-42,100", "1,5,39-42,100", 7)
        self._testRS("1, 5,39-42,100", "1,5,39-42,100", 7)
        self._testRS("1,5 ,39-42,100", "1,5,39-42,100", 7)
        self._testRS("1,5, 39-42,100", "1,5,39-42,100", 7)
        self._testRS("1,5,39-42 ,100", "1,5,39-42,100", 7)
        self._testRS("1,5,39-42, 100", "1,5,39-42,100", 7)
        self._testRS("1,5,39-42,100 ", "1,5,39-42,100", 7)
        self._testRS(" 1 ,5,39-42,100", "1,5,39-42,100", 7)
        self._testRS("1 , 5 , 39-42 , 100", "1,5,39-42,100", 7)
        self._testRS(" 1 , 5 , 39-42 , 100 ", "1,5,39-42,100", 7)

        # whitespaces within ranges
        self._testRS("1 - 2", "1-2", 2)
        self._testRS("01 - 02", "01-02", 2)
        self._testRS("01- 02", "01-02", 2)
        self._testRS("01 -02", "01-02", 2)
        self._testRS(" 01-02", "01-02", 2)
        self._testRS(" 01 -02", "01-02", 2)
        self._testRS(" 01 - 02", "01-02", 2)
        self._testRS(" 01 - 02 ", "01-02", 2)
        self._testRS("01 - 02 ", "01-02", 2)
        self._testRS("01- 02 ", "01-02", 2)
        self._testRS("01-02 ", "01-02", 2)

        self._testRS("0-8/2", "0-8/2", 5)
        self._testRS("1-7/2", "1-7/2", 4)
        self._testRS("0-8 /2", "0-8/2", 5)
        self._testRS("1-7 /2", "1-7/2", 4)
        self._testRS("0-8/ 2", "0-8/2", 5)
        self._testRS("1-7/ 2", "1-7/2", 4)
        self._testRS("0-8 / 2", "0-8/2", 5)
        self._testRS("1-7 / 2", "1-7/2", 4)
        self._testRS("0 -8 / 2", "0-8/2", 5)
        self._testRS("1 -7 / 2", "1-7/2", 4)
        self._testRS("0 - 8 / 2", "0-8/2", 5)
        self._testRS("1 - 7 / 2", "1-7/2", 4)
        self._testRS("00-08/2", "00-08/2", 5)
        self._testRS("01-07/2", "01-07/2", 4)
        self._testRS("00-08 /2", "00-08/2", 5)
        self._testRS("01-07 /2", "01-07/2", 4)
        self._testRS("00-08/ 2", "00-08/2", 5)
        self._testRS("01-07/ 2", "01-07/2", 4)
        self._testRS("00-08 / 2", "00-08/2", 5)
        self._testRS("01-07 / 2", "01-07/2", 4)

        # invalid patterns
        self.assertRaises(RangeSetParseError, RangeSet, " 0 0")
        self.assertRaises(RangeSetParseError, RangeSet, " 1 2")
        self.assertRaises(RangeSetParseError, RangeSet, "0 1")
        self.assertRaises(RangeSetParseError, RangeSet, "0 1 ")
        self.assertRaises(RangeSetParseError, RangeSet, "1,5,39-42,10 0")
        self.assertRaises(RangeSetParseError, RangeSet, "1,5,39-42,12 3,300")
        self.assertRaises(RangeSetParseError, RangeSet, "1,5,")
        self.assertRaises(RangeSetParseError, RangeSet, "1,5,")
        self.assertRaises(RangeSetParseError, RangeSet, "1,5, ")
        self.assertRaises(RangeSetParseError, RangeSet, "1,5,, ")
