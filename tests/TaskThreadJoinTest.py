#!/usr/bin/env python
# ClusterShell test suite
# Written by S. Thiell 2010-01-16
# $Id$


"""Unit test for ClusterShell task's join feature in multithreaded
environments"""

import random
import sys
import time
import thread
import unittest

sys.path.insert(0, '../lib')

from ClusterShell.Task import *
from ClusterShell.Event import EventHandler


class TaskThreadJoinTest(unittest.TestCase):

    def tearDown(self):
        task_cleanup()

    def testThreadTaskWaitWhenRunning(self):
        """test task_wait() when workers are running"""

        for i in range(1, 5):
            task = Task()
            task.shell("sleep %d" % i)
            task.resume()

        task_wait()


    def testThreadTaskWaitWhenSomeFinished(self):
        """test task_wait() when some workers finished"""

        for i in range(1, 5):
            task = Task()
            task.shell("sleep %d" % i)
            task.resume()

        time.sleep(2)
        task_wait()


    def testThreadTaskWaitWhenAllFinished(self):
        """test task_wait() when some workers finished"""

        for i in range(1, 3):
            task = Task()
            task.shell("sleep %d" % i)
            task.resume()

        time.sleep(4)
        task_wait()

    def _thread_delayed_unsuspend_func(self, task):
        """thread used to unsuspend task during task_wait()"""
        time_th = int(random.random()*6+5)
        #print "TIME unsuspend thread=%d" % time_th
        time.sleep(time_th)
        self.resumed = True
        task.resume()

    def testThreadTaskWaitWithSuspend(self):
        """test task_wait() with suspended tasks"""
        task = Task()
        self.resumed = False
        thread.start_new_thread(TaskThreadJoinTest._thread_delayed_unsuspend_func, (self, task))
        time_sh = int(random.random()*4)
        #print "TIME shell=%d" % time_sh
        task.shell("sleep %d" % time_sh)
        task.resume()
        time.sleep(1)
        suspended = task.suspend()

        for i in range(1, 4):
            task = Task()
            task.shell("sleep %d" % i)
            task.resume()

        time.sleep(1)
        task_wait()
        self.assert_(self.resumed or suspended == False)

    def testThreadSimpleTaskSupervisor(self):
        """test task methods from another thread"""
        #print "PASS 1"
        task = Task()
        task.shell("sleep 3")
        task.shell("echo testing", key=1)
        task.resume()
        task.join()
        self.assertEqual(task.key_buffer(1), "testing")
        #print "PASS 2"
        task.shell("echo ok", key=2)
        task.resume()
        task.join()
        #print "PASS 3"
        self.assertEqual(task.key_buffer(2), "ok")
        task.shell("sleep 1 && echo done", key=3)
        task.resume()
        task.join()
        #print "PASS 4"
        self.assertEqual(task.key_buffer(3), "done")
        task.abort()


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TaskThreadJoinTest)
    unittest.TextTestRunner(verbosity=2).run(suite)

