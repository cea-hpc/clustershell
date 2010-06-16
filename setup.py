#!/usr/bin/env python
#
# Copyright CEA/DAM/DIF (2008, 2009)
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
#
# $Id$

from distutils.core import setup
import os

if not os.access('scripts/clubak', os.F_OK):
    os.symlink('clubak.py', 'scripts/clubak')
if not os.access('scripts/clush', os.F_OK):
    os.symlink('clush.py', 'scripts/clush')
if not os.access('scripts/nodeset', os.F_OK):
    os.symlink('nodeset.py', 'scripts/nodeset')

setup(name='ClusterShell',
      version='1.2.85',
      license='CeCILL-C',
      description='ClusterShell library',
      author='Stephane Thiell',
      author_email='stephane.thiell@cea.fr',
      url='http://clustershell.sourceforge.net/',
      package_dir={'': 'lib'},
      packages=['ClusterShell',
               'ClusterShell.Engine',
               'ClusterShell.Worker'],
      scripts=['scripts/clubak',
               'scripts/clush',
               'scripts/nodeset']
     )

