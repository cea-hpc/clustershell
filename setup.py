#!/usr/bin/env python
#
# Copyright (C) 2008, 2009 CEA
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
# $Id$

from distutils.core import setup
import os

if not os.access('scripts/clush', os.F_OK):
    os.symlink('clush.py', 'scripts/clush')
if not os.access('scripts/nodeset', os.F_OK):
    os.symlink('nodeset.py', 'scripts/nodeset')

setup(name='ClusterShell',
      version='1.0.91',
      license='GPL',
      description='ClusterShell library',
      author='Stephane Thiell',
      author_email='stephane.thiell@cea.fr',
      url='http://clustershell.sourceforge.net/',
      package_dir={'': 'lib'},
      packages=['ClusterShell',
               'ClusterShell.Engine',
               'ClusterShell.Worker'],
      scripts=['scripts/clush',
               'scripts/nodeset']
     )

