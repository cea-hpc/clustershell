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


class EngineClientException(Exception):
    """Generic EngineClient exception."""

class EngineClientError(Exception):
    """Base EngineClient error exception."""

class EngineClientNotSupportedError(EngineClientError):
    """Operation not supported by EngineClient."""


class EngineClient(object):
    """
    Abstract class EngineClient.
    """

    def __init__(self, timeout, worker):
        """
        Initializer. Should be called from derived classes.
        """
        # "engine-friendly"
        self._engine = None
        self._iostate = 0                   # what we want : read, write or both
        self._processing = False            # engine is working on us

        # read-only public
        self.timeout = timeout              # needed by WorkerTimerQ
        self.registered = False             # registered on engine

        self.worker = worker

    def _set_engine(self, engine):
        """
        Set engine, called by Engine.
        """
        self._engine = engine

    def _start(self):
        """
        Starts worker and returns worker instance as a convenience.
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
        Stop this worker.
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

