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
# $Id: Worker.py 7 2007-12-20 14:52:31Z st-cea $

"""
Worker

ClusterShell worker interface.
"""

from ClusterShell.Event import EventHandler


class WorkerError(Exception):
    """
    Base worker error exception.
    """

class WorkerBadArgumentError(WorkerError):
    """
    Raised when bad argument usage is encountered.
    """


class Worker(object):
    """
    Base class Worker.
    """
    
    def __init__(self, handler, timeout, task):
        """
        Initializer. Should be called from derived classes.
        """
        self.eh = handler
        self.engine = None
        self.timeout = timeout
        self._task = task
        self.registered = False

    def task(self):
        """
        Return worker's task.
        """
        return self._task

    def last_read(self):
        """
        Get last read message from event handler.
        """
        raise NotImplementedError("Derived classes must implement.")

    def _set_engine(self, engine):
        """
        Set engine, called by Task.
        """
        self.engine = engine

    def _start(self):
        """
        Starts worker and returns worker instance as a convenience.
        Derived classes must implement.
        """
        raise NotImplementedError("Derived classes must implement.")

    def fileno(self):
        """
        Returns the file descriptor as an integer.
        """
        raise NotImplementedError("Derived classes must implement.")
    
    def abort(self):
        """
        Stop this worker.
        """
        self.engine.remove(self)

    def closed(self):
        """
        Returns True if the underlying file object is closed.
        """
        raise NotImplementedError("Derived classes must implement.")

    def _close(self, force, timeout):
        """
        Close worker. Called by engine after worker has been
        unregistered. This method should handle all termination types
        (normal, forced or on timeout).
        Derived classes must implement.
        """
        raise NotImplementedError("Derived classes must implement.")

    def _handle_read(self):
        """
        Engine is telling us a read is available.
        Return False on EOF, True otherwise.
        """
        raise NotImplementedError("Derived classes must implement.")
    
    def _invoke(self, ev_type):
        if self.eh:
            self.eh._invoke(ev_type, self)

