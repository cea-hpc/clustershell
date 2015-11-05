#!/usr/bin/env python
#
# Copyright CEA/DAM/DIF (2008-2015)
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

import os
from setuptools import setup, find_packages


if not os.access('scripts/clubak', os.F_OK):
    os.symlink('clubak.py', 'scripts/clubak')
if not os.access('scripts/clush', os.F_OK):
    os.symlink('clush.py', 'scripts/clush')
if not os.access('scripts/nodeset', os.F_OK):
    os.symlink('nodeset.py', 'scripts/nodeset')

if os.geteuid() == 0:
    # System-wide, out-of-prefix config install (rpmbuild or pip as root)
    CFGDIR = '/etc/clustershell'
else:
    # User, in-prefix config install (rpmbuild or pip as user)
    CFGDIR = 'etc/clustershell'

VERSION='1.7'

setup(name='ClusterShell',
      version=VERSION,
      package_dir={'': 'lib'},
      packages=find_packages('lib'),
      data_files = [(CFGDIR,
                     ['conf/clush.conf',
                      'conf/groups.conf',
                      'conf/topology.conf.example']),
                    (os.path.join(CFGDIR, 'groups.conf.d'),
                     ['conf/groups.conf.d/genders.conf.example',
                      'conf/groups.conf.d/slurm.conf.example',
                      'conf/groups.conf.d/README']),
                    (os.path.join(CFGDIR,'groups.d'),
                     ['conf/groups.d/cluster.yaml.example',
                      'conf/groups.d/local.cfg',
                      'conf/groups.d/README'])],
      scripts=['scripts/clubak',
               'scripts/clush',
               'scripts/nodeset'],
      author='Stephane Thiell',
      author_email='stephane.thiell@cea.fr',
      license='CeCILL-C (French equivalent to LGPLv2+)',
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
          "Operating System :: MacOS :: MacOS X",
          "Operating System :: POSIX :: BSD",
          "Operating System :: POSIX :: Linux",
          "Programming Language :: Python",
          "Topic :: Software Development :: Libraries :: Python Modules",
          "Topic :: System :: Clustering",
          "Topic :: System :: Distributed Computing"
      ]
     )

