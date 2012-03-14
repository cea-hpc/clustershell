#!/usr/bin/env python
# ClusterShell (distant, pdsh worker) test suite
# Written by S. Thiell 2009-02-13


"""Unit test for ClusterShell Task (distant, pdsh worker)"""

import copy
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, '../lib')

from ClusterShell.Event import EventHandler
from ClusterShell.NodeSet import NodeSet
from ClusterShell.Task import *
from ClusterShell.Worker.Worker import WorkerBadArgumentError
from ClusterShell.Worker.Pdsh import WorkerPdsh
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

    def setUp(self):
        self._task = task_self()
        self.assert_(self._task != None)

    def testWorkerPdshGetCommand(self):
        """test worker.command with WorkerPdsh"""

        worker1 = WorkerPdsh("localhost", command="/bin/echo foo bar fuu",
                             handler=None, timeout=5)
        self.assert_(worker1 != None)
        self._task.schedule(worker1)
        worker2 = WorkerPdsh("localhost", command="/bin/echo blah blah foo",
                             handler=None, timeout=5)
        self.assert_(worker2 != None)
        self._task.schedule(worker2)
        # run task
        self._task.resume()
        # test output
        self.assertEqual(worker1.node_buffer("localhost"), "foo bar fuu")
        self.assertEqual(worker1.command, "/bin/echo foo bar fuu")
        self.assertEqual(worker2.node_buffer("localhost"), "blah blah foo")
        self.assertEqual(worker2.command, "/bin/echo blah blah foo")
    
    def testLocalhostExplicitPdshCopy(self):
        """test simple localhost copy with explicit pdsh worker"""
        dest = "/tmp/cs-test_testLocalhostExplicitPdshCopy"
        worker = WorkerPdsh("localhost", source="/etc/hosts",
                dest=dest, handler=None, timeout=10)
        self._task.schedule(worker) 
        self._task.resume()
        self.assertEqual(worker.source, "/etc/hosts")
        self.assertEqual(worker.dest, dest)

    def testLocalhostExplicitPdshCopyDir(self):
        """test simple localhost copy dir with explicit pdsh worker"""
        dtmp_src = tempfile.mkdtemp("_cs-test_src")
        # pdcp worker doesn't create custom destination directory
        dtmp_dst = tempfile.mkdtemp( \
            "_cs-test_testLocalhostExplicitPdshCopyDir")
        try:
            os.mkdir(os.path.join(dtmp_src, "lev1_a"))
            os.mkdir(os.path.join(dtmp_src, "lev1_b"))
            os.mkdir(os.path.join(dtmp_src, "lev1_a", "lev2"))
            worker = WorkerPdsh("localhost", source=dtmp_src,
                    dest=dtmp_dst, handler=None, timeout=10)
            self._task.schedule(worker) 
            self._task.resume()
            self.assert_(os.path.exists(os.path.join(dtmp_dst, \
                os.path.basename(dtmp_src), "lev1_a", "lev2")))
        finally:
            shutil.rmtree(dtmp_dst, ignore_errors=True)
            shutil.rmtree(dtmp_src, ignore_errors=True)

    def testLocalhostExplicitPdshCopyDirPreserve(self):
        """test simple localhost preserve copy dir with explicit pdsh worker"""
        dtmp_src = tempfile.mkdtemp("_cs-test_src")
        # pdcp worker doesn't create custom destination directory
        dtmp_dst = tempfile.mkdtemp( \
            "_cs-test_testLocalhostExplicitPdshCopyDirPreserve")
        try:
            os.mkdir(os.path.join(dtmp_src, "lev1_a"))
            os.mkdir(os.path.join(dtmp_src, "lev1_b"))
            os.mkdir(os.path.join(dtmp_src, "lev1_a", "lev2"))
            worker = WorkerPdsh("localhost", source=dtmp_src,
                    dest=dtmp_dst, handler=None, timeout=10, preserve=True)
            self._task.schedule(worker) 
            self._task.resume()
            self.assert_(os.path.exists(os.path.join(dtmp_dst, \
                os.path.basename(dtmp_src), "lev1_a", "lev2")))
        finally:
            shutil.rmtree(dtmp_dst, ignore_errors=True)
            shutil.rmtree(dtmp_src, ignore_errors=True)

    def testExplicitPdshWorker(self):
        """test simple localhost command with explicit pdsh worker"""
        # init worker
        worker = WorkerPdsh("localhost", command="echo alright", handler=None, timeout=5)
        self.assert_(worker != None)
        self._task.schedule(worker)
        # run task
        self._task.resume()
        # test output
        self.assertEqual(worker.node_buffer("localhost"), "alright")

    def testExplicitPdshWorkerStdErr(self):
        """test simple localhost command with explicit pdsh worker (stderr)"""
        # init worker
        worker = WorkerPdsh("localhost", command="echo alright 1>&2",
                    handler=None, stderr=True, timeout=5)
        self.assert_(worker != None)
        self._task.schedule(worker)
        # run task
        self._task.resume()
        # test output
        self.assertEqual(worker.node_error_buffer("localhost"), "alright")

        # Re-test with stderr=False
        worker = WorkerPdsh("localhost", command="echo alright 1>&2",
                    handler=None, stderr=False, timeout=5)
        self.assert_(worker != None)
        self._task.schedule(worker)
        # run task
        self._task.resume()
        # test output
        self.assertEqual(worker.node_error_buffer("localhost"), None)


    def testPdshWorkerWriteNotSupported(self):
        """test that write is reported as not supported with pdsh"""
        # init worker
        worker = WorkerPdsh("localhost", command="uname -r", handler=None, timeout=5)
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
            self.last_node, self.last_read = worker.last_read()
        def ev_written(self, worker):
            self.test.assert_(self.flags & EV_START)
            self.flags |= EV_WRITTEN
        def ev_hup(self, worker):
            self.test.assert_(self.flags & EV_START)
            self.flags |= EV_HUP
            self.last_rc = worker.last_retcode()
        def ev_timeout(self, worker):
            self.test.assert_(self.flags & EV_START)
            self.flags |= EV_TIMEOUT
            self.last_node = worker.last_node()
        def ev_close(self, worker):
            self.test.assert_(self.flags & EV_START)
            self.test.assert_(self.flags & EV_CLOSE == 0)
            self.flags |= EV_CLOSE

    def testExplicitWorkerPdshShellEvents(self):
        """test triggered events with explicit pdsh worker"""
        # init worker
        test_eh = self.__class__.TEventHandlerChecker(self)
        worker = WorkerPdsh("localhost", command="hostname", handler=test_eh, timeout=None)
        self.assert_(worker != None)
        self._task.schedule(worker)
        # run task
        self._task.resume()
        # test events received: start, read, hup, close
        self.assertEqual(test_eh.flags, EV_START | EV_READ | EV_HUP | EV_CLOSE)
    
    def testExplicitWorkerPdshShellEventsWithTimeout(self):
        """test triggered events (with timeout) with explicit pdsh worker"""
        # init worker
        test_eh = self.__class__.TEventHandlerChecker(self)
        worker = WorkerPdsh("localhost", command="echo alright && sleep 10",
                handler=test_eh, timeout=2)
        self.assert_(worker != None)
        self._task.schedule(worker)
        # run task
        self._task.resume()
        # test events received: start, read, timeout, close
        self.assertEqual(test_eh.flags, EV_START | EV_READ | EV_TIMEOUT | EV_CLOSE)
        self.assertEqual(worker.node_buffer("localhost"), "alright")

    def testShellPdshEventsNoReadNoTimeout(self):
        """test triggered events (no read, no timeout) with explicit pdsh worker"""
        # init worker
        test_eh = self.__class__.TEventHandlerChecker(self)
        worker = WorkerPdsh("localhost", command="sleep 2",
                handler=test_eh, timeout=None)
        self.assert_(worker != None)
        self._task.schedule(worker)
        # run task
        self._task.resume()
        # test events received: start, close
        self.assertEqual(test_eh.flags, EV_START | EV_HUP | EV_CLOSE)
        self.assertEqual(worker.node_buffer("localhost"), None)

    def testWorkerPdshBuffers(self):
        """test buffers at pdsh worker level"""
        task = task_self()
        self.assert_(task != None)

        worker = WorkerPdsh("localhost", command="printf 'foo\nbar\nxxx\n'",
                            handler=None, timeout=None)
        task.schedule(worker)
        task.resume()

        cnt = 2
        for buf, nodes in worker.iter_buffers():
            cnt -= 1
            if buf == "foo\nbar\nxxx\n":
                self.assertEqual(len(nodes), 1)
                self.assertEqual(str(nodes), "localhost")
        self.assertEqual(cnt, 1)
        for buf, nodes in worker.iter_buffers("localhost"):
            cnt -= 1
            if buf == "foo\nbar\nxxx\n":
                self.assertEqual(len(nodes), 1)
                self.assertEqual(str(nodes), "localhost")
        self.assertEqual(cnt, 0)

    def testWorkerPdshNodeBuffers(self):
        """test iter_node_buffers on distant pdsh workers"""
        task = task_self()
        self.assert_(task != None)

        worker = WorkerPdsh("localhost", command="/usr/bin/printf 'foo\nbar\nxxx\n'",
                            handler=None, timeout=None)
        task.schedule(worker)
        task.resume()

        cnt = 1
        for node, buf in worker.iter_node_buffers():
            cnt -= 1
            if buf == "foo\nbar\nxxx\n":
                self.assertEqual(node, "localhost")
        self.assertEqual(cnt, 0)

    def testWorkerPdshNodeErrors(self):
        """test iter_node_errors on distant pdsh workers"""
        task = task_self()
        self.assert_(task != None)

        worker = WorkerPdsh("localhost", command="/usr/bin/printf 'foo\nbar\nxxx\n' 1>&2",
                            handler=None, timeout=None, stderr=True)
        task.schedule(worker)
        task.resume()

        cnt = 1
        for node, buf in worker.iter_node_errors():
            cnt -= 1
            if buf == "foo\nbar\nxxx\n":
                self.assertEqual(node, "localhost")
        self.assertEqual(cnt, 0)

    def testWorkerPdshRetcodes(self):
        """test retcodes on distant pdsh workers"""
        task = task_self()
        self.assert_(task != None)

        worker = WorkerPdsh("localhost", command="/bin/sh -c 'exit 3'",
                            handler=None, timeout=None)
        task.schedule(worker)
        task.resume()

        cnt = 2
        for rc, keys in worker.iter_retcodes():
            cnt -= 1
            self.assertEqual(rc, 3)
            self.assertEqual(len(keys), 1)
            self.assert_(keys[0] == "localhost")

        self.assertEqual(cnt, 1)

        for rc, keys in worker.iter_retcodes("localhost"):
            cnt -= 1
            self.assertEqual(rc, 3)
            self.assertEqual(len(keys), 1)
            self.assert_(keys[0] == "localhost")

        self.assertEqual(cnt, 0)

        # test node_retcode
        self.assertEqual(worker.node_retcode("localhost"), 3)   # 1.2.91+
        self.assertEqual(worker.node_rc("localhost"), 3)

        # test node_retcode failure
        self.assertRaises(KeyError, worker.node_retcode, "dummy")

        # test max retcode API
        self.assertEqual(task.max_retcode(), 3)

    def testWorkerNodeRetcodes(self):
        """test iter_node_retcodes on distant pdsh workers"""
        task = task_self()
        self.assert_(task != None)

        worker = WorkerPdsh("localhost", command="/bin/sh -c 'exit 3'",
                            handler=None, timeout=None)
        task.schedule(worker)
        task.resume()

        cnt = 1
        for node, rc in worker.iter_node_retcodes():
            cnt -= 1
            self.assertEqual(rc, 3)
            self.assertEqual(node, "localhost")

        self.assertEqual(cnt, 0)

    def testEscapePdsh(self):
        """test distant worker (pdsh) cmd with escaped variable"""
        worker = WorkerPdsh("localhost", command="export CSTEST=foobar; /bin/echo \$CSTEST | sed 's/\ foo/bar/'",
                handler=None, timeout=None)
        self.assert_(worker != None)
        #task.set_info("debug", True)
        self._task.schedule(worker)
        # execute
        self._task.resume()
        # read result
        self.assertEqual(worker.node_buffer("localhost"), "$CSTEST")

    def testEscapePdsh2(self):
        """test distant worker (pdsh) cmd with non-escaped variable"""
        worker = WorkerPdsh("localhost", command="export CSTEST=foobar; /bin/echo $CSTEST | sed 's/\ foo/bar/'",
                handler=None, timeout=None)
        self._task.schedule(worker)
        # execute
        self._task.resume()
        # read result
        self.assertEqual(worker.node_buffer("localhost"), "foobar")

    def testShellPdshStderrWithHandler(self):
        """test reading stderr of distant pdsh worker on event handler"""
        class StdErrHandler(EventHandler):
            def ev_error(self, worker):
                assert worker.last_error() == "something wrong"

        worker = WorkerPdsh("localhost", command="echo something wrong 1>&2",
                handler=StdErrHandler(), timeout=None)
        self._task.schedule(worker)
        self._task.resume()
        for buf, nodes in worker.iter_errors():
            self.assertEqual(buf, "something wrong")
        for buf, nodes in worker.iter_errors('localhost'):
            self.assertEqual(buf, "something wrong")

    def testCommandTimeoutOption(self):
        """test pdsh shell with command_timeout set"""
        command_timeout_orig = self._task.info("command_timeout")
        self._task.set_info("command_timeout", 1)
        worker = WorkerPdsh("localhost", command="sleep 10",
                handler=None, timeout=None)
        self._task.schedule(worker)
        self.assert_(worker != None)
        self._task.resume()
        # restore original command_timeout (0)
        self.assertEqual(command_timeout_orig, 0)
        self._task.set_info("command_timeout", command_timeout_orig)

    def testPdshBadArgumentOption(self):
        """test WorkerPdsh constructor bad argument"""
	# Check code < 1.4 compatibility
        self.assertRaises(WorkerBadArgumentError, WorkerPdsh, "localhost",
			  None, None)
	# As of 1.4, ValueError is raised for missing parameter
        self.assertRaises(ValueError, WorkerPdsh, "localhost",
			  None, None) # 1.4+

    def testCopyEvents(self):
        """test triggered events on WorkerPdsh copy"""
        test_eh = self.__class__.TEventHandlerChecker(self)
        dest = "/tmp/cs-test_testLocalhostPdshCopyEvents"
        worker = WorkerPdsh("localhost", source="/etc/hosts",
                dest=dest, handler=test_eh, timeout=10)
        self._task.schedule(worker) 
        self._task.resume()
        self.assertEqual(test_eh.flags, EV_START | EV_HUP | EV_CLOSE)

    def testWorkerAbort(self):
        """test WorkerPdsh abort() on timer"""
        task = task_self()
        self.assert_(task != None)

        class AbortOnTimer(EventHandler):
            def __init__(self, worker):
                EventHandler.__init__(self)
                self.ext_worker = worker
                self.testtimer = False
            def ev_timer(self, timer):
                self.ext_worker.abort()
                self.testtimer = True

        worker = WorkerPdsh("localhost", command="sleep 10",
                handler=None, timeout=None)
        task.schedule(worker)

        aot = AbortOnTimer(worker)
        self.assertEqual(aot.testtimer, False)
        task.timer(2.0, handler=aot)
        task.resume()
        self.assertEqual(aot.testtimer, True)

    def testWorkerAbortSanity(self):
        """test WorkerPdsh abort() (sanity)"""
        task = task_self()
        # test noop abort() on unscheduled worker
        worker = WorkerPdsh("localhost", command="sleep 1", handler=None,
                            timeout=None)
        worker.abort()
        
    def testLocalhostExplicitPdshReverseCopy(self):
        """test simple localhost rcopy with explicit pdsh worker"""
        dest = "/tmp/cs-test_testLocalhostExplicitPdshRCopy"
        shutil.rmtree(dest, ignore_errors=True)
        os.mkdir(dest)
        worker = WorkerPdsh("localhost", source="/etc/hosts",
                dest=dest, handler=None, timeout=10, reverse=True)
        self._task.schedule(worker) 
        self._task.resume()
        self.assertEqual(worker.source, "/etc/hosts")
        self.assertEqual(worker.dest, dest)
        self.assert_(os.path.exists(os.path.join(dest, "hosts.localhost")))

    def testLocalhostExplicitPdshReverseCopyDir(self):
        """test simple localhost rcopy dir with explicit pdsh worker"""
        dtmp_src = tempfile.mkdtemp("_cs-test_src")
        dtmp_dst = tempfile.mkdtemp( \
            "_cs-test_testLocalhostExplicitPdshReverseCopyDir")
        try:
            os.mkdir(os.path.join(dtmp_src, "lev1_a"))
            os.mkdir(os.path.join(dtmp_src, "lev1_b"))
            os.mkdir(os.path.join(dtmp_src, "lev1_a", "lev2"))
            worker = WorkerPdsh("localhost", source=dtmp_src,
                    dest=dtmp_dst, handler=None, timeout=30, reverse=True)
            self._task.schedule(worker) 
            self._task.resume()
            self.assert_(os.path.exists(os.path.join(dtmp_dst, \
                "%s.localhost" % os.path.basename(dtmp_src), "lev1_a", "lev2")))
        finally:
            shutil.rmtree(dtmp_dst, ignore_errors=True)
            shutil.rmtree(dtmp_src, ignore_errors=True)

    def testLocalhostExplicitPdshReverseCopyDirPreserve(self):
        """test simple localhost preserve rcopy dir with explicit pdsh worker"""
        dtmp_src = tempfile.mkdtemp("_cs-test_src")
        dtmp_dst = tempfile.mkdtemp( \
            "_cs-test_testLocalhostExplicitPdshReverseCopyDirPreserve")
        try:
            os.mkdir(os.path.join(dtmp_src, "lev1_a"))
            os.mkdir(os.path.join(dtmp_src, "lev1_b"))
            os.mkdir(os.path.join(dtmp_src, "lev1_a", "lev2"))
            worker = WorkerPdsh("localhost", source=dtmp_src,
                    dest=dtmp_dst, handler=None, timeout=30, preserve=True,
                    reverse=True)
            self._task.schedule(worker) 
            self._task.resume()
            self.assert_(os.path.exists(os.path.join(dtmp_dst, \
                "%s.localhost" % os.path.basename(dtmp_src), "lev1_a", "lev2")))
        finally:
            shutil.rmtree(dtmp_dst, ignore_errors=True)
            shutil.rmtree(dtmp_src, ignore_errors=True)


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TaskDistantTest)
    unittest.TextTestRunner(verbosity=2).run(suite)

