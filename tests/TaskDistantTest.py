#!/usr/bin/env python


"""Unit test for ClusterShell Task with all engines (distant worker)"""

import sys
import unittest

sys.path.insert(0, '../lib')

from ClusterShell.Defaults import DEFAULTS
from ClusterShell.Engine.Select import EngineSelect
from ClusterShell.Engine.Poll import EnginePoll
from ClusterShell.Engine.EPoll import EngineEPoll
from ClusterShell.Task import *

from TaskDistantMixin import TaskDistantMixin

ENGINE_SELECT_ID = EngineSelect.identifier
ENGINE_POLL_ID = EnginePoll.identifier
ENGINE_EPOLL_ID = EngineEPoll.identifier

class TaskDistantEngineSelectTest(TaskDistantMixin, unittest.TestCase):

    def setUp(self):
        task_terminate()
        self.engine_id_save = DEFAULTS.task_default['engine']
        DEFAULTS.task_default['engine'] = ENGINE_SELECT_ID
        # select should be supported anywhere...
        self.assertEqual(task_self().info('engine'), ENGINE_SELECT_ID)
        TaskDistantMixin.setUp(self)

    def tearDown(self):
        DEFAULTS.task_default['engine'] = self.engine_id_save
        task_terminate()

class TaskDistantEnginePollTest(TaskDistantMixin, unittest.TestCase):

    def setUp(self):
        task_terminate()
        self.engine_id_save = DEFAULTS.task_default['engine']
        DEFAULTS.task_default['engine'] = ENGINE_POLL_ID
        if task_self().info('engine') != ENGINE_POLL_ID:
            self.skipTest("engine %s not supported on this host" % ENGINE_POLL_ID)
        TaskDistantMixin.setUp(self)

    def tearDown(self):
        DEFAULTS.task_default['engine'] = self.engine_id_save
        task_terminate()

# select.epoll is only available with Python 2.6 (if condition to be
# removed once we only support Py2.6+)
if sys.version_info >= (2, 6, 0):

    class TaskDistantEngineEPollTest(TaskDistantMixin, unittest.TestCase):

        def setUp(self):
            task_terminate()
            self.engine_id_save = DEFAULTS.task_default['engine']
            DEFAULTS.task_default['engine'] = ENGINE_EPOLL_ID
            if task_self().info('engine') != ENGINE_EPOLL_ID:
                self.skipTest("engine %s not supported on this host" % ENGINE_EPOLL_ID)
            TaskDistantMixin.setUp(self)

        def tearDown(self):
            DEFAULTS.task_default['engine'] = self.engine_id_save
            task_terminate()

