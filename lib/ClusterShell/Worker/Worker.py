#
# Copyright (C) 2007-2016 CEA/DAM
# Copyright (C) 2015-2017 Stephane Thiell <sthiell@stanford.edu>
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
ClusterShell worker interface.

A worker is a generic object which provides "grouped" work in a specific task.
"""

try:
    from inspect import getfullargspec  # py3
except ImportError:
    from inspect import getargspec as getfullargspec  # py2

import warnings

from ClusterShell.Worker.EngineClient import EngineClient
from ClusterShell.NodeSet import NodeSet
from ClusterShell.Engine.Engine import FANOUT_UNLIMITED, FANOUT_DEFAULT


def _eh_sigspec_invoke_compat(method, argc_legacy, *args):
    """
    Helper function to invoke an event handler method, with legacy
    signature compatibility if actual argc does match argc_legacy.
    This should be removed when old signatures (< 1.8) aren't supported
    anymore (in 2.x).
    """
    argc_actual = len(getfullargspec(method)[0])
    if argc_actual == argc_legacy:
        # Use legacy signature (1.x)
        return method(*args[0:argc_legacy - 1])
    else:
        # Assume new signature (2.x)
        return method(*args)

def _eh_sigspec_ev_read_17(ev_read):
    """Helper function to check whether ev_read has the old 1.7 signature."""
    return len(getfullargspec(ev_read)[0]) == 2


class WorkerException(Exception):
    """Generic worker exception."""

class WorkerError(WorkerException):
    """Generic worker error."""

# DEPRECATED: WorkerBadArgumentError exception is deprecated as of 1.4,
# use ValueError instead.
WorkerBadArgumentError = ValueError

class Worker(object):
    """
    Worker is an essential base class for the ClusterShell library. The goal
    of a worker object is to execute a common work on a single or several
    targets (abstract notion) in parallel. Concrete targets and also the
    notion of local or distant targets are managed by Worker's subclasses
    (for example, see the DistantWorker base class).

    A configured Worker object is associated to a specific ClusterShell Task,
    which can be seen as a single-threaded Worker supervisor. Indeed, the work
    to be done is executed in parallel depending on other Workers and Task's
    current parameters, like current fanout value.

    ClusterShell is designed to write event-driven applications, and the Worker
    class is key here as Worker objects are passed as parameter of most event
    handlers (see the ClusterShell.Event.EventHandler class).

    Example of use:

        >>> from ClusterShell.Event import EventHandler
        >>> class MyOutputHandler(EventHandler):
        ...     def ev_read(self, worker, node, sname, msg):
        ...             print "%s: %s" % (node, line)
        ...
    """

    # The following common stream names are recognized by the Task class.
    # They can be changed per Worker, thus avoiding any Task buffering.
    SNAME_STDIN  = 'stdin'   #: stream name usually used for stdin
    SNAME_STDOUT = 'stdout'  #: stream name usually used for stdout
    SNAME_STDERR = 'stderr'  #: stream name usually used for stderr

    def __init__(self, handler):
        """Initializer. Should be called from derived classes."""
        # Associated EventHandler object
        self.eh = handler           #: associated :class:`.EventHandler`

        # Per Worker fanout value (positive integer).
        # Default is FANOUT_DEFAULT to use the fanout set at the Task level.
        # Change to FANOUT_UNLIMITED to always schedule this worker.
        # NOTE: the fanout value must be set before the Worker starts and
        # cannot currently be changed afterwards.
        self._fanout = FANOUT_DEFAULT

        # Update task rc? [private]
        # TODO: to be replaced with Task Event Handlers
        self._update_task_rc = True

        # Parent task (once bound)
        self.task = None            #: worker's task when scheduled or None
        self.started = False        #: set to True when worker has started
        self.metaworker = None
        self.metarefcnt = 0

        # current_x public variables (updated at each event accordingly)
        self.current_node = None    #: set to node in event handler
        self.current_msg = None     #: set to stdout message in event handler
        self.current_errmsg = None  #: set to stderr message in event handler
        self.current_rc = 0         #: set to return code in event handler
        self.current_sname = None   #: set to stream name in event handler

    def _set_task(self, task):
        """Bind worker to task. Called by task.schedule()."""
        if self.task is not None:
            # one-shot-only schedule supported for now
            raise WorkerError("worker has already been scheduled")
        self.task = task

    def _task_bound_check(self):
        """Helper method to check that worker is bound to a task."""
        if not self.task:
            raise WorkerError("worker is not task bound")

    def _engine_clients(self):
        """Return a list of underlying engine clients."""
        raise NotImplementedError("Derived classes must implement.")

    # Event generators

    def _on_start(self, key):
        """Called on command start."""
        self.current_node = key

        if not self.started:
            self.started = True
            if self.eh is not None:
                self.eh.ev_start(self)

        if self.eh is not None:
            _eh_sigspec_invoke_compat(self.eh.ev_pickup, 2, self, key)

    def _on_close(self, key, rc=None):
        """Called to generate events when the Worker is closing."""
        if self._update_task_rc:
            # rc may be None here for example when called from StreamClient
            # Only update task if rc is not None.
            if rc is not None:
                self.task._rc_set(self, key, rc)

        self.current_node = key
        self.current_rc = rc

        if self.eh is not None:
            _eh_sigspec_invoke_compat(self.eh.ev_hup, 2, self, key, rc)

    def _on_written(self, key, bytes_count, sname):
        """Notification of bytes written."""
        # set node and stream name (compat only)
        self.current_node = key
        self.current_sname = sname

        if self.eh is not None:
            _eh_sigspec_invoke_compat(self.eh.ev_written, 5, self, key, sname,
                                      bytes_count)

    # Base getters

    def last_read(self):
        """
        Get last read message from event handler.
        [DEPRECATED] use current_msg
        """
        raise NotImplementedError("Derived classes must implement.")

    def last_error(self):
        """
        Get last error message from event handler.
        [DEPRECATED] use current_errmsg
        """
        raise NotImplementedError("Derived classes must implement.")

    def did_timeout(self):
        """Return whether this worker has aborted due to timeout."""
        self._task_bound_check()
        return self.task._num_timeout_by_worker(self) > 0

    def read(self, node=None, sname='stdout'):
        """Read worker stream buffer.

        Return stream read buffer of current worker.

        Arguments:
            node -- node name; can also be set to None for simple worker
                    having worker.key defined (default is None)
            sname -- stream name (default is 'stdout')
        """
        self._task_bound_check()
        return self.task._msg_by_source(self, node, sname)

    # Base actions

    def abort(self):
        """Abort processing any action by this worker.

        Safe to call on an already closing or aborting worker.
        """
        raise NotImplementedError("Derived classes must implement.")

    def flush_buffers(self):
        """Flush any messages associated to this worker."""
        self._task_bound_check()
        self.task._flush_buffers_by_worker(self)

    def flush_errors(self):
        """Flush any error messages associated to this worker."""
        self._task_bound_check()
        self.task._flush_errors_by_worker(self)


class DistantWorker(Worker):
    """Base class DistantWorker.

    DistantWorker provides a useful set of setters/getters to use with
    distant workers like ssh or pdsh.
    """

    # Event generators

    def _on_node_msgline(self, node, msg, sname):
        """Message received from node, update last* stuffs."""
        # Maxoptimize this method as it might be called very often.
        task = self.task
        assert not isinstance(node, NodeSet) # for testing
        # update task msgtree
        task._msg_add(self, node, sname, msg)

        ### LEGACY (1.x) ###
        # set stream name
        self.current_sname = sname

        # generate event
        self.current_node = node
        if sname == self.SNAME_STDERR:
            self.current_errmsg = msg
            if self.eh is not None:
                # call old ev_error for compat (default is no-op)
                if hasattr(self.eh, 'ev_error'):  # missing in 1.8.0!
                    self.eh.ev_error(self)
                # /!\ NOT elif
                if not _eh_sigspec_ev_read_17(self.eh.ev_read):
                    ### FUTURE (2.x) ###
                    self.eh.ev_read(self, node, sname, msg)
        else:
            self.current_msg = msg
            if self.eh is not None:
                # ev_read: check for old signature first (< 1.8)
                if _eh_sigspec_ev_read_17(self.eh.ev_read):
                    self.eh.ev_read(self)
                else:
                    ### FUTURE (2.x) ###
                    self.eh.ev_read(self, node, sname, msg)

    def _on_node_close(self, node, rc):
        """Command return code received."""
        Worker._on_close(self, node, rc)

    def _on_node_timeout(self, node):
        """Update on node timeout."""
        # Update current_node to allow node resolution after ev_timeout.
        self.current_node = node

        self.task._timeout_add(self, node)

    def last_node(self):
        """
        Get last node, useful to get the node in an EventHandler
        callback like ev_read().
        [DEPRECATED] use current_node
        """
        warnings.warn("use current_node instead", DeprecationWarning)
        return self.current_node

    def last_read(self):
        """
        Get last (node, buffer), useful in an EventHandler.ev_read()
        [DEPRECATED] use (current_node, current_msg)
        """
        warnings.warn("use current_node and current_msg instead",
                      DeprecationWarning)
        return self.current_node, self.current_msg

    def last_error(self):
        """
        Get last (node, error_buffer), useful in an EventHandler.ev_error()
        [DEPRECATED] use (current_node, current_errmsg)
        """
        warnings.warn("use current_node and current_errmsg instead",
                      DeprecationWarning)
        return self.current_node, self.current_errmsg

    def last_retcode(self):
        """
        Get last (node, rc), useful in an EventHandler.ev_hup()
        [DEPRECATED] use (current_node, current_rc)
        """
        warnings.warn("use current_node and current_rc instead",
                      DeprecationWarning)
        return self.current_node, self.current_rc

    def node_buffer(self, node):
        """Get specific node buffer."""
        return self.read(node, self.SNAME_STDOUT)

    def node_error(self, node):
        """Get specific node error buffer."""
        return self.read(node, self.SNAME_STDERR)

    node_error_buffer = node_error

    def node_retcode(self, node):
        """
        Get specific node return code.

        :raises KeyError: command on node has not yet finished (no return code
            available), or this node is not known by this worker
        """
        self._task_bound_check()
        try:
            rc = self.task._rc_by_source(self, node)
        except KeyError:
            raise KeyError(node)
        return rc

    node_rc = node_retcode

    def iter_buffers(self, match_keys=None):
        """
        Returns an iterator over available buffers and associated
        NodeSet. If the optional parameter match_keys is defined, only
        keys found in match_keys are returned.
        """
        self._task_bound_check()
        for msg, keys in self.task._call_tree_matcher(
                self.task._msgtree(self.SNAME_STDOUT).walk, match_keys, self):
            yield msg, NodeSet.fromlist(keys)

    def iter_errors(self, match_keys=None):
        """
        Returns an iterator over available error buffers and associated
        NodeSet. If the optional parameter match_keys is defined, only
        keys found in match_keys are returned.
        """
        self._task_bound_check()
        for msg, keys in self.task._call_tree_matcher(
                self.task._msgtree(self.SNAME_STDERR).walk, match_keys, self):
            yield msg, NodeSet.fromlist(keys)

    def iter_node_buffers(self, match_keys=None):
        """
        Returns an iterator over each node and associated buffer.
        """
        self._task_bound_check()
        return self.task._call_tree_matcher(
            self.task._msgtree(self.SNAME_STDOUT).items, match_keys, self)

    def iter_node_errors(self, match_keys=None):
        """
        Returns an iterator over each node and associated error buffer.
        """
        self._task_bound_check()
        return self.task._call_tree_matcher(
            self.task._msgtree(self.SNAME_STDERR).items, match_keys, self)

    def iter_retcodes(self, match_keys=None):
        """
        Returns an iterator over return codes and associated NodeSet.
        If the optional parameter match_keys is defined, only keys
        found in match_keys are returned.
        """
        self._task_bound_check()
        for rc, keys in self.task._rc_iter_by_worker(self, match_keys):
            yield rc, NodeSet.fromlist(keys)

    def iter_node_retcodes(self):
        """
        Returns an iterator over each node and associated return code.
        """
        self._task_bound_check()
        return self.task._krc_iter_by_worker(self)

    def num_timeout(self):
        """
        Return the number of timed out "keys" (ie. nodes) for this worker.
        """
        self._task_bound_check()
        return self.task._num_timeout_by_worker(self)

    def iter_keys_timeout(self):
        """
        Iterate over timed out keys (ie. nodes) for a specific worker.
        """
        self._task_bound_check()
        return self.task._iter_keys_timeout_by_worker(self)

class StreamClient(EngineClient):
    """StreamWorker's default EngineClient.

    StreamClient is the EngineClient subclass used by default by
    StreamWorker. It handles some generic methods to pass data to the
    StreamWorker.
    """

    def _start(self):
        """Called on EngineClient start."""
        assert not self.worker.started
        self.worker._on_start(self.key)
        return self

    def _read(self, sname, size=65536):
        """Read data from process."""
        return EngineClient._read(self, sname, size)

    def _close(self, abort, timeout):
        """Close client. See EngineClient._close()."""
        EngineClient._close(self, abort, timeout)
        if timeout:
            assert abort, "abort flag not set on timeout"
            self.worker._on_timeout(self.key)

        # return code not available
        self.worker._on_close(self.key)

        if self.worker.eh:
            _eh_sigspec_invoke_compat(self.worker.eh.ev_close, 2, self, timeout)

    def _handle_read(self, sname):
        """Engine is telling us there is data available for reading."""
        # Local variables optimization
        task = self.worker.task
        msgline = self.worker._on_msgline

        debug = task.info("debug", False)
        if debug:
            print_debug = task.info("print_debug")
            for msg in self._readlines(sname):
                print_debug(task, "LINE %s" % msg)
                msgline(self.key, msg, sname)
        else:
            for msg in self._readlines(sname):
                msgline(self.key, msg, sname)

    def _flush_read(self, sname):
        """Called at close time to flush stream read buffer."""
        stream = self.streams[sname]
        if stream.readable() and stream.rbuf:
            # We still have some read data available in buffer, but no
            # EOL. Generate a final message before closing.
            self.worker._on_msgline(self.key, stream.rbuf, sname)

    def write(self, buf, sname=None):
        """Write to writable stream(s)."""
        if sname is not None:
            self._write(sname, buf)
            return
        # sname not specified: "broadcast" to all writable streams...
        for writer in self.streams.writers():
            self._write(writer.name, buf)

    def set_write_eof(self, sname=None):
        """Set EOF flag to writable stream(s)."""
        if sname is not None:
            self._set_write_eof(sname)
            return
        # sname not specified: set eof flag on all writable streams...
        for writer in self.streams.writers():
            self._set_write_eof(writer.name)

class StreamWorker(Worker):
    """StreamWorker base class [v1.7+]

    The StreamWorker class implements a base (but concrete) Worker that
    can read and write to multiple streams. Unlike most other Workers,
    it does not execute any external commands by itself. Rather, it
    should be pre-bound to "streams", ie. file(s) or file descriptor(s),
    using the two following methods:
        >>> worker.set_reader('stream1', fd1)
        >>> worker.set_writer('stream2', fd2)

    Like other Workers, the StreamWorker instance should be associated
    with a Task using task.schedule(worker). When the task engine is
    ready to process the StreamWorker, all of its streams are being
    processed together. For that reason, it is not possible to add new
    readers or writers to a running StreamWorker (ie. task is running
    and worker is already scheduled).

    Configured readers will generate ev_read() events when data is
    available for reading, with the stream name passed as one of its
    argument.

    Configured writers will allow the use of the method write(), eg.
    worker.write(data, 'stream2'), to write to the stream.
    """

    def __init__(self, handler, key=None, stderr=False, timeout=-1,
                 autoclose=False, client_class=StreamClient):
        Worker.__init__(self, handler)
        if key is None: # allow key=0
            key = self
        self.clients = [client_class(self, key, stderr, timeout, autoclose)]

    def set_reader(self, sname, sfile, retain=True, closefd=True):
        """Add a readable stream to StreamWorker.

        Arguments:
            sname   -- the name of the stream (string)
            sfile   -- the stream file or file descriptor
            retain  -- whether the stream retains engine client
                       (default is True)
            closefd -- whether to close fd when the stream is closed
                       (default is True)
        """
        if not self.clients[0].registered:
            self.clients[0].streams.set_reader(sname, sfile, retain, closefd)
        else:
            raise WorkerError("cannot add new stream at runtime")

    def set_writer(self, sname, sfile, retain=True, closefd=True):
        """Set a writable stream to StreamWorker.

        Arguments:
            sname -- the name of the stream (string)
            sfile -- the stream file or file descriptor
            retain  -- whether the stream retains engine client
                       (default is True)
            closefd -- whether to close fd when the stream is closed
                       (default is True)
        """
        if not self.clients[0].registered:
            self.clients[0].streams.set_writer(sname, sfile, retain, closefd)
        else:
            raise WorkerError("cannot add new stream at runtime")

    def _engine_clients(self):
        """Return a list of underlying engine clients."""
        return self.clients

    def set_key(self, key):
        """Source key for this worker is free for use.

        Use this method to set the custom source key for this worker.
        """
        self.clients[0].key = key

    def _on_msgline(self, key, msg, sname):
        """Add a message."""
        # update task msgtree
        self.task._msg_add(self, key, sname, msg)

        ### LEGACY (1.x) ###
        # set stream name
        self.current_sname = sname

        # generate event
        if sname == 'stderr':
            self.current_errmsg = msg
            if self.eh is not None:
                # call old ev_error for compat (default is no-op)
                if hasattr(self.eh, 'ev_error'):  # missing in 1.8.0!
                    self.eh.ev_error(self)
                # /!\ NOT elif
                if not _eh_sigspec_ev_read_17(self.eh.ev_read):
                    ### FUTURE (2.x) ###
                    self.eh.ev_read(self, key, sname, msg)
        else:
            self.current_msg = msg
            if self.eh is not None:
                # ev_read: check for old signature first (< 1.8)
                if _eh_sigspec_ev_read_17(self.eh.ev_read):
                    self.eh.ev_read(self)
                else:
                    ### FUTURE (2.x) ###
                    self.eh.ev_read(self, key, sname, msg)

    def _on_timeout(self, key):
        """Update on timeout."""
        self.task._timeout_add(self, key)

        # trigger timeout event (deprecated in 1.8+)
        # also use hasattr check because ev_timeout was missing in 1.8.0
        if self.eh and hasattr(self.eh, 'ev_timeout'):
            self.eh.ev_timeout(self)

    def abort(self):
        """Abort processing any action by this worker.

        Safe to call on an already closing or aborting worker.
        """
        self.clients[0].abort()

    def read(self, node=None, sname='stdout'):
        """Read worker stream buffer.

        Return stream read buffer of current worker.

        Arguments:
            node -- node name; can also be set to None for simple worker
                    having worker.key defined (default is None)
            sname -- stream name (default is 'stdout')
        """
        return Worker.read(self, node or self.clients[0].key, sname)

    def write(self, buf, sname=None):
        """Write to worker.

        If sname is specified, write to the associated stream,
        otherwise write to all writable streams.
        """
        self.clients[0].write(buf, sname)

    def set_write_eof(self, sname=None):
        """
        Tell worker to close its writer file descriptor once flushed.

        Do not perform writes after this call. Like write(), sname can
        be optionally specified to target a specific writable stream,
        otherwise all writable streams are marked as EOF.
        """
        self.clients[0].set_write_eof(sname)

class WorkerSimple(StreamWorker):
    """WorkerSimple base class [DEPRECATED]

    Implements a simple Worker to manage common process
    stdin/stdout/stderr streams.

    [DEPRECATED] use StreamWorker.
    """

    def __init__(self, file_reader, file_writer, file_error, key, handler,
                 stderr=False, timeout=-1, autoclose=False, closefd=True,
                 client_class=StreamClient):
        """Initialize WorkerSimple worker."""
        StreamWorker.__init__(self, handler, key, stderr, timeout, autoclose,
                              client_class=client_class)
        if file_reader:
            self.set_reader('stdout', file_reader, closefd=closefd)
        if file_error:
            self.set_reader('stderr', file_error, closefd=closefd)
        if file_writer:
            self.set_writer('stdin', file_writer, closefd=closefd)
        # keep reference of provided file objects during worker lifetime
        self._filerefs = (file_reader, file_writer, file_error)

    def error_fileno(self):
        """Return the standard error reader file descriptor (integer)."""
        return self.clients[0].streams['stderr'].fd

    def reader_fileno(self):
        """Return the reader file descriptor (integer)."""
        return self.clients[0].streams['stdout'].fd

    def writer_fileno(self):
        """Return the writer file descriptor as an integer."""
        return self.clients[0].streams['stdin'].fd

    def last_read(self):
        """
        Get last read message.

        [DEPRECATED] use current_msg
        """
        warnings.warn("use current_msg instead", DeprecationWarning)
        return self.current_msg

    def last_error(self):
        """
        Get last error message.

        [DEPRECATED] use current_errmsg
        """
        warnings.warn("use current_errmsg instead", DeprecationWarning)
        return self.current_errmsg

    def error(self):
        """Read worker error buffer."""
        return self.read(sname='stderr')

    def _on_start(self, key):
        """Called on command start."""
        if not self.started:
            self.started = True
            if self.eh is not None:
                self.eh.ev_start(self)

        if self.eh is not None:
            # generate ev_pickup
            _eh_sigspec_invoke_compat(self.eh.ev_pickup, 2, self, key)

    def _on_close(self, key, rc=None):
        """Called to generate events when the Worker is closing."""
        self.current_rc = rc

        # rc may be None here for example when called from StreamClient
        # Only update task if rc is not None.
        if rc is not None:
            self.task._rc_set(self, key, rc)

        if self.eh is not None:
            # generate ev_hup
            _eh_sigspec_invoke_compat(self.eh.ev_hup, 2, self, key, rc)

    def _on_written(self, key, bytes_count, sname):
        """Notification of bytes written."""
        # set node and stream name (compat only)
        self.current_sname = sname

        if self.eh is not None:
            # generate ev_written
            _eh_sigspec_invoke_compat(self.eh.ev_written, 5, self, key, sname,
                                      bytes_count)
