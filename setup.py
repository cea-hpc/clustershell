#!/usr/bin/env python
#
# Copyright (C) 2008-2016 CEA/DAM
# Copyright (C) 2016-2018 Stephane Thiell <sthiell@stanford.edu>
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

import os
from setuptools import setup, find_packages


VERSION = '1.8.1'

# Default CFGDIR: in-prefix config install (rpmbuild or pip as user)
CFGDIR = 'etc/clustershell'

# Use system-wide CFGDIR instead when installing as root on Unix
try:
    if os.geteuid() == 0:
        CFGDIR = '/etc/clustershell'
except AttributeError:  # Windows?
    pass

# Dependencies (for pip install)
REQUIRES = ['PyYAML']

setup(name='ClusterShell',
      version=VERSION,
      package_dir={'': 'lib'},
      packages=find_packages('lib'),
      data_files=[(CFGDIR,
                   ['conf/clush.conf',
                    'conf/groups.conf',
                    'conf/topology.conf.example']),
                  (os.path.join(CFGDIR, 'groups.conf.d'),
                   ['conf/groups.conf.d/genders.conf.example',
                    'conf/groups.conf.d/slurm.conf.example',
                    'conf/groups.conf.d/README']),
                  (os.path.join(CFGDIR, 'groups.d'),
                   ['conf/groups.d/cluster.yaml.example',
                    'conf/groups.d/local.cfg',
                    'conf/groups.d/README'])],
      entry_points={'console_scripts':
                    ['clubak=ClusterShell.CLI.Clubak:main',
                     'cluset=ClusterShell.CLI.Nodeset:main',
                     'clush=ClusterShell.CLI.Clush:main',
                     'nodeset=ClusterShell.CLI.Nodeset:main'],
                   },
      author='Stephane Thiell',
      author_email='sthiell@stanford.edu',
      license='LGPLv2+',
      url='http://clustershell.sourceforge.net/',
      download_url='http://sourceforge.net/projects/clustershell/files/'
                   'clustershell/%s/' % VERSION,
      platforms=['GNU/Linux', 'BSD', 'MacOSX'],
      keywords=['clustershell', 'clush', 'clubak', 'nodeset'],
      description='ClusterShell library and tools',
      long_description=open('doc/txt/clustershell.rst').read(),
      classifiers=[
          "Development Status :: 5 - Production/Stable",
          "Environment :: Console",
          "Intended Audience :: System Administrators",
          "License :: OSI Approved :: GNU Lesser General Public License v2 or later (LGPLv2+)",
          "Operating System :: MacOS :: MacOS X",
          "Operating System :: POSIX :: BSD",
          "Operating System :: POSIX :: Linux",
          "Programming Language :: Python",
          "Programming Language :: Python :: 2.6",
          "Programming Language :: Python :: 2.7",
          "Programming Language :: Python :: 3",
          "Topic :: Software Development :: Libraries :: Python Modules",
          "Topic :: System :: Clustering",
          "Topic :: System :: Distributed Computing"
      ],
      install_requires=REQUIRES,
     )
