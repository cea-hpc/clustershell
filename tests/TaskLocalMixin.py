# ClusterShell (local) test suite
# Written by S. Thiell

"""Unit test for ClusterShell Task (local)"""

import copy
import os
import signal
import socket
import threading
import time
import warnings

from ClusterShell.Defaults import DEFAULTS
from ClusterShell.Event import EventHandler
from ClusterShell.Task import *
from ClusterShell.Worker.Exec import ExecWorker
from ClusterShell.Worker.Worker import StreamWorker, WorkerSimple
from ClusterShell.Worker.Worker import WorkerBadArgumentError
from ClusterShell.Worker.Worker import FANOUT_UNLIMITED


def _test_print_debug(task, s):
    # Use custom task info (prefix 'user_' is recommended)
    task.set_info("user_print_debug_last", s)

class TaskLocalMixin(object):
    """Mixin test case class: should be overrided and used in multiple
    inheritance with unittest.TestCase"""

    def setUp(self):
        warnings.simplefilter("once")
        # save original fanout value
        self.fanout_orig = task_self().info("fanout")

    def tearDown(self):
        # restore original fanout value
        task_self().set_info("fanout", self.fanout_orig)
        warnings.resetwarnings()

    def testSimpleCommand(self):
        task = task_self()
        # init worker
        worker = task.shell("/bin/hostname")
        # run task
        task.resume()

    def testSimpleDualTask(self):
        task0 = task_self()
        worker1 = task0.shell("/bin/hostname")
        worker2 = task0.shell("/bin/uname -a")
        task0.resume()
        b1 = copy.copy(worker1.read())
        b2 = copy.copy(worker2.read())
        task1 = task_self()
        self.assertTrue(task1 is task0)
        worker1 = task1.shell("/bin/hostname")
        worker2 = task1.shell("/bin/uname -a")
        task1.resume()
        self.assertEqual(worker2.read(), b2)
        self.assertEqual(worker1.read(), b1)

    def testSimpleCommandNoneArgs(self):
        task = task_self()
        # init worker
        worker = task.shell("/bin/hostname", nodes=None, handler=None)
        # run task
        task.resume()

    def testSimpleMultipleCommands(self):
        task = task_self()
        # run commands
        workers = []
        for i in range(0, 100):
            workers.append(task.shell("/bin/hostname"))
        task.resume()
        # verify results
        hn = socket.gethostname()
        for i in range(0, 100):
            t_hn = workers[i].read().splitlines()[0]
            self.assertEqual(t_hn.decode('utf-8'), hn)

    def testHugeOutputCommand(self):
        task = task_self()

        # init worker
        worker = task.shell("for i in $(seq 1 100000); do echo -n ' huge! '; done")

        # run task
        task.resume()
        self.assertEqual(worker.retcode(), 0)
        self.assertEqual(len(worker.read()), 700000)

    # task configuration
    def testTaskInfo(self):
        task = task_self()
        fanout = task.info("fanout")
        self.assertEqual(fanout, DEFAULTS.fanout)

    def testSimpleCommandTimeout(self):
        task = task_self()

        # init worker
        worker = task.shell("/bin/sleep 30")

        # run task
        self.assertRaises(TimeoutError, task.resume, 1)

    def testSimpleCommandNoTimeout(self):
        task = task_self()

        # init worker
        worker = task.shell("/bin/sleep 1")

        try:
            # run task
            task.resume(3)
        except TimeoutError:
            self.fail("did detect timeout")

    def testSimpleCommandNoTimeout(self):
        task = task_self()

        # init worker
        worker = task.shell("/bin/usleep 900000")

        try:
            # run task
            task.resume(1)
        except TimeoutError:
            self.fail("did detect timeout")

    def testWorkersTimeout(self):
        task = task_self()

        # init worker
        worker = task.shell("/bin/sleep 6", timeout=1)

        worker = task.shell("/bin/sleep 6", timeout=0.5)

        try:
            # run task
            task.resume()
        except TimeoutError:
            self.fail("did detect timeout")

        self.assertTrue(worker.did_timeout())

    def testWorkersTimeout2(self):
        task = task_self()

        worker = task.shell("/bin/sleep 10", timeout=1)

        worker = task.shell("/bin/sleep 10", timeout=0.5)

        try:
            # run task
            task.resume()
        except TimeoutError:
            self.fail("did detect task timeout")

    def testWorkersAndTaskTimeout(self):
        task = task_self()

        worker = task.shell("/bin/sleep 10", timeout=5)

        worker = task.shell("/bin/sleep 10", timeout=3)

        self.assertRaises(TimeoutError, task.resume, 1)

    def testLocalEmptyBuffer(self):
        task = task_self()
        task.shell("true", key="empty")
        task.resume()
        self.assertEqual(task.key_buffer("empty"), b'')
        for buf, keys in task.iter_buffers():
            self.assertTrue(False)

    def testLocalEmptyError(self):
        task = task_self()
        task.shell("true", key="empty")
        task.resume()
        self.assertEqual(task.key_error("empty"), b'')
        for buf, keys in task.iter_errors():
            self.assertTrue(False)

    def testTaskKeyErrors(self):
        task = task_self()
        task.shell("true", key="dummy")
        task.resume()
        # task.key_retcode raises KeyError
        self.assertRaises(KeyError, task.key_retcode, "not_known")
        # unlike task.key_buffer/error
        self.assertEqual(task.key_buffer("not_known"), b'')
        self.assertEqual(task.key_error("not_known"), b'')

    def testLocalSingleLineBuffers(self):
        task = task_self()

        task.shell("/bin/echo foo", key="foo")
        task.shell("/bin/echo bar", key="bar")
        task.shell("/bin/echo bar", key="bar2")
        task.shell("/bin/echo foobar", key="foobar")
        task.shell("/bin/echo foobar", key="foobar2")
        task.shell("/bin/echo foobar", key="foobar3")

        task.resume()

        self.assertEqual(task.key_buffer("foobar"), b"foobar")

        cnt = 3
        for buf, keys in task.iter_buffers():
            cnt -= 1
            if buf == b"foo":
                self.assertEqual(len(keys), 1)
                self.assertEqual(keys[0], "foo")
            elif buf == b"bar":
                self.assertEqual(len(keys), 2)
                self.assertTrue(keys[0] == "bar" or keys[1] == "bar")
            elif buf == b"foobar":
                self.assertEqual(len(keys), 3)

        self.assertEqual(cnt, 0)

    def testLocalBuffers(self):
        task = task_self()

        task.shell("/usr/bin/printf 'foo\nbar\n'", key="foobar")
        task.shell("/usr/bin/printf 'foo\nbar\n'", key="foobar2")
        task.shell("/usr/bin/printf 'foo\nbar\n'", key="foobar3")
        task.shell("/usr/bin/printf 'foo\nbar\nxxx\n'", key="foobarX")
        task.shell("/usr/bin/printf 'foo\nfuu\n'", key="foofuu")
        task.shell("/usr/bin/printf 'faa\nber\n'", key="faaber")
        task.shell("/usr/bin/printf 'foo\nfuu\n'", key="foofuu2")

        task.resume()

        cnt = 4
        for buf, keys in task.iter_buffers():
            cnt -= 1
            if buf == b"faa\nber\n":
                self.assertEqual(len(keys), 1)
                self.assertTrue(keys[0].startswith("faaber"))
            elif buf == b"foo\nfuu\n":
                self.assertEqual(len(keys), 2)
                self.assertTrue(keys[0].startswith("foofuu"))
            elif buf == b"foo\nbar\n":
                self.assertEqual(len(keys), 3)
            elif buf == b"foo\nbar\nxxx\n":
                self.assertEqual(len(keys), 1)
                self.assertTrue(keys[0].startswith("foobarX"))
                self.assertTrue(keys[0].startswith("foobar"))
            elif buf == b"foo\nbar\nxxx\n":
                self.assertEqual(len(keys), 1)
                self.assertTrue(keys[0].startswith("foobarX"))

        self.assertEqual(cnt, 0)

    def testLocalRetcodes(self):
        task = task_self()

        # 0 ['worker0']
        # 1 ['worker1']
        # 2 ['worker2']
        # 3 ['worker3bis', 'worker3']
        # 4 ['worker4']
        # 5 ['worker5bis', 'worker5']

        task.shell("true", key="worker0")
        task.shell("false", key="worker1")
        task.shell("/bin/sh -c 'exit 1'", key="worker1bis")
        task.shell("/bin/sh -c 'exit 2'", key="worker2")
        task.shell("/bin/sh -c 'exit 3'", key="worker3")
        task.shell("/bin/sh -c 'exit 3'", key="worker3bis")
        task.shell("/bin/sh -c 'exit 4'", key="worker4")
        task.shell("/bin/sh -c 'exit 1'", key="worker4")
        task.shell("/bin/sh -c 'exit 5'", key="worker5")
        task.shell("/bin/sh -c 'exit 5'", key="worker5bis")

        task.resume()

        # test key_retcode(key)
        self.assertEqual(task.key_retcode("worker2"), 2) # single
        self.assertEqual(task.key_retcode("worker4"), 4) # multiple
        self.assertRaises(KeyError, task.key_retcode, "worker9") # error

        cnt = 6
        for rc, keys in task.iter_retcodes():
            cnt -= 1
            if rc == 0:
                self.assertEqual(len(keys), 1)
                self.assertEqual(keys[0], "worker0" )
            elif rc == 1:
                self.assertEqual(len(keys), 3)
                self.assertTrue(keys[0] in ("worker1", "worker1bis", "worker4"))
            elif rc == 2:
                self.assertEqual(len(keys), 1)
                self.assertEqual(keys[0], "worker2" )
            elif rc == 3:
                self.assertEqual(len(keys), 2)
                self.assertTrue(keys[0] in ("worker3", "worker3bis"))
            elif rc == 4:
                self.assertEqual(len(keys), 1)
                self.assertEqual(keys[0], "worker4" )
            elif rc == 5:
                self.assertEqual(len(keys), 2)
                self.assertTrue(keys[0] in ("worker5", "worker5bis"))

        self.assertEqual(cnt, 0)

        # test max retcode API
        self.assertEqual(task.max_retcode(), 5)

    def testCustomPrintDebug(self):
        task = task_self()

        # first test that simply changing print_debug doesn't enable debug
        default_print_debug = task.info("print_debug")
        try:
            task.set_info("print_debug", _test_print_debug)
            task.shell("true")
            task.resume()
            self.assertEqual(task.info("user_print_debug_last"), None)

            # with debug enabled, it should work
            task.set_info("debug", True)
            task.shell("true")
            task.resume()
            self.assertEqual(task.info("user_print_debug_last"), "POPEN: true")

            # remove debug
            task.set_info("debug", False)
            # re-run for default print debug callback code coverage
            task.shell("true")
            task.resume()
        finally:
            # restore default print_debug
            task.set_info("debug", False)
            task.set_info("print_debug", default_print_debug)

    def testLocalRCBufferGathering(self):
        task = task_self()

        task.shell("/usr/bin/printf 'foo\nbar\n' && exit 1", key="foobar5")
        task.shell("/usr/bin/printf 'foo\nbur\n' && exit 1", key="foobar2")
        task.shell("/usr/bin/printf 'foo\nbar\n' && exit 1", key="foobar3")
        task.shell("/usr/bin/printf 'foo\nfuu\n' && exit 5", key="foofuu")
        task.shell("/usr/bin/printf 'foo\nbar\n' && exit 4", key="faaber")
        task.shell("/usr/bin/printf 'foo\nfuu\n' && exit 1", key="foofuu2")

        task.resume()

        foobur = b"foo\nbur"

        cnt = 5
        for rc, keys in task.iter_retcodes():
            for buf, keys in task.iter_buffers(keys):
                cnt -= 1
                if buf == b"foo\nbar":
                    self.assertTrue(rc == 1 or rc == 4)
                elif foobur == buf:
                    self.assertEqual(rc, 1)
                elif b"foo\nfuu" == buf:
                    self.assertTrue(rc == 1 or rc == 5)
                else:
                    self.fail("invalid buffer returned")

        self.assertEqual(cnt, 0)

    def testLocalBufferRCGathering(self):
        task = task_self()

        task.shell("/usr/bin/printf 'foo\nbar\n' && exit 1", key="foobar5")
        task.shell("/usr/bin/printf 'foo\nbur\n' && exit 1", key="foobar2")
        task.shell("/usr/bin/printf 'foo\nbar\n' && exit 1", key="foobar3")
        task.shell("/usr/bin/printf 'foo\nfuu\n' && exit 5", key="foofuu")
        task.shell("/usr/bin/printf 'foo\nbar\n' && exit 4", key="faaber")
        task.shell("/usr/bin/printf 'foo\nfuu\n' && exit 1", key="foofuu2")

        task.resume()

        cnt = 9
        for buf, keys in task.iter_buffers():
            for rc, keys in task.iter_retcodes(keys):
                # same checks as testLocalRCBufferGathering
                cnt -= 1
                if buf == b"foo\nbar\n":
                    self.assertTrue(rc == 1 and rc == 4)
                elif buf == b"foo\nbur\n":
                    self.assertEqual(rc, 1)
                elif buf == b"foo\nbuu\n":
                    self.assertEqual(rc, 5)

        self.assertEqual(cnt, 0)

    def testLocalWorkerWrites(self):
        # Simple test: we write to a cat process and see if read matches.
        task = task_self()
        worker = task.shell("cat")
        # write first line
        worker.write(b"foobar\n")
        # write second line
        worker.write(b"deadbeaf\n")
        worker.set_write_eof()
        task.resume()
        self.assertEqual(worker.read(), b"foobar\ndeadbeaf")

    def testLocalWorkerWritesBcExample(self):
        # Other test: write a math statement to a bc process and check
        # for the result.
        task = task_self()
        worker = task.shell("bc -q")

        # write statement
        worker.write(b"2+2\n")
        worker.set_write_eof()

        # execute
        task.resume()

        # read result
        self.assertEqual(worker.read(), b"4")

    def testLocalWorkerWritesWithLateEOF(self):
        class LateEOFHandler(EventHandler):
            def ev_start(self, worker):
                worker.set_write_eof()

        task = task_self()
        worker = task.shell("(sleep 1; cat)", handler=LateEOFHandler())
        worker.write(b"cracoucasse\n")
        task.resume()

        # read result
        self.assertEqual(worker.read(), b"cracoucasse")

    def testEscape(self):
        task = task_self()
        worker = task.shell("export CSTEST=foobar; /bin/echo \$CSTEST | sed 's/\ foo/bar/'")
        # execute
        task.resume()
        # read result
        self.assertEqual(worker.read(), b"$CSTEST")

    def testEscape2(self):
        task = task_self()
        worker = task.shell("export CSTEST=foobar; /bin/echo $CSTEST | sed 's/\ foo/bar/'")
        # execute
        task.resume()
        # read result
        self.assertEqual(worker.read(), b"foobar")

    def testEngineClients(self):
        # private EngineClient stream basic tests
        class StartHandler(EventHandler):
            def __init__(self, test):
                self.test = test
            def ev_start(self, worker):
                if len(streams) == 2:
                    for streamd in streams:
                        for name, stream in streamd.items():
                            self.test.assertTrue(name in ['stdin', 'stdout', 'stderr'])
                            if name == 'stdin':
                                self.test.assertTrue(stream.writable())
                                self.test.assertFalse(stream.readable())
                            else:
                                self.test.assertTrue(stream.readable())
                                self.test.assertFalse(stream.writable())

        task = task_self()
        shdl = StartHandler(self)
        worker1 = task.shell("/bin/hostname", handler=shdl)
        worker2 = task.shell("echo ok", handler=shdl)
        engine = task._engine
        clients = engine.clients()
        self.assertEqual(len(clients), 2)
        streams = [client.streams for client in clients]
        task.resume()

    def testEnginePorts(self):
        task = task_self()
        worker = task.shell("/bin/hostname")
        self.assertEqual(len(task._engine.ports()), 1)
        task.resume()

    def testSimpleCommandAutoclose(self):
        task = task_self()
        worker = task.shell("/bin/sleep 3; /bin/uname", autoclose=True)
        task.resume()
        self.assertEqual(worker.read(), None)

    def testTwoSimpleCommandsAutoclose(self):
        task = task_self()
        worker1 = task.shell("/bin/sleep 2; /bin/echo ok")
        worker2 = task.shell("/bin/sleep 3; /bin/uname", autoclose=True)
        task.resume()
        self.assertEqual(worker1.read(), b"ok")
        self.assertEqual(worker2.read(), None)

    def test_unregister_stream_autoclose(self):
        task = task_self()
        worker1 = task.shell("/bin/sleep 2; /bin/echo ok")
        worker2 = task.shell("/bin/sleep 3; /bin/uname", autoclose=True)
        # the following leads to a call to unregister_stream() with autoclose flag set
        worker3 = task.shell("sleep 1; echo blah | cat", autoclose=True)
        task.resume()
        self.assertEqual(worker1.read(), b"ok")
        self.assertEqual(worker2.read(), None)

    def testLocalWorkerErrorBuffers(self):
        task = task_self()
        w1 = task.shell("/usr/bin/printf 'foo bar\n' 1>&2", key="foobar", stderr=True)
        w2 = task.shell("/usr/bin/printf 'foo\nbar\n' 1>&2", key="foobar2", stderr=True)
        task.resume()
        self.assertEqual(w1.error(), b'foo bar')
        self.assertEqual(w2.error(), b'foo\nbar')

    def testLocalErrorBuffers(self):
        task = task_self()

        task.shell("/usr/bin/printf 'foo\nbar\n' 1>&2", key="foobar", stderr=True)
        task.shell("/usr/bin/printf 'foo\nbar\n' 1>&2", key="foobar2", stderr=True)
        task.shell("/usr/bin/printf 'foo\nbar\n 1>&2'", key="foobar3", stderr=True)
        task.shell("/usr/bin/printf 'foo\nbar\nxxx\n' 1>&2", key="foobarX", stderr=True)
        task.shell("/usr/bin/printf 'foo\nfuu\n' 1>&2", key="foofuu", stderr=True)
        task.shell("/usr/bin/printf 'faa\nber\n' 1>&2", key="faaber", stderr=True)
        task.shell("/usr/bin/printf 'foo\nfuu\n' 1>&2", key="foofuu2", stderr=True)

        task.resume()

        cnt = 4
        for buf, keys in task.iter_errors():
            cnt -= 1
            if buf == b"faa\nber\n":
                self.assertEqual(len(keys), 1)
                self.assertTrue(keys[0].startswith("faaber"))
            elif buf == b"foo\nfuu\n":
                self.assertEqual(len(keys), 2)
                self.assertTrue(keys[0].startswith("foofuu"))
            elif buf == b"foo\nbar\n":
                self.assertEqual(len(keys), 3)
                self.assertTrue(keys[0].startswith("foobar"))
            elif buf == b"foo\nbar\nxxx\n":
                self.assertEqual(len(keys), 1)
                self.assertTrue(keys[0].startswith("foobarX"))

        self.assertEqual(cnt, 0)

    def testTaskPrintDebug(self):
        task = task_self()
        # simple test, just run a task with debug on to improve test
        # code coverage
        task.set_info("debug", True)
        worker = task.shell("/bin/echo test")
        task.resume()
        task.set_info("debug", False)

    def testTaskAbortSelf(self):
        task = task_self()

        # abort(False) keeps current task_self() object
        task.abort()
        self.assertEqual(task, task_self())

        # abort(True) unbinds current task_self() object
        task.abort(True)
        self.assertNotEqual(task, task_self())

        # retry
        task = task_self()
        worker = task.shell("/bin/echo shouldnt see that")
        task.abort()
        self.assertEqual(task, task_self())

    def testTaskAbortHandler(self):

        class AbortOnReadTestHandler(EventHandler):
            def ev_read(self, worker):
                self.has_ev_read = True
                worker.task.abort()
                assert False, "Shouldn't reach this line"

        task = task_self()
        eh = AbortOnReadTestHandler()
        eh.has_ev_read = False
        task.shell("/bin/echo test", handler=eh)
        task.resume()
        self.assertTrue(eh.has_ev_read)

    def testWorkerSetKey(self):
        task = task_self()
        task.shell("/bin/echo foo", key="foo")
        worker = task.shell("/bin/echo foobar")
        worker.set_key("bar")
        task.resume()
        self.assertEqual(task.key_buffer("bar"), b"foobar")

    def testWorkerSimplePipeStdout(self):
        task = task_self()
        rfd, wfd = os.pipe()
        os.write(wfd, b"test\n")
        os.close(wfd)
        worker = WorkerSimple(os.fdopen(rfd), None, None, "pipe", None,
                              stderr=True, timeout=-1, autoclose=False,
                              closefd=False)
        self.assertEqual(worker.reader_fileno(), rfd)
        task.schedule(worker)
        task.resume()
        self.assertEqual(task.key_buffer("pipe"), b'test')
        dummy = os.fstat(rfd) # just to check that rfd is still valid here
                              # (worker keeps a reference of file object)
        # rfd will be closed when associated file is released

    def testWorkerSimplePipeStdErr(self):
        task = task_self()
        rfd, wfd = os.pipe()
        os.write(wfd, b"test\n")
        os.close(wfd)
        # be careful, stderr is arg #3
        worker = WorkerSimple(None, None, os.fdopen(rfd), "pipe", None,
                              stderr=True, timeout=-1, autoclose=False,
                              closefd=False)
        self.assertEqual(worker.error_fileno(), rfd)
        task.schedule(worker)
        task.resume()
        self.assertEqual(task.key_error("pipe"), b'test')
        dummy = os.fstat(rfd) # just to check that rfd is still valid here
        # rfd will be closed when associated file is released

    def testWorkerSimplePipeStdin(self):
        task = task_self()
        rfd, wfd = os.pipe()
        # be careful, stdin is arg #2
        worker = WorkerSimple(None, os.fdopen(wfd, "w"), None, "pipe", None,
                              stderr=True, timeout=-1, autoclose=False,
                              closefd=False)
        self.assertEqual(worker.writer_fileno(), wfd)
        worker.write(b"write to stdin test\n")
        worker.set_write_eof() # close stream after write!
        task.schedule(worker)
        task.resume()
        self.assertEqual(os.read(rfd, 1024), b"write to stdin test\n")
        os.close(rfd)
        # wfd will be closed when associated file is released

    # FIXME: reconsider this kind of test (which now must fail) especially
    #        when using epoll engine, as soon as testsuite is improved (#95).
    #def testWorkerSimpleFile(self):
    #    """test WorkerSimple (file)"""
    #    task = task_self()
    #    # use tempfile
    #    tmpfile = tempfile.TemporaryFile()
    #    tmpfile.write("one line without EOL")
    #    tmpfile.seek(0)
    #    worker = WorkerSimple(tmpfile, None, None, "file", None, 0, True)
    #    task.schedule(worker)
    #    task.resume()
    #    self.assertEqual(worker.read(), "one line without EOL")

    def testInterruptEngine(self):
        class KillerThread(threading.Thread):
            def run(self):
                time.sleep(1)
                os.kill(self.pidkill, signal.SIGUSR1)
                task_wait()

        kth = KillerThread()
        kth.pidkill = os.getpid()

        task = task_self()
        signal.signal(signal.SIGUSR1, lambda x, y: None)
        task.shell("/bin/sleep 2", timeout=5)

        kth.start()
        task.resume()

    def testSignalWorker(self):
        class TestSignalHandler(EventHandler):
            def ev_read(self, worker):
                pid = int(worker.current_msg)
                os.kill(pid, signal.SIGTERM)
        task = task_self()
        wrk = task.shell("echo $$; /bin/sleep 2", handler=TestSignalHandler())
        task.resume()
        self.assertEqual(wrk.retcode(), 128 + signal.SIGTERM)

    def testShellDelayedIO(self):
        class TestDelayedHandler(EventHandler):
            def __init__(self, target_worker=None):
                self.target_worker = target_worker
                self.counter = 0
            def ev_read(self, worker):
                self.counter += 1
                if self.counter == 100:
                    worker.write(b"another thing to read\n")
                    worker.set_write_eof()
            def ev_timer(self, timer):
                self.target_worker.write(b"something to read\n" * 300)

        task = task_self()
        hdlr = TestDelayedHandler()
        reader = task.shell("cat", handler=hdlr)
        timer = task.timer(0.6, handler=TestDelayedHandler(reader))
        task.resume()
        self.assertEqual(hdlr.counter, 301)

    def testSimpleCommandReadNoEOL(self):
        task = task_self()
        # init worker
        worker = task.shell("echo -n okay")
        # run task
        task.resume()
        self.assertEqual(worker.read(), b"okay")

    def testLocalFanout(self):
        task = task_self()
        task.set_info("fanout", 3)

        # Test #1: simple
        for i in range(0, 10):
            worker = task.shell("echo test %d" % i)
        task.resume()

        # Test #2: fanout change during run
        class TestFanoutChanger(EventHandler):
            def ev_timer(self, timer):
                task_self().set_info("fanout", 1)
        timer = task.timer(2.0, handler=TestFanoutChanger())
        for i in range(0, 10):
            worker = task.shell("sleep 0.5")
        task.resume()

    def testLocalWorkerFanout(self):

        class TestRunCountChecker(EventHandler):

            def __init__(self):
                self.workers = []
                self.max_run_cnt = 0

            def ev_start(self, worker):
                self.workers.append(worker)

            def ev_read(self, worker):
                run_cnt = sum(e.registered for w in self.workers
                              for e in w._engine_clients())
                self.max_run_cnt = max(self.max_run_cnt, run_cnt)

        task = task_self()

        TEST_FANOUT = 3
        task.set_info("fanout", TEST_FANOUT)

        # TEST 1 - default worker fanout
        eh = TestRunCountChecker()
        for i in range(10):
            task.shell("echo foo", handler=eh)
        task.resume()
        # Engine fanout should be enforced
        self.assertTrue(eh.max_run_cnt <= TEST_FANOUT)

        # TEST 1bis - default worker fanout with ExecWorker
        eh = TestRunCountChecker()
        worker = ExecWorker(nodes='foo[0-9]', handler=eh, command='echo bar')
        task.schedule(worker)
        task.resume()
        # Engine fanout should be enforced
        self.assertTrue(eh.max_run_cnt <= TEST_FANOUT)

        # TEST 2 - create n x workers using worker.fanout
        eh = TestRunCountChecker()
        for i in range(10):
            task.shell("echo foo", handler=eh)._fanout = 1
        task.resume()
        # max_run_cnt should reach the total number of workers
        self.assertEqual(eh.max_run_cnt, 10)

        # TEST 2bis - create ExecWorker with multiple clients [larger fanout]
        eh = TestRunCountChecker()
        worker = ExecWorker(nodes='foo[0-9]', handler=eh, command='echo bar')
        worker._fanout = 5
        task.schedule(worker)
        task.resume()
        # max_run_cnt should reach worker._fanout
        self.assertEqual(eh.max_run_cnt, 5)

        # TEST 2ter - create ExecWorker with multiple clients [smaller fanout]
        eh = TestRunCountChecker()
        worker = ExecWorker(nodes='foo[0-9]', handler=eh, command='echo bar')
        worker._fanout = 1
        task.schedule(worker)
        task.resume()
        # max_run_cnt should reach worker._fanout
        self.assertEqual(eh.max_run_cnt, 1)

        # TEST 4 - create workers using unlimited fanout
        eh = TestRunCountChecker()
        for i in range(10):
            w = task.shell("echo foo", handler=eh)
            w._fanout = FANOUT_UNLIMITED
        task.resume()
        # max_run_cnt should reach the total number of workers
        self.assertEqual(eh.max_run_cnt, 10)

        # TEST 4bis - create ExecWorker with unlimited fanout
        eh = TestRunCountChecker()
        worker = ExecWorker(nodes='foo[0-9]', handler=eh, command='echo bar')
        worker._fanout = FANOUT_UNLIMITED
        task.schedule(worker)
        task.resume()
        # max_run_cnt should reach the total number of clients (10)
        self.assertEqual(eh.max_run_cnt, 10)

    def testPopenBadArgumentOption(self):
	    # Check code < 1.4 compatibility
        self.assertRaises(WorkerBadArgumentError, WorkerPopen, None, None)
	    # As of 1.4, ValueError is raised for missing parameter
        self.assertRaises(ValueError, WorkerPopen, None, None) # 1.4+

    def testWorkerAbort(self):
        task = task_self()

        class AbortOnTimer(EventHandler):
            def __init__(self, worker):
                EventHandler.__init__(self)
                self.ext_worker = worker
                self.testtimer = False
            def ev_timer(self, timer):
                self.ext_worker.abort()
                self.ext_worker.abort()  # safe but no effect
                self.testtimer = True

        aot = AbortOnTimer(task.shell("sleep 10"))
        self.assertEqual(aot.testtimer, False)
        task.timer(1.0, handler=aot)
        task.resume()
        self.assertEqual(aot.testtimer, True)

    def testWorkerAbortSanity(self):
        task = task_self()
        worker = task.shell("sleep 1")
        worker.abort()

        # test noop abort() on unscheduled worker
        worker = WorkerPopen("sleep 1")
        worker.abort()

    def testKBI(self):
        class TestKBI(EventHandler):
            def ev_read(self, worker):
                raise KeyboardInterrupt
        task = task_self()
        ok = False
        try:
            task.run("echo test; sleep 5", handler=TestKBI())
        except KeyboardInterrupt:
            ok = True
            # We want to test here if engine clients are not properly
            # cleaned, or results are not cleaned on re-run()
            #
            # cannot assert on task.iter_retcodes() as we are not sure in
            # what order the interpreter will proceed
            #self.assertEqual(len(list(task.iter_retcodes())), 1)
            self.assertEqual(len(list(task.iter_buffers())), 1)
            # hard to test without really checking the number of clients of engine
            self.assertEqual(len(task._engine._clients), 0)
            task.run("echo newrun")
            self.assertEqual(len(task._engine._clients), 0)
            self.assertEqual(len(list(task.iter_retcodes())), 1)
            self.assertEqual(len(list(task.iter_buffers())), 1)
            self.assertEqual(bytes(list(task.iter_buffers())[0][0]), b"newrun")
        self.assertTrue(ok, "KeyboardInterrupt not raised")

    # From old TaskAdvancedTest.py:

    def testTaskRun(self):
        wrk = task_self().shell("true")
        task_self().run()

    def testTaskRunTimeout(self):
        wrk = task_self().shell("sleep 1")
        self.assertRaises(TimeoutError, task_self().run, 0.3)

        wrk = task_self().shell("sleep 1")
        self.assertRaises(TimeoutError, task_self().run, timeout=0.3)

    def testTaskShellRunLocal(self):
        wrk = task_self().run("false")
        self.assertTrue(wrk)
        self.assertEqual(task_self().max_retcode(), 1)

        # Timeout in shell() fashion way.
        wrk = task_self().run("sleep 1", timeout=0.3)
        self.assertTrue(wrk)
        self.assertEqual(task_self().num_timeout(), 1)

    def testTaskEngineUserSelection(self):
        task_terminate()
        try:
            DEFAULTS.engine = 'select'
            self.assertEqual(task_self().info('engine'), 'select')
            task_terminate()
        finally:
            DEFAULTS.engine = 'auto'

    def testTaskEngineWrongUserSelection(self):
        try:
            task_terminate()
            DEFAULTS.engine = 'foobar'
            # Check for KeyError in case of wrong engine request
            self.assertRaises(KeyError, task_self)
        finally:
            DEFAULTS.engine = 'auto'

        task_terminate()

    def testTaskNewThread1(self):
        # create a task in a new thread
        task = Task()

        match = "test"

        # schedule a command in that task
        worker = task.shell("/bin/echo %s" % match)

        # run this task
        task.resume()

        # wait for the task to complete
        task_wait()

        # verify that the worker has completed
        self.assertEqual(worker.read(), match.encode('ascii'))

        # stop task
        task.abort()

    def testTaskInNewThread2(self):
        # create a task in a new thread
        task = Task()

        match = "again"

        # schedule a command in that task
        worker = task.shell("/bin/echo %s" % match)

        # run this task
        task.resume()

        # wait for the task to complete
        task_wait()

        # verify that the worker has completed
        self.assertEqual(worker.read(), match.encode('ascii'))

        # stop task
        task.abort()

    def testTaskInNewThread3(self):
        # create a task in a new thread
        task = Task()

        match = "once again"

        # schedule a command in that task
        worker = task.shell("/bin/echo %s" % match)

        # run this task
        task.resume()

        # wait for the task to complete
        task_wait()

        # verify that the worker has completed
        self.assertEqual(worker.read(), match.encode('ascii'))

        # stop task
        task.abort()

    def testLocalPickupHup(self):

        class PickupHupCounter(EventHandler):
            def __init__(self):
                self.pickup_count = 0
                self.hup_count = 0
            def ev_pickup(self, worker):
                self.pickup_count += 1
            def ev_hup(self, worker):
                self.hup_count += 1

        task = task_self()
        fanout = task.info("fanout")
        try:
            task.set_info("fanout", 3)

            # Test #1: simple
            chdlr = PickupHupCounter()
            for i in range(0, 10):
                task.shell("/bin/echo test %d" % i, handler=chdlr)
            task.resume()
            self.assertEqual(chdlr.pickup_count, 10)
            self.assertEqual(chdlr.hup_count, 10)

            # Test #2: fanout change during run
            chdlr = PickupHupCounter()
            class TestFanoutChanger(EventHandler):
                def ev_timer(self, timer):
                    task_self().set_info("fanout", 1)
            timer = task.timer(2.0, handler=TestFanoutChanger())
            for i in range(0, 10):
                task.shell("sleep 0.5", handler=chdlr)
            task.resume()
            self.assertEqual(chdlr.pickup_count, 10)
            self.assertEqual(chdlr.hup_count, 10)
        finally:
            # restore original fanout value
            task.set_info("fanout", fanout)

    def test_shell_nostdin(self):
        # this shouldn't block if we do prevent the use of stdin
        task = task_self()
        task.shell("cat", stdin=False)
        task.resume()
        # same thing with run()
        task.run("cat", stdin=False)

    def test_mixed_worker_retcodes(self):
        """test Task retcode handling with mixed workers"""

        # This test case failed with CS <= 1.7.3
        # Conditions: task.max_retcode() set during runtime (not None)
        # and then a StreamWorker closing, thus calling Task._set_rc(rc=None)
        # To reproduce, we start a StreamWorker on first read of a ExecWorker.

        class TestH(EventHandler):
            def __init__(self, worker2):
                self.worker2 = worker2

            def ev_read(self, worker):
                worker.task.schedule(self.worker2)

        worker2 = StreamWorker(handler=None)
        worker1 = ExecWorker(nodes='localhost', handler=TestH(worker2),
                             command="echo ok")

        # Create pipe stream
        rfd1, wfd1 = os.pipe()
        worker2.set_reader("pipe1", rfd1, closefd=False)
        os.write(wfd1, b"test\n")
        os.close(wfd1)

        # Enable pipe1_msgtree
        task_self().set_default("pipe1_msgtree", True)

        task_self().schedule(worker1)
        task_self().run()

        self.assertEqual(worker1.node_buffer('localhost'), b"ok")
        self.assertEqual(worker1.node_retcode('localhost'), 0)
        self.assertEqual(worker2.read(sname="pipe1"), b"test")
        self.assertEqual(task_self().max_retcode(), 0)

    def testWorkerPopenKeyCompat(self):
        """test WorkerPopen.key attribute (compat with 1.6)"""
        # Was broken in 1.7 to 1.7.3 after StreamWorker changes
        task = task_self()
        worker = task.shell("echo ok", key="ok")
        self.assertEqual(worker.key, "ok")
        worker = WorkerPopen("echo foo", key="foo")
        self.assertEqual(worker.key, "foo")
        task.run()
