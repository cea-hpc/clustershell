ClusterShell 1.7 Python Library and Tools
=========================================

ClusterShell is an event-driven open source Python library, designed to run
local or distant commands in parallel on server farms or on large Linux
clusters. It will take care of common issues encountered on HPC clusters, such
as operating on groups of nodes, running distributed commands using optimized
execution algorithms, as well as gathering results and merging identical
outputs, or retrieving return codes. ClusterShell takes advantage of existing
remote shell facilities already installed on your systems, like SSH.

ClusterShell's primary goal is to improve the administration of high-
performance clusters by providing a lightweight but scalable Python API for
developers. It also provides clush, clubak and nodeset, three convenient
command-line tools that allow traditional shell scripts to benefit from some
of the library features.

Requirements (v1.7)
-------------------

 * GNU/Linux, *BSD, Mac OS X
 * OpenSSH (ssh/scp) or rsh
 * Python 2.x (x >= 4)
 * PyYAML (optional)

License
-------

ClusterShell is distributed under the CeCILL-C license, a French transposition
of the GNU LGPL, and is fully LGPL-compatible (see Licence_CeCILL-C_V1-en.txt).

Documentation
-------------

Online documentation is available here:

    http://clustershell.readthedocs.org/

The Sphinx documentation source is available under the doc/sphinx directory.
Type 'make' to see all available formats (you need Sphinx installed and
sphinx_rtd_theme to build the documentation). For example, to generate html
docs, just type:

    make html BUILDDIR=/dest/path

For local library API documentation, just type:

    $ pydoc ClusterShell

The following man pages are also provided:

    clush(1), clubak(1), nodeset(1), clush.conl(5), groups.conf(5)

Test Suite
----------

Regression testing scripts are available in the 'tests' directory:

    $ cd tests
    $ nosetests -sv <Test.py>
    $ nosetests -sv --all-modules

You have to allow 'ssh localhost' and 'ssh $HOSTNAME' without any warnings for
"remote" tests to run as expected. $HOSTNAME should not be 127.0.0.1 nor ::1.
Also some tests use the 'bc' command.

ClusterShell interactively
--------------------------

```python
>>> from ClusterShell.Task import task_self
>>> from ClusterShell.NodeSet import NodeSet
>>> task = task_self()
>>> task.run("/bin/uname -r", nodes="linux[4-6,32-39]")
<ClusterShell.Worker.Ssh.WorkerSsh object at 0x20a5e90>
>>> for buf, key in task.iter_buffers():
...     print NodeSet.fromlist(key), buf
... 
linux[32-39] 2.6.40.6-0.fc15.x86_64

linux[4-6] 2.6.32-71.el6.x86_64
```

Links
-----

Web site:

    http://clustershell.sourceforge.net
    or http://cea-hpc.github.com/clustershell/

Online documentation:

    http://clustershell.readthedocs.org/

Github source respository:

    https://github.com/cea-hpc/clustershell

Github Wiki:

    https://github.com/cea-hpc/clustershell/wiki

Github Issue tracking system:

    https://github.com/cea-hpc/clustershell/issues

Sourceforge.net project page:

    http://sourceforge.net/projects/clustershell

Python Package Index (PyPI) link:

    http://pypi.python.org/pypi/ClusterShell

ClusterShell was born along with Shine, a scalable Lustre FS admin tool:

    http://lustre-shine.sourceforge.net

Core developers/reviewers
-------------------------

* Stephane Thiell
* Aurelien Degremont
* Henri Doreau
* Dominique Martinet

CEA/DAM 2010, 2011, 2012, 2013, 2014, 2015 - http://www-hpc.cea.fr
