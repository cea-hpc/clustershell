#!/usr/bin/env python
# ClusterShell (distant) test suite
# Written by S. Thiell 2008-04-09
# $Id$


"""Unit test for ClusterShell Task (distant)"""

import copy
import sys
import unittest

sys.path.insert(0, '../lib')

import ClusterShell

from ClusterShell.NodeSet import NodeSet
from ClusterShell.Task import *

import socket

import thread


class TaskDistantTest(unittest.TestCase):

    def testLocalhostCommand(self):
        """test simple localhost command"""
        task = task_self()
        self.assert_(task != None)
        # init worker
        worker = task.shell("/bin/hostname", nodes='localhost')
        self.assert_(worker != None)
        # run task
        task.resume()
    

if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TaskDistantTest)
    unittest.TextTestRunner(verbosity=2).run(suite)

