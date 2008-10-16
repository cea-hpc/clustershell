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


did_start = False
did_open = False
did_read = False
did_close = False

did_start2 = False
did_open2 = False
did_read2 = False
did_close2 = False

class TestHandler(EventHandler):

    def __init__(self):
        EventHandler.__init__(self)

    def ev_start(self, worker):
        did_start = True

    def ev_open(self, worker):
        did_open = True

    def ev_read(self, worker):
        did_read = True
        assert worker.last_read() == "abcdefghijklmnopqrstuvwxyz"

    def ev_close(self, worker):
        did_close = True
        assert worker.read().startswith("abcdefghijklmnopqrstuvwxyz")


class TestHandler2(EventHandler):

    def __init__(self):
        EventHandler.__init__(self)

    def ev_start(self, worker):
        did_start2 = True

    def ev_open(self, worker):
        did_open2 = True

    def ev_read(self, worker):
        did_read2 = True
        r = worker.last_read()

    def ev_close(self, worker):
        did_close2 = True
        r = worker.read()


class TaskEventTest(unittest.TestCase):

    def testSimpleEventHandler(self):
        """test simple event handler"""
        task = task_self()
        self.assert_(task != None)

        # init worker
        worker = task.shell("./test_command.py --test=cmp_out", handler=TestHandler())
        self.assert_(worker != None)
        # run task
        task.resume()

        self.assert_(not did_start, "ev_start not called")
        self.assert_(not did_open, "ev_open not called")
        self.assert_(not did_read, "ev_read not called")
        self.assert_(not did_close, "ev_close not called")


    def testSimpleEventHandlerWithTimeout(self):
        """test simple event handler with timeout"""
        task = task_self()
        self.assert_(task != None)

        # init worker
        worker = task.shell("/bin/sleep 3", handler=TestHandler2())
        self.assert_(worker != None)

        try:
            task.resume(1)
        except TimeoutError:
            pass
        else:
            self.fail("did detect timeout")

        self.assert_(not did_start2, "ev_start not called")
        self.assert_(not did_open2, "ev_open not called")
        self.assert_(not did_read2, "ev_read not called")
        self.assert_(not did_close2, "ev_close not called")
       


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TaskEventTest)
    unittest.TextTestRunner(verbosity=2).run(suite)

