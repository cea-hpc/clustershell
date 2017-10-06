# ClusterShell test suite
# Written by S. Thiell

"""Unit test for ClusterShell common library misusages"""

import unittest

from TLib import HOSTNAME
from ClusterShell.Event import EventHandler
from ClusterShell.Worker.Popen import WorkerPopen
from ClusterShell.Worker.Ssh import WorkerSsh
from ClusterShell.Worker.Worker import WorkerError
from ClusterShell.Task import task_self, AlreadyRunningError


class MisusageTest(unittest.TestCase):

    def testTaskResumedTwice(self):
        """test library misusage (task_self resumed twice)"""
        class ResumeAgainHandler(EventHandler):
            def ev_read(self, worker):
                worker.task.resume()
        task = task_self()
        task.shell("/bin/echo OK", handler=ResumeAgainHandler())
        self.assertRaises(AlreadyRunningError, task.resume)

    def testWorkerNotScheduledLocal(self):
        """test library misusage (local worker not scheduled)"""
        task = task_self()
        worker = WorkerPopen(command="/bin/hostname")
        task.resume()
        self.assertRaises(WorkerError, worker.read)

    def testWorkerNotScheduledDistant(self):
        """test library misusage (distant worker not scheduled)"""
        task = task_self()
        worker = WorkerSsh(HOSTNAME, command="/bin/hostname", handler=None, timeout=0)
        task.resume()
        self.assertRaises(WorkerError, worker.node_buffer, HOSTNAME)

    def testTaskScheduleTwice(self):
        """test task worker schedule twice error"""
        task = task_self()
        worker = task.shell("/bin/echo itsme")
        self.assertRaises(WorkerError, task.schedule, worker)
        task.abort()
