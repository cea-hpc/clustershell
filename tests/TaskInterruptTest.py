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
from ClusterShell.Event import EventHandler

import socket

import time
import thread


class IEH(EventHandler):
    def ev_read(self, worker):
        m = worker.last_read()
        task = worker.task()

        print task.workers()
        task.workers().pop()
        print task.workers()

        if m == "abort":
            task.abort()
        elif m == "wabort":
            worker.abort()




class TaskInterruptTest(unittest.TestCase):

    def testSimpleCommand(self):
        """test simple command"""
        task = task_self()
        self.assert_(task != None)
        
        task.set_info("debug", True)

        print "worker #1"
        # init worker
        worker = task.shell("./signal_handler.py")
        self.assert_(worker != None)

        try:
            # run task
            task.resume()
        except KeyboardInterrupt, e:
            print "KeyboardInterrupt", e

        print "worker #2"
        # init worker
        worker = task.shell("/bin/sleep 10", timeout=8)
        self.assert_(worker != None)

        task.file(sys.stdin, handler=IEH())

        try:
            # run task
            task.resume()
        except KeyboardInterrupt, e:
            print "KeyboardInterrupt", e


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TaskInterruptTest)
    unittest.TextTestRunner(verbosity=2).run(suite)

