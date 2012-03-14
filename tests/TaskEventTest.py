#!/usr/bin/env python
# ClusterShell (local) test suite
# Written by S. Thiell 2008-04-09


"""Unit test for ClusterShell Task (event-based mode)"""

import copy
import sys
import unittest

sys.path.insert(0, '../lib')

import ClusterShell

from ClusterShell.NodeSet import NodeSet
from ClusterShell.Task import *
from ClusterShell.Event import EventHandler

import socket
import thread


class TestHandler(EventHandler):

    def __init__(self):
        self.reset_asserts()

    def do_asserts_read_notimeout(self):
        assert self.did_start, "ev_start not called"
        assert self.did_read, "ev_read not called"
        assert not self.did_readerr, "ev_error called"
        assert self.did_close, "ev_close not called"
        assert not self.did_timeout, "ev_timeout called"

    def do_asserts_timeout(self):
        assert self.did_start, "ev_start not called"
        assert not self.did_read, "ev_read called"
        assert not self.did_readerr, "ev_error called"
        assert self.did_close, "ev_close not called"
        assert self.did_timeout, "ev_timeout not called"

    def reset_asserts(self):
        self.did_start = False
        self.did_open = False
        self.did_read = False
        self.did_readerr = False
        self.did_close = False
        self.did_timeout = False

    def ev_start(self, worker):
        self.did_start = True

    def ev_read(self, worker):
        self.did_read = True
        assert worker.last_read() == "abcdefghijklmnopqrstuvwxyz"
        assert worker.last_error() != "abcdefghijklmnopqrstuvwxyz"

    def ev_error(self, worker):
        self.did_readerr = True
        assert worker.last_error() == "errerrerrerrerrerrerrerr"
        assert worker.last_read() != "errerrerrerrerrerrerrerr"

    def ev_close(self, worker):
        self.did_close = True
        if worker.read():
            assert worker.read().startswith("abcdefghijklmnopqrstuvwxyz")

    def ev_timeout(self, worker):
        self.did_timeout = True

class AbortOnReadHandler(EventHandler):
    def ev_read(self, worker):
        worker.abort()

class TaskEventTest(unittest.TestCase):

    def testSimpleEventHandler(self):
        """test simple event handler"""
        task = task_self()
        self.assert_(task != None)
        eh = TestHandler()
        # init worker
        worker = task.shell("./test_command.py --test=cmp_out", handler=eh)
        self.assert_(worker != None)
        # run task
        task.resume()
        eh.do_asserts_read_notimeout()
        eh.reset_asserts()
        # re-test
        # init worker
        worker = task.shell("./test_command.py --test=cmp_out", handler=eh)
        self.assert_(worker != None)
        # run task
        task.resume()
        eh.do_asserts_read_notimeout()
        eh.reset_asserts()

    def testSimpleEventHandlerWithTaskTimeout(self):
        """test simple event handler with timeout"""
        task = task_self()
        self.assert_(task != None)

        eh = TestHandler()
        # init worker
        worker = task.shell("/bin/sleep 3", handler=eh)
        self.assert_(worker != None)

        try:
            task.resume(2)
        except TimeoutError:
            pass
        else:
            self.fail("did not detect timeout")

        eh.do_asserts_timeout()
       
    class TInFlyAdder(EventHandler):
        def ev_read(self, worker):
            assert worker.task.running()
            # in-fly workers addition
            other1 = worker.task.shell("/bin/sleep 1")
            assert other1 != None
            other2 = worker.task.shell("/bin/sleep 1")
            assert other2 != None

    def testEngineInFlyAdd(self):
        """test client add while running (in-fly add)"""
        task = task_self()
        self.assert_(task != None)
        eh = self.__class__.TInFlyAdder()
        worker = task.shell("/bin/uname", handler=eh)
        self.assert_(worker != None)
        task.resume()

    class TWriteOnStart(EventHandler):
        def ev_start(self, worker):
            assert worker.task.running()
            worker.write("foo bar\n")
        def ev_read(self, worker):
            assert worker.current_msg == "foo bar"
            worker.abort()

    def testWriteOnStartEvent(self):
        """test write on ev_start"""
        task = task_self()
        self.assert_(task != None)
        task.shell("cat", handler=self.__class__.TWriteOnStart())
        task.resume()
        
    def testEngineMayReuseFD(self):
        """test write + worker.abort() on read to reuse FDs"""
        task = task_self()
        fanout = task.info("fanout")
        try:
            task.set_info("fanout", 1)
            eh = AbortOnReadHandler()
            for i in range(10):
                worker = task.shell("echo ok; sleep 1", handler=eh)
                worker.write("OK\n")
                self.assert_(worker is not None)
            task.resume()
        finally:
            task.set_info("fanout", fanout)


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TaskEventTest)
    unittest.TextTestRunner(verbosity=2).run(suite)

