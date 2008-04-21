#!/usr/bin/env python
# ClusterShell (local) test suite
# Written by S. Thiell 2008-04-09
# $Id$


"""Unit test for ClusterShell"""

import copy
import sys
import unittest

sys.path.append('../lib')

import ClusterShell

from ClusterShell.NodeSet import NodeSet
from ClusterShell.Task import Task

import socket


class LocalTests(unittest.TestCase):

    def test0(self):
        task = Task.current()
        assert task != None
        work = task.shell("/bin/hostname")
        task.run()

    def test1(self):
        task = Task.current()
        assert task != None
        work = task.shell("/bin/hostname", nodes=None, handler=None)
        task.run()

    def test2(self):
        task = Task.current()
        assert task != None
        workers = []
        for i in range(0, 9):
            workers.append(task.shell("/bin/hostname"))
        task.run()
        hn = socket.gethostname()
        for i in range(0, 9):
            t_hn = workers[i].read_buffer().splitlines()[0]
            assert t_hn == hn

    def testVersion(self):
        assert ClusterShell.version > 0.5


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(LocalTests)
    unittest.TextTestRunner(verbosity=2).run(suite)

