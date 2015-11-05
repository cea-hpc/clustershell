#
# Copyright CEA/DAM/DIF (2007-2015)
#  Contributor: Stephane THIELL <sthiell@stanford.edu>
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

__version__ = '1.7'
__version_info__ = tuple([ int(_n) for _n in __version__.split('.')])
__date__    = '2015/11/10'
__author__  = 'Stephane Thiell <sthiell@stanford.edu>'
__url__     = 'http://clustershell.readthedocs.org/'
