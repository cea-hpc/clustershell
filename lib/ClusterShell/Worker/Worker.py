# Worker.py -- Base class for task worker
# Copyright (C) 2007, 2008, 2009 CEA
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
Worker

ClusterShell worker interface.

A worker is a generic object which provides "grouped" work in a specific task.
"""

from EngineClient import EngineClient, EngineClientEOF

from ClusterShell.Event import EventHandler
from ClusterShell.NodeSet import NodeSet


class WorkerException(Exception):
    """Generic worker exception."""

class WorkerError(WorkerException):
    """Generic worker error."""

class Worker(object):
    """
    Base class Worker.
    """

    def __init__(self, handler):
        """
        Initializer. Should be called from derived classes.
        """
        self.eh = handler                   # associated EventHandler
        self.task = None

    def _set_task(self, task):
        """
        Bind worker to task. Called by task.schedule()
        """
        if self.task is not None:
            # one-shot-only schedule supported for now
            raise WorkerError()

        self.task = task

    def _engine_clients(self):
        """
        Return a list of underlying engine clients.
        """
        raise NotImplementedError("Derived classes must implement.")

    def _start(self):
        """
        Starts worker and returns worker instance as a convenience.
        Derived classes must implement.
        """
        raise NotImplementedError("Derived classes must implement.")

    def _invoke(self, ev_type):
        """
        Invoke user EventHandler method if needed.
        """
        if self.eh:
            self.eh._invoke(ev_type, self)

    def last_read(self):
        """
        Get last read message from event handler.
        """
        raise NotImplementedError("Derived classes must implement.")

    def abort(self):
        """
        Stop this worker.
        """
        raise NotImplementedError("Derived classes must implement.")

    def did_timeout(self):
        """
        Return True if this worker aborted due to timeout.
        """
        return self.task._num_timeout_by_worker(self) > 0


class DistantWorker(Worker):
    """
    Base class DistantWorker, which provides a useful set of setters/getters
    to use with distant workers like ssh or pdsh.
    """

    def __init__(self, handler):
        Worker.__init__(self, handler)

        self._last_node = None
        self._last_msg = None
        self._last_rc = 0
        self.started = False

    def _on_start(self):
        """
        Starting
        """
        if not self.started:
            self.started = True
            self._invoke("ev_start")

    def _on_node_msgline(self, node, msg):
        """
        Message received from node, update last* stuffs.
        """
        self._last_node = node
        self._last_msg = msg

        self.task._msg_add((self, node), msg)

        self._invoke("ev_read")

    def _on_node_rc(self, node, rc):
        """
        Return code received from a node, update last* stuffs.
        """
        self._last_node = node
        self._last_rc = rc

        self.task._rc_set((self, node), rc)

        self._invoke("ev_hup")

    def _on_node_timeout(self, node):
        """
        Update on node timeout.
        """
        # Update _last_node to allow node resolution after ev_timeout.
        self._last_node = node

        self.task._timeout_add((self, node))

    def last_node(self):
        """
        Get last node, useful to get the node in an EventHandler
        callback like ev_timeout().
        """
        return self._last_node

    def last_read(self):
        """
        Get last (node, buffer), useful in an EventHandler.ev_read()
        """
        return self._last_node, self._last_msg

    def last_retcode(self):
        """
        Get last (node, rc), useful in an EventHandler.ev_hup()
        """
        return self._last_node, self._last_rc

    def node_buffer(self, node):
        """
        Get specific node buffer.
        """
        return self.task._msg_by_source((self, node))
        
    def node_rc(self, node):
        """
        Get specific node return code.
        """
        return self.task._rc_by_source((self, node))

    def iter_buffers(self, match_keys=None):
        """
        Returns an iterator over available buffers and associated
        NodeSet. If the optional parameter match_keys is defined, only
        keys found in match_keys are returned.
        """
        for msg, keys in self.task._msg_iter_by_worker(self, match_keys):
            yield msg, NodeSet.fromlist(keys)

    def iter_node_buffers(self):
        """
        Returns an iterator over each node and associated buffer.
        """
        return self.task._kmsg_iter_by_worker(self)

    def iter_retcodes(self, match_keys=None):
        """
        Returns an iterator over return codes and associated NodeSet.
        If the optional parameter match_keys is defined, only keys
        found in match_keys are returned.
        """
        for rc, keys in self.task._rc_iter_by_worker(self, match_keys):
            yield rc, NodeSet.fromlist(keys)

    def iter_node_retcodes(self):
        """
        Returns an iterator over each node and associated return code.
        """
        return self.task._krc_iter_by_worker(self)

    def num_timeout(self):
        """
        Return the number of timed out "keys" (ie. nodes) for this worker.
        """
        return self.task._num_timeout_by_worker(self)

    def iter_keys_timeout(self):
        """
        Iterate over timed out keys (ie. nodes) for a specific worker.
        """
        return self.task._iter_keys_timeout_by_worker(self)


class WorkerSimple(EngineClient,Worker):
    """
    Implements a simple Worker being itself an EngineClient.
    """

    def __init__(self, file_reader, file_writer, file_error, key, handler, timeout, autoclose=False):
        """
        Initialize worker.
        """
        Worker.__init__(self, handler)
        EngineClient.__init__(self, self, timeout, autoclose)

        self.last_msg = None
        self.key = key or self
        self.file_reader = file_reader
        self.file_writer = file_writer
        self.file_error = file_error

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
        Start worker.
        """
        self._invoke("ev_start")

        return self

    def reader_fileno(self):
        """
        Returns the reader file descriptor as an integer.
        """
        if self.file_reader:
            return self.file_reader.fileno()

        return None
    
    def writer_fileno(self):
        """
        Returns the writer file descriptor as an integer.
        """
        if self.file_writer:
            return self.file_writer.fileno()
        
        return None
    
    def _read(self, size=4096):
        """
        Read data from process.
        """
        #result = self.file_reader.read(size)
        result = self.file_reader.read(size)
        if not len(result):
            raise EngineClientEOF()
        self._set_reading()
        return result

    def _close(self, force, timeout):
        """
        Close worker. Called by engine after worker has been
        unregistered. This method should handle all termination types
        (normal, forced or on timeout).
        """
        if self.file_reader != None:
            self.file_reader.close()
        if self.file_writer != None:
            self.file_writer.close()
        if self.file_error != None:
            self.file_error.close()

        if timeout:
            self._on_timeout()

        self._invoke("ev_close")

    def _handle_read(self):
        """
        Engine is telling us a read is available.
        """
        debug = self.task.info("debug", False)
        if debug:
            print_debug = self.task.info("print_debug")

        for msg in self._readlines():
            if debug:
                print_debug(self.task, "LINE %s" % msg)
            self._on_msgline(msg)

    def last_read(self):
        """
        Read last msg, useful in an EventHandler.
        """
        return self.last_msg

    def _on_msgline(self, msg):
        """
        Add a message.
        """
        # add last msg to local buffer
        self.last_msg = msg

        # update task
        self.task._msg_add((self, self.key), msg)

        self._invoke("ev_read")

    def _on_timeout(self):
        """
        Update on timeout.
        """
        self.task._timeout_add((self, self.key))

        # trigger timeout event
        self._invoke("ev_timeout")

    def read(self):
        """
        Read worker buffer.
        """
        for key, msg in self.task._kmsg_iter_by_worker(self):
            assert key == self.key
            return msg

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

