# Engine.py -- Base class for ClusterShell engine
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
# $Id: Engine.py 7 2007-12-20 14:52:31Z st-cea $


class Engine:

    def __init__(self):
        self.worker_list = []

    def add(self, worker):
        self.worker_list.append(worker)

    def reset(self):
        self.worker_list = []
    
    def run(self, timeout):
        raise NotImplementedError("Derived classes must implement.")

    def read(self):
        raise NotImplementedError("Derived classes must implement.")

    def retcode(self):
        raise NotImplementedError("Derived classes must implement.")


