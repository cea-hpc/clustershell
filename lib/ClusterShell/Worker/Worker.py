# Worker.py -- Base class for task worker
# Copyright (C) 2007, 2008 CEA
#
# This file is part of shine
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

Base class worker
"""

from ClusterShell.Event import EventHandler


class WorkerBadArgumentException(Exception):
    pass

class Worker:
    """
    Worker Interface
    """
    
    def __init__(self, handler, info):
        """
        Initializer.
        """
        self.eh = handler
        self.info = info
        self.engine = None

    def last_read(self):
        """
        Get last read message from event handler.
        """
        raise NotImplementedError("Derived classes must implement.")

    def set_engine(self, engine):
        self.engine = engine

    def handle_read(self):
        raise NotImplementedError("Derived classes must implement.")

    def _invoke_ev_start(self):
        if self.eh:
            self.eh._invoke(self, EventHandler.START)

    def _invoke_ev_open(self):
        if self.eh:
            self.eh._invoke(self, EventHandler.OPEN)

    def _invoke_ev_read(self):
        if self.eh:
            self.eh._invoke(self, EventHandler.READ)

    def _invoke_ev_write(self):
        if self.eh:
            self.eh._invoke(self, EventHandler.WRITE)

    def _invoke_ev_close(self):
        if self.eh:
            self.eh._invoke(self, EventHandler.CLOSE)

