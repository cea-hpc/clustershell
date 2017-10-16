"""
Unit test for ClusterShell.Worker.TreeWorker

This unit test requires working ssh connections to the following
local addresses: $HOSTNAME, localhost, 127.0.0.[2-4]

You can use the following options in ~/.ssh/config:

    Host your_hostname localhost 127.0.0.*
      StrictHostKeyChecking no
      LogLevel ERROR
"""

import os
from os.path import basename, join
import shutil
import unittest

from ClusterShell.NodeSet import NodeSet
from ClusterShell.Task import task_self, task_terminate
from ClusterShell.Topology import TopologyGraph
from ClusterShell.Worker.Tree import TreeWorker, WorkerTree

from TLib import HOSTNAME, make_temp_dir, make_temp_file, make_temp_filename


NODE_HEAD = HOSTNAME
NODE_GATEWAY = 'localhost'
NODE_DISTANT = '127.0.0.2'
NODE_DIRECT = '127.0.0.3'
NODE_FOREIGN = '127.0.0.4'


class TEventHandlerBase(object):
    """Base Test class for EventHandler"""

    def __init__(self):
        self.ev_start_cnt = 0
        self.ev_pickup_cnt = 0
        self.ev_read_cnt = 0
        self.ev_written_cnt = 0
        self.ev_written_sz = 0
        self.ev_hup_cnt = 0
        self.ev_close_cnt = 0
        self.ev_timedout_cnt = 0
        self.last_read = None


class TEventHandlerLegacy(TEventHandlerBase):
    """Test Legacy Event Handler (< 1.8)"""

    def ev_start(self, worker):
        self.ev_start_cnt += 1

    def ev_pickup(self, worker):
        self.ev_pickup_cnt += 1

    def ev_read(self, worker):
        self.ev_read_cnt += 1
        self.last_read = worker.current_msg

    def ev_written(self, worker, node, sname, size):
        self.ev_written_cnt += 1
        self.ev_written_sz += size

    def ev_hup(self, worker):
        self.ev_hup_cnt += 1

    def ev_timeout(self, worker):
        self.ev_timedout_cnt += 1

    def ev_close(self, worker):
        self.ev_close_cnt += 1


class TEventHandler(TEventHandlerBase):
    """Test Event Handler (1.8+)"""

    def ev_start(self, worker):
        self.ev_start_cnt += 1

    def ev_pickup(self, worker, node):
        self.ev_pickup_cnt += 1

    def ev_read(self, worker, node, sname, msg):
        self.ev_read_cnt += 1
        self.last_read = msg

    def ev_written(self, worker, node, sname, size):
        self.ev_written_cnt += 1
        self.ev_written_sz += size

    def ev_hup(self, worker, node, rc):
        self.ev_hup_cnt += 1

    def ev_close(self, worker, timedout):
        self.ev_close_cnt += 1
        if timedout:
            self.ev_timedout_cnt += 1


class TreeWorkerTest(unittest.TestCase):
    """
    TreeWorkerTest: test TreeWorker

        NODE_HEAD -> NODE_GATEWAY -> NODE_DISTANT
                  -> NODE_DIRECT    [defined in topology]
                  -> NODE_FOREIGN   [not defined in topology]

    Connections are really established to the target and command results
    are tested.
    """

    def setUp(self):
        """setup test environment topology"""
        task_terminate()  # ideally shouldn't be needed...
        self.task = task_self()
        # set task topology
        graph = TopologyGraph()
        graph.add_route(NodeSet(HOSTNAME), NodeSet(NODE_GATEWAY))
        graph.add_route(NodeSet(NODE_GATEWAY), NodeSet(NODE_DISTANT))
        graph.add_route(NodeSet(HOSTNAME), NodeSet(NODE_DIRECT))
        # NODE_FOREIGN is not included
        self.task.topology = graph.to_tree(HOSTNAME)

    def tearDown(self):
        """clean up test environment"""
        task_terminate()
        self.task = None

    def test_tree_run_event_legacy(self):
        """test simple tree run with legacy EventHandler"""
        teh = TEventHandlerLegacy()
        self.task.run('echo Lorem Ipsum', nodes=NODE_DISTANT, handler=teh)
        self.assertEqual(teh.ev_start_cnt, 1)
        self.assertEqual(teh.ev_pickup_cnt, 1)
        self.assertEqual(teh.ev_read_cnt, 1)
        self.assertEqual(teh.ev_written_cnt, 0)
        self.assertEqual(teh.ev_hup_cnt, 1)
        self.assertEqual(teh.ev_timedout_cnt, 0)
        self.assertEqual(teh.ev_close_cnt, 1)
        self.assertEqual(teh.last_read, b'Lorem Ipsum')

    def test_tree_run_event_legacy_timeout(self):
        """test simple tree run with legacy EventHandler with timeout"""
        teh = TEventHandlerLegacy()
        self.task.run('sleep 10', nodes=NODE_DISTANT, handler=teh, timeout=0.5)
        self.assertEqual(teh.ev_start_cnt, 1)
        self.assertEqual(teh.ev_pickup_cnt, 1)
        self.assertEqual(teh.ev_read_cnt, 0)      # nothing to read
        self.assertEqual(teh.ev_written_cnt, 0)
        self.assertEqual(teh.ev_hup_cnt, 0)       # no hup event if timed out
        self.assertEqual(teh.ev_timedout_cnt, 1)  # command timed out
        self.assertEqual(teh.ev_close_cnt, 1)

    def test_tree_run_event(self):
        """test simple tree run with EventHandler (1.8+)"""
        teh = TEventHandler()
        self.task.run('echo Lorem Ipsum', nodes=NODE_DISTANT, handler=teh)
        self.assertEqual(teh.ev_start_cnt, 1)
        self.assertEqual(teh.ev_pickup_cnt, 1)
        self.assertEqual(teh.ev_read_cnt, 1)
        self.assertEqual(teh.ev_written_cnt, 0)
        self.assertEqual(teh.ev_hup_cnt, 1)
        self.assertEqual(teh.ev_timedout_cnt, 0)
        self.assertEqual(teh.ev_close_cnt, 1)
        self.assertEqual(teh.last_read, b'Lorem Ipsum')

    def test_tree_run_event_timeout(self):
        """test simple tree run with EventHandler (1.8+) with timeout"""
        teh = TEventHandler()
        self.task.run('sleep 10', nodes=NODE_DISTANT, handler=teh, timeout=0.5)
        self.assertEqual(teh.ev_start_cnt, 1)
        self.assertEqual(teh.ev_pickup_cnt, 1)
        self.assertEqual(teh.ev_read_cnt, 0)      # nothing to read
        self.assertEqual(teh.ev_written_cnt, 0)
        self.assertEqual(teh.ev_hup_cnt, 0)       # no hup event if timed out
        self.assertEqual(teh.ev_timedout_cnt, 1)  # command timed out
        self.assertEqual(teh.ev_close_cnt, 1)

    def test_tree_run_noremote(self):
        """test tree run with remote=False"""
        teh = TEventHandler()
        self.task.run('echo %h', nodes=NODE_DISTANT, handler=teh, remote=False)
        self.assertEqual(teh.ev_start_cnt, 1)
        self.assertEqual(teh.ev_pickup_cnt, 1)
        self.assertEqual(teh.ev_read_cnt, 1)
        self.assertEqual(teh.ev_written_cnt, 0)
        self.assertEqual(teh.ev_hup_cnt, 1)
        self.assertEqual(teh.ev_timedout_cnt, 0)
        self.assertEqual(teh.ev_close_cnt, 1)
        self.assertEqual(teh.last_read, NODE_DISTANT.encode('ascii'))

    def test_tree_run_direct(self):
        """test tree run with direct target, in topology"""
        teh = TEventHandler()
        self.task.run('echo Lorem Ipsum', nodes=NODE_DIRECT, handler=teh)
        self.assertEqual(teh.ev_start_cnt, 1)
        self.assertEqual(teh.ev_pickup_cnt, 1)
        self.assertEqual(teh.ev_read_cnt, 1)
        self.assertEqual(teh.ev_written_cnt, 0)
        self.assertEqual(teh.ev_hup_cnt, 1)
        self.assertEqual(teh.ev_timedout_cnt, 0)
        self.assertEqual(teh.ev_close_cnt, 1)
        self.assertEqual(teh.last_read, b'Lorem Ipsum')

    def test_tree_run_foreign(self):
        """test tree run with direct target, not in topology"""
        teh = TEventHandler()
        self.task.run('echo Lorem Ipsum', nodes=NODE_FOREIGN, handler=teh)
        self.assertEqual(teh.ev_start_cnt, 1)
        self.assertEqual(teh.ev_pickup_cnt, 1)
        self.assertEqual(teh.ev_read_cnt, 1)
        self.assertEqual(teh.ev_written_cnt, 0)
        self.assertEqual(teh.ev_hup_cnt, 1)
        self.assertEqual(teh.ev_timedout_cnt, 0)
        self.assertEqual(teh.ev_close_cnt, 1)
        self.assertEqual(teh.last_read, b'Lorem Ipsum')

    def _tree_run_write(self, target):
        teh = TEventHandler()
        worker = self.task.shell('cat', nodes=target, handler=teh)
        worker.write(b'Lorem Ipsum')
        worker.set_write_eof()
        self.task.run()
        self.assertEqual(teh.ev_start_cnt, 1)
        self.assertEqual(teh.ev_pickup_cnt, 1)
        self.assertEqual(teh.ev_read_cnt, 1)
        self.assertEqual(teh.ev_written_cnt, 1)
        self.assertEqual(teh.ev_written_sz, len('Lorem Ipsum'))
        self.assertEqual(teh.ev_hup_cnt, 1)
        self.assertEqual(teh.ev_timedout_cnt, 0)
        self.assertEqual(teh.ev_close_cnt, 1)
        self.assertEqual(teh.last_read, b'Lorem Ipsum')

    def test_tree_run_write_distant(self):
        """test tree run with write(), distant target"""
        self._tree_run_write(NODE_DISTANT)

    def test_tree_run_write_direct(self):
        """test tree run with write(), direct target, in topology"""
        self._tree_run_write(NODE_DIRECT)

    def test_tree_run_write_foreign(self):
        """test tree run with write(), direct target, not in topology"""
        self._tree_run_write(NODE_FOREIGN)

    def test_tree_run_write_gateway(self):
        """test tree run with write(), gateway is target, not in topology"""
        self._tree_run_write(NODE_GATEWAY)

    def _tree_copy_file(self, target):
        teh = TEventHandler()
        srcf = make_temp_file(b'Lorem Ipsum', 'test_tree_copy_file_src')
        dest = make_temp_filename('test_tree_copy_file_dest')
        try:
            worker = self.task.copy(srcf.name, dest, nodes=target, handler=teh)
            self.task.run()
            self.assertEqual(teh.ev_start_cnt, 1)
            self.assertEqual(teh.ev_pickup_cnt, 1)
            self.assertEqual(teh.ev_read_cnt, 0)
            #self.assertEqual(teh.ev_written_cnt, 0)  # FIXME
            self.assertEqual(teh.ev_hup_cnt, 1)
            self.assertEqual(teh.ev_timedout_cnt, 0)
            self.assertEqual(teh.ev_close_cnt, 1)
            with open(dest, 'r') as destf:
                self.assertEqual(destf.read(), 'Lorem Ipsum')
        finally:
            os.remove(dest)

    def test_tree_copy_file_distant(self):
        """test tree copy: file, distant target"""
        self._tree_copy_file(NODE_DISTANT)

    def test_tree_copy_file_direct(self):
        """test tree copy: file, direct target, in topology"""
        self._tree_copy_file(NODE_DIRECT)

    def test_tree_copy_file_foreign(self):
        """test tree copy: file, direct target, not in topology"""
        self._tree_copy_file(NODE_FOREIGN)

    def test_tree_copy_file_gateway(self):
        """test tree copy: file, gateway is target"""
        self._tree_copy_file(NODE_GATEWAY)

    def _tree_copy_dir(self, target):
        teh = TEventHandler()

        srcdir = make_temp_dir()
        destdir = make_temp_dir()
        file1 = make_temp_file(b'Lorem Ipsum Unum', suffix=".txt", dir=srcdir)
        file2 = make_temp_file(b'Lorem Ipsum Duo', suffix=".txt", dir=srcdir)

        try:
            # add '/' to dest so that distant does like the others
            worker = self.task.copy(srcdir, destdir + '/', nodes=target,
                                    handler=teh)
            self.task.run()
            self.assertEqual(teh.ev_start_cnt, 1)
            self.assertEqual(teh.ev_pickup_cnt, 1)
            self.assertEqual(teh.ev_read_cnt, 0)
            #self.assertEqual(teh.ev_written_cnt, 0)  # FIXME
            self.assertEqual(teh.ev_hup_cnt, 1)
            self.assertEqual(teh.ev_timedout_cnt, 0)
            self.assertEqual(teh.ev_close_cnt, 1)

            # copy successful?
            copy_dest = join(destdir, srcdir)
            with open(join(copy_dest, basename(file1.name)), 'rb') as rfile1:
                self.assertEqual(rfile1.read(), b'Lorem Ipsum Unum')
            with open(join(copy_dest, basename(file2.name)), 'rb') as rfile2:
                self.assertEqual(rfile2.read(), b'Lorem Ipsum Duo')
        finally:
            # src
            file1 = None
            file2 = None
            os.rmdir(srcdir)
            # dest
            shutil.rmtree(destdir)

    def test_tree_copy_dir_distant(self):
        """test tree copy: directory, distant target"""
        self._tree_copy_dir(NODE_DISTANT)

    def test_tree_copy_dir_direct(self):
        """test tree copy: directory, direct target, in topology"""
        self._tree_copy_dir(NODE_DIRECT)

    def test_tree_copy_dir_foreign(self):
        """test tree copy: directory, direct target, not in topology"""
        self._tree_copy_dir(NODE_FOREIGN)

    def test_tree_copy_dir_gateway(self):
        """test tree copy: directory, gateway is target"""
        self._tree_copy_dir(NODE_GATEWAY)

    def _tree_rcopy_dir(self, target, dirsuffix=None):
        teh = TEventHandler()

        srcdir = make_temp_dir()
        destdir = make_temp_dir()
        file1 = make_temp_file(b'Lorem Ipsum Unum', suffix=".txt", dir=srcdir)
        file2 = make_temp_file(b'Lorem Ipsum Duo', suffix=".txt", dir=srcdir)

        try:
            worker = self.task.rcopy(srcdir, destdir, nodes=target, handler=teh)
            self.task.run()
            self.assertEqual(teh.ev_start_cnt, 1)
            self.assertEqual(teh.ev_pickup_cnt, 1)
            self.assertEqual(teh.ev_read_cnt, 0)
            #self.assertEqual(teh.ev_written_cnt, 0)  # FIXME
            self.assertEqual(teh.ev_hup_cnt, 1)
            self.assertEqual(teh.ev_timedout_cnt, 0)
            self.assertEqual(teh.ev_close_cnt, 1)

            # rcopy successful?
            if not dirsuffix:
                dirsuffix = target
            rcopy_dest = join(destdir, basename(srcdir) + '.' + dirsuffix)
            with open(join(rcopy_dest, basename(file1.name)), 'rb') as rfile1:
                self.assertEqual(rfile1.read(), b'Lorem Ipsum Unum')
            with open(join(rcopy_dest, basename(file2.name)), 'rb') as rfile2:
                self.assertEqual(rfile2.read(), b'Lorem Ipsum Duo')
        finally:
            # src
            file1 = None
            file2 = None
            os.rmdir(srcdir)
            # dest
            shutil.rmtree(destdir)

    def test_tree_rcopy_dir_distant(self):
        """test tree rcopy: directory, distant target"""
        # In distant tree mode, the returned result will include the
        # hostname of the distant host, not target name
        self._tree_rcopy_dir(NODE_DISTANT, dirsuffix=HOSTNAME)

    def test_tree_rcopy_dir_direct(self):
        """test tree rcopy: directory, direct target, in topology"""
        self._tree_rcopy_dir(NODE_DIRECT)

    def test_tree_rcopy_dir_foreign(self):
        """test tree rcopy: directory, direct target, not in topology"""
        self._tree_rcopy_dir(NODE_FOREIGN)

    def test_tree_rcopy_dir_gateway(self):
        """test tree rcopy: directory, gateway is target"""
        self._tree_rcopy_dir(NODE_GATEWAY)

    def test_tree_worker_missing_arguments(self):
        """test TreeWorker with missing arguments"""
        teh = TEventHandler()
        # no command nor source
        self.assertRaises(ValueError, TreeWorker, NODE_DISTANT, teh, 10)

    def test_tree_worker_name_compat(self):
        """test TreeWorker former name (WorkerTree)"""
        self.assertEqual(TreeWorker, WorkerTree)
