# Task.py -- Cluster task management
# Copyright (C) 2007, 2008 CEA
# Written by S. Thiell
#
# This file is part of ClusterShell
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
# $Id: Task.py 7 2007-12-20 14:52:31Z st-cea $

"""
Task

ClusterShell Task module.

Simple example of use:

    from ClusterShell.Task import *

    # get task associated with calling thread
    task = task_self()

    # add a command to execute on distant nodes
    task.shell("/bin/uname -r", nodes="tiger[1-30,35]")

    # run task in calling thread
    task.resume()

    # get results
    for buf, nodelist in task.iter_buffers():
        print NodeSet.fromlist(nodelist), buf

"""

from Engine.Poll import EnginePoll
from Worker.Pdsh import WorkerPdsh
from Worker.Popen2 import WorkerPopen2

import thread


class Task(object):
    """
    Task to execute. May be bound to a specific thread.

    To create a task in a new thread:
        task = Task()

    To create or get the instance of the task associated with the thread
    identifier tid:
        task = Task(thread_id=tid)

    Add command to execute locally in task with:
        task.shell("/bin/hostname")

    Add command to execute in a distant node in task with:
        task.shell("/bin/hostname", nodes="tiger[1-20]")

    Run task in its associated thread (will block only if the calling thread
    is the associated thread:
        task.resume()
    """

    _default_info = { "debug"           : False,
                      "fanout"          : 32,
                      "connect_timeout" : 10,
                      "command_timeout" : 0 }
    _tasks = {}

    def __new__(cls, thread_id=None):
        """
        For task bound to a specific thread, this class acts like a "thread singleton", so
        new style class is used and new object are only instantiated if needed.
        """
        if thread_id:                       # a thread identifier is a nonzero integer
            if thread_id not in cls._tasks:
                cls._tasks[thread_id] = object.__new__(cls)
            return cls._tasks[thread_id]

        return object.__new__(cls)

    def __init__(self, thread_id=None):
        """
        Initialize a Task, creating a new thread if needed.
        """
        if not getattr(self, "engine", None):

            # first time called

            self._info = self.__class__._default_info.copy()
            self.engine = EnginePoll(self._info)
            self.timeout = 0
            self.l_run = None

            # create new thread if needed

            if not thread_id:
                self.l_run = thread.allocate_lock()
                self.l_run.acquire()
                print "starting new thread"
                tid = thread.start_new_thread(Task._start_thread, (self,))
                self._tasks[tid] = self

    def _start_thread(self):
        print "thread started (id=0x%x)" % thread.get_ident()

        self.l_run.acquire()
        self.engine.run(self.timeout)

        print "thread exited (id=0x%x)" % thread.get_ident()

    def info(self, info_key, def_val=None):
        """
        Return per-task information.
        """
        return self._info.get(info_key, def_val)

    def set_info(self, info_key, value):
        """
        Set task-specific information state.
        """
        self._info[info_key] = value

    def shell(self, command, **kwargs):
        """
        Schedule a shell command for local or distant execution.

        Local usage:
            task.shell(command [, key=key] [, handler=handler])

        Distant usage:
            task.shell(command, nodes=nodeset [, handler=handler])
        """

        handler = kwargs.get("handler", None)

        if kwargs.get("nodes", None):
            assert kwargs.get("key", None) is None, "'key' argument not supported for distant command"
            worker =  WorkerPdsh(kwargs["nodes"], command=command, handler=handler, task=self)
        else:
            worker = WorkerPopen2(command, key=kwargs.get("key", None), handler=handler, task=self)

        # Schedule task for this new shell worker.
        self.engine.add(worker)

        return worker

    def copy(self, source, dest, nodes, handler=None):
        """
        Copy local file to distant nodes.
        """
        assert nodes != None, "local copy not supported"

        # Start new Pdcp worker (supported by WorkerPdsh)
        worker = WorkerPdsh(nodes, source=source, dest=dest, handler=handler, task=self)

        # Schedule task for this new copy worker.
        self.engine.add(worker)

        return worker

    def resume(self, timeout=0):
        """
        Resume task. If task is task_self(), workers are executed in the calling thread so this
        method will block until workers have finished. This is always the case for a
        single-threaded application (eg. which doesn't create other Task() instance than task_self()).
        Otherwise, the current thread doesn't block. In that case, you may then want to call
        task_wait() to wait for completion.
        """
        if self.l_run:
            self.timeout = timeout
            self.l_run.release()
        else:
            self.engine.run(timeout)

    def join(self):
        """
        Suspend execution of the calling thread until the target task terminates, unless the target
        task has already terminated.
        """
        self.engine.join()

    def wait(cls, from_thread_id):
        """
        Class method that blocks calling thread until all tasks have finished.
        """
        for thread_id, task in Task._tasks.iteritems():
            if thread_id != from_thread_id:
                task.join()
    wait = classmethod(wait)

    def max_retcode(self):
        """
        Get max return code encountered during last run.
        """
        return self.engine.max_retcode()

    def iter_buffers(self):
        """
        Returns an iterator over buffers and associated keys list.
        """
        for m, k in self.engine.iter_messages():
            yield m, list(k)
            
    def iter_retcodes(self):
        """
        Iterate over rc, returns key list and rc.
        """
        for k, rc in self.engine.iter_retcodes():
            yield list(k), rc


def task_self():
    """
    Get the Task instance bound to the current thread. This function provided as a convenience
    is available in the top-level ClusterShell.Task package namespace.
    """
    return Task(thread_id=thread.get_ident())

def task_wait():
    """
    Suspend execution of the calling thread until all tasks terminate, unless all tasks
    have already terminated. This function is provided as a convenience and is available in the
    top-level ClusterShell.Task package namespace.
    """
    Task.wait(thread.get_ident())

