"""
Unit test for ClusterShell.Task in tree mode
"""

import logging
import os
from textwrap import dedent
import unittest

from ClusterShell.Propagation import RouteResolvingError
from ClusterShell.Task import task_self
from ClusterShell.Topology import TopologyError

from TLib import HOSTNAME, make_temp_file

# live logging with nosetests --nologcapture
logging.basicConfig(level=logging.DEBUG)


class TreeTaskTest(unittest.TestCase):
    """Test cases for Tree-related Task methods"""

    def tearDown(self):
        """clear task topology"""
        task_self().topology = None

    def test_shell_auto_tree_dummy(self):
        """test task shell auto tree"""
        # initialize a dummy topology.conf file
        topofile = make_temp_file(dedent("""
                        [Main]
                        %s: dummy-gw
                        dummy-gw: dummy-node"""% HOSTNAME).encode())
        task = task_self()
        task.set_default("auto_tree", True)
        task.TOPOLOGY_CONFIGS = [topofile.name]

        self.assertRaises(RouteResolvingError, task.run, "/bin/hostname",
                          nodes="dummy-node", stderr=True)
        self.assertEqual(task.max_retcode(), None)

    def test_shell_auto_tree_noconf(self):
        """test task shell auto tree [no topology.conf]"""
        task = task_self()
        task.set_default("auto_tree", True)
        dummyfile = "/some/dummy/path/topo.conf"
        self.assertFalse(os.path.exists(dummyfile))
        task.TOPOLOGY_CONFIGS = [dummyfile]
        # do not raise exception
        task.run("/bin/hostname", nodes="dummy-node")

    def test_shell_auto_tree_error(self):
        """test task shell auto tree [TopologyError]"""
        # initialize an erroneous topology.conf file
        topofile = make_temp_file(dedent("""
                        [Main]
                        %s: dummy-gw
                        dummy-gw: dummy-gw"""% HOSTNAME).encode())
        task = task_self()
        task.set_default("auto_tree", True)
        task.TOPOLOGY_CONFIGS = [topofile.name]
        self.assertRaises(TopologyError, task.run, "/bin/hostname",
                          nodes="dummy-node")
