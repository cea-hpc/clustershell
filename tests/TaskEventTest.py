# ClusterShell (local) test suite
# Written by S. Thiell

"""Unit test for ClusterShell Task (event-based mode)"""

import unittest
import warnings

from ClusterShell.Task import *
from ClusterShell.Event import EventHandler


class BaseAssertTestHandler(EventHandler):
    """Base Assert Test Handler"""

    def __init__(self):
        self.reset_asserts()

    def do_asserts_read_notimeout(self):
        assert self.did_start, "ev_start not called"
        assert self.cnt_pickup > 0, "ev_pickup not called"
        assert self.did_read, "ev_read not called"
        assert not self.did_readerr, "ev_error called"
        assert self.cnt_written == 0, "ev_written called"
        assert self.cnt_hup > 0, "ev_hup not called"
        assert self.did_close, "ev_close not called"
        assert not self.did_timeout, "ev_timeout called"

    def do_asserts_timeout(self):
        assert self.did_start, "ev_start not called"
        assert self.cnt_pickup > 0, "ev_pickup not called"
        assert not self.did_read, "ev_read called"
        assert not self.did_readerr, "ev_error called"
        assert self.cnt_written == 0, "ev_written called"
        assert self.cnt_hup == 0, "ev_hup called"
        assert self.did_close, "ev_close not called"
        assert self.did_timeout, "ev_timeout not called"

    def do_asserts_noread_notimeout(self):
        assert self.did_start, "ev_start not called"
        assert self.cnt_pickup > 0, "ev_pickup not called"
        assert not self.did_read, "ev_read called"
        assert not self.did_readerr, "ev_error called"
        assert self.cnt_written == 0, "ev_written called"
        assert self.cnt_hup > 0, "ev_hup not called"
        assert self.did_close, "ev_close not called"
        assert not self.did_timeout, "ev_timeout called"

    def do_asserts_read_write_notimeout(self):
        assert self.did_start, "ev_start not called"
        assert self.cnt_pickup > 0, "ev_pickup not called"
        assert self.did_read, "ev_read not called"
        assert not self.did_readerr, "ev_error called"
        assert self.cnt_written > 0, "ev_written not called"
        assert self.cnt_hup > 0, "ev_hup not called"
        assert self.did_close, "ev_close not called"
        assert not self.did_timeout, "ev_timeout called"

    def reset_asserts(self):
        self.did_start = False
        self.cnt_pickup = 0
        self.did_read = False
        self.did_readerr = False
        self.cnt_written = 0
        self.bytes_written = 0
        self.cnt_hup = 0
        self.did_close = False
        self.did_timeout = False


class LegacyTestHandler(BaseAssertTestHandler):
    """Legacy Test Handler (deprecated as of 1.8)"""

    def ev_start(self, worker):
        self.did_start = True

    def ev_pickup(self, worker):
        self.cnt_pickup += 1

    def ev_read(self, worker):
        self.did_read = True
        assert worker.current_msg == b"abcdefghijklmnopqrstuvwxyz"
        assert worker.current_errmsg != b"abcdefghijklmnopqrstuvwxyz"

    def ev_error(self, worker):
        self.did_readerr = True
        assert worker.current_errmsg == b"errerrerrerrerrerrerrerr"
        assert worker.current_msg != b"errerrerrerrerrerrerrerr"

    def ev_written(self, worker, node, sname, size):
        self.cnt_written += 1
        self.bytes_written += size

    def ev_hup(self, worker):
        self.cnt_hup += 1

    def ev_close(self, worker):
        self.did_close = True
        if worker.read():
            assert worker.read().startswith(b"abcdefghijklmnopqrstuvwxyz")

    def ev_timeout(self, worker):
        self.did_timeout = True


class TestHandler(BaseAssertTestHandler):
    """New Test Handler (1.8+)"""

    def ev_start(self, worker):
        self.did_start = True

    def ev_pickup(self, worker, node):
        assert node is not None
        self.cnt_pickup += 1

    def ev_read(self, worker, node, sname, msg):
        if sname == 'stdout':
            self.did_read = True
            assert msg == b"abcdefghijklmnopqrstuvwxyz"
        elif sname == 'stderr':
            self.did_readerr = True
            assert msg == b"errerrerrerrerrerrerrerr"

    def ev_written(self, worker, node, sname, size):
        self.cnt_written += 1
        self.bytes_written += size

    def ev_hup(self, worker, node, rc):
        assert node is not None
        self.cnt_hup += 1

    def ev_close(self, worker, did_timeout):
        self.did_timeout = did_timeout
        self.did_close = True
        if worker.read():
            assert worker.read().startswith(b"abcdefghijklmnopqrstuvwxyz")


class AbortOnReadHandler(EventHandler):
    def ev_read(self, worker):
        worker.abort()


class TaskEventTest(unittest.TestCase):

    def run_task_and_catch_warnings(self, task, expected_warn_cnt=0,
                                    category=DeprecationWarning,
                                    task_timeout=None):
        """helper to run task and catch+test issued warnings"""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            task.run(timeout=task_timeout)
            if len(w) != expected_warn_cnt:
                self.fail("Expected %d warnings, got %d: %s"
                          % (expected_warn_cnt, len(w),
                             '\n'.join(str(ex.message) for ex in w)))
            if len(w) > 0:
                self.assertTrue(issubclass(w[-1].category, category))

    def test_simple_event_handler_legacy(self):
        """test simple event handler (legacy)"""
        task = task_self()

        eh = LegacyTestHandler()
        # init worker
        worker = task.shell("echo abcdefghijklmnopqrstuvwxyz", handler=eh)
        # future warnings: pickup + read + hup + close
        #self.run_task_and_catch_warnings(task, 4)
        self.run_task_and_catch_warnings(task, 0)
        eh.do_asserts_read_notimeout()
        eh.reset_asserts()

        # test again
        worker = task.shell("echo abcdefghijklmnopqrstuvwxyz", handler=eh)
        # future warnings: pickup + read + hup + close
        #self.run_task_and_catch_warnings(task, 4)
        self.run_task_and_catch_warnings(task, 0)
        eh.do_asserts_read_notimeout()

    def test_simple_event_handler(self):
        """test simple event handler (1.8+)"""
        task = task_self()
        eh = TestHandler()
        worker = task.shell("echo abcdefghijklmnopqrstuvwxyz", handler=eh)
        self.run_task_and_catch_warnings(task)
        eh.do_asserts_read_notimeout()
        eh.reset_asserts()

        # test again
        worker = task.shell("echo abcdefghijklmnopqrstuvwxyz", handler=eh)
        self.run_task_and_catch_warnings(task)
        eh.do_asserts_read_notimeout()

    def test_simple_event_handler_with_task_timeout_legacy(self):
        """test simple event handler with timeout (legacy)"""
        task = task_self()

        eh = LegacyTestHandler()

        task.shell("/bin/sleep 3", handler=eh)

        try:
            # future warnings: pickup + close
            #self.run_task_and_catch_warnings(task, 2, task_timeout=2)
            self.run_task_and_catch_warnings(task, 0, task_timeout=2)
        except TimeoutError:
            pass
        else:
            self.fail("did not detect timeout")

        eh.do_asserts_timeout()

    def test_simple_event_handler_with_task_timeout(self):
        """test simple event handler with timeout (1.8+)"""
        task = task_self()

        eh = TestHandler()
        # init worker
        worker = task.shell("/bin/sleep 3", handler=eh)

        try:
            self.run_task_and_catch_warnings(task, task_timeout=2)
        except TimeoutError:
            pass
        else:
            self.fail("did not detect timeout")

        eh.do_asserts_timeout()

    def test_popen_specific_behaviour_legacy(self):
        """test WorkerPopen events specific behaviour (legacy)"""

        class LegacyWorkerPopenEH(LegacyTestHandler):
            def __init__(self, testcase):
                LegacyTestHandler.__init__(self)
                self.testcase = testcase

            def ev_start(self, worker):
                LegacyTestHandler.ev_start(self, worker)
                self.testcase.assertEqual(worker.current_node, None)

            def ev_read(self, worker):
                LegacyTestHandler.ev_read(self, worker)
                self.testcase.assertEqual(worker.current_node, None)

            def ev_error(self, worker):
                LegacyTestHandler.ev_error(self, worker)
                self.testcase.assertEqual(worker.current_node, None)

            def ev_written(self, worker, node, sname, size):
                LegacyTestHandler.ev_written(self, worker, node, sname, size)
                self.testcase.assertEqual(worker.current_node, None)

            def ev_pickup(self, worker):
                LegacyTestHandler.ev_pickup(self, worker)
                self.testcase.assertEqual(worker.current_node, None)

            def ev_hup(self, worker):
                LegacyTestHandler.ev_hup(self, worker)
                self.testcase.assertEqual(worker.current_node, None)

            def ev_close(self, worker):
                LegacyTestHandler.ev_close(self, worker)
                self.testcase.assertEqual(worker.current_node, None)

        task = task_self()
        eh = LegacyWorkerPopenEH(self)

        worker = task.shell("cat", handler=eh)
        content = b"abcdefghijklmnopqrstuvwxyz\n"
        worker.write(content)
        worker.set_write_eof()

        # future warnings: 1 x pickup + 1 x read + 1 x hup + 1 x close
        #self.run_task_and_catch_warnings(task, 4)
        self.run_task_and_catch_warnings(task, 0)
        eh.do_asserts_read_write_notimeout()

    def test_popen_specific_behaviour(self):
        """test WorkerPopen events specific behaviour (1.8+)"""

        class WorkerPopenEH(TestHandler):
            def __init__(self, testcase):
                TestHandler.__init__(self)
                self.testcase = testcase
                self.worker = None

            def ev_start(self, worker):
                TestHandler.ev_start(self, worker)
                self.testcase.assertEqual(worker, self.worker)

            def ev_read(self, worker, node, sname, msg):
                TestHandler.ev_read(self, worker, node, sname, msg)
                self.testcase.assertEqual(worker, self.worker)
                self.testcase.assertEqual(worker, node)

            def ev_written(self, worker, node, sname, size):
                TestHandler.ev_written(self, worker, node, sname, size)
                self.testcase.assertEqual(worker, self.worker)
                self.testcase.assertEqual(worker, node)

            def ev_pickup(self, worker, node):
                TestHandler.ev_pickup(self, worker, node)
                self.testcase.assertEqual(worker, self.worker)
                self.testcase.assertEqual(worker, node)

            def ev_hup(self, worker, node, rc):
                TestHandler.ev_hup(self, worker, node, rc)
                self.testcase.assertEqual(worker, self.worker)
                self.testcase.assertEqual(worker, node)

            def ev_close(self, worker, did_timeout):
                TestHandler.ev_close(self, worker, did_timeout)
                self.testcase.assertEqual(worker.current_node, None)  # XXX

        task = task_self()
        eh = WorkerPopenEH(self)

        worker = task.shell("cat", handler=eh)
        eh.worker = worker
        content = b"abcdefghijklmnopqrstuvwxyz\n"
        worker.write(content)
        worker.set_write_eof()

        self.run_task_and_catch_warnings(task)
        eh.do_asserts_read_write_notimeout()

    class LegacyTOnTheFlyLauncher(EventHandler):
        """Legacy Test Event handler to shedules commands on the fly"""
        def ev_read(self, worker):
            assert worker.task.running()
            # in-fly workers addition
            other1 = worker.task.shell("/bin/sleep 0.1", handler=self)
            assert other1 != None
            other2 = worker.task.shell("/bin/sleep 0.1", handler=self)
            assert other2 != None
        def ev_pickup(self, worker):
            """legacy ev_pickup signature to check for warnings"""
        def ev_hup(self, worker):
            """legacy ev_hup signature to check for warnings"""
        def ev_close(self, worker):
            """legacy ev_close signature to check for warnings"""

    def test_engine_on_the_fly_launch_legacy(self):
        """test client add on the fly while running (legacy)"""
        task = task_self()
        eh = self.__class__.LegacyTOnTheFlyLauncher()
        worker = task.shell("/bin/uname", handler=eh)
        self.assertNotEqual(worker, None)

        # future warnings: 1 x pickup + 1 x read + 2 x pickup + 3 x hup +
        #                  3 x close
        #self.run_task_and_catch_warnings(task, 10)
        self.run_task_and_catch_warnings(task, 0)

    class TOnTheFlyLauncher(EventHandler):
        """CS v1.8 Test Event handler to shedules commands on the fly"""
        def ev_read(self, worker, node, sname, msg):
            assert worker.task.running()
            # in-fly workers addition
            other1 = worker.task.shell("/bin/sleep 0.1")
            assert other1 != None
            other2 = worker.task.shell("/bin/sleep 0.1")
            assert other2 != None

    def test_engine_on_the_fly_launch(self):
        """test client add on the fly while running (1.8+)"""
        task = task_self()
        eh = self.__class__.TOnTheFlyLauncher()
        worker = task.shell("/bin/uname", handler=eh)
        self.assertNotEqual(worker, None)

        self.run_task_and_catch_warnings(task)

    class LegacyTWriteOnStart(EventHandler):
        def ev_start(self, worker):
            assert worker.task.running()
            worker.write(b"foo bar\n")
        def ev_read(self, worker):
            assert worker.current_msg == b"foo bar"
            worker.abort()

    def test_write_on_ev_start_legacy(self):
        """test write on ev_start (legacy)"""
        task = task_self()
        task.shell("cat", handler=self.__class__.LegacyTWriteOnStart())
        #self.run_task_and_catch_warnings(task, 1)  # future: read
        self.run_task_and_catch_warnings(task, 0)

    class TWriteOnStart(EventHandler):
        def ev_start(self, worker):
            assert worker.task.running()
            worker.write(b"foo bar\n")
        def ev_read(self, worker, node, sname, msg):
            assert msg == b"foo bar"
            worker.abort()

    def test_write_on_ev_start(self):
        """test write on ev_start"""
        task = task_self()
        task.shell("cat", handler=self.__class__.TWriteOnStart())
        self.run_task_and_catch_warnings(task)

    class LegacyAbortOnReadHandler(EventHandler):
        def ev_read(self, worker):
            worker.abort()

    def test_engine_may_reuse_fd_legacy(self):
        """test write + worker.abort() on read to reuse FDs (legacy)"""
        task = task_self()
        fanout = task.info("fanout")
        try:
            task.set_info("fanout", 1)
            eh = self.__class__.LegacyAbortOnReadHandler()
            for i in range(10):
                worker = task.shell("echo ok; sleep 1", handler=eh)
                self.assertTrue(worker is not None)
                worker.write(b"OK\n")
            # future warnings: 10 x read
            #self.run_task_and_catch_warnings(task, 10)
            self.run_task_and_catch_warnings(task, 0)
        finally:
            task.set_info("fanout", fanout)

    class AbortOnReadHandler(EventHandler):
        def ev_read(self, worker, node, sname, msg):
            worker.abort()

    def test_engine_may_reuse_fd(self):
        """test write + worker.abort() on read to reuse FDs"""
        task = task_self()
        fanout = task.info("fanout")
        try:
            task.set_info("fanout", 1)
            eh = self.__class__.AbortOnReadHandler()
            for i in range(10):
                worker = task.shell("echo ok; sleep 1", handler=eh)
                self.assertTrue(worker is not None)
                worker.write(b"OK\n")
            self.run_task_and_catch_warnings(task)
        finally:
            task.set_info("fanout", fanout)

    def test_ev_pickup_legacy(self):
        """test ev_pickup event (legacy)"""
        task = task_self()

        eh = LegacyTestHandler()

        task.shell("/bin/sleep 0.4", handler=eh)
        task.shell("/bin/sleep 0.5", handler=eh)
        task.shell("/bin/sleep 0.5", handler=eh)

        # future warnings: 3 x pickup + 3 x hup + 3 x close
        #self.run_task_and_catch_warnings(task, 9)
        self.run_task_and_catch_warnings(task, 0)

        eh.do_asserts_noread_notimeout()
        self.assertEqual(eh.cnt_pickup, 3)
        self.assertEqual(eh.cnt_hup, 3)

    def test_ev_pickup(self):
        """test ev_pickup event (1.8+)"""
        task = task_self()

        eh = TestHandler()

        task.shell("/bin/sleep 0.4", handler=eh)
        task.shell("/bin/sleep 0.5", handler=eh)
        task.shell("/bin/sleep 0.5", handler=eh)

        self.run_task_and_catch_warnings(task)

        eh.do_asserts_noread_notimeout()
        self.assertEqual(eh.cnt_pickup, 3)
        self.assertEqual(eh.cnt_hup, 3)

    def test_ev_pickup_fanout_legacy(self):
        """test ev_pickup event with fanout (legacy)"""
        task = task_self()
        fanout = task.info("fanout")
        try:
            task.set_info("fanout", 1)

            eh = LegacyTestHandler()

            task.shell("/bin/sleep 0.4", handler=eh, key="n1")
            task.shell("/bin/sleep 0.5", handler=eh, key="n2")
            task.shell("/bin/sleep 0.5", handler=eh, key="n3")

            # future warnings: 3 x pickup + 3 x hup + 3 x close
            #self.run_task_and_catch_warnings(task, 9)
            self.run_task_and_catch_warnings(task, 0)

            eh.do_asserts_noread_notimeout()
            self.assertEqual(eh.cnt_pickup, 3)
            self.assertEqual(eh.cnt_hup, 3)
        finally:
            task.set_info("fanout", fanout)

    def test_ev_pickup_fanout(self):
        """test ev_pickup event with fanout"""
        task = task_self()
        fanout = task.info("fanout")
        try:
            task.set_info("fanout", 1)

            eh = TestHandler()

            task.shell("/bin/sleep 0.4", handler=eh, key="n1")
            task.shell("/bin/sleep 0.5", handler=eh, key="n2")
            task.shell("/bin/sleep 0.5", handler=eh, key="n3")

            self.run_task_and_catch_warnings(task)

            eh.do_asserts_noread_notimeout()
            self.assertEqual(eh.cnt_pickup, 3)
            self.assertEqual(eh.cnt_hup, 3)
        finally:
            task.set_info("fanout", fanout)

    def test_ev_written_legacy(self):
        """test ev_written event (legacy)"""
        task = task_self()

        eh = LegacyTestHandler()

        worker = task.shell("cat", handler=eh)
        content = b"abcdefghijklmnopqrstuvwxyz\n"
        worker.write(content)
        worker.set_write_eof()

        # future warnings: pickup + read + hup + close
        #self.run_task_and_catch_warnings(task, 4)
        self.run_task_and_catch_warnings(task, 0)

        eh.do_asserts_read_write_notimeout()
        self.assertEqual(eh.cnt_written, 1)
        self.assertEqual(eh.bytes_written, len(content))

    def test_ev_written(self):
        """test ev_written event"""
        task = task_self()

        # ev_written itself is using the same signature but it is just for
        # the sake of completeness...
        eh = TestHandler()

        worker = task.shell("cat", handler=eh)
        content = b"abcdefghijklmnopqrstuvwxyz\n"
        worker.write(content)
        worker.set_write_eof()

        self.run_task_and_catch_warnings(task)

        eh.do_asserts_read_write_notimeout()
        self.assertEqual(eh.cnt_written, 1)
        self.assertEqual(eh.bytes_written, len(content))
