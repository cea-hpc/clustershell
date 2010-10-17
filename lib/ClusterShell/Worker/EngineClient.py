#
# Copyright CEA/DAM/DIF (2009, 2010)
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
EngineClient

ClusterShell engine's client interface.

An engine client is similar to a process, you can start/stop it, read data from
it and write data to it.
"""

import fcntl
import os
import Queue
from subprocess import Popen, PIPE, STDOUT
import thread

from ClusterShell.Engine.Engine import EngineBaseTimer


class EngineClientException(Exception):
    """Generic EngineClient exception."""

class EngineClientEOF(EngineClientException):
    """EOF from client."""

class EngineClientError(EngineClientException):
    """Base EngineClient error exception."""

class EngineClientNotSupportedError(EngineClientError):
    """Operation not supported by EngineClient."""


class EngineClient(EngineBaseTimer):
    """
    Abstract class EngineClient.
    """

    def __init__(self, worker, stderr, timeout, autoclose):
        """
        Initializer. Should be called from derived classes.
        """
        EngineBaseTimer.__init__(self, timeout, -1, autoclose)

        # engine-friendly variables
        self._events = 0                    # current configured set of
                                            # interesting events (read,
                                            # write) for client
        self._new_events = 0                # new set of interesting events
        self._processing = False            # engine is working on us

        # read-only public
        self.registered = False             # registered on engine or not
        self.delayable = True               # subject to fanout limit

        self.worker = worker

        # boolean indicating whether stderr is on a separate fd
        self._stderr = stderr

        # associated files
        self.file_error = None
        self.file_reader = None
        self.file_writer = None

        # initialize error, read and write buffers
        self._ebuf = ""
        self._rbuf = ""
        self._wbuf = ""
        self._weof = False                  # write-ends notification

    def _fire(self):
        """
        Fire timeout timer.
        """
        if self._engine:
            self._engine.remove(self, abort=True, did_timeout=True)

    def _start(self):
        """
        Starts client and returns client instance as a convenience.
        Derived classes (except EnginePort) must implement.
        """
        raise NotImplementedError("Derived classes must implement.")

    def error_fileno(self):
        """
        Return the standard error reader file descriptor as an integer.
        """
        if self.file_error:
            return self.file_error.fileno()
        return None

    def reader_fileno(self):
        """
        Return the reader file descriptor as an integer.
        """
        if self.file_reader:
            return self.file_reader.fileno()
        return None
    
    def writer_fileno(self):
        """
        Return the writer file descriptor as an integer.
        """
        if self.file_writer:
            return self.file_writer.fileno()
        return None

    def _close(self, abort, flush, timeout):
        """
        Close client. Called by the engine after client has been
        unregistered. This method should handle all termination types
        (normal or aborted) with some options like flushing I/O buffers
        or setting timeout status.

        Derived classes must implement.
        """
        raise NotImplementedError("Derived classes must implement.")

    def _set_reading(self):
        """
        Set reading state.
        """
        self._engine.set_reading(self)

    def _set_reading_error(self):
        """
        Set error reading state.
        """
        self._engine.set_reading_error(self)

    def _set_writing(self):
        """
        Set writing state.
        """
        self._engine.set_writing(self)

    def _read(self, size=-1):
        """
        Read data from process.
        """
        result = self.file_reader.read(size)
        if not len(result):
            raise EngineClientEOF()
        self._set_reading()
        return result

    def _readerr(self, size=-1):
        """
        Read error data from process.
        """
        result = self.file_error.read(size)
        if not len(result):
            raise EngineClientEOF()
        self._set_reading_error()
        return result

    def _handle_read(self):
        """
        Handle a read notification. Called by the engine as the result of an
        event indicating that a read is available.
        """
        raise NotImplementedError("Derived classes must implement.")

    def _handle_error(self):
        """
        Handle a stderr read notification. Called by the engine as the result
        of an event indicating that a read is available on stderr.
        """
        raise NotImplementedError("Derived classes must implement.")

    def _handle_write(self):
        """
        Handle a write notification. Called by the engine as the result of an
        event indicating that a write can be performed now.
        """
        if len(self._wbuf) > 0:
            # write syscall
            c = os.write(self.file_writer.fileno(), self._wbuf)
            # dequeue written buffer
            self._wbuf = self._wbuf[c:]
            # check for possible ending
            if self._weof and not self._wbuf:
                self._close_writer()
            else:
                self._set_writing()
    
    def _exec_nonblock(self, commandlist, shell=False, env=None):
        """
        Utility method to launch a command with stdin/stdout file
        descriptors configured in non-blocking mode.
        """
        full_env = None
        if env:
            full_env = os.environ.copy()
            full_env.update(env)

        if self._stderr:
            stderr_setup = PIPE
        else:
            stderr_setup = STDOUT

        # Launch process in non-blocking mode
        proc = Popen(commandlist, bufsize=0, stdin=PIPE, stdout=PIPE,
            stderr=stderr_setup, close_fds=False, shell=shell, env=full_env)

        if self._stderr:
            fcntl.fcntl(proc.stderr, fcntl.F_SETFL,
                    fcntl.fcntl(proc.stderr, fcntl.F_GETFL) | os.O_NDELAY)
        fcntl.fcntl(proc.stdout, fcntl.F_SETFL,
                fcntl.fcntl(proc.stdout, fcntl.F_GETFL) | os.O_NDELAY)
        fcntl.fcntl(proc.stdin, fcntl.F_SETFL,
                fcntl.fcntl(proc.stdin, fcntl.F_GETFL) | os.O_NDELAY)

        return proc

    def _readlines(self):
        """
        Utility method to read client lines
        """
        # read a chunk of data, may raise eof
        readbuf = self._read()
        assert len(readbuf) > 0, "assertion failed: len(readbuf) > 0"

        # Current version implements line-buffered reads. If needed, we could
        # easily provide direct, non-buffered, data reads in the future.

        buf = self._rbuf + readbuf
        lines = buf.splitlines(True)
        self._rbuf = ""
        for line in lines:
            if line.endswith('\n'):
                if line.endswith('\r\n'):
                    yield line[:-2] # trim CRLF
                else:
                    # trim LF
                    yield line[:-1] # trim LF
            else:
                # keep partial line in buffer
                self._rbuf = line
                # breaking here

    def _readerrlines(self):
        """
        Utility method to read client lines
        """
        # read a chunk of data, may raise eof
        readerrbuf = self._readerr()
        assert len(readerrbuf) > 0, "assertion failed: len(readerrbuf) > 0"

        buf = self._ebuf + readerrbuf
        lines = buf.splitlines(True)
        self._ebuf = ""
        for line in lines:
            if line.endswith('\n'):
                if line.endswith('\r\n'):
                    yield line[:-2] # trim CRLF
                else:
                    # trim LF
                    yield line[:-1] # trim LF
            else:
                # keep partial line in buffer
                self._ebuf = line
                # breaking here

    def _write(self, buf):
        """
        Add some data to be written to the client.
        """
        fd = self.writer_fileno()
        if fd:
            assert not self.file_writer.closed
            # TODO: write now if ready
            self._wbuf += buf
            self._set_writing()
        else:
            # bufferize until pipe is ready
            self._wbuf += buf
    
    def _set_write_eof(self):
        self._weof = True
        if not self._wbuf:
            # sendq empty, try to close writer now
            self._close_writer()

    def _close_writer(self):
        if self.file_writer and not self.file_writer.closed:
            self._engine.unregister_writer(self)
            self.file_writer.close()
            self.file_writer = None

    def abort(self):
        """
        Abort processing any action by this client.
        """
        if self._engine:
            self._engine.remove(self, abort=True)

class EnginePort(EngineClient):
    """
    An EnginePort is an abstraction object to deliver messages
    reliably between tasks.
    """

    class _Msg:
        """Private class representing a port message.
        
        A port message may be any Python object.
        """

        def __init__(self, user_msg, sync):
            self._user_msg = user_msg
            self._sync_msg = sync
            self.reply_lock = thread.allocate_lock()
            self.reply_lock.acquire()

        def get(self):
            """
            Get and acknowledge message.
            """
            self.reply_lock.release()
            return self._user_msg

        def sync(self):
            """
            Wait for message acknowledgment if needed.
            """
            if self._sync_msg:
                self.reply_lock.acquire()

    def __init__(self, task, handler=None, autoclose=False):
        """
        Initialize EnginePort object.
        """
        EngineClient.__init__(self, None, False, -1, autoclose)
        self.task = task
        self.eh = handler
        # ports are no subject to fanout
        self.delayable = False

        # Port messages queue
        self._msgq = Queue.Queue(self.task.default("port_qlimit"))

        # Request pipe
        (readfd, writefd) = os.pipe()
        # Use file objects instead of FD for convenience
        self.file_reader = os.fdopen(readfd, 'r')
        self.file_writer = os.fdopen(writefd, 'w')
        # Set nonblocking flag
        fcntl.fcntl(readfd, fcntl.F_SETFL,
            fcntl.fcntl(readfd, fcntl.F_GETFL) | os.O_NDELAY)
        fcntl.fcntl(writefd, fcntl.F_SETFL,
            fcntl.fcntl(writefd, fcntl.F_GETFL) | os.O_NDELAY)

    def _start(self):
        return self

    def _close(self, abort, flush, timeout):
        """
        Close port pipes.
        """
        if not self._msgq.empty():
            # purge msgq
            try:
                while not self._msgq.empty():
                    pmsg = self._msgq.get(block=False)
                    self.task.info("print_debug")(self.task,
                        "EnginePort: dropped msg: %s" % pmsg.get())
            except Queue.Empty:
                pass
        self._msgq = None
        self.file_reader.close()
        self.file_writer.close()

    def _read(self, size=4096):
        """
        Read data from pipe.
        """
        return EngineClient._read(self, size)

    def _handle_read(self):
        """
        Handle a read notification. Called by the engine as the result of an
        event indicating that a read is available.
        """
        readbuf = self._read()
        for c in readbuf:
            # raise Empty if empty (should never happen)
            pmsg = self._msgq.get(block=False)
            self.eh.ev_msg(self, pmsg.get())

    def msg(self, send_msg, send_once=False):
        """
        Port message send method that will wait for acknowledgement
        unless the send_once parameter if set.
        """
        pmsg = EnginePort._Msg(send_msg, not send_once)
        self._msgq.put(pmsg, block=True, timeout=None)
        try:
            ret = os.write(self.writer_fileno(), "M")
        except OSError:
            raise
        pmsg.sync()
        return ret == 1

    def msg_send(self, send_msg):
        """
        Port message send-once method (no acknowledgement).
        """
        self.msg(send_msg, send_once=True)


