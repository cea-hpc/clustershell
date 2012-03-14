#!/usr/bin/env python
# ClusterShell (local) test suite
# Written by S. Thiell 2008-04-09


"""Unit test for ClusterShell Task (local)"""

import copy
import os
import signal
import sys
import time
import unittest

sys.path.insert(0, '../lib')

import ClusterShell

from ClusterShell.Event import EventHandler
from ClusterShell.NodeSet import NodeSet
from ClusterShell.Task import *
from ClusterShell.Worker.Worker import WorkerSimple, WorkerError
from ClusterShell.Worker.Worker import WorkerBadArgumentError

import socket

import threading
import tempfile


def _test_print_debug(task, s):
    # Use custom task info (prefix 'user_' is recommended)
    task.set_info("user_print_debug_last", s)

class TaskLocalTest(unittest.TestCase):

    def testSimpleCommand(self):
        """test simple command"""
        task = task_self()
        self.assert_(task != None)
        # init worker
        worker = task.shell("/bin/hostname")
        self.assert_(worker != None)
        # run task
        task.resume()

    def testSimpleDualTask(self):
        """test simple task doing 2 sequential jobs"""

        task0 = task_self()
        self.assert_(task0 != None)
        worker1 = task0.shell("/bin/hostname")
        worker2 = task0.shell("/bin/uname -a")
        task0.resume()
        b1 = copy.copy(worker1.read())
        b2 = copy.copy(worker2.read())
        task1 = task_self()
        self.assert_(task1 is task0)
        worker1 = task1.shell("/bin/hostname")
        self.assert_(worker1 != None)
        worker2 = task1.shell("/bin/uname -a")
        self.assert_(worker2 != None)
        task1.resume()
        self.assert_(worker2.read() == b2)
        self.assert_(worker1.read() == b1)

    def testSimpleCommandNoneArgs(self):
        """test simple command with args=None"""
        task = task_self()
        self.assert_(task != None)
        # init worker
        worker = task.shell("/bin/hostname", nodes=None, handler=None)
        self.assert_(worker != None)
        # run task
        task.resume()

    def testSimpleMultipleCommands(self):
        """test and verify results of 100 commands"""
        task = task_self()
        self.assert_(task != None)
        # run commands
        workers = []
        for i in range(0, 100):
            workers.append(task.shell("/bin/hostname"))
        task.resume()
        # verify results
        hn = socket.gethostname()
        for i in range(0, 100):
            t_hn = workers[i].read().splitlines()[0]
            self.assertEqual(t_hn, hn)

    def testHugeOutputCommand(self):
        """test huge output command"""
        task = task_self()
        self.assert_(task != None)

        # init worker
        worker = task.shell("python test_command.py --test huge --rc 0")
        self.assert_(worker != None)

        # run task
        task.resume()
        self.assertEqual(worker.retcode(), 0)
        self.assertEqual(len(worker.read()), 699999)

    # task configuration
    def testTaskInfo(self):
        """test task info"""
        task = task_self()
        self.assert_(task != None)

        fanout = task.info("fanout")
        self.assertEqual(fanout, Task._std_info["fanout"])

    def testSimpleCommandTimeout(self):
        """test simple command timeout"""
        task = task_self()
        self.assert_(task != None)

        # init worker
        worker = task.shell("/bin/sleep 30")
        self.assert_(worker != None)

        # run task
        self.assertRaises(TimeoutError, task.resume, 3)

    def testSimpleCommandNoTimeout(self):
        """test simple command exiting before timeout"""
        task = task_self()
        self.assert_(task != None)

        # init worker
        worker = task.shell("/bin/sleep 3")
        self.assert_(worker != None)

        try:
            # run task
            task.resume(5)
        except TimeoutError:
            self.fail("did detect timeout")

    def testSimpleCommandNoTimeout(self):
        """test simple command exiting just before timeout"""
        task = task_self()
        self.assert_(task != None)

        # init worker
        worker = task.shell("/bin/usleep 900000")
        self.assert_(worker != None)

        try:
            # run task
            task.resume(1)
        except TimeoutError:
            self.fail("did detect timeout")

    def testWorkersTimeout(self):
        """test workers with timeout"""
        task = task_self()
        self.assert_(task != None)

        # init worker
        worker = task.shell("/bin/sleep 6", timeout=3)
        self.assert_(worker != None)

        worker = task.shell("/bin/sleep 6", timeout=2)
        self.assert_(worker != None)

        try:
            # run task
            task.resume()
        except TimeoutError:
            self.fail("did detect timeout")

        self.assert_(worker.did_timeout())

    def testWorkersTimeout2(self):
        """test workers with timeout (more)"""
        task = task_self()
        self.assert_(task != None)

        worker = task.shell("/bin/sleep 10", timeout=5)
        self.assert_(worker != None)

        worker = task.shell("/bin/sleep 10", timeout=3)
        self.assert_(worker != None)

        try:
            # run task
            task.resume()
        except TimeoutError:
            self.fail("did detect task timeout")

    def testWorkersAndTaskTimeout(self):
        """test task and workers with timeout"""
        task = task_self()
        self.assert_(task != None)

        worker = task.shell("/bin/sleep 10", timeout=5)
        self.assert_(worker != None)

        worker = task.shell("/bin/sleep 10", timeout=3)
        self.assert_(worker != None)

        self.assertRaises(TimeoutError, task.resume, 2)

    def testLocalEmptyBuffer(self):
        """test task local empty buffer"""
        task = task_self()
        self.assert_(task != None)
        task.shell("true", key="empty")
        task.resume()
        self.assertEqual(task.key_buffer("empty"), '')
        for buf, keys in task.iter_buffers():
            self.assert_(False)

    def testLocalEmptyError(self):
        """test task local empty error buffer"""
        task = task_self()
        self.assert_(task != None)
        task.shell("true", key="empty")
        task.resume()
        self.assertEqual(task.key_error("empty"), '')
        for buf, keys in task.iter_errors():
            self.assert_(False)

    def testTaskKeyErrors(self):
        """test some task methods raising KeyError"""
        task = task_self()
        self.assert_(task != None)
        task.shell("true", key="dummy")
        task.resume()
        # task.key_retcode raises KeyError
        self.assertRaises(KeyError, task.key_retcode, "not_known")
        # unlike task.key_buffer/error
        self.assertEqual(task.key_buffer("not_known"), '')
        self.assertEqual(task.key_error("not_known"), '')

    def testLocalSingleLineBuffers(self):
        """test task local single line buffers gathering"""
        task = task_self()
        self.assert_(task != None)

        task.shell("/bin/echo foo", key="foo")
        task.shell("/bin/echo bar", key="bar")
        task.shell("/bin/echo bar", key="bar2")
        task.shell("/bin/echo foobar", key="foobar")
        task.shell("/bin/echo foobar", key="foobar2")
        task.shell("/bin/echo foobar", key="foobar3")

        task.resume()

        self.assert_(task.key_buffer("foobar") == "foobar")

        cnt = 3
        for buf, keys in task.iter_buffers():
            cnt -= 1
            if buf == "foo":
                self.assertEqual(len(keys), 1)
                self.assertEqual(keys[0], "foo")
            elif buf == "bar":
                self.assertEqual(len(keys), 2)
                self.assert_(keys[0] == "bar" or keys[1] == "bar")
            elif buf == "foobar":
                self.assertEqual(len(keys), 3)

        self.assertEqual(cnt, 0)

    def testLocalBuffers(self):
        """test task local multi-lines buffers gathering"""
        task = task_self()
        self.assert_(task != None)

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
            if buf == "faa\nber\n":
                self.assertEqual(len(keys), 1)
                self.assert_(keys[0].startswith("faaber"))
            elif buf == "foo\nfuu\n":
                self.assertEqual(len(keys), 2)
                self.assert_(keys[0].startswith("foofuu"))
            elif buf == "foo\nbar\n":
                self.assertEqual(len(keys), 3)
            elif buf == "foo\nbar\nxxx\n":
                self.assertEqual(len(keys), 1)
                self.assert_(keys[0].startswith("foobarX"))
                self.assert_(keys[0].startswith("foobar"))
            elif buf == "foo\nbar\nxxx\n":
                self.assertEqual(len(keys), 1)
                self.assert_(keys[0].startswith("foobarX"))

        self.assertEqual(cnt, 0)

    def testLocalRetcodes(self):
        """test task with local return codes"""
        task = task_self()
        self.assert_(task != None)

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
                self.assert_(keys[0] == "worker0" )
            elif rc == 1:
                self.assertEqual(len(keys), 3)
                self.assert_(keys[0] in ("worker1", "worker1bis", "worker4"))
            elif rc == 2:
                self.assertEqual(len(keys), 1)
                self.assert_(keys[0] == "worker2" )
            elif rc == 3:
                self.assertEqual(len(keys), 2)
                self.assert_(keys[0] in ("worker3", "worker3bis"))
            elif rc == 4:
                self.assertEqual(len(keys), 1)
                self.assert_(keys[0] == "worker4" )
            elif rc == 5:
                self.assertEqual(len(keys), 2)
                self.assert_(keys[0] in ("worker5", "worker5bis"))

        self.assertEqual(cnt, 0)

        # test max retcode API
        self.assertEqual(task.max_retcode(), 5)

    def testCustomPrintDebug(self):
        """test task with custom print debug callback"""
        task = task_self()
        self.assert_(task != None)

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
        """test task local rc+buffers gathering"""
        task = task_self()
        self.assert_(task != None)

        task.shell("/usr/bin/printf 'foo\nbar\n' && exit 1", key="foobar5")
        task.shell("/usr/bin/printf 'foo\nbur\n' && exit 1", key="foobar2")
        task.shell("/usr/bin/printf 'foo\nbar\n' && exit 1", key="foobar3")
        task.shell("/usr/bin/printf 'foo\nfuu\n' && exit 5", key="foofuu")
        task.shell("/usr/bin/printf 'foo\nbar\n' && exit 4", key="faaber")
        task.shell("/usr/bin/printf 'foo\nfuu\n' && exit 1", key="foofuu2")

        task.resume()
        
        foobur = "foo\nbur"

        cnt = 5
        for rc, keys in task.iter_retcodes():
            for buf, keys in task.iter_buffers(keys):
                cnt -= 1
                if buf == "foo\nbar":
                    self.assert_(rc == 1 or rc == 4)
                elif foobur == buf:
                    self.assertEqual(rc, 1)
                elif "foo\nfuu" == buf:
                    self.assert_(rc == 1 or rc == 5)
                else:
                    self.fail("invalid buffer returned")

        self.assertEqual(cnt, 0)
    
    def testLocalBufferRCGathering(self):
        """test task local buffers+rc gathering"""
        task = task_self()
        self.assert_(task != None)

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
                if buf == "foo\nbar\n":
                    self.assert_(rc == 1 and rc == 4)
                elif buf == "foo\nbur\n":
                    self.assertEqual(rc, 1)
                elif buf == "foo\nbuu\n":
                    self.assertEqual(rc, 5)

        self.assertEqual(cnt, 0)
    
    def testLocalWorkerWrites(self):
        """test worker writes (i)"""
        # Simple test: we write to a cat process and see if read matches.
        task = task_self()
        self.assert_(task != None)
        worker = task.shell("cat")
        # write first line
        worker.write("foobar\n")
        # write second line
        worker.write("deadbeaf\n")
        worker.set_write_eof()
        task.resume()

        self.assertEqual(worker.read(), "foobar\ndeadbeaf")

    def testLocalWorkerWritesBcExample(self):
        """test worker writes (ii)"""
        # Other test: write a math statement to a bc process and check
        # for the result.
        task = task_self()
        self.assert_(task != None)
        worker = task.shell("bc -q")

        # write statement
        worker.write("2+2\n")
        worker.set_write_eof()

        # execute
        task.resume()

        # read result
        self.assertEqual(worker.read(), "4")

    def testEscape(self):
        """test local worker (ssh) cmd with escaped variable"""
        task = task_self()
        self.assert_(task != None)
        worker = task.shell("export CSTEST=foobar; /bin/echo \$CSTEST | sed 's/\ foo/bar/'")
        # execute
        task.resume()
        # read result
        self.assertEqual(worker.read(), "$CSTEST")

    def testEscape2(self):
        """test local worker (ssh) cmd with non-escaped variable"""
        task = task_self()
        self.assert_(task != None)
        worker = task.shell("export CSTEST=foobar; /bin/echo $CSTEST | sed 's/\ foo/bar/'")
        # execute
        task.resume()
        # read result
        self.assertEqual(worker.read(), "foobar")

    def testEngineClients(self):
        """test Engine.clients() [private]"""
        task = task_self()
        self.assert_(task != None)
        worker = task.shell("/bin/hostname")
        self.assert_(worker != None)
        self.assertEqual(len(task._engine.clients()), 1)
        task.resume()

    def testEnginePorts(self):
        """test Engine.ports() [private]"""
        task = task_self()
        self.assert_(task != None)
        worker = task.shell("/bin/hostname")
        self.assert_(worker != None)
        self.assertEqual(len(task._engine.ports()), 1)
        task.resume()

    def testSimpleCommandAutoclose(self):
        """test simple command (autoclose)"""
        task = task_self()
        self.assert_(task != None)
        worker = task.shell("/bin/sleep 3; /bin/uname", autoclose=True)
        self.assert_(worker != None)
        task.resume()
        self.assertEqual(worker.read(), None)

    def testTwoSimpleCommandsAutoclose(self):
        """test two simple commands (one autoclosing)"""
        task = task_self()
        self.assert_(task != None)
        worker1 = task.shell("/bin/sleep 2; /bin/echo ok")
        worker2 = task.shell("/bin/sleep 3; /bin/uname", autoclose=True)
        self.assert_(worker2 != None)
        task.resume()
        self.assertEqual(worker1.read(), "ok")
        self.assertEqual(worker2.read(), None)

    def testLocalWorkerErrorBuffers(self):
        """test task local stderr worker buffers"""
        task = task_self()
        self.assert_(task != None)

        w1 = task.shell("/usr/bin/printf 'foo bar\n' 1>&2", key="foobar", stderr=True)
        w2 = task.shell("/usr/bin/printf 'foo\nbar\n' 1>&2", key="foobar2", stderr=True)
        task.resume()
        self.assertEqual(w1.error(), 'foo bar')
        self.assertEqual(w2.error(), 'foo\nbar')

    def testLocalErrorBuffers(self):
        """test task local stderr buffers gathering"""
        task = task_self()
        self.assert_(task != None)

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
            if buf == "faa\nber\n":
                self.assertEqual(len(keys), 1)
                self.assert_(keys[0].startswith("faaber"))
            elif buf == "foo\nfuu\n":
                self.assertEqual(len(keys), 2)
                self.assert_(keys[0].startswith("foofuu"))
            elif buf == "foo\nbar\n":
                self.assertEqual(len(keys), 3)
                self.assert_(keys[0].startswith("foobar"))
            elif buf == "foo\nbar\nxxx\n":
                self.assertEqual(len(keys), 1)
                self.assert_(keys[0].startswith("foobarX"))

        self.assertEqual(cnt, 0)

    def testTaskPrintDebug(self):
        """test task default print_debug"""
        task = task_self()
        self.assert_(task != None)
        # simple test, just run a task with debug on to improve test
        # code coverage
        task.set_info("debug", True)
        worker = task.shell("/bin/echo test")
        self.assert_(worker != None)
        task.resume()
        task.set_info("debug", False)

    def testTaskAbortSelf(self):
        """test task abort self (outside handler)"""
        task = task_self()
        self.assert_(task != None)

        # abort(False) keeps current task_self() object
        task.abort()
        self.assert_(task == task_self())

        # abort(True) unbinds current task_self() object
        task.abort(True)
        self.assert_(task != task_self())

        # retry
        task = task_self()
        self.assert_(task != None)
        worker = task.shell("/bin/echo shouldnt see that")
        task.abort()
        self.assert_(task == task_self())

    def testTaskAbortHandler(self):
        """test task abort self (inside handler)"""

        class AbortOnReadTestHandler(EventHandler):
            def ev_read(self, worker):
                self.has_ev_read = True
                worker.task.abort()
                assert False, "Shouldn't reach this line"

        task = task_self()
        self.assert_(task != None)
        eh = AbortOnReadTestHandler()
        eh.has_ev_read = False
        task.shell("/bin/echo test", handler=eh)
        task.resume()
        self.assert_(eh.has_ev_read)

    def testWorkerSetKey(self):
        """test worker set_key()"""
        task = task_self()
        self.assert_(task != None)
        task.shell("/bin/echo foo", key="foo")
        worker = task.shell("/bin/echo foobar")
        worker.set_key("bar")
        task.resume()
        self.assert_(task.key_buffer("bar") == "foobar")

    def testWorkerSimpleStdin(self):
        """test WorkerSimple (stdin)"""
        task = task_self()
        self.assert_(task != None)
        file_reader = sys.stdin
        worker = WorkerSimple(file_reader, None, None, "stdin", None, 0, True)
        self.assert_(worker != None)
        task.schedule(worker)
        task.resume()

    # FIXME: reconsider this kind of test (which now must fail) especially 
    #        when using epoll engine, as soon as testsuite is improved (#95).
    #def testWorkerSimpleFile(self):
    #    """test WorkerSimple (file)"""
    #    task = task_self()
    #    self.assert_(task != None)
    #    # use tempfile
    #    tmpfile = tempfile.TemporaryFile()
    #    tmpfile.write("one line without EOL")
    #    tmpfile.seek(0)
    #    worker = WorkerSimple(tmpfile, None, None, "file", None, 0, True)
    #    self.assert_(worker != None)
    #    task.schedule(worker)
    #    task.resume()
    #    self.assertEqual(worker.read(), "one line without EOL")

    def testInterruptEngine(self):
        """test Engine signal interruption"""
        class KillerThread(threading.Thread):
            def run(self):
                time.sleep(1)
                os.kill(self.pidkill, signal.SIGUSR1)
                task_wait()

        kth = KillerThread()
        kth.pidkill = os.getpid()

        task = task_self()
        self.assert_(task != None)
        signal.signal(signal.SIGUSR1, lambda x, y: None)
        task.shell("/bin/sleep 2", timeout=5)

        kth.start()
        task.resume()

    def testShellDelayedIO(self):
        """test delayed io in event handler"""
        class TestDelayedHandler(EventHandler):
            def __init__(self, target_worker=None):
                self.target_worker = target_worker
                self.counter = 0
            def ev_read(self, worker):
                self.counter += 1
                if self.counter == 100:
                    worker.write("another thing to read\n")
                    worker.set_write_eof()
            def ev_timer(self, timer):
                self.target_worker.write("something to read\n" * 300)

        task = task_self()
        hdlr = TestDelayedHandler()
        reader = task.shell("cat", handler=hdlr)
        timer = task.timer(0.6, handler=TestDelayedHandler(reader))
        task.resume()
        self.assertEqual(hdlr.counter, 301)

    def testSimpleCommandReadNoEOL(self):
        """test simple command read without EOL"""
        task = task_self()
        self.assert_(task != None)
        # init worker
        worker = task.shell("/bin/echo -n okay")
        self.assert_(worker != None)
        # run task
        task.resume()
        self.assertEqual(worker.read(), "okay")

    def testLocalFanout(self):
        """test local task fanout"""
        task = task_self()
        self.assert_(task != None)
        fanout = task.info("fanout")
        try:
            task.set_info("fanout", 3)

            # Test #1: simple
            for i in range(0, 10):
                worker = task.shell("/bin/echo test %d" % i)
                self.assert_(worker != None)
            task.resume()

            # Test #2: fanout change during run
            class TestFanoutChanger(EventHandler):
                def ev_timer(self, timer):
                    task_self().set_info("fanout", 1)
            timer = task.timer(2.0, handler=TestFanoutChanger())
            for i in range(0, 10):
                worker = task.shell("/bin/echo sleep 1")
                self.assert_(worker != None)
            task.resume()
        finally:
            # restore original fanout value
            task.set_info("fanout", fanout)

    def testPopenBadArgumentOption(self):
        """test WorkerPopen constructor bad argument"""
	# Check code < 1.4 compatibility
        self.assertRaises(WorkerBadArgumentError, WorkerPopen, None, None)
	# As of 1.4, ValueError is raised for missing parameter
        self.assertRaises(ValueError, WorkerPopen, None, None) # 1.4+

    def testWorkerAbort(self):
        """test local Worker abort() on timer"""
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

        aot = AbortOnTimer(task.shell("sleep 10"))
        self.assertEqual(aot.testtimer, False)
        task.timer(1.0, handler=aot)
        task.resume()
        self.assertEqual(aot.testtimer, True)
        
    def testWorkerAbortSanity(self):
        """test local Worker abort() (sanity)"""
        task = task_self()
        worker = task.shell("sleep 1")
        worker.abort()

        # test noop abort() on unscheduled worker
        worker = WorkerPopen("sleep 1")
        worker.abort()


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TaskLocalTest)
    unittest.TextTestRunner(verbosity=2).run(suite)

