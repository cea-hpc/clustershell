#
# Copyright (C) 2007-2016 CEA/DAM
# Copyright (C) 2015-2016 Stephane Thiell <sthiell@stanford.edu>
#
# This file is part of ClusterShell.
#
# ClusterShell is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# ClusterShell is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with ClusterShell; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

"""
ClusterShell Task module.

Simple example of use:

>>> from ClusterShell.Task import task_self, NodeSet
>>>  
>>> # get task associated with calling thread
... task = task_self()
>>> 
>>> # add a command to execute on distant nodes
... task.shell("/bin/uname -r", nodes="tiger[1-30,35]")
<ClusterShell.Worker.Ssh.WorkerSsh object at 0x7f41da71b890>
>>> 
>>> # run task in calling thread
... task.run()
>>> 
>>> # get results
... for output, nodelist in task.iter_buffers():
...     print '%s: %s' % (NodeSet.fromlist(nodelist), output)
... 

"""

from itertools import imap
import logging
from operator import itemgetter
import os
import socket
import sys
import threading
from time import sleep
import traceback

from ClusterShell.Defaults import config_paths, DEFAULTS
from ClusterShell.Defaults import _local_workerclass, _distant_workerclass
from ClusterShell.Engine.Engine import EngineAbortException
from ClusterShell.Engine.Engine import EngineTimeoutException
from ClusterShell.Engine.Engine import EngineAlreadyRunningError
from ClusterShell.Engine.Engine import EngineTimer
from ClusterShell.Engine.Factory import PreferredEngine
from ClusterShell.Worker.EngineClient import EnginePort
from ClusterShell.Worker.Popen import WorkerPopen
from ClusterShell.Worker.Tree import WorkerTree
from ClusterShell.Worker.Worker import FANOUT_UNLIMITED

from ClusterShell.Event import EventHandler
from ClusterShell.MsgTree import MsgTree
from ClusterShell.NodeSet import NodeSet

from ClusterShell.Topology import TopologyParser, TopologyError
from ClusterShell.Propagation import PropagationTreeRouter, PropagationChannel


class TaskException(Exception):
    """Base task exception."""

class TaskError(TaskException):
    """Base task error exception."""

class TimeoutError(TaskError):
    """Raised when the task timed out."""

class AlreadyRunningError(TaskError):
    """Raised when trying to resume an already running task."""

class TaskMsgTreeError(TaskError):
    """Raised when trying to access disabled MsgTree."""


def _getshorthostname():
    """Get short hostname (host name cut at the first dot)"""
    return socket.gethostname().split('.')[0]


class Task(object):
    """
    The Task class defines an essential ClusterShell object which aims to
    execute commands in parallel and easily get their results.

    More precisely, a Task object manages a coordinated (ie. with respect of
    its current parameters) collection of independent parallel Worker objects.
    See ClusterShell.Worker.Worker for further details on ClusterShell Workers.

    Always bound to a specific thread, a Task object acts like a "thread
    singleton". So most of the time, and even more for single-threaded
    applications, you can get the current task object with the following
    top-level Task module function:

        >>> task = task_self()

    However, if you want to create a task in a new thread, use:

        >>> task = Task()

    To create or get the instance of the task associated with the thread
    object thr (threading.Thread):

        >>> task = Task(thread=thr)

    To submit a command to execute locally within task, use:

        >>> task.shell("/bin/hostname")

    To submit a command to execute to some distant nodes in parallel, use:

        >>> task.shell("/bin/hostname", nodes="tiger[1-20]")

    The previous examples submit commands to execute but do not allow result
    interaction during their execution. For your program to interact during
    command execution, it has to define event handlers that will listen for
    local or remote events. These handlers are based on the EventHandler
    class, defined in ClusterShell.Event. The following example shows how to
    submit a command on a cluster with a registered event handler:

        >>> task.shell("uname -r", nodes="node[1-9]", handler=MyEventHandler())

    Run task in its associated thread (will block only if the calling thread is
    the task associated thread):

        >>> task.resume()
    or:

        >>> task.run()

    You can also pass arguments to task.run() to schedule a command exactly
    like in task.shell(), and run it:

        >>> task.run("hostname", nodes="tiger[1-20]", handler=MyEventHandler())

    A common need is to set a maximum delay for command execution, especially
    when the command time is not known. Doing this with ClusterShell Task is
    very straighforward. To limit the execution time on each node, use the
    timeout parameter of shell() or run() methods to set a delay in seconds,
    like:

        >>> task.run("check_network.sh", nodes="tiger[1-20]", timeout=30)

    You can then either use Task's iter_keys_timeout() method after execution
    to see on what nodes the command has timed out, or listen for ev_timeout()
    events in your event handler.

    To get command result, you can either use Task's iter_buffers() method for
    standard output, iter_errors() for standard error after command execution
    (common output contents are automatically gathered), or you can listen for
    ev_read() and ev_error() events in your event handler and get live command
    output.

    To get command return codes, you can either use Task's iter_retcodes(),
    node_retcode() and max_retcode() methods after command execution, or
    listen for ev_hup() events in your event handler.
    """

    # topology.conf file path list
    TOPOLOGY_CONFIGS = config_paths('topology.conf')

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
                elif task._dispatch_port:
                    # no, safely call the task method by message
                    # through the task special dispatch port
                    task._dispatch_port.msg_send((f, fargs, kwargs))
                else:
                    task.info("print_debug")(task, "%s: dropped call: %s" % \
                                                   (task, str(fargs)))
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


    def __new__(cls, thread=None, defaults=None):
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

    def __init__(self, thread=None, defaults=None):
        """Initialize a Task, creating a new non-daemonic thread if
        needed."""
        if not getattr(self, "_engine", None):
            # first time called
            self._default_lock = threading.Lock()
            if defaults is None:
                defaults = DEFAULTS
            self._default = defaults._task_default.copy()
            self._default.update(
                {"local_worker": _local_workerclass(defaults),
                 "distant_worker": _distant_workerclass(defaults)})
            self._info = defaults._task_info.copy()

            # use factory class PreferredEngine that gives the proper
            # engine instance
            self._engine = PreferredEngine(self.default("engine"), self._info)
            self.timeout = None

            # task synchronization objects
            self._run_lock = threading.Lock()       # primitive lock
            self._suspend_lock = threading.RLock()  # reentrant lock
            # both join and suspend conditions share the same underlying lock
            self._suspend_cond = Task._SuspendCondition(self._suspend_lock, 1)
            self._join_cond = threading.Condition(self._suspend_lock)
            self._suspended = False
            self._quit = False
            self._terminated = False

            # Default router
            self.topology = None
            self.router = None
            self.gateways = {}

            # dict of MsgTree by sname
            self._msgtrees = {}
            # dict of sources to return codes
            self._d_source_rc = {}
            # dict of return codes to sources
            self._d_rc_sources = {}
            # keep max rc
            self._max_rc = None
            # keep timeout'd sources
            self._timeout_sources = set()
            # allow no-op call to getters before resume()
            self._reset()

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
            self._thread_foreign = bool(thread)
            if self._thread_foreign:
                self.thread = thread
            else:
                self.thread = thread = \
                    threading.Thread(None,
                                     Task._thread_start,
                                     "Task-%d" % self._taskid,
                                     args=(self,))
                Task._tasks[thread] = self
                thread.start()

    def _is_task_self(self):
        """Private method used by the library to check if the task is
        task_self(), but do not create any task_self() instance."""
        return self.thread == threading.currentThread()

    def default_excepthook(self, exc_type, exc_value, tb):
        """Default excepthook for a newly Task. When an exception is
        raised and uncaught on Task thread, excepthook is called, which
        is default_excepthook by default. Once excepthook overriden,
        you can still call default_excepthook if needed."""
        print >> sys.stderr, 'Exception in thread %s:' % self.thread
        traceback.print_exception(exc_type, exc_value, tb, file=sys.stderr)

    _excepthook = default_excepthook

    def _getexcepthook(self):
        return self._excepthook

    def _setexcepthook(self, hook):
        self._excepthook = hook
        # If thread has not been created by us, install sys.excepthook which
        # might handle uncaught exception.
        if self._thread_foreign:
            sys.excepthook = self._excepthook

    # When an exception is raised and uncaught on Task's thread,
    # excepthook is called. You may want to override this three
    # arguments method (very similar of what you can do with
    # sys.excepthook)."""
    excepthook = property(_getexcepthook, _setexcepthook)

    def _thread_start(self):
        """Task-managed thread entry point"""
        while not self._quit:
            self._suspend_cond.wait_check()
            if self._quit:  # may be set by abort()
                break
            try:
                self._resume()
            except:
                self.excepthook(*sys.exc_info())
                self._quit = True

        self._terminate(kill=True)

    def _run(self, timeout):
        """Run task (always called from its self thread)."""
        # check if task is already running
        if self._run_lock.locked():
            raise AlreadyRunningError("task is already running")
        # use with statement later
        try:
            self._run_lock.acquire()
            self._engine.run(timeout)
        finally:
            self._run_lock.release()

    def _default_tree_is_enabled(self):
        """Return whether default tree is enabled (load topology_file btw)"""
        if self.topology is None:
            for topology_file in self.TOPOLOGY_CONFIGS[::-1]:
                if os.path.exists(topology_file):
                    self.load_topology(topology_file)
                    break
        return (self.topology is not None) and self.default("auto_tree")

    def load_topology(self, topology_file):
        """Load propagation topology from provided file.

        On success, task.topology is set to a corresponding TopologyTree
        instance.

        On failure, task.topology is left untouched and a TopologyError
        exception is raised.
        """
        self.topology = TopologyParser(topology_file).tree(_getshorthostname())

    def _default_router(self):
        if self.router is None:
            self.router = PropagationTreeRouter(str(self.topology.root.nodeset),
                                                self.topology)
        return self.router

    def default(self, default_key, def_val=None):
        """
        Return per-task value for key from the "default" dictionary.
        See set_default() for a list of reserved task default_keys.
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

        Task default_keys are:
          - "stderr": Boolean value indicating whether to enable
            stdout/stderr separation when using task.shell(), if not
            specified explicitly (default: False).
          - "stdout_msgtree": Whether to instantiate standard output
            MsgTree for automatic internal gathering of result messages
            coming from Workers (default: True).
          - "stderr_msgtree": Same for stderr (default: True).
          - "engine": Used to specify an underlying Engine explicitly
            (default: "auto").
          - "port_qlimit": Size of port messages queue (default: 32).
          - "worker": Worker-based class used when spawning workers through
            shell()/run().

        Threading considerations
        ========================
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
        Return per-task information. See set_info() for a list of
        reserved task info_keys.
        """
        return self._info.get(info_key, def_val)

    @tasksyncmethod()
    def set_info(self, info_key, value):
        """
        Set task value for a specific key information. Key, value
        pairs can be passed to the engine and/or workers.
        Users may store their own task-specific info key, value pairs
        using this method and retrieve them with info().

        The following example changes the fanout value to 128:
            >>> task.set_info('fanout', 128)

        The following example enables debug messages:
            >>> task.set_info('debug', True)

        Task info_keys are:
          - "debug": Boolean value indicating whether to enable library
            debugging messages (default: False).
          - "print_debug": Debug messages processing function. This
            function takes 2 arguments: the task instance and the
            message string (default: an internal function doing standard
            print).
          - "fanout": Max number of registered clients in Engine at a
            time (default: 64).
          - "grooming_delay": Message maximum end-to-end delay requirement
            used for traffic grooming, in seconds as float (default: 0.5).
          - "connect_timeout": Time in seconds to wait for connecting to
            remote host before aborting (default: 10).
          - "command_timeout": Time in seconds to wait for a command to
            complete before aborting (default: 0, which means
            unlimited).

        Threading considerations
        ========================
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
        Schedule a shell command for local or distant parallel execution. This
        essential method creates a local or remote Worker (depending on the
        presence of the nodes parameter) and immediately schedules it for
        execution in task's runloop. So, if the task is already running
        (ie. called from an event handler), the command is started immediately,
        assuming current execution contraintes are met (eg. fanout value). If
        the task is not running, the command is not started but scheduled for
        late execution. See resume() to start task runloop.

        The following optional parameters are passed to the underlying local
        or remote Worker constructor:
          - handler: EventHandler instance to notify (on event) -- default is
            no handler (None)
          - timeout: command timeout delay expressed in second using a floating
            point value -- default is unlimited (None)
          - autoclose: if set to True, the underlying Worker is automatically
            aborted as soon as all other non-autoclosing task objects (workers,
            ports, timers) have finished -- default is False
          - stderr: separate stdout/stderr if set to True -- default is False.

        Local usage::
            task.shell(command [, key=key] [, handler=handler]
                  [, timeout=secs] [, autoclose=enable_autoclose]
                  [, stderr=enable_stderr])

        Distant usage::
            task.shell(command, nodes=nodeset [, handler=handler]
                  [, timeout=secs], [, autoclose=enable_autoclose]
                  [, tree=None|False|True] [, remote=False|True]
                  [, stderr=enable_stderr])

        Example:

        >>> task = task_self()
        >>> task.shell("/bin/date", nodes="node[1-2345]")
        >>> task.resume()
        """

        handler = kwargs.get("handler", None)
        timeo = kwargs.get("timeout", None)
        autoclose = kwargs.get("autoclose", False)
        stderr = kwargs.get("stderr", self.default("stderr"))
        remote = kwargs.get("remote", True)

        if kwargs.get("nodes", None):
            assert kwargs.get("key", None) is None, \
                    "'key' argument not supported for distant command"

            tree = kwargs.get("tree")

            # tree == None means auto
            if tree != False and self._default_tree_is_enabled():
                # fail if tree is forced without any topology
                if tree and self.topology is None:
                    raise TaskError("tree mode required for distant shell "
                                    "command with unknown topology!")
                # create tree worker
                wrkcls = WorkerTree
            elif not remote:
                # create local worker
                wrkcls = self.default('local_worker')
            else:
                # create distant worker
                wrkcls = self.default('distant_worker')

            worker = wrkcls(NodeSet(kwargs["nodes"]), command=command,
                            handler=handler, stderr=stderr,
                            timeout=timeo, autoclose=autoclose, remote=remote)
        else:
            # create old fashioned local worker
            worker = WorkerPopen(command, key=kwargs.get("key", None),
                                 handler=handler, stderr=stderr,
                                 timeout=timeo, autoclose=autoclose)

        # schedule worker for execution in this task
        self.schedule(worker)

        return worker

    def copy(self, source, dest, nodes, **kwargs):
        """
        Copy local file to distant nodes.
        """
        assert nodes != None, "local copy not supported"

        handler = kwargs.get("handler", None)
        stderr = kwargs.get("stderr", self.default("stderr"))
        timeo = kwargs.get("timeout", None)
        preserve = kwargs.get("preserve", None)
        reverse = kwargs.get("reverse", False)

        tree = kwargs.get("tree")

        # tree == None means auto
        if tree != False and self._default_tree_is_enabled():
            # fail if tree is forced without any topology
            if tree and self.topology is None:
                raise TaskError("tree mode required for distant shell "
                                "command with unknown topology!")

            # create tree worker
            wrkcls = WorkerTree
        else:
            # create a new copy worker
            wrkcls = self.default('distant_worker')

        worker = wrkcls(nodes, source=source, dest=dest, handler=handler,
                        stderr=stderr, timeout=timeo, preserve=preserve,
                        reverse=reverse)

        self.schedule(worker)
        return worker

    def rcopy(self, source, dest, nodes, **kwargs):
        """
        Copy distant file or directory to local node.
        """
        kwargs['reverse'] = True
        return self.copy(source, dest, nodes, **kwargs)

    @tasksyncmethod()
    def _add_port(self, port):
        """Add an EnginePort instance to Engine (private method)."""
        self._engine.add(port)

    @tasksyncmethod()
    def remove_port(self, port):
        """Close and remove a port from task previously created with port()."""
        self._engine.remove(port)

    def port(self, handler=None, autoclose=False):
        """
        Create a new task port. A task port is an abstraction object to
        deliver messages reliably between tasks.

        Basic rules:
          - A task can send messages to another task port (thread safe).
          - A task can receive messages from an acquired port either by
            setting up a notification mechanism or using a polling
            mechanism that may block the task waiting for a message
            sent on the port.
          - A port can be acquired by one task only.

        If handler is set to a valid EventHandler object, the port is
        a send-once port, ie. a message sent to this port generates an
        ev_msg event notification issued the port's task. If handler
        is not set, the task can only receive messages on the port by
        calling port.msg_recv().
        """
        port = EnginePort(self, handler, autoclose)
        self._add_port(port)
        return port

    def timer(self, fire, handler, interval=-1.0, autoclose=False):
        """
        Create a timer bound to this task that fires at a preset time
        in the future by invoking the ev_timer() method of `handler'
        (provided EventHandler object). Timers can fire either only
        once or repeatedly at fixed time intervals. Repeating timers
        can also have their next firing time manually adjusted.

        The mandatory parameter `fire' sets the firing delay in seconds.

        The optional parameter `interval' sets the firing interval of
        the timer. If not specified, the timer fires once and then is
        automatically invalidated.

        Time values are expressed in second using floating point
        values. Precision is implementation (and system) dependent.

        The optional parameter `autoclose', if set to True, creates
        an "autoclosing" timer: it will be automatically invalidated
        as soon as all other non-autoclosing task's objects (workers,
        ports, timers) have finished. Default value is False, which
        means the timer will retain task's runloop until it is
        invalidated.

        Return a new EngineTimer instance.

        See ClusterShell.Engine.Engine.EngineTimer for more details.
        """
        assert fire >= 0.0, \
            "timer's relative fire time must be a positive floating number"

        timer = EngineTimer(fire, interval, autoclose, handler)
        # The following method may be sent through msg port (async
        # call) if called from another task.
        self._add_timer(timer)
        # always return new timer (sync)
        return timer

    @tasksyncmethod()
    def _add_timer(self, timer):
        """Add a timer to task engine (thread-safe)."""
        self._engine.add_timer(timer)

    @tasksyncmethod()
    def schedule(self, worker):
        """
        Schedule a worker for execution, ie. add worker in task running
        loop. Worker will start processing immediately if the task is
        running (eg. called from an event handler) or as soon as the
        task is started otherwise. Only useful for manually instantiated
        workers, for example:

        >>> task = task_self()
        >>> worker = WorkerSsh("node[2-3]", None, 10, command="/bin/ls")
        >>> task.schedule(worker)
        >>> task.resume()
        """
        assert self in Task._tasks.values(), \
            "deleted task instance, call task_self() again!"

        # bind worker to task self
        worker._set_task(self)

        # add worker clients to engine
        for client in worker._engine_clients():
            self._engine.add(client)

    def _resume_thread(self):
        """Resume task - called from another thread."""
        self._suspend_cond.notify_all()

    def _resume(self):
        """Resume task - called from self thread."""
        assert self.thread == threading.currentThread()
        try:
            try:
                self._reset()
                self._run(self.timeout)
            except EngineTimeoutException:
                raise TimeoutError()
            except EngineAbortException, exc:
                self._terminate(exc.kill)
            except EngineAlreadyRunningError:
                raise AlreadyRunningError("task engine is already running")
        finally:
            # task becomes joinable
            self._join_cond.acquire()
            self._suspend_cond.atomic_inc()
            self._join_cond.notifyAll()
            self._join_cond.release()

    def resume(self, timeout=None):
        """
        Resume task. If task is task_self(), workers are executed in the
        calling thread so this method will block until all (non-autoclosing)
        workers have finished. This is always the case for a single-threaded
        application (eg. which doesn't create other Task() instance than
        task_self()). Otherwise, the current thread doesn't block. In that
        case, you may then want to call task_wait() to wait for completion.

        Warning: the timeout parameter can be used to set an hard limit of
        task execution time (in seconds). In that case, a TimeoutError
        exception is raised if this delay is reached. Its value is 0 by
        default, which means no task time limit (TimeoutError is never
        raised). In order to set a maximum delay for individual command
        execution, you should use Task.shell()'s timeout parameter instead.
        """
        # If you change options here, check Task.run() compatibility.

        self.timeout = timeout

        self._suspend_cond.atomic_dec()

        if self._is_task_self():
            self._resume()
        else:
            self._resume_thread()

    def run(self, command=None, **kwargs):
        """
        With arguments, it will schedule a command exactly like a Task.shell()
        would have done it and run it.
        This is the easiest way to simply run a command.

        >>> task.run("hostname", nodes="foo")

        Without argument, it starts all outstanding actions.
        It behaves like Task.resume().

        >>> task.shell("hostname", nodes="foo")
        >>> task.shell("hostname", nodes="bar")
        >>> task.run()

        When used with a command, you can set a maximum delay of individual
        command execution with the help of the timeout parameter (see
        Task.shell's parameters). You can then listen for ev_timeout() events
        in your Worker event handlers, or use num_timeout() or
        iter_keys_timeout() afterwards.
        But, when used as an alias to Task.resume(), the timeout parameter
        sets an hard limit of task execution time. In that case, a TimeoutError
        exception is raised if this delay is reached.
        """
        worker = None
        timeout = None

        # Both resume() and shell() support a 'timeout' parameter. We need a
        # trick to behave correctly for both cases.
        #
        # Here, we mock: task.resume(10)
        if type(command) in (int, float):
            timeout = command
            command = None
        # Here, we mock: task.resume(timeout=10)
        elif 'timeout' in kwargs and command is None:
            timeout = kwargs.pop('timeout')
        # All other cases mean a classical: shell(...)
        # we mock: task.shell("mycommand", [timeout=..., ...])
        elif command is not None:
            worker = self.shell(command, **kwargs)

        self.resume(timeout)

        return worker

    @tasksyncmethod()
    def _suspend_wait(self):
        """Suspend request received."""
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
        self._run_lock.acquire()    # run_lock ownership transfer

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
        """Abort request received."""
        assert task_self() == self
        # raise an EngineAbortException when task is running
        self._quit = True
        self._engine.abort(kill)

    def abort(self, kill=False):
        """
        Abort a task. Aborting a task removes (and stops when needed)
        all workers. If optional parameter kill is True, the task
        object is unbound from the current thread, so calling
        task_self() creates a new Task object.
        """
        if not self._run_lock.acquire(0):
            # self._run_lock is locked, try to call synchronized method
            self._abort(kill)
            # but there is no guarantee that it has really been called, as the
            # task could have aborted during the same time, so we use polling
            while not self._run_lock.acquire(0):
                sleep(0.001)
        # in any case, once _run_lock has been acquired, confirm abort
        self._quit = True
        self._run_lock.release()
        if self._is_task_self():
            self._terminate(kill)
        else:
            # abort on stopped/suspended task
            self._suspend_cond.notify_all()

    def _terminate(self, kill):
        """
        Abort completion subroutine.
        """
        assert self._quit == True
        self._terminated = True

        if kill:
            # invalidate dispatch port
            self._dispatch_port = None
        # clear engine
        self._engine.clear(clear_ports=kill)
        if kill:
            self._engine.release()
            self._engine = None

        # clear result objects
        self._reset()

        # unlock any remaining threads that are waiting for our
        # termination (late join()s)
        # must be called after _terminated is set to True
        self._join_cond.acquire()
        self._join_cond.notifyAll()
        self._join_cond.release()

        # destroy task if needed
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
            if self._suspend_cond.suspend_count > 0 and not self._suspended:
                # ignore stopped task
                return
            if self._terminated:
                # ignore join() on dead task
                return
            self._join_cond.wait()
        finally:
            self._join_cond.release()

    def running(self):
        """
        Return True if the task is running.
        """
        return self._engine and self._engine.running

    def _reset(self):
        """
        Reset buffers and retcodes management variables.
        """
        # reinit MsgTree dict
        self._msgtrees = {}
        # other re-init's
        self._d_source_rc = {}
        self._d_rc_sources = {}
        self._max_rc = None
        self._timeout_sources.clear()

    def _msgtree(self, sname, strict=True):
        """Helper method to return msgtree instance by sname if allowed."""
        if self.default("%s_msgtree" % sname):
            if sname not in self._msgtrees:
                self._msgtrees[sname] = MsgTree()
            return self._msgtrees[sname]
        elif strict:
            raise TaskMsgTreeError("%s_msgtree not set" % sname)

    def _msg_add(self, worker, node, sname, msg):
        """
        Process a new message into Task's MsgTree that is coming from:
            - a worker instance of this task
            - a node
            - a stream name sname (string identifier)
        """
        assert worker.task == self, "better to add messages from my workers"
        msgtree = self._msgtree(sname, strict=False)
        # As strict=False, if msgtree is None, this means task is set to NOT
        # record messages... in that case we ignore this request, still
        # keeping possible existing MsgTree, thus allowing temporarily
        # disabled ones.
        if msgtree is not None:
            msgtree.add((worker, node), msg)

    def _rc_set(self, worker, node, rc):
        """
        Add a worker return code (rc) that is coming from a node of a
        worker instance.
        """
        source = (worker, node)

        # store rc by source
        self._d_source_rc[source] = rc

        # store source by rc
        self._d_rc_sources.setdefault(rc, set()).add(source)

        # update max rc
        if self._max_rc is None or rc > self._max_rc:
            self._max_rc = rc

    def _timeout_add(self, worker, node):
        """
        Add a timeout indicator that is coming from a node of a worker
        instance.
        """
        # store source in timeout set
        self._timeout_sources.add((worker, node))

    def _msg_by_source(self, worker, node, sname):
        """Get a message by its worker instance, node and stream name."""
        msg = self._msgtree(sname).get((worker, node))
        if msg is None:
            return None
        return str(msg)

    def _call_tree_matcher(self, tree_match_func, match_keys=None, worker=None):
        """Call identified tree matcher (items, walk) method with options."""
        if isinstance(match_keys, basestring): # change to str for Python 3
            raise TypeError("Sequence of keys/nodes expected for 'match_keys'.")
        # filter by worker and optionally by matching keys
        if worker and match_keys is None:
            match = lambda k: k[0] is worker
        elif worker and match_keys is not None:
            match = lambda k: k[0] is worker and k[1] in match_keys
        elif match_keys:
            match = lambda k: k[1] in match_keys
        else:
            match = None
        # Call tree matcher function (items or walk)
        return tree_match_func(match, itemgetter(1))

    def _rc_by_source(self, worker, node):
        """Get a return code by worker instance and node."""
        return self._d_source_rc[(worker, node)]

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
                keys = [t[1] for t in src if t[0] is worker and \
                                             t[1] in match_keys]
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

    def _flush_buffers_by_worker(self, worker):
        """
        Remove any messages from specified worker.
        """
        msgtree = self._msgtree('stdout', strict=False)
        if msgtree is not None:
            msgtree.remove(lambda k: k[0] == worker)

    def _flush_errors_by_worker(self, worker):
        """
        Remove any error messages from specified worker.
        """
        errtree = self._msgtree('stderr', strict=False)
        if errtree is not None:
            errtree.remove(lambda k: k[0] == worker)

    def key_buffer(self, key):
        """
        Get buffer for a specific key. When the key is associated
        to multiple workers, the resulting buffer will contain
        all workers content that may overlap. This method returns an
        empty buffer if key is not found in any workers.
        """
        msgtree = self._msgtree('stdout')
        select_key = lambda k: k[1] == key
        return "".join(imap(str, msgtree.messages(select_key)))

    node_buffer = key_buffer

    def key_error(self, key):
        """
        Get error buffer for a specific key. When the key is associated
        to multiple workers, the resulting buffer will contain all
        workers content that may overlap. This method returns an empty
        error buffer if key is not found in any workers.
        """
        errtree = self._msgtree('stderr')
        select_key = lambda k: k[1] == key
        return "".join(imap(str, errtree.messages(select_key)))

    node_error = key_error

    def key_retcode(self, key):
        """
        Return return code for a specific key. When the key is
        associated to multiple workers, return the max return
        code from these workers. Raises a KeyError if key is not found
        in any finished workers.
        """
        codes = list(self._rc_iter_by_key(key))
        if not codes:
            raise KeyError(key)
        return max(codes)

    node_retcode = key_retcode

    def max_retcode(self):
        """
        Get max return code encountered during last run
            or None in the following cases:
                - all commands timed out,
                - no command was executed.

        How retcodes work
        =================
          If the process exits normally, the return code is its exit
          status. If the process is terminated by a signal, the return
          code is 128 + signal number.
        """
        return self._max_rc

    def _iter_msgtree(self, sname, match_keys=None):
        """Helper method to iterate over recorded buffers by sname."""
        try:
            msgtree = self._msgtrees[sname]
            return self._call_tree_matcher(msgtree.walk, match_keys)
        except KeyError:
            if not self.default("%s_msgtree" % sname):
                raise TaskMsgTreeError("%s_msgtree not set" % sname)
            return iter([])

    def iter_buffers(self, match_keys=None):
        """
        Iterate over buffers, returns a tuple (buffer, keys). For remote
        workers (Ssh), keys are list of nodes. In that case, you should use
        NodeSet.fromlist(keys) to get a NodeSet instance (which is more
        convenient and efficient):

        Optional parameter match_keys add filtering on these keys.

        Usage example:

        >>> for buffer, nodelist in task.iter_buffers():
        ...     print NodeSet.fromlist(nodelist)
        ...     print buffer
        """
        return self._iter_msgtree('stdout', match_keys)

    def iter_errors(self, match_keys=None):
        """
        Iterate over error buffers, returns a tuple (buffer, keys).

        See iter_buffers().
        """
        return self._iter_msgtree('stderr', match_keys)

    def iter_retcodes(self, match_keys=None):
        """
        Iterate over return codes, returns a tuple (rc, keys).

        Optional parameter match_keys add filtering on these keys.

        How retcodes work
        =================
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

    def flush_buffers(self):
        """
        Flush all task messages (from all task workers).
        """
        msgtree = self._msgtree('stdout', strict=False)
        if msgtree is not None:
            msgtree.clear()

    def flush_errors(self):
        """
        Flush all task error messages (from all task workers).
        """
        errtree = self._msgtree('stderr', strict=False)
        if errtree is not None:
            errtree.clear()

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

    def _pchannel(self, gateway, metaworker):
        """Get propagation channel for gateway (create one if needed).

        Use self.gateways dictionary that allows lookup like:
            gateway => (worker channel, set of metaworkers)
        """
        # create gateway channel if needed
        if gateway not in self.gateways:
            chan = PropagationChannel(self, gateway)
            logger = logging.getLogger(__name__)
            logger.info("pchannel: creating new channel %s", chan)
            # invoke gateway
            timeout = None # FIXME: handle timeout for gateway channels
            wrkcls = self.default('distant_worker')
            chanworker = wrkcls(gateway, command=metaworker.invoke_gateway,
                                handler=chan, stderr=True, timeout=timeout)
            # gateway is special! define worker._fanout to not rely on the
            # engine's fanout, and use the special value FANOUT_UNLIMITED to
            # always allow registration of gateways
            chanworker._fanout = FANOUT_UNLIMITED
            # change default stream names to avoid internal task buffering
            # and conform with channel stream names
            chanworker.SNAME_STDIN = chan.SNAME_WRITER
            chanworker.SNAME_STDOUT = chan.SNAME_READER
            chanworker.SNAME_STDERR = chan.SNAME_ERROR
            self.schedule(chanworker)
            # update gateways dict
            self.gateways[gateway] = (chanworker, set([metaworker]))
        else:
            # TODO: assert chanworker is running (need Worker.running())
            chanworker, metaworkers = self.gateways[gateway]
            metaworkers.add(metaworker)
        return chanworker.eh

    def _pchannel_release(self, gateway, metaworker):
        """Release propagation channel associated to gateway.

        Lookup by gateway, decref associated metaworker set and release
        channel worker if needed.
        """
        logger = logging.getLogger(__name__)
        logger.debug("pchannel_release %s %s", gateway, metaworker)

        if gateway not in self.gateways:
            logger.error("pchannel_release: no pchannel found for gateway %s",
                         gateway)
        else:
            # TODO: delay gateway closing when other gateways are running
            chanworker, metaworkers = self.gateways[gateway]
            metaworkers.remove(metaworker)
            if len(metaworkers) == 0:
                logger.info("pchannel_release: destroying channel %s",
                            chanworker.eh)
                chanworker.abort()
                # delete gateway reference
                del self.gateways[gateway]


def task_self(defaults=None):
    """
    Return the current Task object, corresponding to the caller's thread of
    control (a Task object is always bound to a specific thread). This function
    provided as a convenience is available in the top-level ClusterShell.Task
    package namespace.
    """
    return Task(thread=threading.currentThread(), defaults=defaults)

def task_wait():
    """
    Suspend execution of the calling thread until all tasks terminate, unless
    all tasks have already terminated. This function is provided as a
    convenience and is available in the top-level ClusterShell.Task package
    namespace.
    """
    Task.wait(threading.currentThread())

def task_terminate():
    """
    Destroy the Task instance bound to the current thread. A next call to
    task_self() will create a new Task object. Not to be called from a signal
    handler. This function provided as a convenience is available in the
    top-level ClusterShell.Task package namespace.
    """
    task_self().abort(kill=True)

def task_cleanup():
    """
    Cleanup routine to destroy all created tasks. This function provided as a
    convenience is available in the top-level ClusterShell.Task package
    namespace. This is mainly used for testing purposes and should be avoided
    otherwise. task_cleanup() may be called from any threads but not from a
    signal handler.
    """
    # be sure to return to a clean state (no task at all)
    while True:
        Task._task_lock.acquire()
        try:
            tasks = Task._tasks.copy()
            if len(tasks) == 0:
                break
        finally:
            Task._task_lock.release()
        # send abort to all known tasks (it's needed to retry as we may have
        # missed the engine notification window (it was just exiting, which is
        # quite a common case if we didn't task_join() previously), or we may
        # have lost some task's dispatcher port messages.
        for task in tasks.itervalues():
            task.abort(kill=True)
        # also, for other task than self, task.abort() is async and performed
        # through an EngineAbortException, so tell the Python scheduler to give
        # up control to raise this exception (handled by task._terminate())...
        sleep(0.001)
