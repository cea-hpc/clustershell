#!/usr/bin/env python
# ClusterShell test suite
# Written by S. Thiell 2010-01-16
# $Id$


"""Unit test for ClusterShell in multithreaded environments"""

import sys
import time
import unittest

sys.path.insert(0, '../lib')

from ClusterShell.Task import *
from ClusterShell.Event import EventHandler


class TaskThreadSuspendTest(unittest.TestCase):

    def tearDown(self):
        task_cleanup()

    def testSuspendMiscTwoTasks(self):
        """test task suspend/resume (2 tasks)"""
        task = task_self()
        task2 = Task()

        task2.shell("sleep 4 && echo thr1")
        task2.resume()
        w = task.shell("sleep 1 && echo thr0", key=0)
        task.resume()
        self.assertEqual(task.key_buffer(0), "thr0")
        self.assertEqual(w.read(), "thr0")

        assert task2 != task
        task2.suspend()
        time.sleep(10)
        task2.resume()

        task_wait()

        task2.shell("echo suspend_test", key=1)
        task2.resume()

        task_wait()
        self.assertEqual(task2.key_buffer(1), "suspend_test")


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TaskThreadSuspendTest)
    unittest.TextTestRunner(verbosity=2).run(suite)

