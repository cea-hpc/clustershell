#
# Copyright (C) 2007-2016 CEA/DAM
#
# This file is part of ClusterShell.
#
# ClusterShell is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# ClusterShell is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with ClusterShell; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

"""ClusterShell Python Library

ClusterShell is an event-driven open source Python library, designed to run
local or distant commands in parallel on server farms or on large clusters.
You can use ClusterShell as a building block to create cluster aware
administration scripts and system applications in Python. It will take care of
common issues encountered on HPC clusters, such as operating on groups of
nodes, running distributed commands using optimized execution algorithms, as
well as gathering results and merging identical outputs, or retrieving return
codes. ClusterShell takes advantage of existing remote shell facilities already
installed on your systems, like SSH.

Please see first:
  - ClusterShell.NodeSet
  - ClusterShell.Task
"""

__version__ = '1.8.1'
__version_info__ = tuple([ int(_n) for _n in __version__.split('.')])
__date__    = '2018/10/30'
__author__  = 'Stephane Thiell <sthiell@stanford.edu>'
__url__     = 'http://clustershell.readthedocs.org/'
