#!/usr/bin/env python
#
# Copyright (C) 2008-2016 CEA/DAM
# Copyright (C) 2016-2025 Stephane Thiell <sthiell@stanford.edu>
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


VERSION = '1.9.3'

CFGDIR = 'etc/clustershell'
MANDIR = 'share/man'

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
                  (os.path.join(CFGDIR, 'clush.conf.d'),
                   ['conf/clush.conf.d/sshpass.conf.example',
                    'conf/clush.conf.d/sudo.conf.example',
                    'conf/clush.conf.d/README']),
                  (os.path.join(CFGDIR, 'groups.conf.d'),
                   ['conf/groups.conf.d/genders.conf.example',
                    'conf/groups.conf.d/slurm.conf.example',
                    'conf/groups.conf.d/xcat.conf.example',
                    'conf/groups.conf.d/README']),
                  (os.path.join(CFGDIR, 'groups.d'),
                   ['conf/groups.d/cluster.yaml.example',
                    'conf/groups.d/local.cfg',
                    'conf/groups.d/README']),
                  (os.path.join(MANDIR, 'man1'),
                   ['doc/man/man1/clubak.1',
                    'doc/man/man1/cluset.1',
                    'doc/man/man1/clush.1',
                    'doc/man/man1/nodeset.1']),
                  (os.path.join(MANDIR, 'man5'),
                   ['doc/man/man5/clush.conf.5',
                    'doc/man/man5/groups.conf.5']),
                    ],
      entry_points={'console_scripts':
                    ['clubak=ClusterShell.CLI.Clubak:main',
                     'cluset=ClusterShell.CLI.Nodeset:main',
                     'clush=ClusterShell.CLI.Clush:main',
                     'nodeset=ClusterShell.CLI.Nodeset:main'],
                   },
      author='Stephane Thiell',
      author_email='sthiell@stanford.edu',
      license='LGPLv2+',
      url='https://clustershell.readthedocs.io/',
      download_url='https://github.com/cea-hpc/clustershell/archive/refs/tags/v%s.tar.gz' % VERSION,
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
          "Programming Language :: Python :: 2.7",
          "Programming Language :: Python :: 3",
          "Topic :: Software Development :: Libraries :: Python Modules",
          "Topic :: System :: Clustering",
          "Topic :: System :: Distributed Computing"
      ],
      install_requires=REQUIRES,
     )
