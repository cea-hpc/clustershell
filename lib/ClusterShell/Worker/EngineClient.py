# EngineClient.py -- Base class for task's engine client
# Copyright (C) 2009 CEA
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
EngineClient

ClusterShell engine's client interface.

An engine client is similar to a process, you can start/stop it, read data from
it and write data to it.
"""

import fcntl
import popen2
import os

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
        self._weof = False

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
            if self._weof:
                self._close_writer()
            else:
                self._set_writing()
    
    def _exec_nonblock(self, command):
        """
        Utility method to launch a command with stdin/stdout file
        descriptors configured in non-blocking mode.
        """
        # Launch process in non-blocking mode
        fid = popen2.Popen4(command)
        fl = fcntl.fcntl(fid.fromchild, fcntl.F_GETFL)
        fcntl.fcntl(fid.fromchild, fcntl.F_SETFL, os.O_NDELAY)
        fl = fcntl.fcntl(fid.tochild, fcntl.F_GETFL)
        fcntl.fcntl(fid.tochild, fcntl.F_SETFL, os.O_NDELAY)
        return fid

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
        if self._wbuf or self.writer_fileno() == None:
            # write is not fully performed yet
            self._weof = True
        else:
            # sendq empty, close writer now
            self._close_writer()

    def _close_writer(self):
        if self.file_writer and not self.file_writer.closed:
            self._engine.unregister_writer(self)
            self.file_writer.close()
            self.file_writer = None

