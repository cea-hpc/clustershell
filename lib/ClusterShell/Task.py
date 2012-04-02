#
# Copyright CEA/DAM/DIF (2007, 2008, 2009, 2010, 2011, 2012)
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

"""
ClusterShell Task module.

Simple example of use:

>>> from ClusterShell.Task import task_self
>>>  
>>> # get task associated with calling thread
... task = task_self()
>>> 
>>> # add a command to execute on distant nodes
... task.shell("/bin/uname -r", nodes="tiger[1-30,35]")
<ClusterShell.Worker.Ssh.WorkerSsh object at 0x7f41da71b890>
>>> 
>>> # run task in calling thread
... task.resume()
>>> 
>>> # get results
... for buf, nodelist in task.iter_buffers():
...     print NodeSet.fromlist(nodelist), buf
... 

"""

from itertools import imap
import logging
from operator import itemgetter
import socket
import sys
import threading
from time import sleep
import traceback

from ClusterShell.Engine.Engine import EngineAbortException
from ClusterShell.Engine.Engine import EngineTimeoutException
from ClusterShell.Engine.Engine import EngineAlreadyRunningError
from ClusterShell.Engine.Engine import EngineTimer
from ClusterShell.Engine.Factory import PreferredEngine
from ClusterShell.Worker.EngineClient import EnginePort
from ClusterShell.Worker.Ssh import WorkerSsh
from ClusterShell.Worker.Popen import WorkerPopen
from ClusterShell.Worker.Tree import WorkerTree

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

def _task_print_debug(task, s):
    """
    Default task debug printing function. Cannot provide 'print'
    directly as it is not a function (will be in Py3k!).
    """
    print s


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
    or
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
    _std_default = {  "stderr"             : False,
                      "stdout_msgtree"     : True,
                      "stderr_msgtree"     : True,
                      "engine"             : 'auto',
                      "port_qlimit"        : 100,
                      "auto_tree"          : False,
                      "topology_file"      : "/etc/clustershell/topology.conf" }

    _std_info =     { "debug"              : False,
                      "print_debug"        : _task_print_debug,
                      "fanout"             : 64,
                      "grooming_delay"     : 0.25,
                      "connect_timeout"    : 10,
                      "command_timeout"    : 0 }
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
            self._run_lock = threading.Lock()       # primitive lock
            self._suspend_lock = threading.RLock()  # reentrant lock
            # both join and suspend conditions share the same underlying lock
            self._suspend_cond = Task._SuspendCondition(self._suspend_lock, 1)
            self._join_cond = threading.Condition(self._suspend_lock)
            self._suspended = False
            self._quit = False

            # Default router
            self.topology = None
            self.router = None
            self.pwrks = {}
            self.pmwkrs = {}

            # STDIN tree
            self._msgtree = None
            # STDERR tree
            self._errtree = None
            # dict of sources to return codes
            self._d_source_rc = {}
            # dict of return codes to sources
            self._d_rc_sources = {}
            # keep max rc
            self._max_rc = 0
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
            if self._quit:
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

    def set_topology(self, topology_file):
        """Set new propagation topology from provided file."""
        self.set_default("topology_file", topology_file)
        self.topology = self._default_topology()

    def _default_topology(self):
        try:
            parser = TopologyParser()
            parser.load(self.default("topology_file"))
            return parser.tree(_getshorthostname())
        except TopologyError, exc:
            logging.getLogger(__name__).exception("_default_topology(): %s", \
                                                  str(exc))
            raise
        return None

    def _default_router(self):
        if self.router is None:
            topology = self.topology
            self.router = PropagationTreeRouter(str(topology.root.nodeset), \
                                                topology)
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
          - "stdout_msgtree": Whether to enable standard output MsgTree
            for automatic internal gathering of result messages
            (default: True).
          - "stderr_msgtree": Same for stderr (default: True).
          - "engine": Used to specify an underlying Engine explicitly
            (default: "auto").
          - "port_qlimit": Size of port messages queue (default: 32).

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
                  [, strderr=enable_stderr], [tree=None|False|True])

        Example:

        >>> task = task_self()
        >>> task.shell("/bin/date", nodes="node[1-2345]")
        >>> task.resume()
        """

        handler = kwargs.get("handler", None)
        timeo = kwargs.get("timeout", None)
        autoclose = kwargs.get("autoclose", False)
        stderr = kwargs.get("stderr", self.default("stderr"))

        if kwargs.get("nodes", None):
            assert kwargs.get("key", None) is None, \
                    "'key' argument not supported for distant command"

            tree = kwargs.get("tree")
            if tree and self.topology is None:
                raise TaskError("tree mode required for distant shell command" \
                                " with unknown topology!")
            if tree is None: # means auto
                tree = self.default("auto_tree") and (self.topology is not None)
            if tree:
                # create tree of ssh worker
                worker = WorkerTree(NodeSet(kwargs["nodes"]), command=command,
                                    handler=handler, stderr=stderr,
                                    timeout=timeo, autoclose=autoclose)
            else:
                # create ssh-based worker
                worker = WorkerSsh(NodeSet(kwargs["nodes"]), command=command,
                                   handler=handler, stderr=stderr,
                                   timeout=timeo, autoclose=autoclose)
        else:
            # create (local) worker
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

        # create a new copy worker
        worker = WorkerSsh(nodes, source=source, dest=dest, handler=handler,
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
    def _remove_port(self, port):
        """Remove a port from Engine (private method)."""
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
        assert self in Task._tasks.values(), "deleted task"

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
            self._suspend_cond.suspend_count += 1
            self._join_cond.notifyAll()
            self._join_cond.release()

    def resume(self, timeout=0):
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
        timeout = 0

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
                # abort on stopped/suspended task
                self.resume()
        else:
            # self._run_lock is locked, call synchronized method
            self._abort(kill)

    def _terminate(self, kill):
        """
        Abort completion subroutine.
        """
        if kill:
            # invalidate dispatch port
            self._dispatch_port = None
        # clear engine
        self._engine.clear(clear_ports=kill)

        # clear result objects
        self._reset()

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
        # check and reset stdout MsgTree
        if self.default("stdout_msgtree"):
            if not self._msgtree:
                self._msgtree = MsgTree()
            self._msgtree.clear()
        else:
            self._msgtree = None
        # check and reset stderr MsgTree
        if self.default("stderr_msgtree"):
            if not self._errtree:
                self._errtree = MsgTree()
            self._errtree.clear()
        else:
            self._errtree = None
        # other re-init's
        self._d_source_rc = {}
        self._d_rc_sources = {}
        self._max_rc = 0
        self._timeout_sources.clear()

    def _msg_add(self, source, msg):
        """
        Add a worker message associated with a source.
        """
        msgtree = self._msgtree
        if msgtree is not None:
            msgtree.add(source, msg)

    def _errmsg_add(self, source, msg):
        """
        Add a worker error message associated with a source.
        """
        errtree = self._errtree
        if errtree is not None:
            errtree.add(source, msg)

    def _rc_set(self, source, rc, override=True):
        """
        Add a worker return code associated with a source.
        """
        if not override and self._d_source_rc.has_key(source):
            return

        # store rc by source
        self._d_source_rc[source] = rc

        # store source by rc
        self._d_rc_sources.setdefault(rc, set()).add(source)
        
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
        if self._msgtree is None:
            raise TaskMsgTreeError("stdout_msgtree not set")
        s = self._msgtree.get(source)
        if s is None:
            return None
        return str(s)

    def _errmsg_by_source(self, source):
        """
        Get an error message by its source (worker, key).
        """
        if self._errtree is None:
            raise TaskMsgTreeError("stderr_msgtree not set")
        s = self._errtree.get(source)
        if s is None:
            return None
        return str(s)

    def _call_tree_matcher(self, tree_match_func, match_keys=None, worker=None):
        """Call identified tree matcher (items, walk) method with options."""
        # filter by worker and optionally by matching keys
        if worker and not match_keys:
            match = lambda k: k[0] is worker
        elif worker and match_keys:
            match = lambda k: k[0] is worker and k[1] in match_keys
        elif match_keys:
            match = lambda k: k[1] in match_keys
        else:
            match = None
        # Call tree matcher function (items or walk)
        return tree_match_func(match, itemgetter(1))
    
    def _rc_by_source(self, source):
        """
        Get a return code by its source (worker, key).
        """
        return self._d_source_rc[source]
   
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
        if self._msgtree is not None:
            self._msgtree.remove(lambda k: k[0] == worker)

    def _flush_errors_by_worker(self, worker):
        """
        Remove any error messages from specified worker.
        """
        if self._errtree is not None:
            self._errtree.remove(lambda k: k[0] == worker)

    def key_buffer(self, key):
        """
        Get buffer for a specific key. When the key is associated
        to multiple workers, the resulting buffer will contain
        all workers content that may overlap. This method returns an
        empty buffer if key is not found in any workers.
        """
        msgtree = self._msgtree
        if msgtree is None:
            raise TaskMsgTreeError("stdout_msgtree not set")
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
        errtree = self._errtree
        if errtree is None:
            raise TaskMsgTreeError("stderr_msgtree not set")
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
        Get max return code encountered during last run.

        How retcodes work
        =================
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

        >>> for buffer, nodelist in task.iter_buffers():
        ...     print NodeSet.fromlist(nodelist)
        ...     print buffer
        """
        msgtree = self._msgtree
        if msgtree is None:
            raise TaskMsgTreeError("stdout_msgtree not set")
        return self._call_tree_matcher(msgtree.walk, match_keys)

    def iter_errors(self, match_keys=None):
        """
        Iterate over error buffers, returns a tuple (buffer, keys).

        See iter_buffers().
        """
        errtree = self._errtree
        if errtree is None:
            raise TaskMsgTreeError("stderr_msgtree not set")
        return self._call_tree_matcher(errtree.walk, match_keys)
        
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
        if self._msgtree is not None:
            self._msgtree.clear()

    def flush_errors(self):
        """
        Flush all task error messages (from all task workers).
        """
        if self._errtree is not None:
            self._errtree.clear()

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

    def pchannel(self, gateway, metaworker): #gw_invoke_cmd):
        """Get propagation channel for gateway (create one if needed)"""
        # create channel if needed
        if gateway not in self.pwrks:
            chan = PropagationChannel(self)
            # invoke gateway
            timeout = 0
            worker = self.shell(metaworker.invoke_gateway, nodes=gateway,
                                handler=chan, timeout=timeout, tree=False)
            self.pwrks[gateway] = worker
        else:
            worker = self.pwrks[gateway]
            chan = worker.eh
        
        if metaworker not in self.pmwkrs:
            mw = self.pmwkrs[metaworker] = set()
        else:
            mw = self.pmwkrs[metaworker]
        if worker not in mw:
            #print >>sys.stderr, "pchannel++"
            worker.metarefcnt += 1
            mw.add(worker)
        return chan

    def _pchannel_release(self, metaworker):
        """Release propagation channel"""
        if metaworker in self.pmwkrs:
            for worker in self.pmwkrs[metaworker]:
                #print >>sys.stderr, "pchannel_release2 %s" % worker
                worker.metarefcnt -= 1
                if worker.metarefcnt == 0:
                    #print >>sys.stderr, "worker abort"
                    worker.eh._close()
                    #worker.abort()
            

def task_self():
    """
    Return the current Task object, corresponding to the caller's thread of
    control (a Task object is always bound to a specific thread). This function
    provided as a convenience is available in the top-level ClusterShell.Task
    package namespace.
    """
    return Task(thread=threading.currentThread())

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
    task_self() will create a new Task object. This function provided as a
    convenience is available in the top-level ClusterShell.Task package
    namespace.
    """
    task_self().abort(kill=True)

def task_cleanup():
    """
    Cleanup routine to destroy all created tasks. This function provided as a
    convenience is available in the top-level ClusterShell.Task package
    namespace. This is mainly used for testing purposes and should be avoided
    otherwise. task_cleanup() may be called from any threads.
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
