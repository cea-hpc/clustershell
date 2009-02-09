#!/usr/bin/env python
# ClusterShell (local) test suite
# Written by S. Thiell 2008-04-09
# $Id$


"""Unit test for ClusterShell Task (local)"""

import copy
import sys
import unittest

sys.path.insert(0, '../lib')

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

    def testLocalSingleLineBuffers(self):
        """test task local single line buffers gathering"""
        task = task_self()
        self.assert_(task != None)

        task.shell("/bin/echo foo", key="foo")
        task.shell("/bin/echo bar", key="bar")
        task.shell("/bin/echo bar", key="bar2")
        task.shell("/bin/echo foobar", key="foobar")
        task.shell("/bin/echo foobar", key="foobar2")
        task.shell("/bin/echo foobar", key="foobar3")

        task.resume()

        self.assert_(task.key_buffer("foobar") == "foobar\n")

        cnt = 3
        for buf, keys in task.iter_buffers():
            cnt -= 1
            if buf == "foo":
                self.assertEqual(len(keys), 1)
                self.assert_(keys[0] == "foo")
            elif buf == "bar":
                self.assertEqual(len(keys), 2)
                self.assert_(keys[0] == "bar")
            elif buf == "foobar":
                self.assertEqual(len(keys), 3)
                self.assert_(keys[0] == "foobar")

        self.assertEqual(cnt, 0)

    def testLocalBuffers(self):
        """test task local multi-lines buffers gathering"""
        task = task_self()
        self.assert_(task != None)

        task.shell("/usr/bin/printf 'foo\nbar\n'", key="foobar")
        task.shell("/usr/bin/printf 'foo\nbar\n'", key="foobar2")
        task.shell("/usr/bin/printf 'foo\nbar\n'", key="foobar3")
        task.shell("/usr/bin/printf 'foo\nfuu\n'", key="foofuu")
        task.shell("/usr/bin/printf 'faa\nber\n'", key="faaber")
        task.shell("/usr/bin/printf 'foo\nfuu\n'", key="foofuu2")

        task.resume()

        cnt = 3
        for buf, keys in task.iter_buffers():
            cnt -= 1
            if buf == "faa\nber\n":
                self.assertEqual(len(keys), 1)
                self.assert_(keys[0].startswith("faaber"))
            elif buf == "foo\nfuu\n":
                self.assertEqual(len(keys), 2)
                self.assert_(keys[0].startswith("foofuu"))
            elif buf == "foo\nbar\n":
                self.assertEqual(len(keys), 3)
                self.assert_(keys[0].startswith("foobar"))

        self.assertEqual(cnt, 0)

    def testLocalRetcodes(self):
        """test task with local return codes"""
        task = task_self()
        self.assert_(task != None)

        # 0 ['worker0']
        # 1 ['worker1']
        # 2 ['worker2']
        # 3 ['worker3bis', 'worker3']
        # 4 ['worker4']
        # 5 ['worker5bis', 'worker5']

        task.shell("/bin/true", key="worker0")
        task.shell("/bin/false", key="worker1")
        task.shell("/bin/sh -c 'exit 1'", key="worker1bis")
        task.shell("/bin/sh -c 'exit 2'", key="worker2")
        task.shell("/bin/sh -c 'exit 3'", key="worker3")
        task.shell("/bin/sh -c 'exit 3'", key="worker3bis")
        task.shell("/bin/sh -c 'exit 4'", key="worker4")
        task.shell("/bin/sh -c 'exit 5'", key="worker5")
        task.shell("/bin/sh -c 'exit 5'", key="worker5bis")

        task.resume()

        self.assert_(task.key_retcode("worker4") == 4)

        cnt = 6
        for rc, keys in task.iter_retcodes():
            cnt -= 1
            if rc == 0:
                self.assertEqual(len(keys), 1)
                self.assert_(keys[0] == "worker0" )
            elif rc == 1:
                self.assertEqual(len(keys), 2)
                self.assert_(keys[0] == "worker1" or keys[0] == "worker1bis")
            elif rc == 2:
                self.assertEqual(len(keys), 1)
                self.assert_(keys[0] == "worker2" )
            elif rc == 3:
                self.assertEqual(len(keys), 2)
                self.assert_(keys[0] == "worker3" or keys[0] == "worker3bis")
            elif rc == 4:
                self.assertEqual(len(keys), 1)
                self.assert_(keys[0] == "worker4" )
            elif rc == 5:
                self.assertEqual(len(keys), 2)
                self.assert_(keys[0] == "worker5" or keys[0] == "worker5bis")

        self.assertEqual(cnt, 0)

        # test max retcode API
        self.assertEqual(task.max_retcode(), 5)

    

if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TaskLocalTest)
    unittest.TextTestRunner(verbosity=2).run(suite)

