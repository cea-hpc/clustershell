#!/usr/bin/env python
# ClusterShell (distant) test suite
# Written by S. Thiell 2009-02-13


"""Unit test for ClusterShell Task (distant)"""

import copy
import pwd
import shutil
import sys

sys.path.insert(0, '../lib')

from TLib import make_temp_filename, make_temp_dir
from ClusterShell.Event import EventHandler
from ClusterShell.NodeSet import NodeSet
from ClusterShell.Task import *
from ClusterShell.Worker.Ssh import WorkerSsh
from ClusterShell.Worker.EngineClient import *
from ClusterShell.Worker.Worker import WorkerBadArgumentError

import socket

# TEventHandlerChecker 'received event' flags
EV_START=0x01
EV_READ=0x02
EV_WRITTEN=0x04
EV_HUP=0x08
EV_TIMEOUT=0x10
EV_CLOSE=0x20

class TaskDistantMixin(object):

    def setUp(self):
        self._task = task_self()
        self.assert_(self._task != None)

    def testLocalhostCommand(self):
        # init worker
        worker = self._task.shell("/bin/hostname", nodes='localhost')
        self.assert_(worker != None)
        # run task
        self._task.resume()

    def testLocalhostCommand2(self):
        # init worker
        worker = self._task.shell("/bin/hostname", nodes='localhost')
        self.assert_(worker != None)

        worker = self._task.shell("/bin/uname -r", nodes='localhost')
        self.assert_(worker != None)
        # run task
        self._task.resume()

    def testTaskShellWorkerGetCommand(self):
        worker1 = self._task.shell("/bin/hostname", nodes='localhost')
        self.assert_(worker1 != None)
        worker2 = self._task.shell("/bin/uname -r", nodes='localhost')
        self.assert_(worker2 != None)
        self._task.resume()
        self.assert_(hasattr(worker1, 'command'))
        self.assert_(hasattr(worker2, 'command'))
        self.assertEqual(worker1.command, "/bin/hostname")
        self.assertEqual(worker2.command, "/bin/uname -r")

    def testLocalhostCopy(self):
        # init worker
        dest = make_temp_filename(suffix='LocalhostCopy')
        worker = self._task.copy("/etc/hosts", dest, nodes='localhost')
        self.assert_(worker != None)
        # run task
        self._task.resume()
        os.unlink(dest)

    def testCopyNodeFailure(self):
        # == stderr merged ==
        self._task.set_default("stderr", False)
        dest = make_temp_filename(suffix='LocalhostCopyF')
        worker = self._task.copy("/etc/hosts", dest,
                                 nodes='unlikely-node,localhost')
        self.assert_(worker != None)
        self._task.resume()
        self.assert_(worker.node_error_buffer("unlikely-node") is None)
        self.assert_(len(worker.node_buffer("unlikely-node")) > 2)
        os.unlink(dest)

        # == stderr separated ==
        self._task.set_default("stderr", True)
        try:
            dest = make_temp_filename(suffix='LocalhostCopyF2')
            worker = self._task.copy("/etc/hosts", dest, nodes='unlikely-node,localhost')
            self.assert_(worker != None)
            # run task
            self._task.resume()
            self.assert_(worker.node_buffer("unlikely-node") is None)
            self.assert_(len(worker.node_error_buffer("unlikely-node")) > 2)
            os.unlink(dest)
        finally:
            self._task.set_default("stderr", False)

    def testLocalhostCopyDir(self):
        dtmp_src = make_temp_dir('src')
        dtmp_dst = make_temp_dir('testLocalhostCopyDir')
        try:
            os.mkdir(os.path.join(dtmp_src, "lev1_a"))
            os.mkdir(os.path.join(dtmp_src, "lev1_b"))
            os.mkdir(os.path.join(dtmp_src, "lev1_a", "lev2"))
            worker = self._task.copy(dtmp_src, dtmp_dst, nodes='localhost')
            self.assert_(worker != None)
            self._task.resume()
            self.assert_(os.path.exists(os.path.join(dtmp_dst, \
                os.path.basename(dtmp_src), "lev1_a", "lev2")))
        finally:
            shutil.rmtree(dtmp_dst, ignore_errors=True)
            shutil.rmtree(dtmp_src, ignore_errors=True)

    def testLocalhostExplicitSshCopy(self):
        dest = make_temp_filename('testLocalhostExplicitSshCopy')
        try:
            worker = WorkerSsh("localhost", source="/etc/hosts", dest=dest,
                    handler=None, timeout=10)
            self._task.schedule(worker)
            self._task.resume()
        finally:
            os.remove(dest)

    def testLocalhostExplicitSshCopyDir(self):
        dtmp_src = make_temp_dir('src')
        dtmp_dst = make_temp_dir('testLocalhostExplicitSshCopyDir')
        try:
            os.mkdir(os.path.join(dtmp_src, "lev1_a"))
            os.mkdir(os.path.join(dtmp_src, "lev1_b"))
            os.mkdir(os.path.join(dtmp_src, "lev1_a", "lev2"))
            worker = WorkerSsh("localhost", source=dtmp_src,
                    dest=dtmp_dst, handler=None, timeout=10)
            self._task.schedule(worker)
            self._task.resume()
            self.assert_(os.path.exists(os.path.join(dtmp_dst, \
                os.path.basename(dtmp_src), "lev1_a", "lev2")))
        finally:
            shutil.rmtree(dtmp_dst, ignore_errors=True)
            shutil.rmtree(dtmp_src, ignore_errors=True)

    def testLocalhostExplicitSshCopyDirPreserve(self):
        dtmp_src = make_temp_dir('src')
        dtmp_dst = make_temp_dir('testLocalhostExplicitSshCopyDirPreserve')
        try:
            os.mkdir(os.path.join(dtmp_src, "lev1_a"))
            os.mkdir(os.path.join(dtmp_src, "lev1_b"))
            os.mkdir(os.path.join(dtmp_src, "lev1_a", "lev2"))
            worker = WorkerSsh("localhost", source=dtmp_src, dest=dtmp_dst,
                               handler=None, timeout=10, preserve=True)
            self._task.schedule(worker)
            self._task.resume()
            self.assert_(os.path.exists(os.path.join(dtmp_dst, \
                os.path.basename(dtmp_src), "lev1_a", "lev2")))
        finally:
            shutil.rmtree(dtmp_dst, ignore_errors=True)
            shutil.rmtree(dtmp_src, ignore_errors=True)

    def testExplicitSshWorker(self):
        # init worker
        worker = WorkerSsh("localhost", command="/bin/echo alright", handler=None, timeout=5)
        self.assert_(worker != None)
        self._task.schedule(worker)
        # run task
        self._task.resume()
        # test output
        self.assertEqual(worker.node_buffer("localhost"), "alright")

    def testExplicitSshWorkerStdErr(self):
        # init worker
        worker = WorkerSsh("localhost", command="/bin/echo alright 1>&2",
                    handler=None, stderr=True, timeout=5)
        self.assert_(worker != None)
        self._task.schedule(worker)
        # run task
        self._task.resume()
        # test output
        self.assertEqual(worker.node_error_buffer("localhost"), "alright")

        # Re-test with stderr=False
        worker = WorkerSsh("localhost", command="/bin/echo alright 1>&2",
                    handler=None, stderr=False, timeout=5)
        self.assert_(worker != None)
        self._task.schedule(worker)
        # run task
        self._task.resume()
        # test output
        self.assertEqual(worker.node_error_buffer("localhost"), None)

    class TEventHandlerChecker(EventHandler):

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

    def testShellEvents(self):
        # init worker
        test_eh = self.__class__.TEventHandlerChecker(self)
        worker = self._task.shell("/bin/hostname", nodes='localhost', handler=test_eh)
        self.assert_(worker != None)
        # run task
        self._task.resume()
        # test events received: start, read, hup, close
        self.assertEqual(test_eh.flags, EV_START | EV_READ | EV_HUP | EV_CLOSE)

    def testShellEventsWithTimeout(self):
        # init worker
        test_eh = self.__class__.TEventHandlerChecker(self)
        worker = self._task.shell("/bin/echo alright && /bin/sleep 10", nodes='localhost', handler=test_eh,
                timeout=2)
        self.assert_(worker != None)
        # run task
        self._task.resume()
        # test events received: start, read, timeout, close
        self.assertEqual(test_eh.flags, EV_START | EV_READ | EV_TIMEOUT | EV_CLOSE)
        self.assertEqual(worker.node_buffer("localhost"), "alright")
        self.assertEqual(worker.num_timeout(), 1)
        self.assertEqual(self._task.num_timeout(), 1)
        count = 0
        for node in self._task.iter_keys_timeout():
            count += 1
            self.assertEqual(node, "localhost")
        self.assertEqual(count, 1)
        count = 0
        for node in worker.iter_keys_timeout():
            count += 1
            self.assertEqual(node, "localhost")
        self.assertEqual(count, 1)

    def testShellEventsWithTimeout2(self):
        # init worker
        test_eh1 = self.__class__.TEventHandlerChecker(self)
        worker1 = self._task.shell("/bin/echo alright && /bin/sleep 10", nodes='localhost', handler=test_eh1,
                timeout=2)
        self.assert_(worker1 != None)
        test_eh2 = self.__class__.TEventHandlerChecker(self)
        worker2 = self._task.shell("/bin/echo okay && /bin/sleep 10", nodes='localhost', handler=test_eh2,
                timeout=3)
        self.assert_(worker2 != None)
        # run task
        self._task.resume()
        # test events received: start, read, timeout, close
        self.assertEqual(test_eh1.flags, EV_START | EV_READ | EV_TIMEOUT | EV_CLOSE)
        self.assertEqual(test_eh2.flags, EV_START | EV_READ | EV_TIMEOUT | EV_CLOSE)
        self.assertEqual(worker1.node_buffer("localhost"), "alright")
        self.assertEqual(worker2.node_buffer("localhost"), "okay")
        self.assertEqual(worker1.num_timeout(), 1)
        self.assertEqual(worker2.num_timeout(), 1)
        self.assertEqual(self._task.num_timeout(), 2)

    def testShellEventsReadNoEOL(self):
        # init worker
        test_eh = self.__class__.TEventHandlerChecker(self)
        worker = self._task.shell("/bin/echo -n okay", nodes='localhost', handler=test_eh)
        self.assert_(worker != None)
        # run task
        self._task.resume()
        # test events received: start, close
        self.assertEqual(test_eh.flags, EV_START | EV_READ | EV_HUP | EV_CLOSE)
        self.assertEqual(worker.node_buffer("localhost"), "okay")

    def testShellEventsNoReadNoTimeout(self):
        # init worker
        test_eh = self.__class__.TEventHandlerChecker(self)
        worker = self._task.shell("/bin/sleep 2", nodes='localhost', handler=test_eh)
        self.assert_(worker != None)
        # run task
        self._task.resume()
        # test events received: start, close
        self.assertEqual(test_eh.flags, EV_START | EV_HUP | EV_CLOSE)
        self.assertEqual(worker.node_buffer("localhost"), None)

    def testLocalhostCommandFanout(self):
        fanout = self._task.info("fanout")
        self._task.set_info("fanout", 2)
        # init worker
        for i in range(0, 10):
            worker = self._task.shell("/bin/echo %d" % i, nodes='localhost')
            self.assert_(worker != None)
        # run task
        self._task.resume()
        # restore fanout value
        self._task.set_info("fanout", fanout)

    def testWorkerBuffers(self):
        # Warning: if you modify this test, please also modify testWorkerErrorBuffers()
        task = task_self()
        worker = task.shell("/usr/bin/printf 'foo\nbar\nxxx\n'",
                            nodes='localhost')
        task.resume()
        # test iter_buffers() by worker...
        cnt = 2
        for buf, nodes in worker.iter_buffers():
            cnt -= 1
            if buf == "foo\nbar\nxxx\n":
                self.assertEqual(len(nodes), 1)
                self.assertEqual(str(nodes), "localhost")
        self.assertEqual(cnt, 1)
        # new check in 1.7 to ensure match_keys is not a string
        testgen = worker.iter_buffers("localhost")
        # cast to list to effectively iterate
        self.assertRaises(TypeError, list, testgen)
        # and also fixed an issue when match_keys was an empty list
        for buf, nodes in worker.iter_buffers([]):
            self.assertFalse("Found buffer with empty match_keys?!")
        for buf, nodes in worker.iter_buffers(["localhost"]):
            cnt -= 1
            if buf == "foo\nbar\nxxx\n":
                self.assertEqual(len(nodes), 1)
                self.assertEqual(str(nodes), "localhost")
        self.assertEqual(cnt, 0)
        # test flushing buffers by worker
        worker.flush_buffers()
        self.assertEqual(list(worker.iter_buffers()), [])

    def testWorkerErrorBuffers(self):
        # Warning: if you modify this test, please also modify testWorkerBuffers()
        task = task_self()
        worker = task.shell("/usr/bin/printf 'foo\nbar\nxxx\n' 1>&2",
                            nodes='localhost', stderr=True)
        task.resume()
        # test iter_errors() by worker...
        cnt = 2
        for buf, nodes in worker.iter_errors():
            cnt -= 1
            if buf == "foo\nbar\nxxx\n":
                self.assertEqual(len(nodes), 1)
                self.assertEqual(str(nodes), "localhost")
        self.assertEqual(cnt, 1)
        # new check in 1.7 to ensure match_keys is not a string
        testgen = worker.iter_errors("localhost")
        # cast to list to effectively iterate
        self.assertRaises(TypeError, list, testgen)
        # and also fixed an issue when match_keys was an empty list
        for buf, nodes in worker.iter_errors([]):
            self.assertFalse("Found error buffer with empty match_keys?!")
        for buf, nodes in worker.iter_errors(["localhost"]):
            cnt -= 1
            if buf == "foo\nbar\nxxx\n":
                self.assertEqual(len(nodes), 1)
                self.assertEqual(str(nodes), "localhost")
        self.assertEqual(cnt, 0)
        # test flushing error buffers by worker
        worker.flush_errors()
        self.assertEqual(list(worker.iter_errors()), [])

    def testWorkerNodeBuffers(self):
        task = task_self()
        self.assert_(task != None)

        worker = task.shell("/usr/bin/printf 'foo\nbar\nxxx\n'",
                            nodes='localhost')

        task.resume()

        cnt = 1
        for node, buf in worker.iter_node_buffers():
            cnt -= 1
            if buf == "foo\nbar\nxxx\n":
                self.assertEqual(node, "localhost")
        self.assertEqual(cnt, 0)

    def testWorkerNodeErrors(self):
        task = task_self()
        self.assert_(task != None)

        worker = task.shell("/usr/bin/printf 'foo\nbar\nxxx\n' 1>&2",
                            nodes='localhost', stderr=True)

        task.resume()

        cnt = 1
        for node, buf in worker.iter_node_errors():
            cnt -= 1
            if buf == "foo\nbar\nxxx\n":
                self.assertEqual(node, "localhost")
        self.assertEqual(cnt, 0)

    def testWorkerRetcodes(self):
        task = task_self()
        self.assert_(task != None)

        worker = task.shell("/bin/sh -c 'exit 3'", nodes="localhost")

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
        task = task_self()
        self.assert_(task != None)

        worker = task.shell("/bin/sh -c 'exit 3'", nodes="localhost")

        task.resume()

        cnt = 1
        for node, rc in worker.iter_node_retcodes():
            cnt -= 1
            self.assertEqual(rc, 3)
            self.assertEqual(node, "localhost")

        self.assertEqual(cnt, 0)

    def testEscape(self):
        worker = self._task.shell("export CSTEST=foobar; /bin/echo \$CSTEST | sed 's/\ foo/bar/'", nodes="localhost")
        # execute
        self._task.resume()
        # read result
        self.assertEqual(worker.node_buffer("localhost"), "$CSTEST")

    def testEscape2(self):
        worker = self._task.shell("export CSTEST=foobar; /bin/echo $CSTEST | sed 's/\ foo/bar/'", nodes="localhost")
        # execute
        self._task.resume()
        # read result
        self.assertEqual(worker.node_buffer("localhost"), "foobar")

    def testSshUserOption(self):
        ssh_user_orig = self._task.info("ssh_user")
        self._task.set_info("ssh_user", pwd.getpwuid(os.getuid())[0])
        worker = self._task.shell("/bin/echo foobar", nodes="localhost")
        self.assert_(worker != None)
        self._task.resume()
        # restore original ssh_user (None)
        self.assertEqual(ssh_user_orig, None)
        self._task.set_info("ssh_user", ssh_user_orig)

    def testSshUserOptionForScp(self):
        ssh_user_orig = self._task.info("ssh_user")
        self._task.set_info("ssh_user", pwd.getpwuid(os.getuid())[0])
        dest = make_temp_filename('testLocalhostCopyU')
        worker = self._task.copy("/etc/hosts", dest, nodes='localhost')
        self.assert_(worker != None)
        self._task.resume()
        # restore original ssh_user (None)
        self.assertEqual(ssh_user_orig, None)
        self._task.set_info("ssh_user", ssh_user_orig)
        os.unlink(dest)

    def testSshOptionsOption(self):
        ssh_options_orig = self._task.info("ssh_options")
        try:
            self._task.set_info("ssh_options", "-oLogLevel=QUIET")
            worker = self._task.shell("/bin/echo foobar", nodes="localhost")
            self.assert_(worker != None)
            self._task.resume()
            self.assertEqual(worker.node_buffer("localhost"), "foobar")
            # test 3 options
            self._task.set_info("ssh_options", \
                "-oLogLevel=QUIET -oStrictHostKeyChecking=no -oVerifyHostKeyDNS=no")
            worker = self._task.shell("/bin/echo foobar3", nodes="localhost")
            self.assert_(worker != None)
            self._task.resume()
            self.assertEqual(worker.node_buffer("localhost"), "foobar3")
        finally:
            # restore original ssh_user (None)
            self.assertEqual(ssh_options_orig, None)
            self._task.set_info("ssh_options", ssh_options_orig)

    def testSshOptionsOptionForScp(self):
        ssh_options_orig = self._task.info("ssh_options")
        testfile = None
        try:
            testfile = make_temp_filename('testLocalhostCopyO')
            if os.path.exists(testfile):
                os.remove(testfile)
            self._task.set_info("ssh_options", \
                "-oLogLevel=QUIET -oStrictHostKeyChecking=no -oVerifyHostKeyDNS=no")
            worker = self._task.copy("/etc/hosts", testfile, nodes='localhost')
            self.assert_(worker != None)
            self._task.resume()
            self.assert_(os.path.exists(testfile))
        finally:
            os.unlink(testfile)
            # restore original ssh_user (None)
            self.assertEqual(ssh_options_orig, None)
            self._task.set_info("ssh_options", ssh_options_orig)

    def testShellStderrWithHandler(self):
        class StdErrHandler(EventHandler):
            def ev_error(self, worker):
                assert worker.last_error() == "something wrong"

        worker = self._task.shell("echo something wrong 1>&2", nodes='localhost',
                                  handler=StdErrHandler())
        self._task.resume()
        for buf, nodes in worker.iter_errors():
            self.assertEqual(buf, "something wrong")
        for buf, nodes in worker.iter_errors(['localhost']):
            self.assertEqual(buf, "something wrong")

    def testShellWriteSimple(self):
        worker = self._task.shell("cat", nodes='localhost')
        worker.write("this is a test\n")
        worker.set_write_eof()
        self._task.resume()
        self.assertEqual(worker.node_buffer("localhost"), "this is a test")

    def testShellWriteHandler(self):
        class WriteOnReadHandler(EventHandler):
            def __init__(self, target_worker):
                self.target_worker = target_worker
            def ev_read(self, worker):
                self.target_worker.write("%s:%s\n" % worker.last_read())
                self.target_worker.set_write_eof()

        reader = self._task.shell("cat", nodes='localhost')
        worker = self._task.shell("sleep 1; echo foobar", nodes='localhost',
                                  handler=WriteOnReadHandler(reader))
        self._task.resume()
        self.assertEqual(reader.node_buffer("localhost"), "localhost:foobar")

    def testSshBadArgumentOption(self):
	# Check code < 1.4 compatibility
        self.assertRaises(WorkerBadArgumentError, WorkerSsh, "localhost",
			  None, None)
	# As of 1.4, ValueError is raised for missing parameter
        self.assertRaises(ValueError, WorkerSsh, "localhost",
			  None, None) # 1.4+

    def testCopyEvents(self):
        test_eh = self.__class__.TEventHandlerChecker(self)
        dest = make_temp_filename('testLocalhostCopyEvents')
        worker = self._task.copy("/etc/hosts", dest, nodes='localhost',
                handler=test_eh)
        self.assert_(worker != None)
        # run task
        self._task.resume()
        os.unlink(dest)
        self.assertEqual(test_eh.flags, EV_START | EV_HUP | EV_CLOSE)

    def testWorkerAbort(self):
        task = task_self()
        self.assert_(task != None)

        # Test worker.abort() in an event handler.
        class AbortOnTimer(EventHandler):
            def __init__(self, worker):
                EventHandler.__init__(self)
                self.ext_worker = worker
                self.testtimer = False
            def ev_timer(self, timer):
                self.ext_worker.abort()
                self.testtimer = True

        aot = AbortOnTimer(task.shell("sleep 10", nodes="localhost"))
        self.assertEqual(aot.testtimer, False)
        task.timer(1.5, handler=aot)
        task.resume()
        self.assertEqual(aot.testtimer, True)

    def testWorkerAbortSanity(self):
        task = task_self()
        worker = task.shell("sleep 1", nodes="localhost")
        worker.abort()

        # test noop abort() on unscheduled worker
        worker = WorkerSsh("localhost", command="sleep 1", handler=None,
                           timeout=None)
        worker.abort()

    def testLocalhostExplicitSshReverseCopy(self):
        dest = make_temp_dir('testLocalhostExplicitSshRCopy')
        try:
            worker = WorkerSsh("localhost", source="/etc/hosts",
                    dest=dest, handler=None, timeout=10, reverse=True)
            self._task.schedule(worker)
            self._task.resume()
            self.assertEqual(worker.source, "/etc/hosts")
            self.assertEqual(worker.dest, dest)
            self.assert_(os.path.exists(os.path.join(dest, "hosts.localhost")))
        finally:
            shutil.rmtree(dest, ignore_errors=True)

    def testLocalhostExplicitSshReverseCopyDir(self):
        dtmp_src = make_temp_dir('src')
        dtmp_dst = make_temp_dir('testLocalhostExplicitSshReverseCopyDir')
        try:
            os.mkdir(os.path.join(dtmp_src, "lev1_a"))
            os.mkdir(os.path.join(dtmp_src, "lev1_b"))
            os.mkdir(os.path.join(dtmp_src, "lev1_a", "lev2"))
            worker = WorkerSsh("localhost", source=dtmp_src,
                    dest=dtmp_dst, handler=None, timeout=30, reverse=True)
            self._task.schedule(worker)
            self._task.resume()
            self.assert_(os.path.exists(os.path.join(dtmp_dst, \
                "%s.localhost" % os.path.basename(dtmp_src), "lev1_a", "lev2")))
        finally:
            shutil.rmtree(dtmp_dst, ignore_errors=True)
            shutil.rmtree(dtmp_src, ignore_errors=True)

    def testLocalhostExplicitSshReverseCopyDirPreserve(self):
        dtmp_src = make_temp_dir('src')
        dtmp_dst = make_temp_dir('testLocalhostExplicitSshReverseCopyDirPreserve')
        try:
            os.mkdir(os.path.join(dtmp_src, "lev1_a"))
            os.mkdir(os.path.join(dtmp_src, "lev1_b"))
            os.mkdir(os.path.join(dtmp_src, "lev1_a", "lev2"))
            worker = WorkerSsh("localhost", source=dtmp_src,
                    dest=dtmp_dst, handler=None, timeout=30, reverse=True)
            self._task.schedule(worker)
            self._task.resume()
            self.assert_(os.path.exists(os.path.join(dtmp_dst, \
                "%s.localhost" % os.path.basename(dtmp_src), "lev1_a", "lev2")))
        finally:
            shutil.rmtree(dtmp_dst, ignore_errors=True)
            shutil.rmtree(dtmp_src, ignore_errors=True)

    def testErroneousSshPath(self):
        try:
            self._task.set_info("ssh_path", "/wrong/path/to/ssh")
            # init worker
            worker = self._task.shell("/bin/echo ok", nodes='localhost')
            self.assert_(worker != None)
            # run task
            self._task.resume()
            self.assertEqual(self._task.max_retcode(), 255)
        finally:
            # restore fanout value
            self._task.set_info("ssh_path", None)


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TaskDistantTest)
    unittest.TextTestRunner(verbosity=2).run(suite)

