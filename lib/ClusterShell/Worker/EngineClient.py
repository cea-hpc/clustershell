#
# Copyright CEA/DAM/DIF (2009)
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
from subprocess import *

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

    def __init__(self, worker, timeout, autoclose):
        """
        Initializer. Should be called from derived classes.
        """
        EngineBaseTimer.__init__(self, timeout, -1, autoclose)

        # engine-friendly variables
        self._events = 0                    # current configured set of interesting
                                            # events (read, write) for client
        self._new_events = 0                # new set of interesting events
        self._processing = False            # engine is working on us

        # read-only public
        self.registered = False             # registered on engine or not

        self.worker = worker

        # initialize read and write buffers
        self._rbuf = ""
        self._wbuf = ""
        self._weof = False                  # write-ends notification

    def _fire(self):
        """
        Fire timeout timer.
        """
        if self._engine:
            self._engine.remove(self, did_timeout=True)

    def _start(self):
        """
        Starts client and returns client instance as a convenience.
        Derived classes must implement.
        """
        raise NotImplementedError("Derived classes must implement.")

    def reader_fileno(self):
        """
        Returns the reader file descriptor as an integer.
        """
        raise NotImplementedError("Derived classes must implement.")
    
    def writer_fileno(self):
        """
        Returns the writer file descriptor as an integer.
        """
        raise NotImplementedError("Derived classes must implement.")
    
    def abort(self):
        """
        Stop this client.
        """
        if self._engine:
            self._engine.remove(self)

    def _close(self, force, timeout):
        """
        Close client. Called by the engine after client has been
        unregistered. This method should handle all termination types
        (normal, forced or on timeout).
        Derived classes must implement.
        """
        raise NotImplementedError("Derived classes must implement.")

    def _set_reading(self):
        """
        Set reading state.
        """
        self._engine.set_reading(self)

    def _set_writing(self):
        """
        Set writing state.
        """
        self._engine.set_writing(self)

    def _handle_read(self):
        """
        Handle a read notification. Called by the engine as the result of an
        event indicating that a read is available.
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

        # Launch process in non-blocking mode
        proc = Popen(commandlist, bufsize=0, stdin=PIPE, stdout=PIPE,
                stderr=STDOUT, close_fds=False, shell=shell, env=full_env)

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

