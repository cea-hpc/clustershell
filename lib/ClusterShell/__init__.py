#
# Copyright CEA/DAM/DIF (2007, 2008, 2009, 2010, 2011, 2012)
#  Contributor: Stephane THIELL <stephane.thiell@cea.fr>
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

Event-based Python library to execute commands on local or distant
cluster nodes in parallel depending on the selected engine and worker
mechanisms. It also provides advanced NodeSet and NodeGroups handling
methods to ease and improve administration of large compute clusters
or server farms.

Please see first:
  - ClusterShell.NodeSet
  - ClusterShell.Task
"""

__version__ = '1.5.90'
__version_info__ = tuple([ int(_n) for _n in __version__.split('.')])
__date__    = '2012/03/28'
__author__  = 'Stephane Thiell <stephane.thiell@cea.fr>'
__url__     = 'http://clustershell.sourceforge.net/'

