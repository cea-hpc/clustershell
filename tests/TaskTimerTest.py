#!/usr/bin/env python
# ClusterShell timer test suite
# Written by S. Thiell 2009-02-15
# $Id$


"""Unit test for ClusterShell Task's timer"""

import copy
import sys
import unittest

sys.path.insert(0, '../lib')

from ClusterShell.Event import EventHandler
from ClusterShell.Task import *


class TaskTimerTest(unittest.TestCase):

    class TSimpleTimerChecker(EventHandler):
        def __init__(self):
            self.count = 0

        def ev_timer(self, timer):
            self.count += 1

    def testSimpleTimer(self):
        """test simple timer"""
        task = task_self()
        self.assert_(task != None)

        # init event handler for timer's callback
        test_handler = self.__class__.TSimpleTimerChecker()
        timer1 = task.timer(1.0, handler=test_handler)
        self.assert_(timer1 != None)
        # run task
        task.resume()
        # test events received: start, read, timeout, close
        self.assertEqual(test_handler.count, 1)

    class TRepeaterTimerChecker(EventHandler):
        def __init__(self):
            self.count = 0
            
        def ev_timer(self, timer):
            self.count += 1
            timer.set_interval(timer.interval+0.1)
            if self.count > 4:
                timer.set_interval(-1)

    def testSimpleRepeater(self):
        """test simple repeater timer"""
        task = task_self()
        self.assert_(task != None)
        # init event handler for timer's callback
        test_handler = self.__class__.TRepeaterTimerChecker()
        timer1 = task.timer(1.0, interval=0.5, handler=test_handler)
        self.assert_(timer1 != None)
        # run task
        task.resume()
        # test events received: start, read, timeout, close
        self.assertEqual(test_handler.count, 5)

if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TaskTimerTest)
    unittest.TextTestRunner(verbosity=2).run(suite)

