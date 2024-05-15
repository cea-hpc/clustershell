# ClusterShell timer test suite
# Written by S. Thiell

"""Unit test for ClusterShell Task's timer"""

import copy
import threading
from time import sleep, time
import unittest

from TLib import HOSTNAME
from ClusterShell.Engine.Engine import EngineTimer, EngineIllegalOperationError
from ClusterShell.Event import EventHandler
from ClusterShell.Task import *


EV_START=0x01
EV_READ=0x02
EV_WRITTEN=0x04
EV_HUP=0x08
EV_TIMEOUT=0x10
EV_CLOSE=0x20
EV_TIMER=0x40


class TaskTimerTest(unittest.TestCase):

    class TSimpleTimerChecker(EventHandler):
        def __init__(self):
            self.count = 0

        def ev_timer(self, timer):
            self.count += 1

    def testSimpleTimer(self):
        """test simple timer"""
        task = task_self()

        # init event handler for timer's callback
        test_handler = self.__class__.TSimpleTimerChecker()
        timer1 = task.timer(0.5, handler=test_handler)
        self.assertTrue(timer1 is not None)
        # run task
        task.resume()
        self.assertEqual(test_handler.count, 1)

    def testSimpleTimer2(self):
        """test simple 2 timers with same fire_date"""
        task = task_self()
        test_handler = self.__class__.TSimpleTimerChecker()
        timer1 = task.timer(0.5, handler=test_handler)
        timer2 = task.timer(0.5, handler=test_handler)
        task.resume()
        self.assertEqual(test_handler.count, 2)

    def testSimpleTimerImmediate(self):
        """test simple immediate timer"""
        task = task_self()
        test_handler = self.__class__.TSimpleTimerChecker()
        timer1 = task.timer(0.0, handler=test_handler)
        task.resume()
        self.assertEqual(test_handler.count, 1)

    def testSimpleTimerImmediate2(self):
        """test simple immediate timers"""
        task = task_self()
        test_handler = self.__class__.TSimpleTimerChecker()
        for i in range(10):
            timer1 = task.timer(0.0, handler=test_handler)
        task.resume()
        self.assertEqual(test_handler.count, 10)

    class TRepeaterTimerChecker(EventHandler):
        def __init__(self):
            self.count = 0

        def ev_timer(self, timer):
            self.count += 1
            timer.set_nextfire(0.2)
            if self.count > 4:
                timer.invalidate()

    def testSimpleRepeater(self):
        """test simple repeater timer"""
        task = task_self()
        # init event handler for timer's callback
        test_handler = self.__class__.TRepeaterTimerChecker()
        timer1 = task.timer(0.5, interval=0.2, handler=test_handler)
        # run task
        task.resume()
        self.assertEqual(test_handler.count, 5)

    def testRepeaterInvalidatedTwice(self):
        """test repeater timer invalidated two times"""
        task = task_self()
        # init event handler for timer's callback
        test_handler = self.__class__.TRepeaterTimerChecker()
        timer1 = task.timer(0.5, interval=0.2, handler=test_handler)
        # run task
        task.resume()
        self.assertEqual(test_handler.count, 5)

        # force invalidation again (2d time), this should do nothing
        timer1.invalidate()

        # call handler one more time directly: set_nextfire should raise an error
        self.assertRaises(EngineIllegalOperationError, test_handler.ev_timer, timer1)

        # force invalidation again (3th), this should do nothing
        timer1.invalidate()

    def launchSimplePrecisionTest(self, delay):
        task = task_self()
        # init event handler for timer's callback
        test_handler = self.__class__.TSimpleTimerChecker()
        timer1 = task.timer(delay, handler=test_handler)
        t1 = time()
        # run task
        task.resume()
        t2 = time()
        check_precision = 0.05
        self.assertTrue(abs((t2 - t1) - delay) < check_precision,
                        "%f >= %f" % (abs((t2 - t1) - delay), check_precision))
        self.assertEqual(test_handler.count, 1)

    def testPrecision1(self):
        """test simple timer precision (0.1s)"""
        self.launchSimplePrecisionTest(0.1)

    def testPrecision2(self):
        """test simple timer precision (1.0s)"""
        self.launchSimplePrecisionTest(1.0)

    def testWorkersAndTimer(self):
        """test task with timer and local jobs"""
        task0 = task_self()
        worker1 = task0.shell("/bin/hostname")
        worker2 = task0.shell("/bin/uname -a")
        test_handler = self.__class__.TSimpleTimerChecker()
        timer1 = task0.timer(1.0, handler=test_handler)
        task0.resume()
        self.assertEqual(test_handler.count, 1)
        b1 = copy.copy(worker1.read())
        b2 = copy.copy(worker2.read())
        worker1 = task0.shell("/bin/hostname")
        worker2 = task0.shell("/bin/uname -a")
        timer1 = task0.timer(1.0, handler=test_handler)
        task0.resume()
        self.assertEqual(test_handler.count, 2) # same handler, called 2 times
        self.assertEqual(worker2.read(), b2)
        self.assertEqual(worker1.read(), b1)

    def testNTimers(self):
        """test multiple timers"""
        task = task_self()
        # init event handler for timer's callback
        test_handler = self.__class__.TSimpleTimerChecker()
        for i in range(0, 30):
            timer1 = task.timer(1.0 + 0.2 * i, handler=test_handler)
        # run task
        task.resume()
        self.assertEqual(test_handler.count, 30)

    class TEventHandlerTimerInvalidate(EventHandler):
        """timer operations event handler simulator"""
        def __init__(self, test):
            self.test = test
            self.timer = None
            self.timer_count = 0
            self.flags = 0
        def ev_start(self, worker):
            self.flags |= EV_START
        def ev_read(self, worker, node, sname, msg):
            self.test.assertEqual(self.flags, EV_START)
            self.flags |= EV_READ
        def ev_written(self, worker, node, sname, size):
            self.test.assertTrue(self.flags & EV_START)
            self.flags |= EV_WRITTEN
        def ev_hup(self, worker, node, rc):
            self.test.assertTrue(self.flags & EV_START)
            self.flags |= EV_HUP
        def ev_close(self, worker, timedout):
            self.test.assertTrue(self.flags & EV_START)
            if timedout:
                self.flags |= EV_TIMEOUT
            self.flags |= EV_CLOSE
        def ev_timer(self, timer):
            self.flags |= EV_TIMER
            self.timer_count += 1
            self.timer.invalidate()

    def testTimerInvalidateInHandler(self):
        """test timer invalidate in event handler"""
        task = task_self()
        test_eh = self.__class__.TEventHandlerTimerInvalidate(self)
        # init worker
        worker = task.shell("/bin/sleep 1", handler=test_eh)
        worker = task.shell("/bin/sleep 3", nodes=HOSTNAME, handler=test_eh)
        # init timer
        timer = task.timer(1.5, interval=0.5, handler=test_eh)
        test_eh.timer = timer
        # run task
        task.resume()
        # test timer did fire once
        self.assertEqual(test_eh.timer_count, 1)

    class TEventHandlerTimerSetNextFire(EventHandler):
        def __init__(self, test):
            self.test = test
            self.timer = None
            self.timer_count = 0
            self.flags = 0
        def ev_start(self, worker):
            self.flags |= EV_START
        def ev_read(self, worker, node, sname, msg):
            self.test.assertEqual(self.flags, EV_START)
            self.flags |= EV_READ
        def ev_written(self, worker):
            self.test.assertTrue(self.flags & EV_START)
            self.flags |= EV_WRITTEN
        def ev_hup(self, worker, node, rc):
            self.test.assertTrue(self.flags & EV_START)
            self.flags |= EV_HUP
        def ev_close(self, worker, timedout):
            self.test.assertTrue(self.flags & EV_START)
            if timedout:
                self.flags |= EV_TIMEOUT
            self.flags |= EV_CLOSE
        def ev_timer(self, timer):
            self.flags |= EV_TIMER
            if self.timer_count < 4:
                self.timer.set_nextfire(0.5)
            # else invalidate automatically as timer does not repeat
            self.timer_count += 1

    def testTimerSetNextFireInHandler(self):
        """test timer set_nextfire in event handler"""
        task = task_self()
        test_eh = self.__class__.TEventHandlerTimerSetNextFire(self)
        # init worker
        worker = task.shell("/bin/sleep 3", nodes=HOSTNAME, handler=test_eh)
        # init timer
        timer = task.timer(1.0, interval=0.2, handler=test_eh)
        test_eh.timer = timer
        # run task
        task.resume()
        # test timer did fire one time
        self.assertEqual(test_eh.timer_count, 5)

    class TEventHandlerTimerOtherInvalidate(EventHandler):
        """timer operations event handler simulator"""
        def __init__(self, test):
            self.test = test
            self.timer = None
            self.flags = 0
        def ev_start(self, worker):
            self.flags |= EV_START
        def ev_read(self, worker, node, sname, msg):
            self.flags |= EV_READ
            self.timer.invalidate()
        def ev_written(self, worker):
            self.test.assertTrue(self.flags & EV_START)
            self.flags |= EV_WRITTEN
        def ev_hup(self, worker, node, rc):
            self.test.assertTrue(self.flags & EV_START)
            self.flags |= EV_HUP
        def ev_close(self, worker, timedout):
            self.test.assertTrue(self.flags & EV_START)
            if timedout:
                self.flags |= EV_TIMEOUT
            self.flags |= EV_CLOSE
        def ev_timer(self, timer):
            self.flags |= EV_TIMER

    def testTimerInvalidateInOtherHandler(self):
        """test timer invalidate in other event handler"""
        task = task_self()
        test_eh = self.__class__.TEventHandlerTimerOtherInvalidate(self)
        # init worker
        worker = task.shell("/bin/uname -r", handler=test_eh)
        worker = task.shell("/bin/sleep 2", nodes=HOSTNAME, handler=test_eh)
        # init timer
        timer = task.timer(1.0, interval=0.5, handler=test_eh)
        test_eh.timer = timer
        # run task
        task.resume()
        # test timer didn't fire, invalidated in a worker's event handler
        self.assertTrue(test_eh.flags & EV_READ)
        self.assertFalse(test_eh.flags & EV_TIMER)

    class TEventHandlerTimerInvalidateSameRunloop(EventHandler):
        """timer operations event handler simulator"""

        def __init__(self, test):
            self.timer1 = None
            self.timer2 = None
            self.count = 0

        def ev_timer(self, timer):
            self.count += 1
            # Invalidate both timers, the other is expected to fire during the
            # same runloop, but now it should not.
            self.timer1.invalidate()
            self.timer2.invalidate()

    def testTimerInvalidateSameRunloop(self):
        """test timer invalidate by other timer in same runloop"""
        task = task_self()
        test_eh = self.__class__.TEventHandlerTimerInvalidateSameRunloop(self)
        timer1 = task.timer(0.5, interval=0.5, handler=test_eh)
        test_eh.timer1 = timer1
        timer2 = task.timer(0.5, interval=0.5, handler=test_eh)
        test_eh.timer2 = timer2
        task.resume()
        # check that only one timer is fired
        self.assertEqual(test_eh.count, 1)

    class TEventHandlerTimerOtherSetNextFire(EventHandler):
        def __init__(self, test):
            self.test = test
            self.timer = None
            self.timer_count = 0
            self.flags = 0
        def ev_start(self, worker):
            self.flags |= EV_START
        def ev_read(self, worker, node, sname, msg):
            self.test.assertEqual(self.flags, EV_START)
            self.flags |= EV_READ
        def ev_written(self, worker):
            self.test.assertTrue(self.flags & EV_START)
            self.flags |= EV_WRITTEN
        def ev_hup(self, worker, node, rc):
            self.test.assertTrue(self.flags & EV_START)
            self.flags |= EV_HUP
        def ev_close(self, worker, timedout):
            self.test.assertTrue(self.flags & EV_START)
            if timedout:
                self.flags |= EV_TIMEOUT
            self.flags |= EV_CLOSE
            # set next fire delay, also disable previously setup interval
            # (timer will not repeat anymore)
            self.timer.set_nextfire(0.5)
        def ev_timer(self, timer):
            self.flags |= EV_TIMER
            self.timer_count += 1

    def testTimerSetNextFireInOtherHandler(self):
        """test timer set_nextfire in other event handler"""
        task = task_self()
        test_eh = self.__class__.TEventHandlerTimerOtherSetNextFire(self)
        # init worker
        worker = task.shell("/bin/sleep 1", handler=test_eh)
        # init timer
        timer = task.timer(10.0, interval=0.5, handler=test_eh)
        test_eh.timer = timer
        # run task
        task.resume()
        # test timer did fire one time
        self.assertEqual(test_eh.timer_count, 1)

    def testAutocloseTimer(self):
        """test timer autoclose (one autoclose timer)"""
        task = task_self()

        # Task should return immediately
        test_handler = self.__class__.TSimpleTimerChecker()
        timer_ac = task.timer(10.0, handler=test_handler, autoclose=True)

        # run task
        task.resume()
        self.assertEqual(test_handler.count, 0)

    def testAutocloseWithTwoTimers(self):
        """test timer autoclose (two timers)"""
        task = task_self()

        # build 2 timers, one of 10 secs with autoclose,
        # and one of 1 sec without autoclose.
        # Task should return after 1 sec.
        test_handler = self.__class__.TSimpleTimerChecker()
        timer_ac = task.timer(10.0, handler=test_handler, autoclose=True)
        timer_noac = task.timer(1.0, handler=test_handler, autoclose=False)

        # run task
        task.resume()
        self.assertEqual(test_handler.count, 1)

    class TForceDelayedRepeaterChecker(EventHandler):
        def __init__(self):
            self.count = 0

        def ev_timer(self, timer):
            self.count += 1
            if self.count == 1:
                # force delay timer (NOT a best practice!)
                sleep(2)
                # do not invalidate first time
            else:
                # invalidate next time to stop repeater
                timer.invalidate()

    def testForceDelayedRepeater(self):
        """test repeater being forcibly delayed"""
        task = task_self()
        test_handler = self.__class__.TForceDelayedRepeaterChecker()
        repeater1 = task.timer(0.5, interval=0.25, handler=test_handler)
        task.resume()
        self.assertEqual(test_handler.count, 2)

    class TForceDelayedRepeaterAutoCloseChecker(EventHandler):

        INTERVAL = 0.25

        def __init__(self):
            self.count = 0

        def ev_timer(self, timer):
            self.count += 1
            sleep(self.INTERVAL + 0.1)

    def testForceDelayedRepeaterAutoClose(self):
        """test repeater being forcibly delayed (w/ autoclose)"""
        # Test Github issue #254
        INTERVAL = 0.25
        task = task_self()
        teh = self.__class__.TForceDelayedRepeaterAutoCloseChecker()
        bootstrap = task.shell("sleep %f" % (2 * INTERVAL))
        repeater1 = task.timer(INTERVAL, teh, INTERVAL, autoclose=True)
        repeater2 = task.timer(INTERVAL, teh, INTERVAL, autoclose=True)
        task.resume()
        # Expected behavior: both timers will fire after INTERVAL, the first
        # one will block thread for INTERVAL+0.1, the second one will also
        # block for INTERVAL+0.1 more time. Then at next runloop the engine
        # will see our shell command termination so will unregister associated
        # worker client. At this point, only non-autoclosing timers remain
        # registered, so timer firing will be skipped and runloop will exit.
        #
        # Why two possible values below? This has changed due to #399:
        # count will be 1 if one timer is fired first (most likely without
        #   epsilon batching effect fixed in #399)
        # count will be 2 if both timers are fired during the same runloop
        self.assertTrue(teh.count in (1, 2))

    def testMultipleAddSameTimerPrivate(self):
        """test multiple add() of same timer [private]"""
        task = task_self()
        test_handler = self.__class__.TSimpleTimerChecker()
        timer = EngineTimer(1.0, -1.0, False, test_handler)
        task._engine.add_timer(timer)
        self.assertRaises(EngineIllegalOperationError, task._engine.add_timer, timer)
        task_terminate()

    def testRemoveTimerPrivate(self):
        """test engine.remove_timer() [private]"""
        # [private] because engine methods are currently private,
        # users should use timer.invalidate() instead
        task = task_self()
        test_handler = self.__class__.TSimpleTimerChecker()
        timer = EngineTimer(1.0, -1.0, False, test_handler)
        task._engine.add_timer(timer)
        task._engine.remove_timer(timer)
        task_terminate()

    def _thread_timer_create_func(self, task):
        """thread used to create a timer for another task; hey why not?"""
        timer = task.timer(0.5, self.__class__.TSimpleTimerChecker())

    def testTimerAddFromAnotherThread(self):
        """test timer creation from another thread"""
        task = task_self()
        threading.Thread(None, self._thread_timer_create_func,
                         args=(task,)).start()
        task.resume()
        task_wait()
