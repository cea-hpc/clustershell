# Event.py -- Cluster task events management
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
# $Id: Event.py 7 2007-12-20 14:52:31Z st-cea $

import sys

class EventHandler:
    """
    Class for managing Worker Event handlers.
    """
    
    START = 0
    OPEN = 1
    READ = 2
    WRITE = 3
    CLOSE = -1

    def __init__(self):
        self._ev_map = { self.START: self.ev_start,
                         self.OPEN : self.ev_open,
                         self.READ : self.ev_read,
                         self.WRITE : self.ev_write,
                         self.CLOSE : self.ev_close }
    
    def install(self, target, type):
        """
        Install a new event handler by adding an event target and type.
        """
        try:
            self._ev_map[type] = target
        except AttributeError:
            print >> sys.stderr, "Uninitialized EventHandler object."
            raise

    def remove(self, type=None):
        """
        Remove an installed event handler for the specified type.
        """
        if type:
            del self._ev_map[type]
        else:
            self._ev_map.clear()

    def _invoke(self, worker, type):
        self._ev_map[type](worker)

    def ev_start(self, worker):
        pass

    def ev_open(self, worker):
        pass

    def ev_read(self, worker):
        pass

    def ev_write(self, worker):
        pass

    def ev_close(self, worker):
        pass

