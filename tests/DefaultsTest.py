#!/usr/bin/env python
# ClusterShell.Defaults test suite
# Written by S. Thiell


"""Unit test for ClusterShell Defaults module"""

import sys
import unittest

sys.path.insert(0, '../lib')

from TLib import make_temp_file

import ClusterShell.Defaults as Defaults
from ClusterShell.Defaults import DEFAULTS
# Be sure no local defaults.conf is used
DEFAULTS.__init__([])

from ClusterShell.Task import task_self, task_terminate
from ClusterShell.Worker.Pdsh import WorkerPdsh
from ClusterShell.Worker.Ssh import WorkerSsh


class Defaults000NoConfigTest(unittest.TestCase):

    def test_000_initial(self):
        """test Defaults initial values"""
        # task_default
        self.assertFalse(DEFAULTS.stderr)
        self.assertTrue(DEFAULTS.stdout_msgtree)
        self.assertTrue(DEFAULTS.stderr_msgtree)
        self.assertEqual(DEFAULTS.engine, 'auto')
        self.assertEqual(DEFAULTS.port_qlimit, 100)
        self.assertTrue(DEFAULTS.auto_tree)
        self.assertEqual(DEFAULTS.local_workername, 'exec')
        self.assertEqual(DEFAULTS.distant_workername, 'ssh')
        # task_info
        self.assertFalse(DEFAULTS.debug)
        self.assertEqual(DEFAULTS.print_debug, Defaults._task_print_debug)
        self.assertFalse(DEFAULTS.print_debug is None)
        self.assertEqual(DEFAULTS.fanout, 64)
        self.assertEqual(DEFAULTS.grooming_delay, 0.25)
        self.assertEqual(DEFAULTS.connect_timeout, 10)
        self.assertEqual(DEFAULTS.command_timeout, 0)

    def test_001_setattr(self):
        """test Defaults setattr"""
        # task_default
        DEFAULTS.stderr = True
        self.assertTrue(DEFAULTS.stderr)
        DEFAULTS.stdout_msgtree = False
        self.assertFalse(DEFAULTS.stdout_msgtree)
        DEFAULTS.stderr_msgtree = False
        self.assertFalse(DEFAULTS.stderr_msgtree)
        DEFAULTS.engine = 'select'
        self.assertEqual(DEFAULTS.engine, 'select')
        DEFAULTS.port_qlimit = 1000
        self.assertEqual(DEFAULTS.port_qlimit, 1000)
        DEFAULTS.auto_tree = False
        self.assertFalse(DEFAULTS.auto_tree)
        DEFAULTS.local_workername = 'none'
        self.assertEqual(DEFAULTS.local_workername, 'none')
        DEFAULTS.distant_workername = 'pdsh'
        self.assertEqual(DEFAULTS.distant_workername, 'pdsh')
        # task_info
        DEFAULTS.debug = True
        self.assertTrue(DEFAULTS.debug)
        DEFAULTS.print_debug = None
        self.assertEqual(DEFAULTS.print_debug, None)
        DEFAULTS.fanout = 256
        self.assertEqual(DEFAULTS.fanout, 256)
        DEFAULTS.grooming_delay = 0.5
        self.assertEqual(DEFAULTS.grooming_delay, 0.5)
        DEFAULTS.connect_timeout = 12.5
        self.assertEqual(DEFAULTS.connect_timeout, 12.5)
        DEFAULTS.connect_timeout = 30.5

    def test_002_reinit_defaults(self):
        """Test Defaults manual reinit"""
        # For testing purposes only
        DEFAULTS.__init__(filenames=[])
        self.test_000_initial()

    def test_004_workerclass(self):
        """test Defaults workerclass"""
        DEFAULTS.distant_workername = 'pdsh'
        task = task_self()
        self.assertTrue(task.default("distant_worker") is WorkerPdsh)
        DEFAULTS.distant_workername = 'ssh'
        self.assertTrue(task.default("distant_worker") is WorkerPdsh)
        task_terminate()
        task = task_self()
        self.assertTrue(task.default("distant_worker") is WorkerSsh)
        task_terminate()

    def test_005_misc_value_errors(self):
        """test Defaults misc value errors"""
        DEFAULTS.local_workername = 'dummy1'
        self.assertRaises(ImportError, task_self)
        DEFAULTS.local_workername = 'exec'
        DEFAULTS.distant_workername = 'dummy2'
        self.assertRaises(ImportError, task_self)
        DEFAULTS.distant_workername = 'ssh'
        DEFAULTS.engine = 'unknown'
        self.assertRaises(KeyError, task_self)
        DEFAULTS.engine = 'auto'
        task = task_self()
        self.assertEqual(task.default('engine'), 'auto')
        task_terminate()


class Defaults001ConfigTest(unittest.TestCase):

    def _assert_default_values(self):
        # task_default
        self.assertFalse(DEFAULTS.stderr)
        self.assertTrue(DEFAULTS.stdout_msgtree)
        self.assertTrue(DEFAULTS.stderr_msgtree)
        self.assertEqual(DEFAULTS.engine, 'auto')
        self.assertEqual(DEFAULTS.port_qlimit, 100)
        self.assertTrue(DEFAULTS.auto_tree)
        self.assertEqual(DEFAULTS.local_workername, 'exec')
        self.assertEqual(DEFAULTS.distant_workername, 'ssh')
        # task_info
        self.assertFalse(DEFAULTS.debug)
        self.assertEqual(DEFAULTS.print_debug, Defaults._task_print_debug)
        self.assertFalse(DEFAULTS.print_debug is None)
        self.assertEqual(DEFAULTS.fanout, 64)
        self.assertEqual(DEFAULTS.grooming_delay, 0.25)
        self.assertEqual(DEFAULTS.connect_timeout, 10)
        self.assertEqual(DEFAULTS.command_timeout, 0)

    def test_000_empty(self):
        """test Defaults config file (empty)"""
        conf_test = make_temp_file('')
        DEFAULTS.__init__(filenames=[conf_test.name])
        self._assert_default_values()

    def test_001_defaults(self):
        """test Defaults config file (defaults)"""
        conf_test = make_temp_file("""
[task.default]
stderr: false
stdout_msgtree: true
stderr_msgtree: true
engine: auto
port_qlimit: 100
auto_tree: true
local_workername: exec
distant_workername: ssh

[task.info]
debug: false
fanout: 64
grooming_delay: 0.25
connect_timeout: 10
command_timeout: 0
""")
        DEFAULTS.__init__(filenames=[conf_test.name])
        self._assert_default_values()

    def test_002_changed(self):
        """test Defaults config file (changed)"""
        conf_test = make_temp_file("""
[task.default]
stderr: true
stdout_msgtree: false
stderr_msgtree: false
engine: select
port_qlimit: 1000
auto_tree: false
local_workername: none
distant_workername: pdsh

[task.info]
debug: true
fanout: 256
grooming_delay: 0.5
connect_timeout: 12.5
command_timeout: 30.5
""")
        DEFAULTS.__init__(filenames=[conf_test.name])
        self.assertTrue(DEFAULTS.stderr)
        self.assertFalse(DEFAULTS.stdout_msgtree)
        self.assertFalse(DEFAULTS.stderr_msgtree)
        self.assertEqual(DEFAULTS.engine, 'select')
        self.assertEqual(DEFAULTS.port_qlimit, 1000)
        self.assertFalse(DEFAULTS.auto_tree)
        self.assertEqual(DEFAULTS.local_workername, 'none')
        self.assertEqual(DEFAULTS.distant_workername, 'pdsh')
        # task_info
        self.assertTrue(DEFAULTS.debug)
        self.assertEqual(DEFAULTS.fanout, 256)
        self.assertEqual(DEFAULTS.grooming_delay, 0.5)
        self.assertEqual(DEFAULTS.connect_timeout, 12.5)

    def test_003_changed_reinit(self):
        """Test Defaults config file (reinit)"""
        DEFAULTS.__init__(filenames=[])
        self._assert_default_values()
