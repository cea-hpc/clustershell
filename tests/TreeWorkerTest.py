"""
Unit test for ClusterShell.Worker.WorkerTree
"""

import unittest

from ClusterShell import Task as TaskModule

from ClusterShell.NodeSet import NodeSet
from ClusterShell.Propagation import PropagationChannel
from ClusterShell.Task import task_self, task_terminate
from ClusterShell.Topology import TopologyGraph

from TLib import HOSTNAME


TEST_STRING = 'Lorem Ipsum'


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


class TEventHandler1(TEventHandlerBase):
    """Test Event Handler 1.0"""

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


class TEventHandler2(TEventHandlerBase):
    """Test Event Handler 2.0"""

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
        PropagationChannel.shell(self, 'localhost', command, worker, timeout,
                                 stderr, gw_invoke_cmd, remote)

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

    def test_tree_run_event1(self):
        """test simple tree run with legacy EventHandler"""
        teh = TEventHandler1()
        self.task.run('echo ' + TEST_STRING, nodes='faketarget', handler=teh)
        self.assertEqual(teh.ev_start_cnt, 1)
        #self.assertEqual(teh.ev_pickup_cnt, 1)  # broken!
        self.assertEqual(teh.ev_read_cnt, 1)
        self.assertEqual(teh.ev_hup_cnt, 1)
        self.assertEqual(teh.ev_timedout_cnt, 0)
        self.assertEqual(teh.ev_close_cnt, 1)
        self.assertEqual(teh.last_read, TEST_STRING)

    def test_tree_run_event1_timeout(self):
        """test simple tree run with legacy EventHandler (with timeout)"""
        #self.task.set_info('debug', True)
        teh = TEventHandler1()
        self.task.run('sleep 10', nodes='faketarget', handler=teh, timeout=1)
        self.assertEqual(teh.ev_start_cnt, 1)
        #self.assertEqual(teh.ev_pickup_cnt, 1)   # broken!
        self.assertEqual(teh.ev_read_cnt, 0)      # nothing to read
        #self.assertEqual(teh.ev_hup_cnt, 1)      # broken!
        self.assertEqual(teh.ev_timedout_cnt, 1)  # command timed out
        self.assertEqual(teh.ev_close_cnt, 1)

    def test_tree_run_event2(self):
        """test simple tree run with EventHandler 2.0"""
        teh = TEventHandler2()
        self.task.run('echo ' + TEST_STRING, nodes='faketarget', handler=teh)
        self.assertEqual(teh.ev_start_cnt, 1)
        #self.assertEqual(teh.ev_pickup_cnt, 1)  # broken!
        self.assertEqual(teh.ev_read_cnt, 1)
        self.assertEqual(teh.ev_hup_cnt, 1)
        self.assertEqual(teh.ev_timedout_cnt, 0)
        self.assertEqual(teh.ev_close_cnt, 1)
        self.assertEqual(teh.last_read, TEST_STRING)

    def test_tree_run_event2_timeout(self):
        """test simple tree run with EventHandler 2.0 (with timeout)"""
        teh = TEventHandler2()
        self.task.run('sleep 10', nodes='faketarget', handler=teh, timeout=1)
        self.assertEqual(teh.ev_start_cnt, 1)
        #self.assertEqual(teh.ev_pickup_cnt, 1)   # broken!
        self.assertEqual(teh.ev_read_cnt, 0)      # nothing to read
        #self.assertEqual(teh.ev_hup_cnt, 1)      # broken!
        self.assertEqual(teh.ev_timedout_cnt, 1)  # command timed out
        self.assertEqual(teh.ev_close_cnt, 1)
