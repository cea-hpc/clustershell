# Task.py -- Cluster task management
# Copyright (C) 2007, 2008, 2009 CEA
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
# $Id$

"""
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

from Engine.Engine import EngineAbortException
from Engine.Engine import EngineTimeoutException
from Engine.Engine import EngineAlreadyRunningError
from Engine.Engine import EngineTimer
from Engine.Poll import EnginePoll
from Worker.File import WorkerFile
from Worker.Pdsh import WorkerPdsh
from Worker.Ssh import WorkerSsh
from Worker.Popen2 import WorkerPopen2

from MsgTree import MsgTreeElem
from NodeSet import NodeSet

from sets import Set
import thread

class TaskException(Exception):
    """
    Base task exception.
    """

class TimeoutError(TaskException):
    """
    Raised when the task timed out.
    """

class AlreadyRunningError(TaskException):
    """
    Raised when trying to resume an already running task.
    """
    def __str__(self):
        return "current task already running"


def _task_print_debug(task, s):
    """
    Default task debug printing function. Cannot provide 'print'
    directly as it is not a function (will be in Py3k!).
    """
    print s


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

    Run task in its associated thread (will block only if the calling
    thread is the associated thread:
        task.resume()
    """

    _default_info = { "debug"           : False,
                      "print_debug"     : _task_print_debug,
                      "fanout"          : 32,
                      "connect_timeout" : 10,
                      "command_timeout" : 0 }
    _tasks = {}

    def __new__(cls, thread_id=None):
        """
        For task bound to a specific thread, this class acts like a
        "thread singleton", so new style class is used and new object
        are only instantiated if needed.
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

            # root of msg tree
            self._msg_root = MsgTreeElem()
            # dict of sources to msg tree elements
            self._d_source_msg = {}
            # dict of sources to return codes
            self._d_source_rc = {}
            # dict of return codes to sources
            self._d_rc_sources = {}
            # keep max rc
            self._max_rc = 0
            # keep timeout'd sources
            self._timeout_sources = Set()

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
            task.shell(command [, key=key] [, handler=handler]
                    [, timeout=secs])

        Distant usage:
            task.shell(command, nodes=nodeset [, handler=handler]
                    [, timeout=secs])
        """

        handler = kwargs.get("handler", None)
        timeo = kwargs.get("timeout", None)

        if kwargs.get("nodes", None):
            assert kwargs.get("key", None) is None, \
                    "'key' argument not supported for distant command"

            # create ssh-based worker
            worker = WorkerSsh(NodeSet(kwargs["nodes"]), handler=handler,
                               timeout=timeo, command=command)
        else:
            # create popen2-based (local) worker
            worker = WorkerPopen2(command, key=kwargs.get("key", None),
                                  handler=handler, timeout=timeo)

        # schedule worker for execution in this task
        self.schedule(worker)

        return worker

    def copy(self, source, dest, nodes, **kwargs):
        """
        Copy local file to distant nodes.
        """
        assert nodes != None, "local copy not supported"

        handler = kwargs.get("handler", None)
        timeo = kwargs.get("timeout", None)

        # create a new Pdcp worker (supported by WorkerPdsh)
        worker = WorkerSsh(nodes, source=source, dest=dest, handler=handler,
                timeout=timeo)

        self.schedule(worker)

        return worker

    def timer(self, fire, handler, interval=-1.0):
        """
        Create task's timer.
        """
        assert(fire >= 0.0, "timer's relative fire-time must be a positive \
                floating number")
        
        timer = EngineTimer(fire, interval, handler)
        self.engine.add_timer(timer)
        return timer

    def schedule(self, worker):
        """
        Schedule a worker for execution. Only useful for manually
        instantiated workers.
        """
        # bind worker to task self
        worker._set_task(self)

        # add worker clients to engine
        for client in worker._engine_clients():
            self.engine.add(client)

    def resume(self, timeout=0):
        """
        Resume task. If task is task_self(), workers are executed in
        the calling thread so this method will block until workers have
        finished. This is always the case for a single-threaded
        application (eg. which doesn't create other Task() instance
        than task_self()). Otherwise, the current thread doesn't block.
        In that case, you may then want to call task_wait() to wait for
        completion.
        """
        if self.l_run:
            self.timeout = timeout
            self.l_run.release()
        else:
            try:
                self._reset()
                self.engine.run(timeout)
            except EngineTimeoutException:
                raise TimeoutError()
            except EngineAbortException:
                pass
            except EngineAlreadyRunningError:
                raise AlreadyRunningError()
            except:
                raise

    def abort(self):
        """
        Abort a task.
        """
        self.engine.abort()

    def join(self):
        """
        Suspend execution of the calling thread until the target task
        terminates, unless the target task has already terminated.
        """
        self.engine.join()

    def workers(self):
        """
        Get active workers (as an iterable object).
        """
        return self.engine.workers()

    def _reset(self):
        """
        Reset buffers and retcodes managment variables.
        """
        self._msg_root = MsgTreeElem()
        self._d_source_msg = {}
        self._d_source_rc = {}
        self._d_rc_sources = {}
        self._max_rc = 0
        self._timeout_sources.clear()

    def _msg_add(self, source, msg):
        """
        Add a worker message associated with a source.
        """
        # try first to get current element in msgs tree
        e_msg = self._d_source_msg.get(source)
        if not e_msg:
            # key not found (first msg from it)
            e_msg = self._msg_root

        # add child msg and update dict
        self._d_source_msg[source] = e_msg.add_msg(source, msg)

    def _rc_set(self, source, rc, override=True):
        """
        Add a worker return code associated with a source.
        """
        if not override and self._d_source_rc.has_key(source):
            return

        # store rc by source
        self._d_source_rc[source] = rc

        # store source by rc
        e = self._d_rc_sources.get(rc)
        if e is None:
            self._d_rc_sources[rc] = Set([source])
        else:
            self._d_rc_sources[rc].add(source)
        
        # update max rc
        if rc > self._max_rc:
            self._max_rc = rc

    def _timeout_add(self, source):
        """
        Add a worker timeout associated with a source.
        """
        # store source in timeout set
        self._timeout_sources.add(source)

    def _msg_by_source(self, source):
        """
        Get a message by its source (worker, key).
        """
        e_msg = self._d_source_msg.get(source)

        if e_msg is None:
            return None

        return e_msg.message()

    def _msg_iter_by_key(self, key):
        """
        Return an iterator over stored messages for the given key.
        """
        for (w, k), e in self._d_source_msg.iteritems():
            if k == key:
                yield e.message()

    def _msg_iter_by_worker(self, worker):
        """
        Return an iterator over messages and keys list for a specific
        worker.
        """
        for e in self._msg_root:
            keys = [t[1] for t in e.sources if t[0] is worker]
            if len(keys) > 0:
                yield e.message(), keys

    def _kmsg_iter_by_worker(self, worker):
        """
        Return an iterator over key, message for a specific worker.
        """
        for (w, k), e in self._d_source_msg.iteritems():
            if w is worker:
                yield k, e.message()
 
    def _rc_by_source(self, source):
        """
        Get a return code by its source (worker, key).
        """
        return self._d_source_msg.get(source, 0)
   
    def _rc_iter_by_key(self, key):
        """
        Return an iterator over return codes for the given key.
        """
        for (w, k), rc in self._d_source_rc.iteritems():
            if k == key:
                yield rc

    def _rc_iter_by_worker(self, worker):
        """
        Return an iterator over return codes and keys list for a
        specific worker.
        """
        # Use the items iterator for the underlying dict.
        for rc, src in self._d_rc_sources.iteritems():
            keys = [t[1] for t in src if t[0] is worker]
            if len(keys) > 0:
                yield rc, keys

    def _krc_iter_by_worker(self, worker):
        """
        Return an iterator over key, rc for a specific worker.
        """
        for rc, (w, k) in self._d_rc_sources.iteritems():
            if w is worker:
                yield k, rc

    def _num_timeout_by_worker(self, worker):
        """
        Return the number of timed out "keys" for a specific worker.
        """
        cnt = 0
        for (w, k) in self._timeout_sources:
            if w is worker:
                cnt += 1
        return cnt

    def _iter_keys_timeout_by_worker(self, worker):
        """
        Iterate over timed out keys (ie. nodes) for a specific worker.
        """
        for (w, k) in self._timeout_sources:
            if w is worker:
                yield k

    def key_buffer(self, key):
        """
        Get buffer for a specific key. When the key is associated
        to multiple workers, the resulting buffer will contain
        all workers content that may overlap.
        """
        return "".join(self._msg_iter_by_key(key))
    
    node_buffer = key_buffer

    def key_retcode(self, key):
        """
        Return return code for a specific key. When the key is
        associated to multiple workers, return the max return
        code from these workers.
        """
        return max(self._rc_iter_by_key(key))
    
    node_retcode = key_retcode

    def max_retcode(self):
        """
        Get max return code encountered during last run.

        How retcodes work:
          If the process exits normally, the return code is its exit
          status. If the process is terminated by a signal, the return
          code is 128 + signal number.
        """
        return self._max_rc

    def iter_buffers(self):
        """
        Iterate over buffers, returns a tuple (buffer, keys). For remote
        workers (Ssh), keys are list of nodes. In that case, you should use
        NodeSet.fromlist(keys) to get a NodeSet instance (which is more
        convenient and efficient):

        Usage example:

            for buffer, nodelist in task.iter_buffers():
                print NodeSet.fromlist(nodelist)
                print buffer
        """
        for e in self._msg_root:
            yield e.message(), [t[1] for t in e.sources]
            
    def iter_retcodes(self):
        """
        Iterate over return codes, returns a tuple (rc, keys).

        How retcodes work:
          If the process exits normally, the return code is its exit
          status. If the process is terminated by a signal, the return
          code is 128 + signal number.
        """
        # Use the items iterator for the underlying dict.
        for rc, src in self._d_rc_sources.iteritems():
            yield rc, [t[1] for t in src]

    def max_retcode(self):
        """
        Get max return code encountered during last run.
        """
        return self._max_rc

    def num_timeout(self):
        """
        Return the number of timed out "keys" (ie. nodes).
        """
        return len(self._timeout_sources)

    def iter_keys_timeout(self):
        """
        Iterate over timed out keys (ie. nodes).
        """
        for (w, k) in self._timeout_sources:
            yield k

    def wait(cls, from_thread_id):
        """
        Class method that blocks calling thread until all tasks have
        finished.
        """
        for thread_id, task in Task._tasks.iteritems():
            if thread_id != from_thread_id:
                task.join()
    wait = classmethod(wait)


def task_self():
    """
    Get the Task instance bound to the current thread. This function
    provided as a convenience is available in the top-level
    ClusterShell.Task package namespace.
    """
    return Task(thread_id=thread.get_ident())

def task_wait():
    """
    Suspend execution of the calling thread until all tasks terminate,
    unless all tasks have already terminated. This function is provided
    as a convenience and is available in the top-level
    ClusterShell.Task package namespace.
    """
    Task.wait(thread.get_ident())

