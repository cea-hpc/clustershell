#!/usr/bin/env python
# ClusterShell.NodeSet.RangeSet test suite
# Written by S. Thiell
# $Id$


"""Unit test for RangeSet"""

import copy
import sys
import unittest

sys.path.append('../lib')

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



if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(RangeSetTest)
    unittest.TextTestRunner(verbosity=2).run(suite)
