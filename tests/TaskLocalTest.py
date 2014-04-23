#!/usr/bin/env python


"""Unit test for ClusterShell Task with all engines (local worker)"""

import sys
import unittest

sys.path.insert(0, '../lib')

from ClusterShell.Engine.Select import EngineSelect
from ClusterShell.Engine.Poll import EnginePoll
from ClusterShell.Engine.EPoll import EngineEPoll
from ClusterShell.Task import *

from TaskLocalMixin import TaskLocalMixin

ENGINE_SELECT_ID = EngineSelect.identifier
ENGINE_POLL_ID = EnginePoll.identifier
ENGINE_EPOLL_ID = EngineEPoll.identifier

class TaskLocalEngineSelectTest(TaskLocalMixin, unittest.TestCase):

    def setUp(self):
        task_terminate()
        self.engine_id_save = Task._std_default['engine']
        Task._std_default['engine'] = ENGINE_SELECT_ID
        self.assertEqual(task_self().info('engine'), ENGINE_SELECT_ID)

    def tearDown(self):
        Task._std_default['engine'] = self.engine_id_save
        task_terminate()

class TaskLocalEnginePollTest(TaskLocalMixin, unittest.TestCase):

    def setUp(self):
        task_terminate()
        self.engine_id_save = Task._std_default['engine']
        Task._std_default['engine'] = ENGINE_POLL_ID
        self.assertEqual(task_self().info('engine'), ENGINE_POLL_ID)

    def tearDown(self):
        Task._std_default['engine'] = self.engine_id_save
        task_terminate()

# select.epoll is only available with Python 2.6 (if condition to be
# removed once we only support Py2.6+)
if sys.version_info >= (2, 6, 0):

    class TaskLocalEngineEPollTest(TaskLocalMixin, unittest.TestCase):

        def setUp(self):
            task_terminate()
            self.engine_id_save = Task._std_default['engine']
            Task._std_default['engine'] = ENGINE_EPOLL_ID
            self.assertEqual(task_self().info('engine'), ENGINE_EPOLL_ID)

        def tearDown(self):
            Task._std_default['engine'] = self.engine_id_save
            task_terminate()

