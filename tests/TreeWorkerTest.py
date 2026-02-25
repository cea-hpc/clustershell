"""
Unit test for ClusterShell.Worker.TreeWorker

This unit test requires working ssh connections to the following
local addresses: $HOSTNAME, localhost, 127.0.0.[2-7]

You can use the following options in ~/.ssh/config:

    Host your_hostname localhost 127.0.0.*
      StrictHostKeyChecking no
      LogLevel ERROR

The hostname mock command available in tests/bin needs to be
used on the remote nodes (tests/bin added to PATH in .bashrc).
"""

import logging
import os
from os.path import basename, join
import unittest
import warnings

from ClusterShell.NodeSet import NodeSet
from ClusterShell.Propagation import RouteResolvingError
from ClusterShell.Event import EventHandler
from ClusterShell.Task import task_self, task_terminate, task_wait
from ClusterShell.Task import Task, task_cleanup
from ClusterShell.Topology import TopologyGraph
from ClusterShell.Worker.Tree import TreeWorker, WorkerTree

from .TLib import HOSTNAME, make_temp_dir, make_temp_file, make_temp_filename


NODE_HEAD = HOSTNAME
NODE_GATEWAY = 'localhost'
NODE_GATEWAY2 = '127.0.0.[6-7]' # two ok
NODE_GATEWAY2F1 = '127.0.0.6,192.0.2.0' # one ok, one failed
NODE_DISTANT = '127.0.0.2'
NODE_DISTANT2 = '127.0.0.[2-3]'
NODE_DIRECT = '127.0.0.4'
NODE_FOREIGN = '127.0.0.5'


class TEventHandlerBase(EventHandler):
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

class TRoutingEventHandler(TEventHandler):
    """Test Routing Event Handler"""

    def __init__(self):
        TEventHandler.__init__(self)
        self.routing_events = []

    def _ev_routing(self, worker, arg):
        self.routing_events.append((worker, arg))


class TreeWorkerTestBase(unittest.TestCase):
    """
    TreeWorkerTestBase: test TreeWorker (base class)

    Override setUp() to set up the tree topology.

    Connections are really established to the target and command results
    are tested.
    """

    def setUp(self):
        """setup test environment topology"""
        task_terminate()  # ideally shouldn't be needed...
        self.task = task_self()
        # set task topology (to override)

    def tearDown(self):
        """clean up test environment"""
        task_terminate()
        self.task = None

    def _tree_run_write(self, target, separate_thread=False):
        """helper to write to stdin"""
        if separate_thread:
            task = Task()
        else:
            task = self.task
        teh = TEventHandler()
        worker = task.shell('cat', nodes=target, handler=teh)
        worker.write(b'Lorem Ipsum')
        worker.set_write_eof()
        task.run()
        if separate_thread:
            task_wait()
            task_cleanup()
        target_cnt = len(NodeSet(target))
        self.assertEqual(teh.ev_start_cnt, 1)
        self.assertEqual(teh.ev_pickup_cnt, target_cnt)
        self.assertEqual(teh.ev_read_cnt, target_cnt)
        self.assertEqual(teh.ev_written_cnt, target_cnt)
        self.assertEqual(teh.ev_written_sz, target_cnt * len('Lorem Ipsum'))
        self.assertEqual(teh.ev_hup_cnt, target_cnt)
        self.assertEqual(teh.ev_timedout_cnt, 0)
        self.assertEqual(teh.ev_close_cnt, 1)
        self.assertEqual(teh.last_read, b'Lorem Ipsum')

    def _tree_copy_file(self, target):
        """helper to copy file"""
        teh = TEventHandler()
        srcf = make_temp_file(b'Lorem Ipsum', 'test_tree_copy_file_src')
        dest = make_temp_filename('test_tree_copy_file_dest')
        try:
            worker = self.task.copy(srcf.name, dest, nodes=target, handler=teh)
            self.task.run()
            target_cnt = len(NodeSet(target))
            self.assertEqual(teh.ev_start_cnt, 1)
            self.assertEqual(teh.ev_pickup_cnt, target_cnt)
            self.assertEqual(teh.ev_read_cnt, 0)
            #self.assertEqual(teh.ev_written_cnt, 0)  # FIXME
            self.assertEqual(teh.ev_hup_cnt, target_cnt)
            self.assertEqual(teh.ev_timedout_cnt, 0)
            self.assertEqual(teh.ev_close_cnt, 1)
            with open(dest, 'r') as destf:
                self.assertEqual(destf.read(), 'Lorem Ipsum')
        finally:
            os.remove(dest)

    def _tree_copy_dir(self, target):
        """helper to copy directory"""
        teh = TEventHandler()

        srcdir = make_temp_dir()
        destdir = make_temp_dir()
        file1 = make_temp_file(b'Lorem Ipsum Unum', suffix=".txt",
                               dir=srcdir.name)
        file2 = make_temp_file(b'Lorem Ipsum Duo', suffix=".txt",
                               dir=srcdir.name)

        try:
            # add '/' to dest so that distant does like the others
            worker = self.task.copy(srcdir.name, destdir.name + '/',
                                    nodes=target, handler=teh)
            self.task.run()
            target_cnt = len(NodeSet(target))
            self.assertEqual(teh.ev_start_cnt, 1)
            self.assertEqual(teh.ev_pickup_cnt, target_cnt)
            self.assertEqual(teh.ev_read_cnt, 0)
            #self.assertEqual(teh.ev_written_cnt, 0)  # FIXME
            self.assertEqual(teh.ev_hup_cnt, target_cnt)
            self.assertEqual(teh.ev_timedout_cnt, 0)
            self.assertEqual(teh.ev_close_cnt, 1)

            # copy successful?
            copy_dest = join(destdir.name, srcdir.name)
            with open(join(copy_dest, basename(file1.name)), 'rb') as rfile1:
                self.assertEqual(rfile1.read(), b'Lorem Ipsum Unum')
            with open(join(copy_dest, basename(file2.name)), 'rb') as rfile2:
                self.assertEqual(rfile2.read(), b'Lorem Ipsum Duo')
        finally:
            file1.close()
            file2.close()
            srcdir.cleanup()
            destdir.cleanup()

    def _tree_rcopy_file(self, target):
        """helper to rcopy file"""
        teh = TEventHandler()

        # The file needs to be large enough to test GH#545
        b1 = b'Lorem Ipsum' * 1100000

        srcdir = make_temp_dir()
        destdir = make_temp_dir()
        srcfile = make_temp_file(b1, suffix=".txt", dir=srcdir.name)

        try:
            worker = self.task.rcopy(srcfile.name, destdir.name, nodes=target, handler=teh)
            self.task.run()
            target_cnt = len(NodeSet(target))
            self.assertEqual(teh.ev_start_cnt, 1)
            self.assertEqual(teh.ev_pickup_cnt, target_cnt)
            self.assertEqual(teh.ev_read_cnt, 0)
            #self.assertEqual(teh.ev_written_cnt, 0)  # FIXME
            self.assertEqual(teh.ev_hup_cnt, target_cnt)
            self.assertEqual(teh.ev_timedout_cnt, 0)
            self.assertEqual(teh.ev_close_cnt, 1)

            # rcopy successful?
            for tgt in NodeSet(target):
                rcopy_dest = join(destdir.name, basename(srcfile.name) + '.' + tgt)
                with open(rcopy_dest, 'rb') as tfile:
                    self.assertEqual(tfile.read(), b1)
        finally:
            srcfile.close()
            srcdir.cleanup()
            destdir.cleanup()

    def _tree_rcopy_dir(self, target):
        """helper to rcopy directory"""
        teh = TEventHandler()

        b1 = b'Lorem Ipsum Unum' * 100
        b2 = b'Lorem Ipsum Duo' * 100

        srcdir = make_temp_dir()
        destdir = make_temp_dir()
        file1 = make_temp_file(b1, suffix=".txt", dir=srcdir.name)
        file2 = make_temp_file(b2, suffix=".txt", dir=srcdir.name)

        try:
            worker = self.task.rcopy(srcdir.name, destdir.name, nodes=target,
                                     handler=teh)
            self.task.run()
            target_cnt = len(NodeSet(target))
            self.assertEqual(teh.ev_start_cnt, 1)
            self.assertEqual(teh.ev_pickup_cnt, target_cnt)
            self.assertEqual(teh.ev_read_cnt, 0)
            #self.assertEqual(teh.ev_written_cnt, 0)  # FIXME
            self.assertEqual(teh.ev_hup_cnt, target_cnt)
            self.assertEqual(teh.ev_timedout_cnt, 0)
            self.assertEqual(teh.ev_close_cnt, 1)

            # rcopy successful?
            for tgt in NodeSet(target):
                rcopy_dest = join(destdir.name, basename(srcdir.name) + '.' + tgt)
                with open(join(rcopy_dest, basename(file1.name)), 'rb') as rfile1:
                    self.assertEqual(rfile1.read(), b1)
                with open(join(rcopy_dest, basename(file2.name)), 'rb') as rfile2:
                    self.assertEqual(rfile2.read(), b2)
        finally:
            file1.close()
            file2.close()
            srcdir.cleanup()
            destdir.cleanup()


@unittest.skipIf(HOSTNAME == 'localhost', "does not work with hostname set to 'localhost'")
class TreeWorkerTest(TreeWorkerTestBase):
    """
    TreeWorkerTest: test TreeWorker

        NODE_HEAD -> NODE_GATEWAY -> NODE_DISTANT2
                  -> NODE_DIRECT    [defined in topology]
                  -> NODE_FOREIGN   [not defined in topology]

    Connections are really established to the target and command results
    are tested.
    """

    def setUp(self):
        """setup test environment topology"""
        TreeWorkerTestBase.setUp(self)
        # set task topology
        graph = TopologyGraph()
        graph.add_route(NodeSet(HOSTNAME), NodeSet(NODE_GATEWAY))
        graph.add_route(NodeSet(NODE_GATEWAY), NodeSet(NODE_DISTANT2))
        graph.add_route(NodeSet(HOSTNAME), NodeSet(NODE_DIRECT))
        # NODE_FOREIGN is not included
        self.task.topology = graph.to_tree(HOSTNAME)

    def test_tree_run_event_legacy(self):
        """test tree run with legacy EventHandler"""
        teh = TEventHandlerLegacy()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            self.task.run('echo Lorem Ipsum', nodes=NODE_DISTANT, handler=teh)
            self.assertEqual(len(w), 4)
        self.assertEqual(teh.ev_start_cnt, 1)
        self.assertEqual(teh.ev_pickup_cnt, 1)
        self.assertEqual(teh.ev_read_cnt, 1)
        self.assertEqual(teh.ev_written_cnt, 0)
        self.assertEqual(teh.ev_hup_cnt, 1)
        self.assertEqual(teh.ev_timedout_cnt, 0)
        self.assertEqual(teh.ev_close_cnt, 1)
        self.assertEqual(teh.last_read, b'Lorem Ipsum')

    def test_tree_run_event_legacy_timeout(self):
        """test tree run with legacy EventHandler with timeout"""
        teh = TEventHandlerLegacy()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            self.task.run('sleep 10', nodes=NODE_DISTANT, handler=teh, timeout=0.5)
            self.assertEqual(len(w), 2)
        self.assertEqual(teh.ev_start_cnt, 1)
        self.assertEqual(teh.ev_pickup_cnt, 1)
        self.assertEqual(teh.ev_read_cnt, 0)      # nothing to read
        self.assertEqual(teh.ev_written_cnt, 0)
        self.assertEqual(teh.ev_hup_cnt, 0)       # no hup event if timed out
        self.assertEqual(teh.ev_timedout_cnt, 1)  # command timed out
        self.assertEqual(teh.ev_close_cnt, 1)

    def test_tree_run_event(self):
        """test tree run with EventHandler (1.8+)"""
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

    def test_tree_run_event_multiple(self):
        """test multiple tree runs with EventHandler (1.8+)"""
        # Test for GH#566
        teh = TEventHandler()
        self.task.run('echo Lorem Ipsum Unum', nodes=NODE_DISTANT, handler=teh)
        self.assertEqual(teh.ev_start_cnt, 1)
        self.assertEqual(teh.ev_pickup_cnt, 1)
        self.assertEqual(teh.ev_read_cnt, 1)
        self.assertEqual(teh.ev_written_cnt, 0)
        self.assertEqual(teh.ev_hup_cnt, 1)
        self.assertEqual(teh.ev_timedout_cnt, 0)
        self.assertEqual(teh.ev_close_cnt, 1)
        self.assertEqual(teh.last_read, b'Lorem Ipsum Unum')
        self.task.run('echo Lorem Ipsum Duo', nodes=NODE_DISTANT, handler=teh)
        self.assertEqual(teh.ev_start_cnt, 2)
        self.assertEqual(teh.ev_pickup_cnt, 2)
        self.assertEqual(teh.ev_read_cnt, 2)
        self.assertEqual(teh.ev_written_cnt, 0)
        self.assertEqual(teh.ev_hup_cnt, 2)
        self.assertEqual(teh.ev_timedout_cnt, 0)
        self.assertEqual(teh.ev_close_cnt, 2)
        self.assertEqual(teh.last_read, b'Lorem Ipsum Duo')
        self.task.run('echo Lorem Ipsum Tres', nodes=NODE_DISTANT, handler=teh)
        self.assertEqual(teh.ev_start_cnt, 3)
        self.assertEqual(teh.ev_pickup_cnt, 3)
        self.assertEqual(teh.ev_read_cnt, 3)
        self.assertEqual(teh.ev_written_cnt, 0)
        self.assertEqual(teh.ev_hup_cnt, 3)
        self.assertEqual(teh.ev_timedout_cnt, 0)
        self.assertEqual(teh.ev_close_cnt, 3)
        self.assertEqual(teh.last_read, b'Lorem Ipsum Tres')

    def test_tree_run_event_timeout(self):
        """test tree run with EventHandler (1.8+) with timeout"""
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

    def test_tree_run_noremote_alt_localworker(self):
        """test tree run with remote=False and a non-exec localworker"""
        teh = TEventHandler()
        self.task.set_info('tree_default:local_workername', 'ssh')
        self.task.run('echo %h', nodes=NODE_DISTANT, handler=teh, remote=False)
        self.assertEqual(teh.ev_start_cnt, 1)
        self.assertEqual(teh.ev_pickup_cnt, 1)
        self.assertEqual(teh.ev_read_cnt, 1)
        self.assertEqual(teh.ev_written_cnt, 0)
        self.assertEqual(teh.ev_hup_cnt, 1)
        self.assertEqual(teh.ev_timedout_cnt, 0)
        self.assertEqual(teh.ev_close_cnt, 1)
        # The exec worker will expand %h to the host, but ssh will just echo '%h'
        self.assertEqual(teh.last_read, '%h'.encode('ascii'))
        del self.task._info['tree_default:local_workername']

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

    def test_tree_run_write_distant(self):
        """test tree run with write(), distant target"""
        self._tree_run_write(NODE_DISTANT)

    def test_tree_run_write_distant2(self):
        """test tree run with write(), distant 2 targets"""
        self._tree_run_write(NODE_DISTANT2)

    def test_tree_run_write_direct(self):
        """test tree run with write(), direct target, in topology"""
        self._tree_run_write(NODE_DIRECT)

    def test_tree_run_write_foreign(self):
        """test tree run with write(), direct target, not in topology"""
        self._tree_run_write(NODE_FOREIGN)

    def test_tree_run_write_gateway(self):
        """test tree run with write(), gateway is target, not in topology"""
        self._tree_run_write(NODE_GATEWAY)

    def test_tree_run_write_distant_mt(self):
        """test tree run with write(), distant target, separate thread"""
        self._tree_run_write(NODE_DISTANT, separate_thread=True)

    def test_tree_run_write_distant2_mt(self):
        """test tree run with write(), distant 2 targets, separate thread"""
        self._tree_run_write(NODE_DISTANT2, separate_thread=True)

    def test_tree_run_write_direct_mt(self):
        """test tree run with write(), direct target, in topology, separate thread"""
        self._tree_run_write(NODE_DIRECT, separate_thread=True)

    def test_tree_run_write_foreign_mt(self):
        """test tree run with write(), direct target, not in topology, separate thread"""
        self._tree_run_write(NODE_FOREIGN, separate_thread=True)

    def test_tree_run_write_gateway_mt(self):
        """test tree run with write(), gateway is target, not in topology, separate thread"""
        self._tree_run_write(NODE_GATEWAY, separate_thread=True)

    ### copy ###

    def test_tree_copy_file_distant(self):
        """test tree copy: file, distant target"""
        self._tree_copy_file(NODE_DISTANT)

    def test_tree_copy_file_distant2(self):
        """test tree copy: file, distant 2 targets"""
        self._tree_copy_file(NODE_DISTANT2)

    def test_tree_copy_file_direct(self):
        """test tree copy: file, direct target, in topology"""
        self._tree_copy_file(NODE_DIRECT)

    def test_tree_copy_file_foreign(self):
        """test tree copy: file, direct target, not in topology"""
        self._tree_copy_file(NODE_FOREIGN)

    def test_tree_copy_file_gateway(self):
        """test tree copy: file, gateway is target"""
        self._tree_copy_file(NODE_GATEWAY)

    def test_tree_copy_dir_distant(self):
        """test tree copy: directory, distant target"""
        self._tree_copy_dir(NODE_DISTANT)

    def test_tree_copy_dir_distant2(self):
        """test tree copy: directory, distant 2 targets"""
        self._tree_copy_dir(NODE_DISTANT2)

    def test_tree_copy_dir_direct(self):
        """test tree copy: directory, direct target, in topology"""
        self._tree_copy_dir(NODE_DIRECT)

    def test_tree_copy_dir_foreign(self):
        """test tree copy: directory, direct target, not in topology"""
        self._tree_copy_dir(NODE_FOREIGN)

    def test_tree_copy_dir_gateway(self):
        """test tree copy: directory, gateway is target"""
        self._tree_copy_dir(NODE_GATEWAY)

    ### rcopy ###

    def test_tree_rcopy_dir_distant(self):
        """test tree rcopy: directory, distant target"""
        # In distant tree mode, the returned result will include the
        # hostname of the distant host, not target name
        self._tree_rcopy_dir(NODE_DISTANT)

    def test_tree_rcopy_dir_distant2(self):
        """test tree rcopy: directory, distant 2 targets"""
        self._tree_rcopy_dir(NODE_DISTANT2)

    def test_tree_rcopy_dir_direct(self):
        """test tree rcopy: directory, direct target, in topology"""
        self._tree_rcopy_dir(NODE_DIRECT)

    def test_tree_rcopy_dir_foreign(self):
        """test tree rcopy: directory, direct target, not in topology"""
        self._tree_rcopy_dir(NODE_FOREIGN)

    def test_tree_rcopy_dir_gateway(self):
        """test tree rcopy: directory, gateway is target"""
        self._tree_rcopy_dir(NODE_GATEWAY)

    def test_tree_rcopy_file_distant(self):
        """test tree rcopy: file, distant target"""
        self._tree_rcopy_file(NODE_DISTANT)

    def test_tree_rcopy_file_distant2(self):
        """test tree rcopy: file, distant 2 targets"""
        self._tree_rcopy_file(NODE_DISTANT2)

    def test_tree_rcopy_file_direct(self):
        """test tree rcopy: file, direct target, in topology"""
        self._tree_rcopy_file(NODE_DIRECT)

    def test_tree_rcopy_file_foreign(self):
        """test tree rcopy: file, direct target, not in topology"""
        self._tree_rcopy_file(NODE_FOREIGN)

    def test_tree_worker_missing_arguments(self):
        """test TreeWorker with missing arguments"""
        teh = TEventHandler()
        # no command nor source
        self.assertRaises(ValueError, TreeWorker, NODE_DISTANT, teh, 10)

    def test_tree_worker_name_compat(self):
        """test TreeWorker former name (WorkerTree)"""
        self.assertEqual(TreeWorker, WorkerTree)

    def test_tree_run_abort_on_start(self):
        """test tree run abort on ev_start"""
        class TEventAbortOnStartHandler(TEventHandler):
            """Test Event Abort On Start Handler"""

            def __init__(self, testcase):
                TEventHandler.__init__(self)
                self.testcase = testcase

            def ev_start(self, worker):
                TEventHandler.ev_start(self, worker)
                worker.abort()

            def ev_hup(self, worker, node, rc):
                TEventHandler.ev_hup(self, worker, node, rc)
                self.testcase.assertEqual(rc, os.EX_PROTOCOL)

        teh = TEventAbortOnStartHandler(self)
        self.task.run('echo Lorem Ipsum', nodes=NODE_DISTANT, handler=teh)
        self.assertEqual(teh.ev_start_cnt, 1)
        #self.assertEqual(teh.ev_pickup_cnt, 0) # XXX to be improved
        self.assertEqual(teh.ev_read_cnt, 0)
        self.assertEqual(teh.ev_written_cnt, 0)
        self.assertEqual(teh.ev_hup_cnt, 1)
        self.assertEqual(teh.ev_timedout_cnt, 0)
        self.assertEqual(teh.ev_close_cnt, 1)
        self.assertEqual(teh.last_read, None)

    def test_tree_run_abort_on_pickup(self):
        """test tree run abort on ev_pickup"""
        class TEventAbortOnPickupHandler(TEventHandler):
            """Test Event Abort On Pickup Handler"""

            def __init__(self, testcase):
                TEventHandler.__init__(self)
                self.testcase = testcase

            def ev_pickup(self, worker, node):
                TEventHandler.ev_pickup(self, worker, node)
                worker.abort()

            def ev_hup(self, worker, node, rc):
                TEventHandler.ev_hup(self, worker, node, rc)
                self.testcase.assertEqual(rc, os.EX_PROTOCOL)

        teh = TEventAbortOnPickupHandler(self)
        self.task.run('echo Lorem Ipsum', nodes=NODE_DISTANT, handler=teh)
        self.assertEqual(teh.ev_start_cnt, 1)
        self.assertEqual(teh.ev_pickup_cnt, 1)
        self.assertEqual(teh.ev_read_cnt, 0)
        self.assertEqual(teh.ev_written_cnt, 0)
        self.assertEqual(teh.ev_hup_cnt, 1)
        self.assertEqual(teh.ev_timedout_cnt, 0)
        self.assertEqual(teh.ev_close_cnt, 1)
        self.assertEqual(teh.last_read, None)

    def test_tree_run_abort_on_read(self):
        """test tree run abort on ev_read"""
        class TEventAbortOnReadHandler(TEventHandler):
            """Test Event Abort On Start Handler"""

            def __init__(self, testcase):
                TEventHandler.__init__(self)
                self.testcase = testcase

            def ev_read(self, worker, node, sname, msg):
                TEventHandler.ev_read(self, worker, node, sname, msg)
                worker.abort()

            def ev_hup(self, worker, node, rc):
                TEventHandler.ev_hup(self, worker, node, rc)
                self.testcase.assertEqual(rc, os.EX_PROTOCOL)

        teh = TEventAbortOnReadHandler(self)
        self.task.run('echo Lorem Ipsum', nodes=NODE_DISTANT, handler=teh)
        self.assertEqual(teh.ev_start_cnt, 1)
        self.assertEqual(teh.ev_pickup_cnt, 1)
        self.assertEqual(teh.ev_read_cnt, 1)
        self.assertEqual(teh.ev_written_cnt, 0)
        self.assertEqual(teh.ev_hup_cnt, 1)
        self.assertEqual(teh.ev_timedout_cnt, 0)
        self.assertEqual(teh.ev_close_cnt, 1)
        self.assertEqual(teh.last_read, b'Lorem Ipsum')

    def test_tree_run_abort_on_hup(self):
        """test tree run abort on ev_hup"""
        class TEventAbortOnHupHandler(TEventHandler):
            """Test Event Abort On Hup Handler"""

            def __init__(self, testcase):
                TEventHandler.__init__(self)
                self.testcase = testcase

            def ev_hup(self, worker, node, rc):
                TEventHandler.ev_hup(self, worker, node, rc)
                worker.abort()

        teh = TEventAbortOnHupHandler(self)
        self.task.run('echo Lorem Ipsum', nodes=NODE_DISTANT, handler=teh)
        self.assertEqual(teh.ev_start_cnt, 1)
        self.assertEqual(teh.ev_pickup_cnt, 1)
        self.assertEqual(teh.ev_read_cnt, 1)
        self.assertEqual(teh.ev_written_cnt, 0)
        self.assertEqual(teh.ev_hup_cnt, 1)
        self.assertEqual(teh.ev_timedout_cnt, 0)
        self.assertEqual(teh.ev_close_cnt, 1)
        self.assertEqual(teh.last_read, b'Lorem Ipsum')

    def test_tree_run_abort_on_close(self):
        """test tree run abort on ev_close"""
        class TEventAbortOnCloseHandler(TEventHandler):
            """Test Event Abort On Close Handler"""

            def __init__(self, testcase):
                TEventHandler.__init__(self)
                self.testcase = testcase

            def ev_close(self, worker, timedout):
                TEventHandler.ev_close(self, worker, timedout)
                self.testcase.assertEqual(type(worker), TreeWorker)
                worker.abort()

        teh = TEventAbortOnCloseHandler(self)
        self.task.run('echo Lorem Ipsum', nodes=NODE_DISTANT, handler=teh)
        self.assertEqual(teh.ev_start_cnt, 1)
        self.assertEqual(teh.ev_pickup_cnt, 1)
        self.assertEqual(teh.ev_read_cnt, 1)
        self.assertEqual(teh.ev_written_cnt, 0)
        self.assertEqual(teh.ev_hup_cnt, 1)
        self.assertEqual(teh.ev_timedout_cnt, 0)
        self.assertEqual(teh.ev_close_cnt, 1)
        self.assertEqual(teh.last_read, b'Lorem Ipsum')

    def test_tree_run_abort_on_timer(self):
        """test tree run abort on timer"""
        class TEventAbortOnTimerHandler(TEventHandler):
            """Test Event Abort On Timer Handler"""

            def __init__(self, testcase):
                TEventHandler.__init__(self)
                self.testcase = testcase
                self.worker = None

            def ev_timer(self, timer):
                self.worker.abort()

            def ev_hup(self, worker, node, rc):
                TEventHandler.ev_hup(self, worker, node, rc)
                self.testcase.assertEqual(rc, os.EX_PROTOCOL)

        # Test abort from a timer's event handler
        teh = TEventAbortOnTimerHandler(self)
        # channel might take some time to set up; hard to time it
        # we play it safe here and don't expect anything to read
        teh.worker = self.task.shell('sleep 10; echo Lorem Ipsum', nodes=NODE_DISTANT, handler=teh)
        timer1 = self.task.timer(3, handler=teh)
        self.task.run()
        self.assertEqual(teh.ev_start_cnt, 1)
        self.assertEqual(teh.ev_pickup_cnt, 1)
        self.assertEqual(teh.ev_read_cnt, 0)
        self.assertEqual(teh.ev_written_cnt, 0)
        self.assertEqual(teh.ev_hup_cnt, 1)
        self.assertEqual(teh.ev_timedout_cnt, 0)
        self.assertEqual(teh.ev_close_cnt, 1)
        self.assertEqual(teh.last_read, None)

    def test_tree_gateway_bogus_single(self):
        """test tree run with bogus single gateway"""
        # Part of GH#566
        teh = TEventHandler()
        os.environ['CLUSTERSHELL_GW_PYTHON_EXECUTABLE'] = '/test/bogus'
        try:
            self.assertRaises(RouteResolvingError, self.task.run, 'echo Lorem Ipsum',
                              nodes=NODE_DISTANT, handler=teh)
        finally:
            del os.environ['CLUSTERSHELL_GW_PYTHON_EXECUTABLE']


@unittest.skipIf(HOSTNAME == 'localhost', "does not work with hostname set to 'localhost'")
class TreeWorkerGW2Test(TreeWorkerTestBase):
    """
    TreeWorkerTest: test TreeWorker with two functional gateways

        NODE_HEAD -> NODE_GATEWAY2 -> NODE_DISTANT2

    Connections are really established to the target and command results
    are tested.
    """

    def setUp(self):
        """setup test environment topology"""
        TreeWorkerTestBase.setUp(self)
        # set task topology
        graph = TopologyGraph()
        graph.add_route(NodeSet(HOSTNAME), NodeSet(NODE_GATEWAY2))
        graph.add_route(NodeSet(NODE_GATEWAY2), NodeSet(NODE_DISTANT2))
        self.task.topology = graph.to_tree(HOSTNAME)

    def test_tree_run_gw2_event(self):
        """test tree run with EventHandler and 2 gateways"""
        teh = TEventHandler()
        self.task.run('echo Lorem Ipsum', nodes=NODE_DISTANT2, handler=teh)
        self.assertEqual(teh.ev_start_cnt, 1)
        self.assertEqual(teh.ev_pickup_cnt, 2)
        self.assertEqual(teh.ev_read_cnt, 2)
        self.assertEqual(teh.ev_written_cnt, 0)
        self.assertEqual(teh.ev_hup_cnt, 2)
        self.assertEqual(teh.ev_timedout_cnt, 0)
        self.assertEqual(teh.ev_close_cnt, 1)
        self.assertEqual(teh.last_read, b'Lorem Ipsum')

    def test_tree_run_gw2_event_timeout(self):
        """test tree run with EventHandler, 2 gateways with timeout"""
        teh = TEventHandler()
        self.task.run('sleep 10', nodes=NODE_DISTANT2, handler=teh, timeout=0.5)
        self.assertEqual(teh.ev_start_cnt, 1)
        self.assertEqual(teh.ev_pickup_cnt, 2)
        self.assertEqual(teh.ev_read_cnt, 0)
        self.assertEqual(teh.ev_written_cnt, 0)
        self.assertEqual(teh.ev_hup_cnt, 0)       # no hup event if timed out
        self.assertEqual(teh.ev_timedout_cnt, 1)  # command timed out
        self.assertEqual(teh.ev_close_cnt, 1)

    def test_tree_run_gw2_event_timeout_2w(self):
        """test tree run with EventHandler, 2 gateways with timeout, 2 workers"""
        teh = TEventHandler()
        n1, n2 = NodeSet(NODE_DISTANT2).split(2)
        self.task.shell('sleep 10', nodes=n1, handler=teh, timeout=0.5)
        self.task.run('sleep 10', nodes=n2, handler=teh, timeout=0.5)
        self.assertEqual(teh.ev_start_cnt, 2)
        self.assertEqual(teh.ev_pickup_cnt, 2)
        self.assertEqual(teh.ev_read_cnt, 0)
        self.assertEqual(teh.ev_written_cnt, 0)
        self.assertEqual(teh.ev_hup_cnt, 0)       # no hup event if timed out
        self.assertEqual(teh.ev_timedout_cnt, 2)  # command timed out
        self.assertEqual(teh.ev_close_cnt, 2)

    def test_tree_run_gw2_write_distant(self):
        """test tree run with write(), 2 gateways, distant target"""
        self._tree_run_write(NODE_DISTANT)

    def test_tree_run_gw2_write_distant2(self):
        """test tree run with write(), 2 gateways, distant 2 targets"""
        self._tree_run_write(NODE_DISTANT2)

    def test_tree_run_gw2_write_distant2_mt(self):
        """test tree run with write(), 2 gateways, distant 2 targets, separate thread"""
        self._tree_run_write(NODE_DISTANT2, separate_thread=True)


@unittest.skipIf(HOSTNAME == 'localhost', "does not work with hostname set to 'localhost'")
class TreeWorkerGW2F1FTest(TreeWorkerTestBase):
    """
    TreeWorkerTest: test TreeWorker with two gateways, one being failed

        NODE_HEAD -> NODE_GATEWAY2F1 -> NODE_DISTANT2

    Connections are really established to the target and command results
    are tested.
    """

    def setUp(self):
        """setup test environment topology"""
        TreeWorkerTestBase.setUp(self)
        # set task topology
        graph = TopologyGraph()
        graph.add_route(NodeSet(HOSTNAME), NodeSet(NODE_GATEWAY2F1))
        graph.add_route(NodeSet(NODE_GATEWAY2F1), NodeSet(NODE_DISTANT2))
        self.task.topology = graph.to_tree(HOSTNAME)

    def test_tree_run_gw2f1_event(self):
        """test tree run with EventHandler and 1/2 gateways"""
        teh = TEventHandler()
        self.task.run('echo Lorem Ipsum', nodes=NODE_DISTANT2, handler=teh)
        self.assertEqual(teh.ev_start_cnt, 1)
        self.assertEqual(teh.ev_pickup_cnt, 2)
        self.assertEqual(teh.ev_read_cnt, 3)  # 2 + gw error
        self.assertEqual(teh.ev_written_cnt, 0)
        self.assertEqual(teh.ev_hup_cnt, 2)
        self.assertEqual(teh.ev_timedout_cnt, 0)
        self.assertEqual(teh.ev_close_cnt, 1)
        self.assertEqual(teh.last_read, b'Lorem Ipsum')

    def test_tree_run_gw2f1_event_timeout(self):
        """test tree run with EventHandler, 1/2 gateways with timeout"""
        teh = TEventHandler()
        self.task.run('sleep 10', nodes=NODE_DISTANT2, handler=teh, timeout=0.5)
        self.assertEqual(teh.ev_start_cnt, 1)
        self.assertEqual(teh.ev_pickup_cnt, 2)
        self.assertEqual(teh.ev_read_cnt, 1)      # 1 gateway failure to read
        self.assertEqual(teh.ev_written_cnt, 0)
        self.assertEqual(teh.ev_hup_cnt, 0)       # no hup event if timed out
        self.assertEqual(teh.ev_timedout_cnt, 1)  # command timed out
        self.assertEqual(teh.ev_close_cnt, 1)

    def test_tree_run_gw2f1_event_timeout_2w(self):
        """test tree run with EventHandler, 1/2 gateways with timeout, 2 workers"""
        teh = TEventHandler()
        n1, n2 = NodeSet(NODE_DISTANT2).split(2)
        self.task.shell('sleep 10', nodes=n1, handler=teh, timeout=0.5)
        self.task.run('sleep 10', nodes=n2, handler=teh, timeout=0.5)
        self.assertEqual(teh.ev_start_cnt, 2)
        self.assertEqual(teh.ev_pickup_cnt, 2)
        self.assertEqual(teh.ev_read_cnt, 1)      # 1 gateway failure to read
        self.assertEqual(teh.ev_written_cnt, 0)
        self.assertEqual(teh.ev_hup_cnt, 0)       # no hup event if timed out
        self.assertEqual(teh.ev_timedout_cnt, 2)  # command timed out
        self.assertEqual(teh.ev_close_cnt, 2)

    def test_tree_run_gw2f1_write_distant(self):
        """test tree run with write(), 1/2 gateways, distant target"""
        self._tree_run_write(NODE_DISTANT)

    # FIXME, issue with stdin write in gw2f1 mode
    #def test_tree_run_gw2f1_write_distant2(self):
    #    """test tree run with write(), 1/2 gateways, distant 2 targets"""
    #    logging.basicConfig(level=logging.DEBUG)
    #    self._tree_run_write(NODE_DISTANT2)

    def test_tree_run_gw2f1_write_distant2_mt(self):
        """test tree run with write(), 1/2 gateways, distant 2 targets, separate thread"""
        self._tree_run_write(NODE_DISTANT2, separate_thread=True)

    def test_tree_run_gw2f1_reroute(self):
        """test tree run with reroute event, 1/2 gateways"""
        teh = TRoutingEventHandler()
        self.task.run('echo Lorem Ipsum', nodes=NODE_DISTANT2, handler=teh)
        self.assertEqual(len(teh.routing_events), 1)
        worker, arg = teh.routing_events[0]
        self.assertEqual(worker.command, "echo Lorem Ipsum")
        self.assertEqual(arg["event"], "reroute")
        self.assertIn(arg["targets"], NodeSet(NODE_DISTANT2))
        # event handler checks
        self.assertEqual(teh.ev_start_cnt, 1)
        self.assertEqual(teh.ev_pickup_cnt, 2)
        # read_cnt += 1 for gateway error on stderr (so currently not fully
        # transparent to the user)
        self.assertEqual(teh.ev_read_cnt, 3)
        self.assertEqual(teh.ev_written_cnt, 0)
        self.assertEqual(teh.ev_hup_cnt, 2)
        self.assertEqual(teh.ev_timedout_cnt, 0)
        self.assertEqual(teh.ev_close_cnt, 1)
        self.assertEqual(teh.last_read, b'Lorem Ipsum')
