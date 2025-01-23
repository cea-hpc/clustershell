.. highlight:: console

Installation
============

ClusterShell is distributed in several packages. On RedHat-like OS, we
recommend to use the RPM package (.rpm) distribution.

As system software for cluster, ClusterShell is primarily made for
system-wide installation to be used by system administrators. However,
changes have been made so that it's now possible to install it without
root access (see :ref:`install-pip-user`).

.. _install-requirements:

Requirements
------------

ClusterShell should work with any Unix [#]_ operating systems which provides
Python 2.7 or 3.x and OpenSSH or any compatible Secure Shell clients.

.. warning:: While we are making our best effort to maintain Python 2
   compatibility in ClusterShell 1.9.x, we no longer run tests for Python 2.
   Therefore, functionality on Python 2 is not guaranteed and may break without
   notice. For the best experience and continued support, it is strongly
   recommended to use Python 3.

Furthermore, ClusterShell's engine has been optimized when the ``poll()``
syscall is available or even better, when the ``epoll_wait()`` syscall is
available (Linux only).

For instance, ClusterShell is known to work on the following operating systems:

* GNU/Linux

  * Red Hat Enterprise Linux 7 (Python 2.7)

  * Red Hat Enterprise Linux 8 (Python 3.6)

  * Red Hat Enterprise Linux 9 (Python 3.9)

  * Fedora 30 and above (Python 2.7 to 3.10+)

  * Debian 10 "buster" (Python 3.7)

  * Debian 11 "bullseye" (Python 3.9)

  * Ubuntu 20.04 (Python 3.8)

* Mac OS X 12+ (Python 2.7 and 3.8)

Distribution
------------

ClusterShell is an open-source project distributed under the GNU Lesser General
Public License version or later (`LGPL v2.1+`_), which means that many
possibilities are offered to the end user. Also, as a software library,
ClusterShell should remain easily available to everyone. Hopefully, packages are
currently available for Fedora Linux, RHEL (through EPEL repositories), Debian,
Arch Linux and more.

.. _install-python-support-overview:

Python support overview
^^^^^^^^^^^^^^^^^^^^^^^

As seen in :ref:`install-requirements`, ClusterShell supports Python 2.7 and
onwards, at least up to Python 3.10 at the time of writing.

The table below provides a few examples of versions of Python supported by
ClusterShell packages as found in some common Linux distributions:

+------------------+----------------------------+-----------------------------------+
| Operating        | System Python version used | Alternate Python support          |
| System           | by the clustershell tools  | packaged (version-suffixed tools) |
+==================+============================+===================================+
| RHEL 7           | Python 2.7                 | Python 3.6                        |
+------------------+----------------------------+-----------------------------------+
| RHEL 8           | **Python 3.6**             |                                   |
+------------------+----------------------------+-----------------------------------+
| RHEL 9           | **Python 3.9**             |                                   |
+------------------+----------------------------+-----------------------------------+
| Fedora 36        | **Python 3.10**            |                                   |
+------------------+----------------------------+-----------------------------------+
| openSUSE Leap 15 | Python 2.7                 | Python 3.6                        |
+------------------+----------------------------+-----------------------------------+
| SUSE SLES 12     | Python 2.7                 | Python 3.4                        |
+------------------+----------------------------+-----------------------------------+
| SUSE SLES 15     | Python 2.7                 | Python 3.6                        |
+------------------+----------------------------+-----------------------------------+
| Ubuntu 18.04 LTS | **Python 3.6**             |                                   |
+------------------+----------------------------+-----------------------------------+
| Ubuntu 20.04 LTS | **Python 3.8**             |                                   |
+------------------+----------------------------+-----------------------------------+

Red Hat Enterprise Linux
^^^^^^^^^^^^^^^^^^^^^^^^

ClusterShell packages are maintained on Extra Packages for Enterprise Linux
`EPEL`_ for Red Hat Enterprise Linux (RHEL) and its compatible spinoffs such
as `Alma Linux`_ and `Rocky Linux`_. At the time of writing, ClusterShell |version|
is available on EPEL 8 and 9.


Install ClusterShell from EPEL
""""""""""""""""""""""""""""""

First you have to enable the ``yum`` EPEL repository. We recommend to download
and install the `EPEL`_ repository RPM package. On CentOS, this can be easily
done using the following command::

    $ dnf --enablerepo=extras install epel-release

Then, the ClusterShell installation procedure is quite the same as for
*Fedora Updates*, for instance::

    $ dnf install clustershell

The Python 3 modules and tools are installed by default with ``clustershell``.
If interested in the Python 3 library only, you can install ClusterShell's
Python 3 subpackage using the following command::

    $ dnf install python3-clustershell

With EPEL 8 and 9, however, Python 3 is the system default, and Python 2 has
been deprecated. Thus only Python 3 is supported by the EPEL clustershell
packages, the tools are using Python 3 by default and are not suffixed anymore.

Fedora
^^^^^^

At the time of writing, ClusterShell |version| is available on Fedora 41
(releases being maintained by the Fedora Project).

Install ClusterShell from *Fedora Updates*
""""""""""""""""""""""""""""""""""""""""""

ClusterShell is part of Fedora, so it is really easy to install it with
``dnf``, although you have to keep the Fedora *updates* default repository.
The following command checks whether the packages are available on a Fedora
system::

    $ dnf list \*clustershell
    Available Packages
    clustershell.noarch                     1.8-1.fc26                fedora
    python2-clustershell.noarch             1.8-1.fc26                fedora
    python3-clustershell.noarch             1.8-1.fc26                fedora

Then, install ClusterShell's library module and tools using the following
command::

    $ dnf install clustershell

Prior to Fedora 31, Python 2 modules and tools were installed by default. If
interested in Python 3 support, simply install the additional ClusterShell's
Python 3 subpackage using the following command::

    $ dnf install python3-clustershell

Prior to Fedora 31, Python 3 versions of the tools are installed as
*tool-pythonversion*, like ``clush-3.6``, ``cluset-3.6`` or ``nodeset-3.6``.

On Fedora 31 and onwards, only Python 3 is supported.

Install ClusterShell from Fedora Updates Testing
""""""""""""""""""""""""""""""""""""""""""""""""

Recent releases of ClusterShell are first available through the
`Test Updates`_ repository of Fedora, then it is later pushed to the stable
*updates* repository. The following ``dnf`` command will also checks for
packages availability in the *updates-testing* repository::

    $ dnf list \*clustershell --enablerepo=updates-testing

To install, also add the ``--enablerepo=updates-testing`` option, for
instance::

    $ dnf install clustershell --enablerepo=updates-testing

openSUSE
^^^^^^^^

ClusterShell is available in openSUSE Tumbleweed (Factory) and Leap since 2017::

    $ zypper search clustershell
    Loading repository data...
    Reading installed packages...

    S | Name                 | Summary                                               | Type
    --+----------------------+-------------------------------------------------------+--------
      | clustershell         | Python framework for efficient cluster administration | package
      | python2-clustershell | ClusterShell module for Python 2                      | package
      | python3-clustershell | ClusterShell module for Python 3                      | package


To install ClusterShell on openSUSE, use::

    $ zypper install clustershell

Python 2 module and tools are installed by default. If interested in Python 3 support,
simply install the additional ClusterShell's Python 3 subpackage
using the following command::

    $ zypper install python3-clustershell

Python 3 versions of the tools are installed as *tool-pythonversion*, like
``clush-3.6``, ``cluset-3.6`` or ``nodeset-3.6``.

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

.. _install-python:

Installing ClusterShell the Python way
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. warning:: Installing ClusterShell as root using pip [#]_ is discouraged and
   can result in conflicting behaviour with the system package manager.  Use
   packages provided by your OS instead to install ClusterShell system-wide.

.. _install-pip-user:

Installing ClusterShell as user using pip
"""""""""""""""""""""""""""""""""""""""""

To install ClusterShell as a standard Python package using pip as an user::

    $ pip install --user ClusterShell

Or alternatively, using the source tarball::

    $ pip install --user ClusterShell-1.x.tar.gz

Then, you might need to update your ``PATH`` to easily use the :ref:`tools`,
and possibly set the ``PYTHONPATH`` environment variable to be able to import
the library, and finally ``MANPATH`` for the man pages::

    $ export PATH=$PATH:~/.local/bin
    $
    $ # Might also be needed:
    $ export PYTHONPATH=$PYTHONPATH:~/.local/lib
    $ export MANPATH=$MANPATH:$HOME/.local/share/man

Configuration files are installed in ``~/.local/etc/clustershell`` and are
automatically loaded before system-wide ones (for more info about supported
user config files, please see the :ref:`clush-config` or :ref:`groups-config`
config sections).

.. _install-venv-pip:

Isolated environment using virtualenv and pip
"""""""""""""""""""""""""""""""""""""""""""""

It is possible to use virtual env (`venv`_) and pip to install ClusterShell
in an isolated environment::

    $ python3 -m venv venv
    $ source venv/bin/activate
    $ pip install ClusterShell

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

.. _LGPL v2.1+: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
.. _Test Updates: http://fedoraproject.org/wiki/QA/Updates_Testing
.. _EPEL: http://fedoraproject.org/wiki/EPEL
.. _Alma Linux: https://almalinux.org/
.. _Rocky Linux: https://rockylinux.org/
.. _venv: https://docs.python.org/3/tutorial/venv.html
