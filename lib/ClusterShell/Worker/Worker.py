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

from ClusterShell.Event import EventHandler

class WorkerBadArgumentException(Exception):
    pass

class Worker:
    
    def __init__(self, handler):
        self.eh = handler

    def invoke_ev_start(self):
        if self.eh:
            self.eh._invoke(self, EventHandler.START)

    def invoke_ev_open(self):
        if self.eh:
            self.eh._invoke(self, EventHandler.OPEN)

    def invoke_ev_read(self):
        if self.eh:
            self.eh._invoke(self, EventHandler.READ)

    def invoke_ev_write(self):
        if self.eh:
            self.eh._invoke(self, EventHandler.WRITE)

    def invoke_ev_close(self):
        if self.eh:
            self.eh._invoke(self, EventHandler.CLOSE)

