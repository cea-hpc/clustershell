#!/usr/bin/env python
# ClusterShell (distant) test suite
# Written by S. Thiell 2009-02-13
# $Id$


"""Unit test for ClusterShell Task (distant)"""

import copy
import sys
import unittest

sys.path.insert(0, '../lib')

from ClusterShell.NodeSet import NodeSet
from ClusterShell.Task import *
from ClusterShell.Worker.Pdsh import WorkerPdsh
from ClusterShell.Worker.Ssh import WorkerSsh
from ClusterShell.Worker.EngineClient import *

import socket


class TaskDistantTest(unittest.TestCase):

    def testLocalhostCommand(self):
        """test simple localhost command"""
        task = task_self()
        self.assert_(task != None)
        # init worker
        worker = task.shell("/bin/hostname", nodes='localhost')
        self.assert_(worker != None)
        # run task
        task.resume()
    
    def testLocalhostCommand2(self):
        """test two simple localhost commands"""
        task = task_self()
        self.assert_(task != None)
        # init worker
        worker = task.shell("/bin/hostname", nodes='localhost')
        self.assert_(worker != None)

        worker = task.shell("/bin/uname -r", nodes='localhost')
        self.assert_(worker != None)
        # run task
        task.resume()
    
    def testLocalhostCopy(self):
        """test simple localhost copy"""
        task = task_self()
        self.assert_(task != None)
        # init worker
        worker = task.copy("/etc/hosts",
                "/tmp/cs-test_testLocalhostCopy", nodes='localhost')
        self.assert_(worker != None)
        # run task
        task.resume()

    def testLocalhostExplicitSshCopy(self):
        """test simple localhost copy with explicit ssh worker"""
        task = task_self()
        self.assert_(task != None)
        # init worker
        worker = WorkerSsh("localhost", source="/etc/hosts",
                dest="/tmp/cs-test_testLocalhostExplicitSshCopy",
                handler=None, timeout=10)
        task.schedule(worker) 
        task.resume()

    def testLocalhostExplicitPdshCopy(self):
        """test simple localhost copy with explicit pdsh worker"""
        task = task_self()
        self.assert_(task != None)
        # init worker
        worker = WorkerPdsh("localhost", source="/etc/hosts",
                dest="/tmp/cs-test_testLocalhostExplicitPdshCopy",
                handler=None, timeout=10)
        task.schedule(worker) 
        task.resume()

    def testExplicitSshWorker(self):
        """test simple localhost command with explicit ssh worker"""
        task = task_self()
        self.assert_(task != None)
        # init worker
        worker = WorkerSsh("localhost", command="/bin/echo alright", handler=None, timeout=5)
        self.assert_(worker != None)
        task.schedule(worker)
        # run task
        task.resume()
        # test output
        self.assertEqual(worker.node_buffer("localhost"), "alright")

    def testExplicitPdshWorker(self):
        """test simple localhost command with explicit pdsh worker"""
        task = task_self()
        self.assert_(task != None)
        # init worker
        worker = WorkerPdsh("localhost", command="/bin/echo alright", handler=None, timeout=5)
        self.assert_(worker != None)
        task.schedule(worker)
        # run task
        task.resume()
        # test output
        self.assertEqual(worker.node_buffer("localhost"), "alright")

    def testPdshWorkerWriteNotSupported(self):
        """test that write is reported as not supported with pdsh"""
        task = task_self()
        self.assert_(task != None)
        # init worker
        worker = WorkerPdsh("localhost", command="/bin/uname -r", handler=None, timeout=5)
        self.assertRaises(EngineClientNotSupportedError, worker.write, "toto")


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TaskDistantTest)
    unittest.TextTestRunner(verbosity=2).run(suite)

