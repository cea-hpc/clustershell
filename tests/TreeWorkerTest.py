"""
Unit test for ClusterShell.Worker.WorkerTree
"""

import unittest

from ClusterShell import Task as TaskModule

from ClusterShell.NodeSet import NodeSet
from ClusterShell.Propagation import PropagationChannel
from ClusterShell.Task import task_self, task_terminate, task_cleanup
from ClusterShell.Topology import TopologyGraph

from TLib import HOSTNAME


class TEventHandlerBase(object):
    """Base Test class for EventHandler"""

    def __init__(self):
        self.ev_start_cnt = 0
        self.ev_pickup_cnt = 0
        self.ev_read_cnt = 0
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

    def ev_hup(self, worker, node, rc):
        self.ev_hup_cnt += 1

    def ev_close(self, worker, timedout):
        self.ev_close_cnt += 1
        if timedout:
            self.ev_timedout_cnt += 1


class TPropagationChannel(PropagationChannel):
    """Patched PropagationChannel (see TreeWorkerTest)"""

    def start(self):
        """start: substitute topology sent to gateway"""
        graph = TopologyGraph()
        graph.add_route(NodeSet('dummy-head'), NodeSet(HOSTNAME))
        graph.add_route(NodeSet(HOSTNAME), NodeSet('localhost'))
        self.task.topology = graph.to_tree(HOSTNAME)
        PropagationChannel.start(self)

    def shell(self, nodes, command, worker, timeout, stderr, gw_invoke_cmd,
              remote):
        """shell: substitute target"""
        PropagationChannel.shell(self, NodeSet('localhost'), command, worker,
                                 timeout, stderr, gw_invoke_cmd, remote)

    def recv_ctl(self, msg):
        """recv_ctl: substitute node received"""
        msg.nodes = 'faketarget'
        PropagationChannel.recv_ctl(self, msg)


class TreeWorkerTest(unittest.TestCase):
    """
    TreeWorkerTest: test WorkerTree

        head->gw->target

    We use a node name substitution trick to make the code work with
    only two hostnames: HOSTNAME and localhost.

    Node name substitutions are done by TPropagationChannel.
    Connections are always done this way: HOSTNAME to localhost.
    View from head node:
        HOSTNAME (head) -> localhost (gw) -> faketarget (target)
    View from the gateway (topology is recomputed from gw):
        (dummy-head ->) HOSTNAME (gw, now head) -> localhost (target)

    The connection is really established to the target and command
    result is returned and tested.
    """

    def setUp(self):
        """setup test environment with fake PropagationChannel and topology"""
        task_terminate()  # ideally shouldn't be needed...
        self.task = task_self()

        # class monkey patching
        TaskModule.PropagationChannel = TPropagationChannel

        # set task topology
        graph = TopologyGraph()
        graph.add_route(NodeSet(HOSTNAME), NodeSet('localhost'))
        graph.add_route(NodeSet('localhost'), NodeSet('faketarget'))
        self.task.topology = graph.to_tree(HOSTNAME)

    def tearDown(self):
        """cleanup test environment"""
        task_terminate()
        self.task = None
        TaskModule.PropagationChannel = PropagationChannel

    def test_tree_run_event_legacy(self):
        """test simple tree run with legacy EventHandler"""
        teh = TEventHandlerLegacy()
        self.task.run('echo Lorem Ipsum', nodes='faketarget', handler=teh)
        self.assertEqual(teh.ev_start_cnt, 1)
        self.assertEqual(teh.ev_pickup_cnt, 1)
        self.assertEqual(teh.ev_read_cnt, 1)
        self.assertEqual(teh.ev_hup_cnt, 1)
        self.assertEqual(teh.ev_timedout_cnt, 0)
        self.assertEqual(teh.ev_close_cnt, 1)
        self.assertEqual(teh.last_read, b'Lorem Ipsum')

    def test_tree_run_event_legacy_timeout(self):
        """test simple tree run with legacy EventHandler with timeout"""
        teh = TEventHandlerLegacy()
        self.task.run('sleep 10', nodes='faketarget', handler=teh, timeout=0.5)
        self.assertEqual(teh.ev_start_cnt, 1)
        self.assertEqual(teh.ev_pickup_cnt, 1)
        self.assertEqual(teh.ev_read_cnt, 0)      # nothing to read
        self.assertEqual(teh.ev_hup_cnt, 0)       # no hup event if timed out
        self.assertEqual(teh.ev_timedout_cnt, 1)  # command timed out
        self.assertEqual(teh.ev_close_cnt, 1)

    def test_tree_run_event(self):
        """test simple tree run with EventHandler (1.8+)"""
        teh = TEventHandler()
        self.task.run('echo Lorem Ipsum', nodes='faketarget', handler=teh)
        self.assertEqual(teh.ev_start_cnt, 1)
        self.assertEqual(teh.ev_pickup_cnt, 1)
        self.assertEqual(teh.ev_read_cnt, 1)
        self.assertEqual(teh.ev_hup_cnt, 1)
        self.assertEqual(teh.ev_timedout_cnt, 0)
        self.assertEqual(teh.ev_close_cnt, 1)
        self.assertEqual(teh.last_read, b'Lorem Ipsum')

    def test_tree_run_event_timeout(self):
        """test simple tree run with EventHandler (1.8+) with timeout"""
        teh = TEventHandler()
        self.task.run('sleep 10', nodes='faketarget', handler=teh, timeout=0.5)
        self.assertEqual(teh.ev_start_cnt, 1)
        self.assertEqual(teh.ev_pickup_cnt, 1)
        self.assertEqual(teh.ev_read_cnt, 0)      # nothing to read
        self.assertEqual(teh.ev_hup_cnt, 0)       # no hup event if timed out
        self.assertEqual(teh.ev_timedout_cnt, 1)  # command timed out
        self.assertEqual(teh.ev_close_cnt, 1)
