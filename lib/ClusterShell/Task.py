#
# Copyright CEA/DAM/DIF (2007, 2008, 2009)
#  Contributor: Stephane THIELL <stephane.thiell@cea.fr>
#
# This file is part of the ClusterShell library.
#
# This software is governed by the CeCILL-C license under French law and
# abiding by the rules of distribution of free software.  You can  use,
# modify and/ or redistribute the software under the terms of the CeCILL-C
# license as circulated by CEA, CNRS and INRIA at the following URL
# "http://www.cecill.info".
#
# As a counterpart to the access to the source code and  rights to copy,
# modify and redistribute granted by the license, users are provided only
# with a limited warranty  and the software's author,  the holder of the
# economic rights,  and the successive licensors  have only  limited
# liability.
#
# In this respect, the user's attention is drawn to the risks associated
# with loading,  using,  modifying and/or developing or reproducing the
# software by the user in light of its specific status of free software,
# that may mean  that it is complicated to manipulate,  and  that  also
# therefore means  that it is reserved for developers  and  experienced
# professionals having in-depth computer knowledge. Users are therefore
# encouraged to load and test the software's suitability as regards their
# requirements in conditions enabling the security of their systems and/or
# data to be ensured and,  more generally, to use and operate it in the
# same conditions as regards security.
#
# The fact that you are presently reading this means that you have had
# knowledge of the CeCILL-C license and that you accept its terms.
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
from Engine.Factory import PreferredEngine
from Worker.Pdsh import WorkerPdsh
from Worker.Ssh import WorkerSsh
from Worker.Popen import WorkerPopen

from MsgTree import MsgTree
from NodeSet import NodeSet

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
                      "command_timeout" : 0,
                      "default_stderr"  : False,
                      "engine"          : 'auto' }
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
        if not getattr(self, "_engine", None):
            # first time called
            self._info = self.__class__._default_info.copy()
            # use factory class PreferredEngine that gives the proper engine instance
            self._engine = PreferredEngine(self._info)
            self.timeout = 0
            self.l_run = None

            # STDIN tree
            self._msgtree = MsgTree()

            # STDERR tree
            self._errtree = MsgTree()

            # dict of sources to return codes
            self._d_source_rc = {}
            # dict of return codes to sources
            self._d_rc_sources = {}
            # keep max rc
            self._max_rc = 0
            # keep timeout'd sources
            self._timeout_sources = set()

            # create new thread if needed
            if not thread_id:
                self.l_run = thread.allocate_lock()
                self.l_run.acquire()
                tid = thread.start_new_thread(Task._start_thread, (self,))
                self._tasks[tid] = self

    def _start_thread(self):
        """New Task thread entry point."""
        try:
            while True:
                self.l_run.acquire()
                self._engine.run(self.timeout)
        except:
            # TODO: dispatch exceptions
            raise

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
        ac = kwargs.get("autoclose", False)
        stderr = kwargs.get("stderr", self._info["default_stderr"])

        if kwargs.get("nodes", None):
            assert kwargs.get("key", None) is None, \
                    "'key' argument not supported for distant command"

            # create ssh-based worker
            worker = WorkerSsh(NodeSet(kwargs["nodes"]), command=command,
                               handler=handler, stderr=stderr, timeout=timeo,
                               autoclose=ac)
        else:
            # create (local) worker
            worker = WorkerPopen(command, key=kwargs.get("key", None),
                                 handler=handler, stderr=stderr, timeout=timeo,
                                 autoclose=ac)

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
        preserve = kwargs.get("preserve", None)

        # create a new copy worker
        worker = WorkerSsh(nodes, source=source, dest=dest, handler=handler,
                timeout=timeo, preserve=preserve)

        self.schedule(worker)

        return worker

    def timer(self, fire, handler, interval=-1.0, autoclose=False):
        """
        Create task's timer.
        """
        assert fire >= 0.0, "timer's relative fire time must be a positive floating number"
        
        timer = EngineTimer(fire, interval, autoclose, handler)
        self._engine.add_timer(timer)
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
            self._engine.add(client)

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
                self._engine.run(timeout)
            except EngineTimeoutException:
                raise TimeoutError()
            except EngineAbortException, e:
                self._terminate(e.kill)
            except EngineAlreadyRunningError:
                raise AlreadyRunningError()
            except:
                raise

    def abort(self, kill=False):
        """
        Abort a task. Aborting a task removes (and stops when needed)
        all workers. If optional parameter kill is True, the task
        object is unbound from the current thread, so calling
        task_self() creates a new Task object.
        """
        # Aborting a task from another thread (ie. not the thread
        # bound to task) will be supported through the inter-task msg
        # API (trac #21).
        assert task_self() == self, "Inter-task abort not implemented yet"
        
        # Raise an EngineAbortException when task is running.
        self._engine.abort(kill)

        # Called directly when task is not running.
        self._terminate(kill)

    def _terminate(self, kill):
        """
        Abort completion subroutine.
        """
        self._reset()

        if kill:
            del self.__class__._tasks[thread.get_ident()]

    def join(self):
        """
        Suspend execution of the calling thread until the target task
        terminates, unless the target task has already terminated.
        """
        self._engine.join()

    def _reset(self):
        """
        Reset buffers and retcodes management variables.
        """
        self._msgtree.reset()
        self._errtree.reset()
        self._d_source_rc = {}
        self._d_rc_sources = {}
        self._max_rc = 0
        self._timeout_sources.clear()

    def _msg_add(self, source, msg):
        """
        Add a worker message associated with a source.
        """
        self._msgtree.add(source, msg)

    def _errmsg_add(self, source, msg):
        """
        Add a worker error message associated with a source.
        """
        self._errtree.add(source, msg)

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
            self._d_rc_sources[rc] = set([source])
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
        return self._msgtree.get_by_source(source)

    def _errmsg_by_source(self, source):
        """
        Get an error message by its source (worker, key).
        """
        return self._errtree.get_by_source(source)

    def _msg_iter_by_key(self, key):
        """
        Return an iterator over stored messages for the given key.
        """
        return self._msgtree.iter_by_key(key)

    def _errmsg_iter_by_key(self, key):
        """
        Return an iterator over stored error messages for the given key.
        """
        return self._errtree.iter_by_key()

    def _msg_iter_by_worker(self, worker, match_keys=None):
        """
        Return an iterator over messages and keys list for a specific
        worker and optional matching keys.
        """
        return self._msgtree.iter_by_worker(worker, match_keys)

    def _errmsg_iter_by_worker(self, worker, match_keys=None):
        """
        Return an iterator over error messages and keys list for a specific
        worker and optional matching keys.
        """
        return self._errtree.iter_by_worker(worker, match_keys)

    def _kmsg_iter_by_worker(self, worker):
        """
        Return an iterator over key, message for a specific worker.
        """
        return self._msgtree.iterkey_by_worker(worker)
 
    def _kerrmsg_iter_by_worker(self, worker):
        """
        Return an iterator over key, err_message for a specific worker.
        """
        return self._errtree.iterkey_by_worker(worker)
    
    def _rc_by_source(self, source):
        """
        Get a return code by its source (worker, key).
        """
        return self._d_source_rc.get(source, 0)
   
    def _rc_iter_by_key(self, key):
        """
        Return an iterator over return codes for the given key.
        """
        for (w, k), rc in self._d_source_rc.iteritems():
            if k == key:
                yield rc

    def _rc_iter_by_worker(self, worker, match_keys=None):
        """
        Return an iterator over return codes and keys list for a
        specific worker and optional matching keys.
        """
        if match_keys:
            # Use the items iterator for the underlying dict.
            for rc, src in self._d_rc_sources.iteritems():
                keys = [t[1] for t in src if t[0] is worker and t[1] in match_keys]
                if len(keys) > 0:
                    yield rc, keys
        else:
            for rc, src in self._d_rc_sources.iteritems():
                keys = [t[1] for t in src if t[0] is worker]
                if len(keys) > 0:
                    yield rc, keys

    def _krc_iter_by_worker(self, worker):
        """
        Return an iterator over key, rc for a specific worker.
        """
        for rc, src in self._d_rc_sources.iteritems():
            for w, k in src:
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

    def iter_buffers(self, match_keys=None):
        """
        Iterate over buffers, returns a tuple (buffer, keys). For remote
        workers (Ssh), keys are list of nodes. In that case, you should use
        NodeSet.fromlist(keys) to get a NodeSet instance (which is more
        convenient and efficient):

        Optional parameter match_keys add filtering on these keys.

        Usage example:

            for buffer, nodelist in task.iter_buffers():
                print NodeSet.fromlist(nodelist)
                print buffer
        """
        return self._msgtree.iter_buffers(match_keys)

    def iter_errors(self, match_keys=None):
        """
        Iterate over error buffers, returns a tuple (buffer, keys).

        See iter_buffers().
        """
        return self._errtree.iter_buffers(match_keys)
            
    def iter_retcodes(self, match_keys=None):
        """
        Iterate over return codes, returns a tuple (rc, keys).

        Optional parameter match_keys add filtering on these keys.

        How retcodes work:
          If the process exits normally, the return code is its exit
          status. If the process is terminated by a signal, the return
          code is 128 + signal number.
        """
        if match_keys:
            # Use the items iterator for the underlying dict.
            for rc, src in self._d_rc_sources.iteritems():
                keys = [t[1] for t in src if t[1] in match_keys]
                yield rc, keys
        else:
            for rc, src in self._d_rc_sources.iteritems():
                yield rc, [t[1] for t in src]

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

def task_terminate():
    """
    Destroy the Task instance bound to the current thread. A next call
    to task_self() will create a new Task object. This function provided
    as a convenience is available in the top-level ClusterShell.Task
    package namespace.
    """
    task_self().abort(kill=True)

