#!/usr/bin/env python
# ClusterShell (multi-tasks) test suite
# Written by S. Thiell 2009-10-26


"""Unit test for ClusterShell Task (multi)"""

import copy
import sys
import unittest

sys.path.insert(0, '../lib')

from ClusterShell.Task import *


class TaskAdvancedTest(unittest.TestCase):

    def tearDown(self):
        task_cleanup()

    def testTaskRun(self):
        """test task.run() behaving like task.resume()"""
        wrk = task_self().shell("true")
        task_self().run()

    def testTaskRunTimeout(self):
        """test task.run() behaving like task.resume(timeout)"""
        wrk = task_self().shell("sleep 1")
        self.assertRaises(TimeoutError, task_self().run, 0.3)

        wrk = task_self().shell("sleep 1")
        self.assertRaises(TimeoutError, task_self().run, timeout=0.3)

    def testTaskShellRunLocal(self):
        """test task.run() used as a synchronous task.shell() (local)"""
        wrk = task_self().run("false")
        self.assertTrue(wrk)
        self.assertEqual(task_self().max_retcode(), 1)

        # Timeout in shell() fashion way.
        wrk = task_self().run("sleep 1", timeout=0.3)
        self.assertTrue(wrk)
        self.assertEqual(task_self().num_timeout(), 1)

    def testTaskShellRunDistant(self):
        """test task.run() used as a synchronous task.shell() (distant)"""
        wrk = task_self().run("false", nodes="localhost")
        self.assertTrue(wrk)
        self.assertEqual(wrk.node_retcode("localhost"), 1)

    def testTaskEngineUserSelection(self):
        """test task engine user selection hack"""
        task_terminate()
        # Uh ho! It's a test case, not an example!
        Task._std_default['engine'] = 'select'
        self.assertEqual(task_self().info('engine'), 'select')
        task_terminate()

    def testTaskEngineWrongUserSelection(self):
        """test task engine wrong user selection hack"""
        try:
            task_terminate()
            # Uh ho! It's a test case, not an example!
            Task._std_default['engine'] = 'foobar'
            # Check for KeyError in case of wrong engine request
            self.assertRaises(KeyError, task_self)
        finally:
            Task._std_default['engine'] = 'auto'

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

    def testTaskInNewThread3(self):
        """test task in new thread 3"""
        # create a task in a new thread
        task = Task()
        self.assert_(task != None)

        match = "once again"

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

