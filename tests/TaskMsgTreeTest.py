#!/usr/bin/env python
# ClusterShell test suite
# Written by S. Thiell 2010-02-18


"""Unit test for ClusterShell TaskMsgTree variants"""

import sys
import unittest

sys.path.insert(0, '../lib')

from ClusterShell.Task import Task, TaskMsgTreeError
from ClusterShell.Task import task_cleanup, task_self


class TaskMsgTreeTest(unittest.TestCase):
    
    def tearDown(self):
        # cleanup task_self between tests to restore defaults
        task_cleanup()

    def testEnabledMsgTree(self):
        """test TaskMsgTree enabled"""
        task = task_self()
        self.assert_(task != None)
        # init worker
        worker = task.shell("echo foo bar")
        self.assert_(worker != None)
        task.set_default('stdout_msgtree', True)
        # run task
        task.resume()
        # should not raise
        for buf, keys in task.iter_buffers():
            pass

    def testDisabledMsgTree(self):
        """test TaskMsgTree disabled"""
        task = task_self()
        self.assert_(task != None)
        # init worker
        worker = task.shell("echo foo bar2")
        self.assert_(worker != None)
        task.set_default('stdout_msgtree', False)
        # run task
        task.resume()
        self.assertRaises(TaskMsgTreeError, task.iter_buffers)

    def testEnabledMsgTreeStdErr(self):
        """test TaskMsgTree enabled for stderr"""
        task = task_self()
        self.assert_(task != None)
        # init worker
        worker = task.shell("echo foo bar 1>&2", stderr=True)
        worker = task.shell("echo just foo bar", stderr=True)
        self.assert_(worker != None)
        task.set_default('stderr_msgtree', True)
        # run task
        task.resume()
        # should not raise:
        for buf, keys in task.iter_errors():
            pass
        # this neither:
        for buf, keys in task.iter_buffers():
            pass

    def testDisabledMsgTreeStdErr(self):
        """test TaskMsgTree disabled for stderr"""
        task = task_self()
        self.assert_(task != None)
        # init worker
        worker = task.shell("echo foo bar2 1>&2", stderr=True)
        worker = task.shell("echo just foo bar2", stderr=True)
        self.assert_(worker != None)
        task.set_default('stderr_msgtree', False)
        # run task
        task.resume()
        # should not raise:
        for buf, keys in task.iter_buffers():
            pass
        # but this should:
        self.assertRaises(TaskMsgTreeError, task.iter_errors)

    def testTaskFlushBuffers(self):
        """test Task.flush_buffers"""
        task = task_self()
        self.assert_(task != None)
        # init worker
        worker = task.shell("echo foo bar")
        self.assert_(worker != None)
        task.set_default('stdout_msgtree', True)
        # run task
        task.resume()
        task.flush_buffers()
        self.assertEqual(len(list(task.iter_buffers())), 0)

    def testTaskFlushErrors(self):
        """test Task.flush_errors"""
        task = task_self()
        self.assert_(task != None)
        # init worker
        worker = task.shell("echo foo bar 1>&2")
        self.assert_(worker != None)
        task.set_default('stderr_msgtree', True)
        # run task
        task.resume()
        task.flush_errors()
        self.assertEqual(len(list(task.iter_errors())), 0)


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TaskMsgTreeTest)
    unittest.TextTestRunner(verbosity=2).run(suite)

