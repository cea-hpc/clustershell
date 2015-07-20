.. highlight:: console

Installation
============

In this part, we address ClusterShell installation information first. Then,
ClusterShell user tools are documented. Indeed, three Python scripts using the
ClusterShell library are provided with the distribution:

* ``nodeset``: a tool to manage cluster node sets and groups,
* ``clush``: a powerful parallel command execution tool with output gathering,
* ``clubak``: a tool to gather and display results from clush/pdsh-like output (and more).


Requirements
------------

ClusterShell |version| should work with any Unix [#]_ operating systems which
provides Python 2.4 to 2.7 (not Python 3.x validated) and OpenSSH or any
compatible Secure Shell clients.

Furthermore, ClusterShell's engine has been optimized when the ``poll()``
syscall is available or even better, when the ``epoll_wait()`` syscall (since
Linux 2.6) is available.

For instance, ClusterShell |version| is known to work on the following
operating systems:

* GNU/Linux RedHat EL5 or CentOS 5.x (Python 2.4), EL6 (Python 2.6) and EL7
  (Python 2.7)
* GNU/Linux Fedora 11 to 22 (Python 2.6 - 2.7),
* GNU/Linux Debian (wheezy and sid)
* Mac OS X 10.5.8 or more

Distribution
------------

ClusterShell is an open-source project distributed under the CeCILL-C flavor
of the `CeCILL license family`_, which is in conformance with the French law
and fully compatible with the GNU LGPL (Lesser GPL) license, which means that
many possibilities are offered to the end user. Also, as a software library,
ClusterShell has to remain easily available to everyone. Hopefully, packages
are currently maintained in Fedora Linux, RHEL (through EPEL repositories),
Debian and Arch Linux.

Fedora
^^^^^^

At the time of writing, ClusterShell |version| is available on Fedora 22
(releases being maintained by the Fedora Project).

Install ClusterShell from *Fedora Updates*
""""""""""""""""""""""""""""""""""""""""""

ClusterShell is part of Fedora, so it is really easy to install it with
``yum``, although you have to keep the Fedora *updates* default repository.
The following command checks whether the packages are available on a Fedora
machine::

    $ yum list \*clustershell
    Loaded plugins: presto, priorities, refresh-packagekit
    Available Packages
    clustershell.noarch                        1.5.1-1.fc15                  updates
    vim-clustershell.noarch                    1.5.1-1.fc15                  updates

Then, install ClusterShell (library and tools) with the following command::

    $ yum install clustershell vim-clustershell

Please note that optional (but recommended) ``vim-clustershell`` package will
install VIM syntax files for ClusterShell configuration files like
``clush.conf`` and ``groups.conf``.

Install ClusterShell from Fedora Updates Testing
""""""""""""""""""""""""""""""""""""""""""""""""

Recent releases of ClusterShell are first available through the `Test
Updates`_ ``yum`` repository of Fedora, then it is later pushed to the stable
*updates* repository. The following ``yum`` command will also checks for
packages availability in the *updates-testing* repository::

    $ yum list \*clustershell --enablerepo=updates-testing

To install, also add the ``--enablerepo=updates-testing`` option, for
instance::

    $ yum install clustershell vim-clustershell --enablerepo=updates-testing

Red Hat Enterprise Linux (and CentOS)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

ClusterShell packages are maintained on Extra Packages for Enterprise Linux
`EPEL`_ for Red Hat Enterprise Linux (RHEL) and its compatible spinoffs such
as CentOS. At the time of writing, ClusterShell |version| is available on
EPEL 5, 6 and 7.


Install ClusterShell from EPEL
""""""""""""""""""""""""""""""

First you have to enable the ``yum`` EPEL repository. We recommend to download
and install the EPEL repository RPM package.

Then, the ClusterShell installation procedure is quite the same of the Fedora
*Updates* one, for instance::

    $ yum install clustershell vim-clustershell

Debian
^^^^^^

ClusterShell is available in Debian since the *wheezy* testing release (February 2011):

* http://packages.debian.org/wheezy/clustershell
* http://packages.debian.org/sid/clustershell

To install it on Debian, simply use::

    $ apt-get install clustershell


Ubuntu
^^^^^^

Like Debian, it is easy to get and install ClusterShell on Ubuntu (also with
``apt-get``). To do so, please first enable the **universe** repository.
ClusterShell is available since "Natty" release (11.04):

* http://packages.ubuntu.com/clustershell


General distribution (Sourceforge and Github)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

ClusterShell is distributed in several packages. On RedHat-like OS, we
recommend to use the RPM  package (.rpm) distribution. General distribution
source packages and RPM package are available on the Sourceforge.net download
page:

* http://sourceforge.net/projects/clustershell/files/clustershell/

There is no difference between Fedora (or EPEL) RPM packages and the ones
found on Sourceforge.


Current source is also available through Git, use the following command to
retrieve the latest development version from the repository::

    $ git clone git@github.com:cea-hpc/clustershell.git

Install ClusterShell as a standard Python package (may need to be root)::

    $ tar -xzf clustershell-|version|.tar.gz
    $ cd clustershell-\version{}
    $ python setup.py install

Then, you should create the directory ``/etc/clustershell`` and put in it
files found in conf directory. This is the same thing when using pip [#]_.
This should be fixed in a future release.


.. [#] Unix in the same sense of the *Availability: Unix* notes in the Python
   documentation
.. [#] pip is a tool for installing and managing Python packages, such as
   those found in the Python Package Index

.. _CeCILL license family: http://www.cecill.info/index.en.html
.. _Test Updates: http://fedoraproject.org/wiki/QA/Updates_Testing
.. _EPEL: http://fedoraproject.org/wiki/EPEL
