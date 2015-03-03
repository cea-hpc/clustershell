#!/usr/bin/env python
# ClusterShell.Worker.ExecWorker test suite
# First version by A. Degremont 2014-07-10

import os
import unittest

from TLib import HOSTNAME, make_temp_file, make_temp_dir

from ClusterShell.Worker.Exec import ExecWorker, WorkerError
from ClusterShell.Task import task_self

class ExecTest(unittest.TestCase):

    def execw(self, **kwargs):
        """helper method to spawn and run ExecWorker"""
        worker = ExecWorker(**kwargs)
        task_self().schedule(worker)
        task_self().run()
        return worker

    def test_no_nodes(self):
        """test ExecWorker with a simple command without nodes"""
        self.execw(nodes=None, handler=None, command="echo ok")
        self.assertEqual(task_self().max_retcode(), 0)

    def test_shell_syntax(self):
        """test ExecWorker with a command using shell syntax"""
        cmd = "echo -n 1; echo -n 2"
        self.execw(nodes='localhost', handler=None, command=cmd)
        self.assertEqual(task_self().max_retcode(), 0)
        self.assertEqual(task_self().node_buffer('localhost'), '12')

    def test_one_node(self):
        """test ExecWorker with a simple command on localhost"""
        self.execw(nodes='localhost', handler=None, command="echo ok")
        self.assertEqual(task_self().max_retcode(), 0)
        self.assertEqual(task_self().node_buffer('localhost'), 'ok')

    def test_one_node_error(self):
        """test ExecWorker with an error command on localhost"""
        self.execw(nodes='localhost', handler=None, command="false")
        self.assertEqual(task_self().max_retcode(), 1)
        self.assertEqual(task_self().node_buffer('localhost'), '')

    def test_timeout(self):
        """test ExecWorker with a timeout"""
        nodes = "localhost,%s" % HOSTNAME
        self.execw(nodes=nodes, handler=None, command="sleep 1", timeout=0.2)
        self.assertEqual(task_self().max_retcode(), 0)
        self.assertEqual(task_self().num_timeout(), 2)

    def test_node_placeholder(self):
        """test ExecWorker with several nodes and %h (host)"""
        nodes = "localhost,%s" % HOSTNAME
        self.execw(nodes=nodes, handler=None, command="echo %h")
        self.assertEqual(task_self().max_retcode(), 0)
        self.assertEqual(task_self().node_buffer('localhost'), 'localhost')
        self.assertEqual(task_self().node_buffer(HOSTNAME), HOSTNAME)

    def test_bad_placeholder(self):
        """test ExecWorker with unknown placeholder pattern"""
        self.assertRaises(WorkerError, self.execw,
                          nodes="localhost", handler=None, command="echo %x")

    def test_rank_placeholder(self):
        """test ExecWorker with several nodes and %n (rank)"""
        nodes = "localhost,%s" % HOSTNAME
        self.execw(nodes=nodes, handler=None, command="echo %n")
        self.assertEqual(task_self().max_retcode(), 0)
        self.assertEqual([str(msg) for msg, _ in task_self().iter_buffers()],
                         ['0', '1'])

    def test_copy(self):
        """test copying with an ExecWorker and host placeholder"""
        src = make_temp_file("data")
        dstdir = make_temp_dir()
        dstpath = os.path.join(dstdir, os.path.basename(src.name))
        try:
            pattern = dstpath + ".%h"
            self.execw(nodes='localhost', handler=None, source=src.name,
                       dest=pattern)
            self.assertEqual(task_self().max_retcode(), 0)
            self.assertTrue(os.path.isfile(dstpath + '.localhost'))
        finally:
            os.unlink(dstpath + '.localhost')
            os.rmdir(dstdir)
