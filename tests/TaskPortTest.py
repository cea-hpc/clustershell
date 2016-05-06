#!/usr/bin/env python
# ClusterShell test suite
# Written by S. Thiell


"""Unit test for ClusterShell inter-Task msg"""

import pickle
import sys
import threading
import time
import unittest

sys.path.insert(0, '../lib')

from ClusterShell.Task import *
from ClusterShell.Event import EventHandler


class TaskPortTest(unittest.TestCase):

    def tearDown(self):
        task_cleanup()

    def testPortMsg1(self):
        """test port msg from main thread to task"""

        TaskPortTest.got_msg = False

        # create task in new thread
        task = Task()

        class PortHandler(EventHandler):
            def ev_msg(self, port, msg):
                # receive msg
                assert msg == "toto"
                assert port.task.thread == threading.currentThread()
                TaskPortTest.got_msg = True
                port.task.abort()

        # create non-autoclosing port
        port = task.port(handler=PortHandler())
        task.resume()
        # send msg from main thread
        port.msg("toto")
        task_wait()
        self.assert_(TaskPortTest.got_msg)

    def testPortRemove(self):
        """test remove_port()"""

        class PortHandler(EventHandler):
            def ev_msg(self, port, msg):
                pass

        task = Task() # new thread
        port = task.port(handler=PortHandler(), autoclose=True)
        task.resume()
        task.remove_port(port)
        task_wait()

    def testPortClosed(self):
        """test port msg on closed port"""
        # test sending message to "stillborn" port
        self.port_msg_result = None

        # thread will wait a bit and send a port message
        def test_thread_start(port, test):
            time.sleep(0.5)
            test.port_msg_result = port.msg('foobar')

        class TestHandler(EventHandler):
            pass

        task = task_self()
        test_handler = TestHandler()
        task.timer(0.2, handler=test_handler, autoclose=False)
        port = task.port(handler=test_handler, autoclose=True)
        thread = threading.Thread(None, test_thread_start, args=(port, self))
        thread.setDaemon(True)
        thread.start()
        task.resume()
        task.abort(kill=True) # will remove_port()
        thread.join()
        self.assertEqual(self.port_msg_result, False) # test vs. None and True
