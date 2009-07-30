#!/usr/bin/env python
# ClusterShell (distant) test suite
# Written by S. Thiell 2009-02-13
# $Id$


"""Unit test for ClusterShell Task (distant)"""

import copy
import sys
import unittest

sys.path.insert(0, '../lib')

from ClusterShell.Event import EventHandler
from ClusterShell.NodeSet import NodeSet
from ClusterShell.Task import *
from ClusterShell.Worker.Pdsh import WorkerPdsh
from ClusterShell.Worker.Ssh import WorkerSsh
from ClusterShell.Worker.EngineClient import *

import socket

# TEventHandlerChecker 'received event' flags
EV_START=0x01
EV_READ=0x02
EV_WRITTEN=0x04
EV_HUP=0x08
EV_TIMEOUT=0x10
EV_CLOSE=0x20

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

    class TEventHandlerChecker(EventHandler):

        """simple event trigger validator"""
        def __init__(self, test):
            self.test = test
            self.flags = 0
            self.read_count = 0
            self.written_count = 0
        def ev_start(self, worker):
            self.test.assertEqual(self.flags, 0)
            self.flags |= EV_START
        def ev_read(self, worker):
            self.test.assertEqual(self.flags, EV_START)
            self.flags |= EV_READ
        def ev_written(self, worker):
            self.test.assert_(self.flags & EV_START)
            self.flags |= EV_WRITTEN
        def ev_hup(self, worker):
            self.test.assert_(self.flags & EV_START)
            self.flags |= EV_HUP
        def ev_timeout(self, worker):
            self.test.assert_(self.flags & EV_START)
            self.flags |= EV_TIMEOUT
        def ev_close(self, worker):
            self.test.assert_(self.flags & EV_START)
            self.test.assert_(self.flags & EV_CLOSE == 0)
            self.flags |= EV_CLOSE

    def testShellEvents(self):
        """test triggered events"""
        task = task_self()
        self.assert_(task != None)
        # init worker
        test_eh = self.__class__.TEventHandlerChecker(self)
        worker = task.shell("/bin/hostname", nodes='localhost', handler=test_eh)
        self.assert_(worker != None)
        # run task
        task.resume()
        # test events received: start, read, hup, close
        self.assertEqual(test_eh.flags, EV_START | EV_READ | EV_HUP | EV_CLOSE)
    
    def testShellEventsWithTimeout(self):
        """test triggered events (with timeout)"""
        task = task_self()
        self.assert_(task != None)
        # init worker
        test_eh = self.__class__.TEventHandlerChecker(self)
        worker = task.shell("/bin/echo alright && /bin/sleep 10", nodes='localhost', handler=test_eh,
                timeout=2)
        self.assert_(worker != None)
        # run task
        task.resume()
        # test events received: start, read, timeout, close
        self.assertEqual(test_eh.flags, EV_START | EV_READ | EV_TIMEOUT | EV_CLOSE)
        self.assertEqual(worker.node_buffer("localhost"), "alright")
        self.assertEqual(worker.num_timeout(), 1)
        self.assertEqual(task.num_timeout(), 1)
        count = 0
        for node in task.iter_keys_timeout():
            count += 1
            self.assertEqual(node, "localhost")
        self.assertEqual(count, 1)
        count = 0
        for node in worker.iter_keys_timeout():
            count += 1
            self.assertEqual(node, "localhost")
        self.assertEqual(count, 1)

    def testShellEventsWithTimeout(self):
        """test triggered events (with timeout) (more)"""
        task = task_self()
        self.assert_(task != None)
        # init worker
        test_eh1 = self.__class__.TEventHandlerChecker(self)
        worker1 = task.shell("/bin/echo alright && /bin/sleep 10", nodes='localhost', handler=test_eh1,
                timeout=2)
        self.assert_(worker1 != None)
        test_eh2 = self.__class__.TEventHandlerChecker(self)
        worker2 = task.shell("/bin/echo okay && /bin/sleep 10", nodes='localhost', handler=test_eh2,
                timeout=3)
        self.assert_(worker2 != None)
        # run task
        task.resume()
        # test events received: start, read, timeout, close
        self.assertEqual(test_eh1.flags, EV_START | EV_READ | EV_TIMEOUT | EV_CLOSE)
        self.assertEqual(test_eh2.flags, EV_START | EV_READ | EV_TIMEOUT | EV_CLOSE)
        self.assertEqual(worker1.node_buffer("localhost"), "alright")
        self.assertEqual(worker2.node_buffer("localhost"), "okay")
        self.assertEqual(worker1.num_timeout(), 1)
        self.assertEqual(worker2.num_timeout(), 1)
        self.assertEqual(task.num_timeout(), 2)

    def testShellEventsNoReadNoTimeout(self):
        """test triggered events (no read, no timeout)"""
        task = task_self()
        self.assert_(task != None)
        # init worker
        test_eh = self.__class__.TEventHandlerChecker(self)
        worker = task.shell("/bin/sleep 2", nodes='localhost', handler=test_eh)
        self.assert_(worker != None)
        # run task
        task.resume()
        # test events received: start, close
        self.assertEqual(test_eh.flags, EV_START | EV_HUP | EV_CLOSE)
        self.assertEqual(worker.node_buffer("localhost"), "")

    def testExplicitWorkerPdshShellEvents(self):
        """test triggered events with explicit pdsh worker"""
        task = task_self()
        self.assert_(task != None)
        # init worker
        test_eh = self.__class__.TEventHandlerChecker(self)
        worker = WorkerPdsh("localhost", command="/bin/hostname", handler=test_eh, timeout=None)
        self.assert_(worker != None)
        task.schedule(worker)
        # run task
        task.resume()
        # test events received: start, read, hup, close
        self.assertEqual(test_eh.flags, EV_START | EV_READ | EV_HUP | EV_CLOSE)
    
    def testExplicitWorkerPdshShellEventsWithTimeout(self):
        """test triggered events (with timeout) with explicit pdsh worker"""
        task = task_self()
        self.assert_(task != None)
        # init worker
        test_eh = self.__class__.TEventHandlerChecker(self)
        worker = WorkerPdsh("localhost", command="/bin/echo alright && /bin/sleep 10",
                handler=test_eh, timeout=2)
        self.assert_(worker != None)
        task.schedule(worker)
        # run task
        task.resume()
        # test events received: start, read, timeout, close
        self.assertEqual(test_eh.flags, EV_START | EV_READ | EV_TIMEOUT | EV_CLOSE)
        self.assertEqual(worker.node_buffer("localhost"), "alright")

    def testShellEventsNoReadNoTimeout(self):
        """test triggered events (no read, no timeout) with explicit pdsh worker"""
        task = task_self()
        self.assert_(task != None)
        # init worker
        test_eh = self.__class__.TEventHandlerChecker(self)
        worker = WorkerPdsh("localhost", command="/bin/sleep 2",
                handler=test_eh, timeout=None)
        self.assert_(worker != None)
        task.schedule(worker)
        # run task
        task.resume()
        # test events received: start, close
        self.assertEqual(test_eh.flags, EV_START | EV_HUP | EV_CLOSE)
        self.assertEqual(worker.node_buffer("localhost"), None)

    def testLocalhostCommandFanout(self):
        """test fanout with localhost commands"""
        task = task_self()
        self.assert_(task != None)
        task.set_info("fanout", 2)
        # init worker
        for i in range(0, 10):
            worker = task.shell("/bin/echo %d" % i, nodes='localhost')
            self.assert_(worker != None)
        # run task
        task.resume()
    
    def testEscape(self):
        """test distant worker (ssh) cmd with escaped variable"""
        task = task_self()
        self.assert_(task != None)
        worker = task.shell("export CSTEST=foobar; /bin/echo \$CSTEST | sed 's/\ foo/bar/'", nodes="localhost")
        # execute
        task.resume()
        # read result
        self.assertEqual(worker.node_buffer("localhost"), "$CSTEST")

    def testEscape2(self):
        """test distant worker (ssh) cmd with non-escaped variable"""
        task = task_self()
        self.assert_(task != None)
        worker = task.shell("export CSTEST=foobar; /bin/echo $CSTEST | sed 's/\ foo/bar/'", nodes="localhost")
        # execute
        task.resume()
        # read result
        self.assertEqual(worker.node_buffer("localhost"), "foobar")

    def testEscapePdsh(self):
        """test distant worker (pdsh) cmd with escaped variable"""
        task = task_self()
        self.assert_(task != None)
        worker = WorkerPdsh("localhost", command="export CSTEST=foobar; /bin/echo \$CSTEST | sed 's/\ foo/bar/'",
                handler=None, timeout=None)
        self.assert_(worker != None)
        #task.set_info("debug", True)
        task.schedule(worker)
        # execute
        task.resume()
        # read result
        self.assertEqual(worker.node_buffer("localhost"), "$CSTEST")

    def testEscapePdsh2(self):
        """test distant worker (pdsh) cmd with non-escaped variable"""
        task = task_self()
        self.assert_(task != None)
        worker = WorkerPdsh("localhost", command="export CSTEST=foobar; /bin/echo $CSTEST | sed 's/\ foo/bar/'",
                handler=None, timeout=None)
        task.schedule(worker)
        # execute
        task.resume()
        # read result
        self.assertEqual(worker.node_buffer("localhost"), "foobar")

    def testWorkerBuffers(self):
        """test buffers at worker level"""
        task = task_self()
        self.assert_(task != None)

        worker = task.shell("/usr/bin/printf 'foo\nbar\nxxx\n'", nodes='localhost')
        task.resume()

        cnt = 1
        for buf, nodes in worker.iter_buffers():
            cnt -= 1
            if buf == "foo\nbar\nxxx\n":
                self.assertEqual(len(keys), 1)
                self.assertEqual(str(nodes), "localhost")

        self.assertEqual(cnt, 0)


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TaskDistantTest)
    unittest.TextTestRunner(verbosity=2).run(suite)

