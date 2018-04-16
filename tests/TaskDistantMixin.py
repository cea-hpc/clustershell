# ClusterShell (distant) test suite
# Written by S. Thiell

"""Unit test for ClusterShell Task (distant)"""

import pwd
import shutil
import warnings

from TLib import HOSTNAME, make_temp_filename, make_temp_dir
from ClusterShell.Event import EventHandler
from ClusterShell.Task import *
from ClusterShell.Worker.Ssh import WorkerSsh
from ClusterShell.Worker.EngineClient import *
from ClusterShell.Worker.Worker import FANOUT_UNLIMITED, WorkerBadArgumentError

import socket

# TEventHandlerChecker 'received event' flags
EV_START = 0x01
EV_PICKUP = 0x02
EV_READ = 0x04
EV_WRITTEN = 0x08
EV_HUP = 0x10
EV_TIMEOUT = 0x20
EV_CLOSE = 0x40


class TaskDistantMixin(object):

    def setUp(self):
        self._task = task_self()

    def testLocalhostCommand(self):
        # init worker
        worker = self._task.shell("/bin/hostname", nodes=HOSTNAME)
        # run task
        self._task.resume()

    def testLocalhostCommand2(self):
        # init worker
        worker = self._task.shell("/bin/hostname", nodes=HOSTNAME)

        worker = self._task.shell("/bin/uname -r", nodes=HOSTNAME)
        # run task
        self._task.resume()

    def testTaskShellWorkerGetCommand(self):
        worker1 = self._task.shell("/bin/hostname", nodes=HOSTNAME)
        worker2 = self._task.shell("/bin/uname -r", nodes=HOSTNAME)
        self._task.resume()
        self.assertTrue(hasattr(worker1, 'command'))
        self.assertTrue(hasattr(worker2, 'command'))
        self.assertEqual(worker1.command, "/bin/hostname")
        self.assertEqual(worker2.command, "/bin/uname -r")

    def testTaskShellRunDistant(self):
        wrk = task_self().run("false", nodes=HOSTNAME)
        self.assertEqual(wrk.node_retcode(HOSTNAME), 1)

    def testLocalhostCopy(self):
        dests = []
        try:
            for i in range(5):
                dest = make_temp_filename(suffix='LocalhostCopy')
                dests.append(dest)
                worker = self._task.copy("/etc/hosts", dest, nodes=HOSTNAME)
            self._task.resume()
        finally:
            for dest in dests:
                os.unlink(dest)

    def testCopyNodeFailure(self):
        # == stderr merged ==
        self._task.set_default("stderr", False)
        dest = make_temp_filename(suffix='LocalhostCopyF')
        worker = self._task.copy("/etc/hosts", dest,
                                 nodes='unlikely-node,%s' % HOSTNAME)
        self._task.resume()
        self.assertEqual(worker.node_error_buffer("unlikely-node"), None)
        self.assertTrue(len(worker.node_buffer("unlikely-node")) > 2)
        os.unlink(dest)

        # == stderr separated ==
        self._task.set_default("stderr", True)
        try:
            dest = make_temp_filename(suffix='LocalhostCopyF2')
            worker = self._task.copy("/etc/hosts", dest,
                                     nodes='unlikely-node,%s' % HOSTNAME)
            # run task
            self._task.resume()
            self.assertTrue(worker.node_buffer("unlikely-node") is None)
            self.assertTrue(len(worker.node_error_buffer("unlikely-node")) > 2)
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
            worker = self._task.copy(dtmp_src, dtmp_dst, nodes=HOSTNAME)
            self._task.resume()
            self.assertTrue(os.path.exists(os.path.join(dtmp_dst,
                            os.path.basename(dtmp_src), "lev1_a", "lev2")))
        finally:
            shutil.rmtree(dtmp_dst, ignore_errors=True)
            shutil.rmtree(dtmp_src, ignore_errors=True)

    def testLocalhostExplicitSshCopy(self):
        dest = make_temp_filename('testLocalhostExplicitSshCopy')
        srcsz = os.path.getsize("/etc/hosts")
        try:
            worker = WorkerSsh(HOSTNAME, source="/etc/hosts", dest=dest,
                               handler=None, timeout=10)
            self._task.schedule(worker)
            self._task.resume()
            self.assertEqual(srcsz, os.path.getsize(dest))
        finally:
            os.remove(dest)

    def testLocalhostExplicitSshCopyWithOptions(self):
        dest = make_temp_dir('testLocalhostExplicitSshCopyWithOptions')
        self._task.set_info("scp_path", "/usr/bin/scp -l 10")
        self._task.set_info("scp_options", "-oLogLevel=QUIET")
        try:
            worker = WorkerSsh(HOSTNAME, source="/etc/hosts", dest=dest,
                               handler=None)
            self._task.schedule(worker)
            self._task.resume()
            self.assertEqual(self._task.max_retcode(), 0)
            self.assertTrue(os.path.exists(os.path.join(dest, "hosts")))
        finally:
            os.unlink(os.path.join(dest, "hosts"))
            os.rmdir(dest)
        # clear options after test
        task_cleanup()
        self.assertEqual(task_self().info("scp_path"), None)

    def testLocalhostExplicitSshCopyDir(self):
        dtmp_src = make_temp_dir('src')
        dtmp_dst = make_temp_dir('testLocalhostExplicitSshCopyDir')
        try:
            os.mkdir(os.path.join(dtmp_src, "lev1_a"))
            os.mkdir(os.path.join(dtmp_src, "lev1_b"))
            os.mkdir(os.path.join(dtmp_src, "lev1_a", "lev2"))
            worker = WorkerSsh(HOSTNAME, source=dtmp_src, dest=dtmp_dst,
                               handler=None)
            self._task.schedule(worker)
            self._task.resume()
            path = os.path.join(dtmp_dst, os.path.basename(dtmp_src), "lev1_a",
                                "lev2")
            self.assertTrue(os.path.exists(path))
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
            worker = WorkerSsh(HOSTNAME, source=dtmp_src, dest=dtmp_dst,
                               handler=None, timeout=10, preserve=True)
            self._task.schedule(worker)
            self._task.resume()
            self.assertTrue(os.path.exists(os.path.join(dtmp_dst,
                            os.path.basename(dtmp_src), "lev1_a", "lev2")))
        finally:
            shutil.rmtree(dtmp_dst, ignore_errors=True)
            shutil.rmtree(dtmp_src, ignore_errors=True)

    def testExplicitSshWorker(self):
        # init worker
        worker = WorkerSsh(HOSTNAME, command="/bin/echo alright", handler=None)
        self._task.schedule(worker)
        # run task
        self._task.resume()
        # test output
        self.assertEqual(worker.node_buffer(HOSTNAME), b"alright")

    def testExplicitSshWorkerWithOptions(self):
        self._task.set_info("ssh_path", "/usr/bin/ssh -C")
        self._task.set_info("ssh_options", "-oLogLevel=QUIET")
        worker = WorkerSsh(HOSTNAME, command="/bin/echo alright", handler=None)
        self._task.schedule(worker)
        # run task
        self._task.resume()
        # test output
        self.assertEqual(worker.node_buffer(HOSTNAME), b"alright")
        # clear options after test
        task_cleanup()
        self.assertEqual(task_self().info("ssh_path"), None)

    def testExplicitSshWorkerStdErr(self):
        # init worker
        worker = WorkerSsh(HOSTNAME, command="/bin/echo alright 1>&2",
                           handler=None, stderr=True)
        self._task.schedule(worker)
        # run task
        self._task.resume()
        # test output
        self.assertEqual(worker.node_error_buffer(HOSTNAME), b"alright")

        # Re-test with stderr=False
        worker = WorkerSsh(HOSTNAME, command="/bin/echo alright 1>&2",
                           handler=None, stderr=False)
        self._task.schedule(worker)
        # run task
        self._task.resume()
        # test output
        self.assertEqual(worker.node_error_buffer(HOSTNAME), None)

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
        def ev_pickup(self, worker):
            self.test.assertTrue(self.flags & EV_START)
            self.flags |= EV_PICKUP
            self.last_node = worker.current_node
        def ev_read(self, worker):
            self.test.assertEqual(self.flags, EV_START | EV_PICKUP)
            self.flags |= EV_READ
            self.last_node = worker.current_node
            self.last_read = worker.current_msg
        def ev_written(self, worker):
            self.test.assertTrue(self.flags & (EV_START | EV_PICKUP))
            self.flags |= EV_WRITTEN
        def ev_hup(self, worker):
            self.test.assertTrue(self.flags & (EV_START | EV_PICKUP))
            self.flags |= EV_HUP
            self.last_node = worker.current_node
            self.last_rc = worker.current_rc
        def ev_timeout(self, worker):
            self.test.assertTrue(self.flags & EV_START)
            self.flags |= EV_TIMEOUT
            self.last_node = worker.current_node
        def ev_close(self, worker):
            self.test.assertTrue(self.flags & EV_START)
            self.test.assertTrue(self.flags & EV_CLOSE == 0)
            self.flags |= EV_CLOSE

    def testShellEvents(self):
        # init worker
        test_eh = self.__class__.TEventHandlerChecker(self)
        worker = self._task.shell("/bin/hostname", nodes=HOSTNAME, handler=test_eh)
        # run task
        self._task.resume()
        # test events received: start, read, hup, close
        self.assertEqual(test_eh.flags, EV_START | EV_PICKUP | EV_READ | EV_HUP | EV_CLOSE)

    def testShellEventsWithTimeout(self):
        # init worker
        test_eh = self.__class__.TEventHandlerChecker(self)
        worker = self._task.shell("/bin/echo alright && /bin/sleep 10",
                                  nodes=HOSTNAME, handler=test_eh, timeout=2)
        self.assertTrue(worker != None)
        # run task
        self._task.resume()
        # test events received: start, read, timeout, close
        self.assertEqual(test_eh.flags, EV_START | EV_PICKUP | EV_READ | EV_TIMEOUT | EV_CLOSE)
        self.assertEqual(worker.node_buffer(HOSTNAME), b"alright")
        self.assertEqual(worker.num_timeout(), 1)
        self.assertEqual(self._task.num_timeout(), 1)
        count = 0
        for node in self._task.iter_keys_timeout():
            count += 1
            self.assertEqual(node, HOSTNAME)
        self.assertEqual(count, 1)
        count = 0
        for node in worker.iter_keys_timeout():
            count += 1
            self.assertEqual(node, HOSTNAME)
        self.assertEqual(count, 1)

    def testShellEventsWithTimeout2(self):
        # init worker
        test_eh1 = self.__class__.TEventHandlerChecker(self)
        worker1 = self._task.shell("/bin/echo alright && /bin/sleep 10",
                                   nodes=HOSTNAME, handler=test_eh1, timeout=2)
        test_eh2 = self.__class__.TEventHandlerChecker(self)
        worker2 = self._task.shell("/bin/echo okay && /bin/sleep 10",
                                   nodes=HOSTNAME, handler=test_eh2, timeout=3)
        # run task
        self._task.resume()
        # test events received: start, read, timeout, close
        self.assertEqual(test_eh1.flags, EV_START | EV_PICKUP | EV_READ | EV_TIMEOUT | EV_CLOSE)
        self.assertEqual(test_eh2.flags, EV_START | EV_PICKUP | EV_READ | EV_TIMEOUT | EV_CLOSE)
        self.assertEqual(worker1.node_buffer(HOSTNAME), b"alright")
        self.assertEqual(worker2.node_buffer(HOSTNAME), b"okay")
        self.assertEqual(worker1.num_timeout(), 1)
        self.assertEqual(worker2.num_timeout(), 1)
        self.assertEqual(self._task.num_timeout(), 2)

    def testShellEventsReadNoEOL(self):
        # init worker
        test_eh = self.__class__.TEventHandlerChecker(self)
        worker = self._task.shell("/bin/echo -n okay", nodes=HOSTNAME, handler=test_eh)
        # run task
        self._task.resume()
        # test events received: start, close
        self.assertEqual(test_eh.flags, EV_START | EV_PICKUP | EV_READ | EV_HUP | EV_CLOSE)
        self.assertEqual(worker.node_buffer(HOSTNAME), b"okay")

    def testShellEventsNoReadNoTimeout(self):
        # init worker
        test_eh = self.__class__.TEventHandlerChecker(self)
        worker = self._task.shell("/bin/sleep 2", nodes=HOSTNAME, handler=test_eh)
        # run task
        self._task.resume()
        # test events received: start, close
        self.assertEqual(test_eh.flags, EV_START | EV_PICKUP | EV_HUP | EV_CLOSE)
        self.assertEqual(worker.node_buffer(HOSTNAME), None)

    def testLocalhostCommandFanout(self):
        fanout = self._task.info("fanout")
        self._task.set_info("fanout", 2)
        # init worker
        for i in range(0, 10):
            worker = self._task.shell("/bin/echo %d" % i, nodes=HOSTNAME)
        # run task
        self._task.resume()
        # restore fanout value
        self._task.set_info("fanout", fanout)

    def testWorkerBuffers(self):
        # Warning: if you modify this test, please also modify testWorkerErrorBuffers()
        task = task_self()
        worker = task.shell("/usr/bin/printf 'foo\nbar\nxxx\n'",
                            nodes=HOSTNAME)
        task.resume()
        # test iter_buffers() by worker...
        cnt = 2
        for buf, nodes in worker.iter_buffers():
            cnt -= 1
            if buf == b"foo\nbar\nxxx\n":
                self.assertEqual(len(nodes), 1)
                self.assertEqual(str(nodes), HOSTNAME)
        self.assertEqual(cnt, 1)
        # new check in 1.7 to ensure match_keys is not a string
        testgen = worker.iter_buffers(HOSTNAME)
        # cast to list to effectively iterate
        self.assertRaises(TypeError, list, testgen)
        # and also fixed an issue when match_keys was an empty list
        for buf, nodes in worker.iter_buffers([]):
            self.assertFalse("Found buffer with empty match_keys?!")
        for buf, nodes in worker.iter_buffers([HOSTNAME]):
            cnt -= 1
            if buf == b"foo\nbar\nxxx\n":
                self.assertEqual(len(nodes), 1)
                self.assertEqual(str(nodes), HOSTNAME)
        self.assertEqual(cnt, 0)
        # test flushing buffers by worker
        worker.flush_buffers()
        self.assertEqual(list(worker.iter_buffers()), [])

    def testWorkerErrorBuffers(self):
        # Warning: if you modify this test, please also modify testWorkerBuffers()
        task = task_self()
        worker = task.shell("/usr/bin/printf 'foo\nbar\nxxx\n' 1>&2",
                            nodes=HOSTNAME, stderr=True)
        task.resume()
        # test iter_errors() by worker...
        cnt = 2
        for buf, nodes in worker.iter_errors():
            cnt -= 1
            if buf == b"foo\nbar\nxxx\n":
                self.assertEqual(len(nodes), 1)
                self.assertEqual(str(nodes), HOSTNAME)
        self.assertEqual(cnt, 1)
        # new check in 1.7 to ensure match_keys is not a string
        testgen = worker.iter_errors(HOSTNAME)
        # cast to list to effectively iterate
        self.assertRaises(TypeError, list, testgen)
        # and also fixed an issue when match_keys was an empty list
        for buf, nodes in worker.iter_errors([]):
            self.assertFalse("Found error buffer with empty match_keys?!")
        for buf, nodes in worker.iter_errors([HOSTNAME]):
            cnt -= 1
            if buf == b"foo\nbar\nxxx\n":
                self.assertEqual(len(nodes), 1)
                self.assertEqual(str(nodes), HOSTNAME)
        self.assertEqual(cnt, 0)
        # test flushing error buffers by worker
        worker.flush_errors()
        self.assertEqual(list(worker.iter_errors()), [])

    def testWorkerNodeBuffers(self):
        task = task_self()

        worker = task.shell("/usr/bin/printf 'foo\nbar\nxxx\n'",
                            nodes=HOSTNAME)

        task.resume()

        cnt = 1
        for node, buf in worker.iter_node_buffers():
            cnt -= 1
            if buf == b"foo\nbar\nxxx\n":
                self.assertEqual(node, HOSTNAME)
        self.assertEqual(cnt, 0)

    def testWorkerNodeErrors(self):
        task = task_self()

        worker = task.shell("/usr/bin/printf 'foo\nbar\nxxx\n' 1>&2",
                            nodes=HOSTNAME, stderr=True)

        task.resume()

        cnt = 1
        for node, buf in worker.iter_node_errors():
            cnt -= 1
            if buf == b"foo\nbar\nxxx\n":
                self.assertEqual(node, HOSTNAME)
        self.assertEqual(cnt, 0)

    def testWorkerRetcodes(self):
        task = task_self()

        worker = task.shell("/bin/sh -c 'exit 3'", nodes=HOSTNAME)

        task.resume()

        cnt = 2
        for rc, keys in worker.iter_retcodes():
            cnt -= 1
            self.assertEqual(rc, 3)
            self.assertEqual(len(keys), 1)
            self.assertEqual(keys[0], HOSTNAME)

        self.assertEqual(cnt, 1)

        for rc, keys in worker.iter_retcodes(HOSTNAME):
            cnt -= 1
            self.assertEqual(rc, 3)
            self.assertEqual(len(keys), 1)
            self.assertEqual(keys[0], HOSTNAME)

        self.assertEqual(cnt, 0)

        # test node_retcode
        self.assertEqual(worker.node_retcode(HOSTNAME), 3)   # 1.2.91+
        self.assertEqual(worker.node_rc(HOSTNAME), 3)

        # test node_retcode failure
        self.assertRaises(KeyError, worker.node_retcode, "dummy")

        # test max retcode API
        self.assertEqual(task.max_retcode(), 3)

    def testWorkerNodeRetcodes(self):
        task = task_self()

        worker = task.shell("/bin/sh -c 'exit 3'", nodes=HOSTNAME)

        task.resume()

        cnt = 1
        for node, rc in worker.iter_node_retcodes():
            cnt -= 1
            self.assertEqual(rc, 3)
            self.assertEqual(node, HOSTNAME)

        self.assertEqual(cnt, 0)

    def testEscape(self):
        cmd = r"export CSTEST=foobar; /bin/echo \$CSTEST | sed 's/\ foo/bar/'"
        worker = self._task.shell(cmd, nodes=HOSTNAME)
        # execute
        self._task.resume()
        # read result
        self.assertEqual(worker.node_buffer(HOSTNAME), b"$CSTEST")

    def testEscape2(self):
        cmd = r"export CSTEST=foobar; /bin/echo $CSTEST | sed 's/\ foo/bar/'"
        worker = self._task.shell(cmd, nodes=HOSTNAME)
        # execute
        self._task.resume()
        # read result
        self.assertEqual(worker.node_buffer(HOSTNAME), b"foobar")

    def testSshUserOption(self):
        ssh_user_orig = self._task.info("ssh_user")
        self._task.set_info("ssh_user", pwd.getpwuid(os.getuid())[0])
        worker = self._task.shell("/bin/echo foobar", nodes=HOSTNAME)
        self._task.resume()
        # restore original ssh_user (None)
        self.assertEqual(ssh_user_orig, None)
        self._task.set_info("ssh_user", ssh_user_orig)

    def testSshUserOptionForScp(self):
        ssh_user_orig = self._task.info("ssh_user")
        self._task.set_info("ssh_user", pwd.getpwuid(os.getuid())[0])
        dest = make_temp_filename('testLocalhostCopyU')
        worker = self._task.copy("/etc/hosts", dest, nodes=HOSTNAME)
        self._task.resume()
        # restore original ssh_user (None)
        self.assertEqual(ssh_user_orig, None)
        self._task.set_info("ssh_user", ssh_user_orig)
        os.unlink(dest)

    def testSshOptionsOption(self):
        ssh_options_orig = self._task.info("ssh_options")
        try:
            self._task.set_info("ssh_options", "-oLogLevel=QUIET")
            worker = self._task.shell("/bin/echo foobar", nodes=HOSTNAME)
            self._task.resume()
            self.assertEqual(worker.node_buffer(HOSTNAME), b"foobar")
            # test 3 options
            self._task.set_info("ssh_options", \
                "-oLogLevel=QUIET -oStrictHostKeyChecking=no -oVerifyHostKeyDNS=no")
            worker = self._task.shell("/bin/echo foobar3", nodes=HOSTNAME)
            self._task.resume()
            self.assertEqual(worker.node_buffer(HOSTNAME), b"foobar3")
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
            worker = self._task.copy("/etc/hosts", testfile, nodes=HOSTNAME)
            self._task.resume()
            self.assertTrue(os.path.exists(testfile))
        finally:
            os.unlink(testfile)
            # restore original ssh_user (None)
            self.assertEqual(ssh_options_orig, None)
            self._task.set_info("ssh_options", ssh_options_orig)

    def testShellStderrWithHandler(self):
        class StdErrHandler(EventHandler):
            def ev_error(self, worker):
                assert worker.current_errmsg == b"something wrong"

        worker = self._task.shell("echo something wrong 1>&2", nodes=HOSTNAME,
                                  handler=StdErrHandler(), stderr=True)
        self._task.resume()
        for buf, nodes in worker.iter_errors():
            self.assertEqual(buf, b"something wrong")
        for buf, nodes in worker.iter_errors([HOSTNAME]):
            self.assertEqual(buf, b"something wrong")

    def testShellWriteSimple(self):
        worker = self._task.shell("cat", nodes=HOSTNAME)
        worker.write(b"this is a test\n")
        worker.set_write_eof()
        self._task.resume()
        self.assertEqual(worker.node_buffer(HOSTNAME), b"this is a test")

    def testShellWriteHandler(self):
        class WriteOnReadHandler(EventHandler):
            def __init__(self, target_worker):
                self.target_worker = target_worker
            def ev_read(self, worker):
                self.target_worker.write(worker.current_node.encode('utf-8')
                                         + b':' + worker.current_msg + b'\n')
                self.target_worker.set_write_eof()

        reader = self._task.shell("cat", nodes=HOSTNAME)
        worker = self._task.shell("sleep 1; echo foobar", nodes=HOSTNAME,
                                  handler=WriteOnReadHandler(reader))
        self._task.resume()
        res = "%s:foobar" % HOSTNAME
        self.assertEqual(reader.node_buffer(HOSTNAME), res.encode('utf-8'))

    def testSshBadArgumentOption(self):
        # Check code < 1.4 compatibility
        self.assertRaises(WorkerBadArgumentError, WorkerSsh, HOSTNAME, None,
                          None)
        # As of 1.4, ValueError is raised for missing parameter
        self.assertRaises(ValueError, WorkerSsh, HOSTNAME, None, None) # 1.4+

    def testCopyEvents(self):
        test_eh = self.__class__.TEventHandlerChecker(self)
        dest = make_temp_filename('testLocalhostCopyEvents')
        worker = self._task.copy("/etc/hosts", dest, nodes=HOSTNAME,
                                 handler=test_eh)
        # run task
        self._task.resume()
        os.unlink(dest)
        self.assertEqual(test_eh.flags, EV_START | EV_PICKUP | EV_HUP | EV_CLOSE)

    def testWorkerAbort(self):
        task = task_self()

        # Test worker.abort() in an event handler.
        class AbortOnTimer(EventHandler):
            def __init__(self, worker):
                EventHandler.__init__(self)
                self.ext_worker = worker
                self.testtimer = False
            def ev_timer(self, timer):
                self.ext_worker.abort()
                self.ext_worker.abort()  # safe but no effect
                self.testtimer = True

        aot = AbortOnTimer(task.shell("sleep 10", nodes=HOSTNAME))
        self.assertEqual(aot.testtimer, False)
        task.timer(1.5, handler=aot)
        task.resume()
        self.assertEqual(aot.testtimer, True)

    def testWorkerAbortSanity(self):
        task = task_self()
        worker = task.shell("sleep 1", nodes=HOSTNAME)
        worker.abort()

        # test noop abort() on unscheduled worker
        worker = WorkerSsh(HOSTNAME, command="sleep 1", handler=None,
                           timeout=None)
        worker.abort()

    def testLocalhostRCopy(self):
        try:
            dest = make_temp_dir('testLocalhostRCopy')
            # use fake node 'aaa' to test rank > 0
            worker = self._task.rcopy("/etc/hosts", dest, "aaa,%s" % HOSTNAME,
                                      handler=None, timeout=10)
            self._task.resume()
            self.assertEqual(worker.source, "/etc/hosts")
            self.assertEqual(worker.dest, dest)
            self.assertTrue(os.path.exists(os.path.join(dest, "hosts.%s" % HOSTNAME)))
        finally:
            shutil.rmtree(dest, ignore_errors=True)

    def testLocalhostExplicitSshReverseCopy(self):
        dest = make_temp_dir('testLocalhostExplicitSshRCopy')
        try:
            worker = WorkerSsh(HOSTNAME, source="/etc/hosts", dest=dest,
                               handler=None, timeout=10, reverse=True)
            self._task.schedule(worker)
            self._task.resume()
            self.assertEqual(worker.source, "/etc/hosts")
            self.assertEqual(worker.dest, dest)
            self.assertTrue(os.path.exists(os.path.join(dest, "hosts.%s" % HOSTNAME)))
        finally:
            shutil.rmtree(dest, ignore_errors=True)

    def testLocalhostExplicitSshReverseCopyDir(self):
        dtmp_src = make_temp_dir('src')
        dtmp_dst = make_temp_dir('testLocalhostExplicitSshReverseCopyDir')
        try:
            os.mkdir(os.path.join(dtmp_src, "lev1_a"))
            os.mkdir(os.path.join(dtmp_src, "lev1_b"))
            os.mkdir(os.path.join(dtmp_src, "lev1_a", "lev2"))
            worker = WorkerSsh(HOSTNAME, source=dtmp_src, dest=dtmp_dst,
                               handler=None, timeout=30, reverse=True)
            self._task.schedule(worker)
            self._task.resume()
            self.assertTrue(os.path.exists(os.path.join(dtmp_dst,
                "%s.%s" % (os.path.basename(dtmp_src), HOSTNAME), "lev1_a", "lev2")))
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
            worker = WorkerSsh(HOSTNAME, source=dtmp_src, dest=dtmp_dst,
                               handler=None, timeout=30, reverse=True)
            self._task.schedule(worker)
            self._task.resume()
            self.assertTrue(os.path.exists(os.path.join(dtmp_dst,
                "%s.%s" % (os.path.basename(dtmp_src), HOSTNAME), "lev1_a", "lev2")))
        finally:
            shutil.rmtree(dtmp_dst, ignore_errors=True)
            shutil.rmtree(dtmp_src, ignore_errors=True)

    def testErroneousSshPath(self):
        try:
            self._task.set_info("ssh_path", "/wrong/path/to/ssh")
            # init worker
            worker = self._task.shell("/bin/echo ok", nodes=HOSTNAME)
            # run task
            self._task.resume()
            self.assertEqual(self._task.max_retcode(), 255)
        finally:
            # restore fanout value
            self._task.set_info("ssh_path", None)

    class TEventHandlerEvCountChecker(EventHandler):
        """simple event count validator"""

        def __init__(self):
            self.start_count = 0
            self.pickup_count = 0
            self.hup_count = 0
            self.close_count = 0

        def ev_start(self, worker):
            self.start_count += 1

        def ev_pickup(self, worker):
            self.pickup_count += 1

        def ev_hup(self, worker):
            self.hup_count += 1

        def ev_close(self, worker):
            self.close_count += 1

    def testWorkerEventCount(self):
        test_eh = self.__class__.TEventHandlerEvCountChecker()
        nodes = "localhost,%s" % HOSTNAME
        worker = self._task.shell("/bin/hostname", nodes=nodes, handler=test_eh)
        self._task.resume()
        # test event count
        self.assertEqual(test_eh.pickup_count, 2)
        self.assertEqual(test_eh.hup_count, 2)
        self.assertEqual(test_eh.start_count, 1)
        self.assertEqual(test_eh.close_count, 1)

    def test_last_deprecated(self):

        class TestHandlerHandler(EventHandler):
            def ev_read(self, worker):
                with warnings.catch_warnings(record=True) as wngs:
                    warnings.simplefilter("always")
                    self.node, self.msg = worker.last_read()
                    assert len(wngs) == 1
                    assert issubclass(wngs[-1].category, DeprecationWarning)
            def ev_hup(self, worker):
                with warnings.catch_warnings(record=True) as wngs:
                    warnings.simplefilter("always")
                    self.node, self.rc = worker.last_retcode()
                    assert len(wngs) == 1
                    assert issubclass(wngs[-1].category, DeprecationWarning)

        eh = TestHandlerHandler()
        reader = self._task.shell("echo foobar", nodes=HOSTNAME, handler=eh)
        self._task.resume()
        self.assertEqual(eh.node, HOSTNAME)
        self.assertEqual(eh.rc, 0)
