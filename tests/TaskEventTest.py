#!/usr/bin/env python
# ClusterShell (local) test suite
# Written by S. Thiell 2008-04-09
# $Id$


"""Unit test for ClusterShell Task (event-based mode)"""

import copy
import sys
import unittest

sys.path.append('../lib')

import ClusterShell

from ClusterShell.NodeSet import NodeSet
from ClusterShell.Task import *
from ClusterShell.Event import EventHandler

import socket
import thread


class TestHandler(EventHandler):

    def __init__(self):
        EventHandler.__init__(self)

    def ev_start(self, worker):
        pass

    def ev_read(self, worker):
        r = worker.last_read()

    def ev_close(self, worker):
        r = worker.read()


class TaskEventTest(unittest.TestCase):

    def testSimpleEventHandler(self):
        """test simple event handler"""
        task = task_self()
        self.assert_(task != None)

        # init worker
        worker = task.shell("/bin/hostname", handler=TestHandler())
        self.assert_(worker != None)
        # run task
        task.resume()



if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TaskEventTest)
    unittest.TextTestRunner(verbosity=2).run(suite)

