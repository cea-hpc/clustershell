.. highlight:: console

Installation
============

ClusterShell is distributed in several packages. On RedHat-like OS, we
recommend to use the RPM  package (.rpm) distribution.

As a system software for cluster, ClusterShell is primarily made for
system-wide installation. However, changes have been made so that's it is now
easy to install it without root access (see :ref:`install-pip-user`).


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
* GNU/Linux Debian (wheezy and above)
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

ClusterShell is available in Debian **main** repository (since 2011).

To install it on Debian, simply use::

    $ apt-get install clustershell

You can get the latest version on::

* http://packages.debian.org/sid/clustershell


Ubuntu
^^^^^^

Like Debian, it is easy to get and install ClusterShell on Ubuntu (also with
``apt-get``). To do so, please first enable the **universe** repository.
ClusterShell is available since "Natty" release (11.04):

* http://packages.ubuntu.com/clustershell


Installing ClusterShell using PIP
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Installing ClusterShell as root using PIP
"""""""""""""""""""""""""""""""""""""""""

To install ClusterShell as a standard Python package using PIP [#]_ as root::

    $ pip install clustershell

Or alternatively, using the source tarball::

    $ pip install clustershell-1.x.tar.gz


.. _install-pip-user:

Installing ClusterShell as user using PIP
"""""""""""""""""""""""""""""""""""""""""

To install ClusterShell as a standard Python package using PIP as an user::

    $ pip install --user clustershell

Or alternatively, using the source tarball::

    $ pip install --user clustershell-1.x.tar.gz

Then, you just need to update your ``PYTHONPATH`` environment variable to be
able to import the library and ``PATH`` to easily use the :ref:`tools`::

    $ export PYTHONPATH=$PYTHONPATH:~/.local/lib
    $ export PATH=$PATH:~/.local/bin

Configuration files are installed in ``~/.local/etc/clustershell`` and are
automatically loaded before system-wide ones (for more info about supported
user config files, please see the :ref:`clush-config` or :ref:`groups-config`
config sections).

.. _install-source:

Source
------

Current source is available through Git, use the following command to retrieve
the latest development version from the repository::

    $ git clone git@github.com:cea-hpc/clustershell.git


.. [#] Unix in the same sense of the *Availability: Unix* notes in the Python
   documentation
.. [#] pip is a tool for installing and managing Python packages, such as
   those found in the Python Package Index

.. _CeCILL license family: http://www.cecill.info/index.en.html
.. _Test Updates: http://fedoraproject.org/wiki/QA/Updates_Testing
.. _EPEL: http://fedoraproject.org/wiki/EPEL
