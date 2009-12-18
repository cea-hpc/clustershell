#!/usr/bin/env python
# ClusterShell (multi-tasks) test suite
# Written by S. Thiell 2009-10-26
# $Id$


"""Unit test for ClusterShell Task (multi)"""

import copy
import sys
import unittest

sys.path.insert(0, '../lib')

from ClusterShell.Task import *


class TaskAdvancedTest(unittest.TestCase):

    def testTaskEngineUserSelection(self):
        """test task engine user selection hack"""
        task_terminate()
        # Uh ho! It's a test case, not an example!
        Task._default_info['engine'] = 'poll'
        self.assertEqual(task_self().info('engine'), 'poll')
        task_terminate()

    def testTaskEngineWrongUserSelection(self):
        """test task engine wrong user selection hack"""
        try:
            task_terminate()
            # Uh ho! It's a test case, not an example!
            Task._default_info['engine'] = 'foobar'
            # Check for KeyError in case of wrong engine request
            self.assertRaises(KeyError, task_self)
        finally:
            Task._default_info['engine'] = 'auto'

        task_terminate()

    def testTaskNewThread1(self):
        """test task in new thread 1"""
        # create a task in a new thread
        task = Task()
        self.assert_(task != None)

        match = "test"

        # schedule a command in that task
        worker = task.shell("/bin/echo %s" % match)

        # run this task
        task.resume()

        # wait for the task to complete
        task_wait()

        # verify that the worker has completed
        self.assertEqual(worker.read(), match)

    def testTaskInNewThread2(self):
        """test task in new thread 2"""
        # create a task in a new thread
        task = Task()
        self.assert_(task != None)

        match = "again"

        # schedule a command in that task
        worker = task.shell("/bin/echo %s" % match)

        # run this task
        task.resume()

        # wait for the task to complete
        task_wait()

        # verify that the worker has completed
        self.assertEqual(worker.read(), match)


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TaskAdvancedTest)
    unittest.TextTestRunner(verbosity=2).run(suite)

