#
# Copyright CEA/DAM/DIF (2007, 2008, 2009, 2010, 2011)
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
ClusterShell worker interface.

A worker is a generic object which provides "grouped" work in a specific task.
"""

from ClusterShell.Worker.EngineClient import EngineClient
from ClusterShell.NodeSet import NodeSet

import os


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
    targets (abstract notion) in parallel. Concret targets and also the notion
    of local or distant targets are managed by Worker's subclasses (for
    example, see the DistantWorker base class).

    A configured Worker object is associated to a specific ClusterShell Task,
    which can be seen as a single-threaded Worker supervisor. Indeed, the work
    to be done is executed in parallel depending on other Workers and Task's
    current paramaters, like current fanout value.

    ClusterShell is designed to write event-driven applications, and the Worker
    class is key here as Worker objects are passed as parameter of most event
    handlers (see the ClusterShell.Event.EventHandler class).

    The following public object variables are defined on some events, so you
    may find them useful in event handlers:
        - worker.current_node [ev_read,ev_error,ev_hup]
            node/key concerned by event
        - worker.current_msg [ev_read]
            message just read (from stdout)
        - worker.current_errmsg [ev_error]
            error message just read (from stderr)
        - worker.current_rc [ev_hup]
            return code just received

    Example of use:
        >>> from ClusterShell.Event import EventHandler
        >>> class MyOutputHandler(EventHandler):
        ...     def ev_read(self, worker):
        ...             node = worker.current_node       
        ...             line = worker.current_msg
        ...             print "%s: %s" % (node, line)
        ... 
    """
    def __init__(self, handler):
        """
        Initializer. Should be called from derived classes.
        """
        # Associated EventHandler object
        self.eh = handler
        # Parent task (once bound)
        self.task = None
        self.started = False
        self.metaworker = None
        self.metarefcnt = 0
        # current_x public variables (updated at each event accordingly)
        self.current_node = None
        self.current_msg = None
        self.current_errmsg = None
        self.current_rc = 0

    def _set_task(self, task):
        """
        Bind worker to task. Called by task.schedule()
        """
        if self.task is not None:
            # one-shot-only schedule supported for now
            raise WorkerError("worker has already been scheduled")
        self.task = task

    def _task_bound_check(self):
        if not self.task:
            raise WorkerError("worker is not task bound")

    def _engine_clients(self):
        """
        Return a list of underlying engine clients.
        """
        raise NotImplementedError("Derived classes must implement.")

    def _on_start(self):
        """
        Starting worker.
        """
        if not self.started:
            self.started = True
            if self.eh:
                self.eh.ev_start(self)

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
        """
        Return whether this worker has aborted due to timeout.
        """
        self._task_bound_check()
        return self.task._num_timeout_by_worker(self) > 0

    # Base actions

    def abort(self):
        """
        Abort processing any action by this worker.
        """
        raise NotImplementedError("Derived classes must implement.")

    def flush_buffers(self):
        """
        Flush any messages associated to this worker.
        """
        self._task_bound_check()
        self.task._flush_buffers_by_worker(self)

    def flush_errors(self):
        """
        Flush any error messages associated to this worker.
        """
        self._task_bound_check()
        self.task._flush_errors_by_worker(self)

class DistantWorker(Worker):
    """
    Base class DistantWorker, which provides a useful set of setters/getters
    to use with distant workers like ssh or pdsh.
    """

    def _on_node_msgline(self, node, msg):
        """
        Message received from node, update last* stuffs.
        """
        # Maxoptimize this method as it might be called very often.
        task = self.task
        handler = self.eh

        self.current_node = node
        self.current_msg = msg

        if task._msgtree is not None:   # don't waste time
            task._msg_add((self, node), msg)

        if handler is not None:
            handler.ev_read(self)

    def _on_node_errline(self, node, msg):
        """
        Error message received from node, update last* stuffs.
        """
        task = self.task
        handler = self.eh

        self.current_node = node
        self.current_errmsg = msg

        if task._errtree is not None:
            task._errmsg_add((self, node), msg)

        if handler is not None:
            handler.ev_error(self)

    def _on_node_rc(self, node, rc):
        """
        Return code received from a node, update last* stuffs.
        """
        self.current_node = node
        self.current_rc = rc

        self.task._rc_set((self, node), rc)

        if self.eh:
            self.eh.ev_hup(self)

    def _on_node_timeout(self, node):
        """
        Update on node timeout.
        """
        # Update current_node to allow node resolution after ev_timeout.
        self.current_node = node

        self.task._timeout_add((self, node))

    def last_node(self):
        """
        Get last node, useful to get the node in an EventHandler
        callback like ev_read().
        [DEPRECATED] use current_node
        """
        return self.current_node

    def last_read(self):
        """
        Get last (node, buffer), useful in an EventHandler.ev_read()
        [DEPRECATED] use (current_node, current_msg)
        """
        return self.current_node, self.current_msg

    def last_error(self):
        """
        Get last (node, error_buffer), useful in an EventHandler.ev_error()
        [DEPRECATED] use (current_node, current_errmsg)
        """
        return self.current_node, self.current_errmsg

    def last_retcode(self):
        """
        Get last (node, rc), useful in an EventHandler.ev_hup()
        [DEPRECATED] use (current_node, current_rc)
        """
        return self.current_node, self.current_rc

    def node_buffer(self, node):
        """
        Get specific node buffer.
        """
        self._task_bound_check()
        return self.task._msg_by_source((self, node))
        
    def node_error(self, node):
        """
        Get specific node error buffer.
        """
        self._task_bound_check()
        return self.task._errmsg_by_source((self, node))

    node_error_buffer = node_error

    def node_retcode(self, node):
        """
        Get specific node return code. Raises a KeyError if command on
        node has not yet finished (no return code available), or is
        node is not known by this worker.
        """
        self._task_bound_check()
        try:
            rc = self.task._rc_by_source((self, node))
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
        for msg, keys in self.task._call_tree_matcher( \
                            self.task._msgtree.walk, match_keys, self):
            yield msg, NodeSet.fromlist(keys)

    def iter_errors(self, match_keys=None):
        """
        Returns an iterator over available error buffers and associated
        NodeSet. If the optional parameter match_keys is defined, only
        keys found in match_keys are returned.
        """
        self._task_bound_check()
        for msg, keys in self.task._call_tree_matcher( \
                            self.task._errtree.walk, match_keys, self):
            yield msg, NodeSet.fromlist(keys)

    def iter_node_buffers(self, match_keys=None):
        """
        Returns an iterator over each node and associated buffer.
        """
        self._task_bound_check()
        return self.task._call_tree_matcher(self.task._msgtree.items,
                                            match_keys, self)

    def iter_node_errors(self, match_keys=None):
        """
        Returns an iterator over each node and associated error buffer.
        """
        self._task_bound_check()
        return self.task._call_tree_matcher(self.task._errtree.items,
                                            match_keys, self)

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

class WorkerSimple(EngineClient, Worker):
    """
    Implements a simple Worker being itself an EngineClient.
    """

    def __init__(self, file_reader, file_writer, file_error, key, handler,
            stderr=False, timeout=-1, autoclose=False):
        """
        Initialize worker.
        """
        Worker.__init__(self, handler)
        EngineClient.__init__(self, self, stderr, timeout, autoclose)

        if key is None: # allow key=0
            self.key = self
        else:
            self.key = key
        if file_reader:
            self.fd_reader = file_reader.fileno()
        if file_error:
            self.fd_error = file_error.fileno()
        if file_writer:
            self.fd_writer = file_writer.fileno()

    def _engine_clients(self):
        """
        Return a list of underlying engine clients.
        """
        return [self]

    def set_key(self, key):
        """
        Source key for this worker is free for use. Use this method to
        set the custom source key for this worker.
        """
        self.key = key

    def _start(self):
        """
        Called on EngineClient start.
        """
        # call Worker._on_start()
        self._on_start()
        return self

    def _read(self, size=65536):
        """
        Read data from process.
        """
        return EngineClient._read(self, size)

    def _readerr(self, size=65536):
        """
        Read error data from process.
        """
        return EngineClient._readerr(self, size)

    def _close(self, abort, flush, timeout):
        """
        Close client. See EngineClient._close().
        """
        if flush and self._rbuf:
            # We still have some read data available in buffer, but no
            # EOL. Generate a final message before closing.
            self.worker._on_msgline(self._rbuf)

        if self.fd_reader:
            os.close(self.fd_reader)
        if self.fd_error:
            os.close(self.fd_error)
        if self.fd_writer:
            os.close(self.fd_writer)

        if timeout:
            assert abort, "abort flag not set on timeout"
            self._on_timeout()

        if self.eh:
            self.eh.ev_close(self)

    def _handle_read(self):
        """
        Engine is telling us there is data available for reading.
        """
        # Local variables optimization
        task = self.worker.task
        msgline = self._on_msgline

        debug = task.info("debug", False)
        if debug:
            print_debug = task.info("print_debug")
            for msg in self._readlines():
                print_debug(task, "LINE %s" % msg)
                msgline(msg)
        else:
            for msg in self._readlines():
                msgline(msg)

    def _handle_error(self):
        """
        Engine is telling us there is error available for reading.
        """
        task = self.worker.task
        errmsgline = self._on_errmsgline

        debug = task.info("debug", False)
        if debug:
            print_debug = task.info("print_debug")
            for msg in self._readerrlines():
                print_debug(task, "LINE@STDERR %s" % msg)
                errmsgline(msg)
        else:
            for msg in self._readerrlines():
                errmsgline(msg)

    def last_read(self):
        """
        Read last msg, useful in an EventHandler.
        """
        return self.current_msg

    def last_error(self):
        """
        Get last error message from event handler.
        """
        return self.current_errmsg

    def _on_msgline(self, msg):
        """
        Add a message.
        """
        # add last msg to local buffer
        self.current_msg = msg

        # update task
        self.task._msg_add((self, self.key), msg)

        if self.eh:
            self.eh.ev_read(self)

    def _on_errmsgline(self, msg):
        """
        Add a message.
        """
        # add last msg to local buffer
        self.current_errmsg = msg

        # update task
        self.task._errmsg_add((self, self.key), msg)

        if self.eh:
            self.eh.ev_error(self)

    def _on_rc(self, rc):
        """
        Set return code received.
        """
        self.current_rc = rc

        self.task._rc_set((self, self.key), rc)

        if self.eh:
            self.eh.ev_hup(self)

    def _on_timeout(self):
        """
        Update on timeout.
        """
        self.task._timeout_add((self, self.key))

        # trigger timeout event
        if self.eh:
            self.eh.ev_timeout(self)

    def read(self):
        """
        Read worker buffer.
        """
        self._task_bound_check()
        for key, msg in self.task._call_tree_matcher(self.task._msgtree.items,
                                                     worker=self):
            assert key == self.key
            return str(msg)

    def error(self):
        """
        Read worker error buffer.
        """
        self._task_bound_check()
        for key, msg in self.task._call_tree_matcher(self.task._errtree.items,
                                                     worker=self):
            assert key == self.key
            return str(msg)

    def write(self, buf):
        """
        Write to worker.
        """
        self._write(buf)

    def set_write_eof(self):
        """
        Tell worker to close its writer file descriptor once flushed. Do not
        perform writes after this call.
        """
        self._set_write_eof()

