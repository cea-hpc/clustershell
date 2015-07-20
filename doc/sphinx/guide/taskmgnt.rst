Task management
===============

.. highlight:: python

.. _class-Task:

Structure of Task
-----------------

A ClusterShell *Task* and its underlying *Engine* class are the fundamental
infrastructure associated with a thread. An *Engine* implements an event
processing loop that you use to schedule work and coordinate the receipt of
incoming events. The purpose of this run loop is to keep your thread busy when
there is work to do and put your thread to sleep when there is none. When
calling the :meth:`.Task.resume()` or :meth:`.Task.run()` methods, your thread
enters the Task Engine run loop and calls installed event handlers in response
to incoming events.

Using Task objects
------------------

A *Task* object provides the main interface for adding shell commands, files
to copy or timer and then running it. Every thread has a single *Task* object
(and underlying *Engine* object) associated with it. The *Task* object is an
instance of the :class:`.Task` class.


Getting a Task object
^^^^^^^^^^^^^^^^^^^^^

To get the *Task* object bound to the **current thread**, you use one of the following:

* Use the :func:`.Task.task_self()` function available at the root of the Task
  module
* or use ``task = Task()``; Task objects are only instantiated when needed.

Example of getting the current task object::

    >>> from ClusterShell.Task import task_self
    >>> task = task_self()

So for a single-threaded application, a Task is a simple singleton (which
instance is also available through :func:`.Task.task_self()`).

To get the *Task* object associated to a specific thread identified by the
identifier *tid*, you use the following::

    >>> from ClusterShell.Task import Task
    >>> task = Task(thread_id=tid)


.. _class-Task-configure:

Configuring the Task object
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Each *Task* provides an info dictionary that shares both internal
*Task*-specific parameters and user-defined (key, value) parameters. Use the
following :class:`.Task` class methods to get or set parameters:

* :meth:`.Task.info`
* :meth:`.Task.set_info`


For example, to configure the task debugging behavior::

    >>> task.set_info('debug', True)
    >>> task.info('debug')
    True

You can also use the *Task* info dictionary to set your own *Task*-specific
key, value pairs. You may use any free keys but only keys starting with
*USER_* are guaranteed not to be used by ClusterShell in the future.

Task info keys and their default values:

+-----------------+----------------+------------------------------------+
| Info key string | Default value  | Comment                            |
+=================+================+====================================+
| debug           | False          | Enable debugging support (boolean) |
+-----------------+----------------+------------------------------------+
| print_debug     | internal using | Default is to print debug lines to |
|                 | *print*        | stdout using *print*. To override  |
|                 |                | this behavior, set a function that |
|                 |                | takes two arguments (the task      |
|                 |                | object and a string) as the value. |
+-----------------+----------------+------------------------------------+
| fanout          | 64             | Ssh *fanout* window (integer)      |
+-----------------+----------------+------------------------------------+
| connect_timeout | 10             | Value passed to ssh or pdsh        |
|                 |                | (integer)                          |
+-----------------+----------------+------------------------------------+
| command_timeout | 0 (no timeout) | Value passed to ssh or pdsh        |
|                 |                | (integer)                          |
+-----------------+----------------+------------------------------------+

Below is an example of `print_debug` override. As you can see, we set the
function `print_csdebug(task, s)` as the value. When debugging is enabled,
this function will be called for any debug text line. For example, this
function searchs for any known patterns and print a modified debug line to
stdout when found::

    def print_csdebug(task, s):
       m = re.search("(\w+): SHINE:\d:(\w+):", s)
       if m:
           print "%s<pickle>" % m.group(0)
       else:
           print s

    # Install the new debug printing function
    task_self().set_info("print_debug", print_csdebug)


.. _taskshell:

Submitting a shell command
^^^^^^^^^^^^^^^^^^^^^^^^^^

You can submit a set of commands for local or distant execution in parallel
with :meth:`.Task.shell`.

Local usage::

    task.shell(command [, key=key] [, handler=handler] [, timeout=secs])

Distant usage::

    task.shell(command, nodes=nodeset [, handler=handler] [, timeout=secs])

This method makes use of the default local or distant worker. ClusterShell
uses a default Worker based on the Python Popen2 standard module to execute
local commands, and a Worker based on *ssh* (Secure SHell) for distant
commands.

If the Task is not running, the command is scheduled for later execution. If
the Task is currently running, the command is executed as soon as possible
(depending on the current *fanout*).

To set a per-worker (eg. per-command) timeout value, just use the timeout
parameter (in seconds), for example::

    task.shell("uname -r", nodes=remote_nodes, handler=ehandler, timeout=5)

This is the prefered way to specify a command timeout.
:meth:`.EventHandler.ev_timeout` event is generated before the worker has finished to
indicate that some nodes have timed out. You may then retrieve the nodes with
:meth:`.DistantWorker.iter_keys_timeout()`.

Submitting a file copy action
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Local file copy to distant nodes is supported. You can submit a copy action
with :meth:`.Task.copy`::

    task.copy(source, dest, nodes=nodeset [, handler=handler] [, timeout=secs])

This method makes use of the default distant copy worker which is based on scp
(Secure CoPy) which comes with OpenSSH.

If the Task is not running, the copy is scheduled for later execution. If the
Task is currently running, the copy is started as soon as possible (depending
on the current *fanout*).

Starting the Task
^^^^^^^^^^^^^^^^^

Before you run a Task, you must add at least one worker (shell command, file
copy) or timer to it. If a Task does not have any worker to execute and
monitor, it exits immediately when you try to run it with::

    task.resume()

At this time, all previously submitted commands will start in the associated
Task thread. From a library user point of view, the task thread is blocked
until the end of the command executions.

Please note that the special method :meth:`.Task.run` does a
:meth:`.Task.shell` and a :meth:`.Task.resume` in once.

To set a Task execution timeout, use the optional *timeout* parameter to set
the timeout value in seconds. Once this time is elapsed when the Task is still
running, the running Task raises ``TimeoutError`` exception, cleaning by the
way all scheduled workers and timers. Using such a timeout ensures that the
Task will not exceed a given time for all its scheduled works. You can also
configure per-worker timeout that generates an event
:meth:`.EventHandler.ev_timeout` but will not raise an exception, allowing the
Task to continue. Indeed, using a per-worker timeout is the prefered way for
most applications.


Getting Task results
^^^^^^^^^^^^^^^^^^^^

After the task is finished (after :meth:`.Task.resume` or :meth:`.Task.run`)
or after a worker is completed when you have previously defined an event
handler (at :meth:`.EventHandler.ev_close`), you can use Task result getters:

* :meth:`.Task.iter_buffers`
* :meth:`.Task.iter_errors`
* :meth:`.Task.node_buffer`
* :meth:`.Task.node_error`
* :meth:`.Task.max_retcode`
* :meth:`.Task.num_timeout`
* :meth:`.Task.iter_keys_timeout`

Note: *buffer* refers to standard output, *error* to standard error.

Please see some examples in :ref:`prog-examples`.


Exiting the Task
^^^^^^^^^^^^^^^^

If a Task does not have anymore scheduled worker or timer (for example, if you
run one shell command and then it closes), it exits automatically from
:meth:`.Task.resume`. Still, except from a signal handler, you can always call
the following method to abort the Task execution:

* :meth:`.Task.abort`

For example, it is safe to call this method from an event handler within the
task itself. On abort, all scheduled workers (shell command, file copy) and
timers are cleaned and :meth:`.Task.resume` returns, unblocking the Task
thread from a library user point of view. Please note that commands being
executed remotely are not necessary stopped (this is due to *ssh(1)*
behavior).


Configuring a Timer
^^^^^^^^^^^^^^^^^^^

A timer is bound to a Task (and its underlying Engine) and fires at a preset
time in the future. Timers can fire either only once or repeatedly at fixed
time intervals. Repeating timers can also have their next firing time manually
adjusted (see :meth:`.Task.timer`).

A timer is not a real-time mechanism; it fires when the Task's underlying
Engine to which the timer has been added is running and able to check if the
timer firing time has passed.

When a timer fires, the method :meth:`.EventHandler.ev_timer` of the
associated EventHandler is called.

To configure a timer, use the following (secs in seconds with floating point
precision)::

    task.timer(self, fire=secs, handler=handler [, interval=secs])


.. _task-default-worker:

Changing default worker
^^^^^^^^^^^^^^^^^^^^^^^

When calling :meth:`.Task.shell` or :meth:`.Task.copy` the Task object creates
a worker instance for each call. When the *nodes* argument is defined, the
worker class used for these calls is based on Task default *distant_worker*.
Change this value to use another worker class, by example **Rsh**::

    from ClusterShell.Task import task_self
    from ClusterShell.Worker.Rsh import WorkerRsh

    task_self().set_default('distant_worker', WorkerRsh)


Thread safety and Task objects
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^


ClusterShell is an event-based library and one of its advantage is to avoid
the use of threads (and their safety issues), so it's mainly not thread-safe.
When possible, avoid the use of threads with ClusterShell. However, it's
sometimes not so easy, first because another library you want to use in some
event handler is not event-based and may block the current thread (that's
enough to break the deal). Also, in some cases, it could be useful for you to
run several Tasks at the same time. Since version 1.1, ClusterShell provides
support for launching a Task in another thread and some experimental support
for multiple Tasks, but:

* you should ensure that a Task is configured and accessed from one thread at
  a time before it's running (there is no API lock/mutex protection),
* once the Task is running, you should modify it only from the same thread
  that owns that Task (for example, you cannot call :meth:`.Task.abort` from
  another thread).

The library provides two thread-safe methods and a function for basic Task
interactions: :meth:`.Task.wait`, :meth:`.Task.join` and
:func:`.Task.task_wait` (function defined at the root of the Task module).
Please refer to the API documentation.

Configuring explicit Shell Worker objects
-----------------------------------------

We have seen in :ref:`taskshell` how to easily submit shell commands to the
Task. The :meth:`.Task.shell` method returns an already scheduled Worker
object. It is possible to instantiate the Worker object explicitly, for
example::

    from ClusterShell.Worker.Ssh import WorkerSsh

    worker = WorkerSsh('node3', command="/bin/echo alright")

To be used in a Task, add the worker to it with::

    task.schedule(worker)

If you have pdsh installed, you can use it by easily switching to the Pdsh
worker, which should behave the same manner as the Ssh worker::

    from ClusterShell.Worker.Pdsh import WorkerPdsh

    worker = WorkerPdsh('node3', command="/bin/echo alright")
