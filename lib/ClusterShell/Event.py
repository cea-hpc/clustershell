# Event.py -- Cluster task events management
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
# $Id: Event.py 7 2007-12-20 14:52:31Z st-cea $


"""
Event handler support

EventHandler's derived classes may implement ev_* methods to listen on
worker's events.
"""

class EventHandler:
    """
    Base class EventHandler.
    """
    def _invoke(self, ev_type, worker):
        """
        Invoke a specific event handler.
        """
        ev_handler = getattr(self, ev_type)
        ev_handler(worker)

    def ev_start(self, worker):
        """
        Called to indicate that a worker is about to run.
        """
        pass

    def ev_read(self, worker):
        """
        Called to indicate that a worker has data to read.
        """
        pass

    def ev_write(self, worker):
        """
        Called to indicate that writing now on that worker will not
        block (not supported).
        """
        pass

    def ev_close(self, worker):
        """
        Called to indicate that a worker has finished (it may already
        have failed on timeout).
        """
        pass

    def ev_timeout(self, worker):
        """
        Called to indicate that a worker has timed out (worker specific
        timeout only).
        """
        pass

