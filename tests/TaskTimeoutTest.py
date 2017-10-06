# ClusterShell (local) test suite
# Written by S. Thiell

"""Unit test for ClusterShell Task/Worker timeout support"""

import unittest

from ClusterShell.Task import task_self


class TaskTimeoutTest(unittest.TestCase):

    def testWorkersTimeoutBuffers(self):
        """test worker buffers with timeout"""
        task = task_self()

        worker = task.shell('echo some buffer; echo here...; sleep 10', timeout=4)

        task.resume()
        self.assertEqual(worker.read(), b"""some buffer
here...""")
        test = 1
        for buf, keys in task.iter_buffers():
            test = 0
            self.assertEqual(buf, b"""some buffer
here...""")
        self.assertEqual(test, 0, "task.iter_buffers() did not work")
