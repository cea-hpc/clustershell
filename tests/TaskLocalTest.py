#!/usr/bin/env python
# ClusterShell (local) test suite
# Written by S. Thiell 2008-04-09
# $Id$


"""Unit test for ClusterShell Task (local)"""

import copy
import sys
import unittest

sys.path.append('../lib')

import ClusterShell

from ClusterShell.NodeSet import NodeSet
from ClusterShell.Task import *

import socket

import thread


class TaskLocalTest(unittest.TestCase):

    def testSimpleCommand(self):
        """test simple command"""
        task = task_self()
        self.assert_(task != None)
        # init worker
        worker = task.shell("/bin/hostname")
        self.assert_(worker != None)
        # run task
        task.resume()

    def testSimpleDualTask(self):
        """test simple task doing 2 sequential jobs"""

        task0 = task_self()
        self.assert_(task0 != None)
        worker1 = task0.shell("/bin/hostname")
        worker2 = task0.shell("/bin/uname -a")
        task0.resume()
        b1 = copy.copy(worker1.read())
        b2 = copy.copy(worker2.read())
        task1 = task_self()
        self.assert_(task1 is task0)
        worker1 = task1.shell("/bin/hostname")
        self.assert_(worker1 != None)
        worker2 = task1.shell("/bin/uname -a")
        self.assert_(worker2 != None)
        task1.resume()
        self.assert_(worker2.read() == b2)
        self.assert_(worker1.read() == b1)

    def testSimpleCommandNoneArgs(self):
        """test simple command with args=None"""
        task = task_self()
        self.assert_(task != None)
        # init worker
        worker = task.shell("/bin/hostname", nodes=None, handler=None)
        self.assert_(worker != None)
        # run task
        task.resume()

    def testSimpleMultipleCommands(self):
        """test and verify results of 100 commands"""
        task = task_self()
        self.assert_(task != None)
        # run commands
        workers = []
        for i in range(0, 100):
            workers.append(task.shell("/bin/hostname"))
        task.resume()
        # verify results
        hn = socket.gethostname()
        for i in range(0, 100):
            t_hn = workers[i].read().splitlines()[0]
            self.assertEqual(t_hn, hn)

    def testHugeOutputCommand(self):
        """test huge output command"""
        task = task_self()
        self.assert_(task != None)

        # init worker
        worker = task.shell("python test_command.py --test huge --rc 0")
        self.assert_(worker != None)

        # run task
        task.resume()
        self.assertEqual(worker.retcode(), 0)
        self.assertEqual(len(worker.read()), 700000)

    # task configuration
    def testTaskInfo(self):
        """test task info"""
        task = task_self()
        self.assert_(task != None)

        fanout = task.info("fanout")
        self.assertEqual(fanout, Task._default_info["fanout"])

    def testSimpleCommandTimeout(self):
        """test simple command timeout"""
        task = task_self()
        self.assert_(task != None)

        # init worker
        worker = task.shell("/bin/sleep 30")
        self.assert_(worker != None)

        try:
            # run task
            task.resume(3)
        except TimeoutError:
            pass
        else:
            self.fail("did not detect timeout")

    def testSimpleCommandNoTimeout(self):
        """test simple command exiting before timeout"""
        task = task_self()
        self.assert_(task != None)

        # init worker
        worker = task.shell("/bin/sleep 3")
        self.assert_(worker != None)

        try:
            # run task
            task.resume(5)
        except TimeoutError:
            self.fail("did detect timeout")

    def testSimpleCommandNoTimeout(self):
        """test simple command exiting just before timeout"""
        task = task_self()
        self.assert_(task != None)

        # init worker
        worker = task.shell("/bin/usleep 900000")
        self.assert_(worker != None)

        try:
            # run task
            task.resume(1)
        except TimeoutError:
            self.fail("did detect timeout")

    def testWorkersTimeout(self):
        """test workers with timeout"""
        task = task_self()
        self.assert_(task != None)

        # init worker
        worker = task.shell("/bin/sleep 6", timeout=3)
        self.assert_(worker != None)

        worker = task.shell("/bin/sleep 6", timeout=2)
        self.assert_(worker != None)

        try:
            # run task
            task.resume()
        except TimeoutError:
            self.fail("did detect timeout")

    def testWorkersTimeout2(self):
        """test workers with timeout (more)"""
        task = task_self()
        self.assert_(task != None)

        worker = task.shell("/bin/sleep 10", timeout=5)
        self.assert_(worker != None)

        worker = task.shell("/bin/sleep 10", timeout=3)
        self.assert_(worker != None)

        try:
            # run task
            task.resume()
        except TimeoutError:
            self.fail("did detect task timeout")

    def testLocalRetcodes(self):
        """test local return codes"""
        task = task_self()
        self.assert_(task != None)

        task.shell("/bin/false")
        task.shell("/bin/sh -c 'exit 2'")
        task.shell("/bin/sh -c 'exit 3'")
        task.shell("/bin/sh -c 'exit 4'")

        task.resume()

        for m, nodeset in task.iter_buffers():
            print m, nodeset

        for nodeset, rc in task.iter_retcodes():
            print nodeset, rc



if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TaskLocalTest)
    unittest.TextTestRunner(verbosity=2).run(suite)

