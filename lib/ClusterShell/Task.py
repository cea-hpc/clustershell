#
# Copyright CEA/DAM/DIF (2007, 2008, 2009, 2010)
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

import itertools
import operator
import sys
import threading
import traceback

from Engine.Engine import EngineAbortException
from Engine.Engine import EngineTimeoutException
from Engine.Engine import EngineAlreadyRunningError
from Engine.Engine import EngineTimer
from Engine.Factory import PreferredEngine
from Worker.EngineClient import EnginePort
from Worker.Pdsh import WorkerPdsh
from Worker.Ssh import WorkerSsh
from Worker.Popen import WorkerPopen

from Event import EventHandler
from MsgTree import MsgTree
from NodeSet import NodeSet


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

    To create or get the instance of the task associated with the
    thread object thr (threading.Thread):
        task = Task(thread=thr)

    Add command to execute locally in task with:
        task.shell("/bin/hostname")

    Add command to execute in a distant node in task with:
        task.shell("/bin/hostname", nodes="tiger[1-20]")

    Run task in its associated thread (will block only if the calling
    thread is the associated thread:
        task.resume()
    """

    _std_default = {  "stderr"              : False,
                      "engine"              : 'auto',
                      "port_qlimit"         : 32 }

    _std_info =     { "debug"               : False,
                      "print_debug"         : _task_print_debug,
                      "fanout"              : 64,
                      "connect_timeout"     : 10,
                      "command_timeout"     : 0 }
    _tasks = {}
    _taskid_max = 0
    _task_lock = threading.Lock()

    class _SyncMsgHandler(EventHandler):
        """Special task control port event handler.
        When a message is received on the port, call appropriate
        task method."""
        def ev_msg(self, port, msg):
            """Message received: call appropriate task method."""
            # pull out function and its arguments from message
            func, (args, kwargs) = msg[0], msg[1:]
            # call task method
            func(port.task, *args, **kwargs)

    class tasksyncmethod(object):
        """Class encapsulating a function that checks if the calling
        task is running or is the current task, and allowing it to be
        used as a decorator making the wrapped task method thread-safe."""
        
        def __call__(self, f):
            def taskfunc(*args, **kwargs):
                # pull out the class instance
                task, fargs = args[0], args[1:]
                # check if the calling task is the current thread task
                if task._is_task_self():
                    return f(task, *fargs, **kwargs)
                else:
                    # no, safely call the task method by message 
                    # through the task special dispatch port
                    task._dispatch_port.msg_send((f, fargs, kwargs))

            # modify the decorator meta-data for pydoc
            # Note: should be later replaced  by @wraps (functools)
            # as of Python 2.5
            taskfunc.__name__ = f.__name__
            taskfunc.__doc__ = f.__doc__
            taskfunc.__dict__ = f.__dict__
            taskfunc.__module__ = f.__module__
            return taskfunc

    class _SuspendCondition(object):
        """Special class to manage task suspend condition."""
        def __init__(self, lock=threading.RLock(), initial=0):
            self._cond = threading.Condition(lock)
            self.suspend_count = initial

        def atomic_inc(self):
            """Increase suspend count."""
            self._cond.acquire()
            self.suspend_count += 1
            self._cond.release()

        def atomic_dec(self):
            """Decrease suspend count."""
            self._cond.acquire()
            self.suspend_count -= 1
            self._cond.release()

        def wait_check(self, release_lock=None):
            """Wait for condition if needed."""
            self._cond.acquire()
            try:
                if self.suspend_count > 0:
                    if release_lock:
                        release_lock.release()
                    self._cond.wait()
            finally:
                self._cond.release()
            
        def notify_all(self):
            """Signal all threads waiting for condition."""
            self._cond.acquire()
            try:
                self.suspend_count = min(self.suspend_count, 0)
                self._cond.notifyAll()
            finally:
                self._cond.release()


    def __new__(cls, thread=None):
        """
        For task bound to a specific thread, this class acts like a
        "thread singleton", so new style class is used and new object
        are only instantiated if needed.
        """
        if thread:
            if thread not in cls._tasks:
                cls._tasks[thread] = object.__new__(cls)
            return cls._tasks[thread]

        return object.__new__(cls)

    def __init__(self, thread=None):
        """
        Initialize a Task, creating a new thread if needed.
        """
        if not getattr(self, "_engine", None):
            # first time called
            self._default_lock = threading.Lock()
            self._default = self.__class__._std_default.copy()
            self._info = self.__class__._std_info.copy()

            # use factory class PreferredEngine that gives the proper
            # engine instance
            self._engine = PreferredEngine(self.default("engine"), self._info)
            self.timeout = 0

            # task synchronization objects
            self._run_lock = threading.Lock()
            self._suspend_lock = threading.RLock()
            # both join and suspend conditions share the same underlying lock
            self._suspend_cond = Task._SuspendCondition(self._suspend_lock, 1)
            self._join_cond = threading.Condition(self._suspend_lock)
            self._suspended = False
            self._quit = False

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

            # special engine port for task method dispatching
            self._dispatch_port = EnginePort(self,
                                            handler=Task._SyncMsgHandler(),
                                            autoclose=True)
            self._engine.add(self._dispatch_port)

            # set taskid used as Thread name
            Task._task_lock.acquire()
            Task._taskid_max += 1
            self._taskid = Task._taskid_max
            Task._task_lock.release()

            # create new thread if needed
            if thread:
                self.thread = thread
            else:
                self.thread = thread = threading.Thread(None,
                                                        Task._thread_start,
                                                        "Task-%d" % self._taskid,
                                                        args=(self,))
                Task._tasks[thread] = self
                thread.start()

    def _is_task_self(self):
        """Private method used by the library to check if the task is
        task_self(), but do not create any task_self() instance."""
        return self.thread == threading.currentThread()

    def _handle_exception(self):
        print >>sys.stderr, 'Exception in thread %s:' % self.thread
        traceback.print_exc(file=sys.stderr)
        self._quit = True
        
    def _thread_start(self):
        """Task-managed thread entry point"""
        while not self._quit:
            self._suspend_cond.wait_check()
            if self._quit:
                break
            try:
                self._resume()
            except:
                self._handle_exception()

        self._terminate(kill=True)

    def _run(self, timeout):
        # use with statement later
        try:
            self._run_lock.acquire()
            self._engine.run(timeout)
        finally:
            self._run_lock.release()
        
    def default(self, default_key, def_val=None):
        """
        Return per-task value for key from the "default" dictionary.
        """
        self._default_lock.acquire()
        try:
            return self._default.get(default_key, def_val)
        finally:
            self._default_lock.release()

    def set_default(self, default_key, value):
        """
        Set task value for specified key in the dictionary "default".
        Users may store their own task-specific key, value pairs
        using this method and retrieve them with default().
        
        Threading considerations:
          Unlike set_info(), when called from the task's thread or
          not, set_default() immediately updates the underlying
          dictionary in a thread-safe manner. This method doesn't
          wake up the engine when called.
        """
        self._default_lock.acquire()
        try:
            self._default[default_key] = value
        finally:
            self._default_lock.release()

    def info(self, info_key, def_val=None):
        """
        Return per-task information.
        """
        return self._info.get(info_key, def_val)

    @tasksyncmethod()
    def set_info(self, info_key, value):
        """
        Set task value for a specific key information. Key, value
        pairs can be passed to the engine and/or workers.
        Users may store their own task-specific info key, value pairs
        using this method and retrieve them with info().
        
        Threading considerations:
          Unlike set_default(), the underlying info dictionary is only
          modified from the task's thread. So calling set_info() from
          another thread leads to queueing the request for late apply
          (at run time) using the task dispatch port. When received,
          the request wakes up the engine when the task is running and
          the info dictionary is then updated.
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
        stderr = kwargs.get("stderr", self.default("stderr"))

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
                                 handler=handler, stderr=stderr,
                                 timeout=timeo, autoclose=ac)

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

    @tasksyncmethod()
    def _add_port(self, port):
        self._engine.add(port)

    def port(self, handler=None, autoclose=False):
        """
        Create a new task port. A task port is an abstraction object to
        deliver messages reliably between tasks.

        Basic rules:
            A task can send messages to another task port (thread safe).
            A task can receive messages from an acquired port either by
            setting up a notification mechanism or using a polling
            mechanism that may block the task waiting for a message
            sent on the port.
            A port can be acquired by one task only.

        If handler is set to a valid EventHandler object, the port is
        a send-once port, ie. a message sent to this port generates an
        ev_msg event notification issued the port's task. If handler
        is not set, the task can only receive messages on the port by
        calling port.msg_recv().
        """
        port = EnginePort(self, handler, autoclose)
        self._add_port(port)
        return port

    @tasksyncmethod()
    def timer(self, fire, handler, interval=-1.0, autoclose=False):
        """
        Create task's timer.
        """
        assert fire >= 0.0, \
            "timer's relative fire time must be a positive floating number"
        
        timer = EngineTimer(fire, interval, autoclose, handler)
        self._engine.add_timer(timer)
        return timer

    @tasksyncmethod()
    def schedule(self, worker):
        """
        Schedule a worker for execution. Only useful for manually
        instantiated workers.
        """
        assert self in Task._tasks.values(), "deleted task"

        # bind worker to task self
        worker._set_task(self)

        # add worker clients to engine
        for client in worker._engine_clients():
            self._engine.add(client)

    def _resume_thread(self):
        """Resume called from another thread."""
        self._suspend_cond.notify_all()

    def _resume(self):
        assert self.thread == threading.currentThread()
        try:
            try:
                self._reset()
                self._run(self.timeout)
            except EngineTimeoutException:
                raise TimeoutError()
            except EngineAbortException, e:
                self._terminate(e.kill)
            except EngineAlreadyRunningError:
                raise AlreadyRunningError()
            except:
                raise
        finally:
            # task becomes joinable
            self._join_cond.acquire()
            self._suspend_cond.suspend_count += 1
            self._join_cond.notifyAll()
            self._join_cond.release()

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
        self.timeout = timeout

        self._suspend_cond.atomic_dec()

        if self._is_task_self():
            self._resume()
        else:
            self._resume_thread()

    @tasksyncmethod()
    def _suspend_wait(self, keep_run_lock=False):
        assert task_self() == self
        # atomically set suspend state
        self._suspend_lock.acquire()
        self._suspended = True
        self._suspend_lock.release()

        # wait for special suspend condition, while releasing l_run
        self._suspend_cond.wait_check(self._run_lock)

        # waking up, atomically unset suspend state
        self._suspend_lock.acquire()
        self._suspended = False
        self._suspend_lock.release()
            
    def suspend(self):
        """
        Suspend task execution. This method may be called from another
        task (thread-safe). The function returns False if the task
        cannot be suspended (eg. it's not running), or returns True if
        the task has been successfully suspended.
        To resume a suspended task, use task.resume().
        """
        # first of all, increase suspend count
        self._suspend_cond.atomic_inc()

        # call synchronized suspend method
        self._suspend_wait()

        # wait for stopped task
        self._run_lock.acquire()
        
        # get result: are we really suspended or just stopped?
        result = True
        self._suspend_lock.acquire()
        if not self._suspended:
            # not acknowledging suspend state, task is stopped
            result = False
            self._run_lock.release()
        self._suspend_lock.release()
        return result

    @tasksyncmethod()
    def _abort(self, kill=False):
        assert task_self() == self
        # raise an EngineAbortException when task is running
        self._engine.abort(kill)

    def abort(self, kill=False):
        """
        Abort a task. Aborting a task removes (and stops when needed)
        all workers. If optional parameter kill is True, the task
        object is unbound from the current thread, so calling
        task_self() creates a new Task object.
        """
        if self._run_lock.acquire(0):
            self._quit = True
            self._run_lock.release()
            if self._is_task_self():
                self._terminate(kill)
            else:
                self.resume()
        else:
            # call synchronized method when running
            self._abort(kill)

    def _terminate(self, kill):
        """
        Abort completion subroutine.
        """
        self._engine.clear()
        self._reset()

        if kill:
            Task._task_lock.acquire()
            try:
                del Task._tasks[threading.currentThread()]
            finally:
                Task._task_lock.release()

    def join(self):
        """
        Suspend execution of the calling thread until the target task
        terminates, unless the target task has already terminated.
        """
        self._join_cond.acquire()
        try:
            if self._suspend_cond.suspend_count > 0:
                if not self._suspended:
                    # ignore stopped task
                    return
            self._join_cond.wait()
        finally:
            self._join_cond.release()

    def running(self):
        """
        Return True if the task is running.
        """
        return self._engine.running

    def _reset(self):
        """
        Reset buffers and retcodes management variables.
        """
        self._msgtree.clear()
        self._errtree.clear()
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
        s = self._msgtree.get(source)
        if s is None:
            return None
        return str(s)

    def _errmsg_by_source(self, source):
        """
        Get an error message by its source (worker, key).
        """
        s = self._errtree.get(source)
        if s is None:
            return None
        return str(s)

    def _msg_iter_by_key(self, key):
        """
        Return an iterator over stored messages for the given key.
        """
        return itertools.imap(str, self._msgtree.msgs(lambda k: k[1] == key))

    def _errmsg_iter_by_key(self, key):
        """
        Return an iterator over stored error messages for the given key.
        """
        return itertools.imap(str, self._errtree.msgs(lambda k: k[1] == key))

    def _msg_iter_by_worker(self, worker, match_keys=None):
        """
        Return an iterator over messages and keys list for a specific
        worker and optional matching keys.
        """
        # iterate by worker and optionally by matching keys
        match = None
        if match_keys is not None:
            match = lambda k: k[0] is worker and k[1] in match_keys
            
        return self._msgtree.msg_keys(match, operator.itemgetter(1))

    def _errmsg_iter_by_worker(self, worker, match_keys=None):
        """
        Return an iterator over error messages and keys list for a specific
        worker and optional matching keys.
        """
        # iterate by worker and optionally by matching keys
        match = None
        if match_keys is not None:
            match = lambda k: k[0] is worker and k[1] in match_keys
            
        return self._errtree.msg_keys(match, operator.itemgetter(1))

    def _kmsg_iter_by_worker(self, worker):
        """
        Return an iterator over key, message for a specific worker.
        """
        return self._msgtree.msg_keys(lambda k: k[0] is worker,
                                      operator.itemgetter(1))
 
    def _kerrmsg_iter_by_worker(self, worker):
        """
        Return an iterator over key, err_message for a specific worker.
        """
        return self._msgtree.msg_keys(lambda k: k[0] is worker,
                                      operator.itemgetter(1))
    
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

    def key_error(self, key):
        """
        Get error buffer for a specific key. When the key is associated
        to multiple workers, the resulting buffer will contain all
        workers content that may overlap.
        """
        return "".join(self._errmsg_iter_by_key(key))
    
    node_error = key_error

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
        match = None
        if match_keys:
            match = lambda k: k[1] in match_keys
        return self._msgtree.msg_keys(match=match, mapper=operator.itemgetter(1))

    def iter_errors(self, match_keys=None):
        """
        Iterate over error buffers, returns a tuple (buffer, keys).

        See iter_buffers().
        """
        match = None
        if match_keys:
            match = lambda k: k[1] in match_keys
        return self._errtree.msg_keys(match=match, mapper=operator.itemgetter(1))
            
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

    @classmethod
    def wait(cls, from_thread):
        """
        Class method that blocks calling thread until all tasks have
        finished (from a ClusterShell point of view, for instance,
        their task.resume() return). It doesn't necessarly mean that
        associated threads have finished.
        """
        Task._task_lock.acquire()
        try:
            tasks = Task._tasks.copy()
        finally:
            Task._task_lock.release()
        for thread, task in tasks.iteritems():
            if thread != from_thread:
                task.join()


def task_self():
    """
    Get the Task instance bound to the current thread. This function
    provided as a convenience is available in the top-level
    ClusterShell.Task package namespace.
    """
    return Task(thread=threading.currentThread())

def task_wait():
    """
    Suspend execution of the calling thread until all tasks terminate,
    unless all tasks have already terminated. This function is provided
    as a convenience and is available in the top-level
    ClusterShell.Task package namespace.
    """
    Task.wait(threading.currentThread())

def task_terminate():
    """
    Destroy the Task instance bound to the current thread. A next call
    to task_self() will create a new Task object. This function provided
    as a convenience is available in the top-level ClusterShell.Task
    package namespace.
    """
    task_self().abort(kill=True)

def task_cleanup():
    """
    Cleanup routine to destroy all created tasks. This function
    provided as a convenience is available in the top-level
    ClusterShell.Task package namespace.
    """
    Task._task_lock.acquire()
    try:
        tasks = Task._tasks.copy()
    finally:
        Task._task_lock.release()
    for thread, task in tasks.iteritems():
        task.abort(kill=True)

