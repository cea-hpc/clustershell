.. highlight:: console

Release Notes
=============

Version 1.8
-----------

This adaptive major release is now compatible with both Python 2 and Python 3.

We hope this release will help you manage your clusters, server farms or cloud
farms! Special thanks to the many of you that have sent us feedback on GitHub!

.. warning:: Support for Python 2.5 and below has been dropped in this version.

Version 1.8.4
^^^^^^^^^^^^^

This version contains a few bug fixes and improvements:

* allow out-of-tree worker modules

* use default local_worker and allow overriding :ref:`defaults-config` (tree mode)

* return maxrc properly in the case of the Rsh Worker

* :ref:`clush-tool`: improve stdin support with Python 3

* :ref:`clush-tool`: add maxrc option to :ref:`clush.conf <clush-config>`

* :ref:`clush-tool`: add support for NO_COLOR and CLICOLOR

For more details, please have a look at `GitHub Issues for 1.8.4 milestone`_.


Version 1.8.3
^^^^^^^^^^^^^

This version contains a few bug fixes and improvements, mostly affecting the
:ref:`tree mode <clush-tree>`:

* propagate ``CLUSTERSHELL_GW_PYTHON_EXECUTABLE`` environment variable to
  remote gateways (see :ref:`clush-tree-python`)

* fix defect to properly close gateway channel when worker has aborted

* improve error reporting from gateways

* :ref:`clush-tool`: now properly handles ``--worker=ssh`` when
  :ref:`topology.conf <clush-tree-enabling>` is present to explicitly disable
  :ref:`tree mode <clush-tree>`

* use safe yaml load variant to avoid warning from :class:`.YAMLGroupLoader`


For more details, please have a look at `GitHub Issues for 1.8.3 milestone`_.

We also added a :ref:`Python support matrix <install-python-support-overview>`
for the main Linux distributions.


Version 1.8.2
^^^^^^^^^^^^^

This version contains a few minor fixes:

* :ref:`clush-tool`: support UTF-8 string encoding with
  :ref:`--diff <clush-diff>`

* in some cases, :ref:`timers <configuring-a-timer>` were too fast due to an
  issue in :class:`.EngineTimer`

* fix issue in the :ref:`Slurm group bindings <group-slurm-bindings>` where job
  ids were used instead of user names

* performance update for :ref:`xCAT group bindings <group-xcat-bindings>`

For more details, please have a look at `GitHub Issues for 1.8.2 milestone`_.

Python support
""""""""""""""

Version 1.8.2 adds support for Python 3.7.

.. note:: This version still supports Python 2.6 and thus also RHEL/CentOS
   6, but please note that ClusterShell 1.9 is expected to require at least
   Python 2.7.

OS support
""""""""""

Version 1.8.2 adds support for RHEL 8/CentOS 8 and Fedora 31+, where only the
Python 3 package is provided. The ``clustershell`` packages will be made
available in EPEL-8 as soon as possible.

No packaging changes were made to ``clustershell`` in RHEL/CentOS 6 or 7.


Version 1.8.1
^^^^^^^^^^^^^

This update contains a few bug fixes and some performance improvements of the
:class:`.NodeSet` class.

The :ref:`tree mode <clush-tree>` has been fixed to properly support offline
gateways.

We added the following command line options:

* ``--conf`` to specify alternative clush.conf (clush only)

* ``--groupsconf`` to specify alternative groups.conf (all CLIs)

In :class:`.EventHandler`, we reinstated :meth:`.EventHandler.ev_error`: and
:meth:`.EventHandler.ev_error`: (as deprecated) for compatibility purposes.
Please see below for more details about important :class:`.EventHandler`
changes in 1.8.

Finally, :ref:`cluset <cluset-tool>`/:ref:`nodeset <nodeset-tool>` have been
improved by adding support for:

* litteral new line in ``-S``

* multiline shell variables in options

For more details, please have a look at `GitHub Issues for 1.8.1 milestone`_.

Main changes in 1.8
^^^^^^^^^^^^^^^^^^^

For more details, please have a look at `GitHub Issues for 1.8 milestone`_.

CLI (command line interface)
""""""""""""""""""""""""""""

If you use the :ref:`clush <clush-tool>` or
:ref:`cluset <cluset-tool>`/:ref:`nodeset <nodeset-tool>` tools, there are no
major changes since 1.7, though a few bug fixes and improvements have been
done:

* It is now possible to work with numeric node names with cluset/nodeset::

    $ nodeset --fold 6704 6705 r931 r930
    [6704-6705],r[930-931]

    $ squeue -h -o '%i' -u $USER | cluset -f
    [680240-680245,680310]

  As a reminder, cluset/nodeset has always had an option to switch to numerical
  cluster ranges (only), using ``-R/--rangeset``::

    $ squeue -h -o '%i' -u $USER | cluset -f -R
    680240-680245,680310

* Node group configuration is now loaded and processed only when required.
  This is actually an improvement of the :class:`.NodeSet` class that the
  tools readily benefit. This should improve both usability and performance.

* YAML group files are now ignored for users that don't have the permission
  to read them (see :ref:`group-file-based` for more info about group files).

* :ref:`clush <clush-tool>` now use slightly different colors that are legible
  on dark backgrounds.

* :ref:`clush-tree`:

  + Better detection of the Python executable, and, if needed, we added a new
    environment variable to override it, see :ref:`clush-tree-python`.

  + You must use the same major version of Python on the gateways and the root
    node.

.. highlight:: python

Python library
""""""""""""""

If you're a developer and use the ClusterShell Python library, please read
below.

Python 3 support
++++++++++++++++

Starting in 1.8, the library can also be used with Python 3. The code is
compatible with both Python 2 and 3 at the same time. To make it possible,
we performed a full code refactoring (without changing the behavior).

.. note:: When using Python 3, we recommend Python 3.4 or any more recent
          version.

Improved Event API
++++++++++++++++++

We've made some changes to :class:`.EventHandler`, a class that defines a
simple interface to handle events generated by :class:`.Worker`,
:class:`.EventTimer` and :class:`.EventPort` objects.

Please note that all programs already based on :class:`.EventHandler` should
work with this new version of ClusterShell without any code change (backward
API compatibility across 1.x versions is enforced). We use object
*introspection*, the ability to determine the type of an object at runtime,
to make the Event API evolve smoothly. We do still recommend to change your
code as soon as possible as we'll break backward compatibility in the future
major release 2.0.

The signatures of the following :class:`.EventHandler` methods **changed** in
1.8:

* :meth:`.EventHandler.ev_pickup`: new ``node`` argument
* :meth:`.EventHandler.ev_read`: new ``node``, ``sname`` and ``msg`` arguments
* :meth:`.EventHandler.ev_hup`: new ``node``, ``rc`` argument
* :meth:`.EventHandler.ev_close`: new ``timedout`` argument

Both old and new signatures are supported in 1.8. The old signatures will
be deprecated in a future 1.x release and **removed** in version 2.0.

The new methods aims to be more convenient to use by avoiding the need of
accessing context-specific :class:`.Worker` attributes like
``worker.current_node`` (replaced with the ``node`` argument in that case).

Also, please note that the following :class:`.EventHandler` methods will be
removed in 2.0:

* ``EventHandler.ev_error()``: its use should be replaced with
  :meth:`.EventHandler.ev_read` by comparing the stream name ``sname``
  with :attr:`.Worker.SNAME_STDERR`, like in the example below::

    class MyEventHandler(EventHandler):

        def ev_read(self, worker, node, sname, msg):
            if sname == worker.SNAME_STDERR:
                print('error from %s: %s' % (node, msg))

* ``EventHandler.ev_timeout()``: its use should be replaced with
  :meth:`.EventHandler.ev_close` by checking for the new ``timedout``
  argument, which is set to ``True`` when a timeout occurred.

We recommend developers to start using the improved :mod:`.Event` API now.
Please don't forget to update your packaging requirements to use ClusterShell
1.8 or later.

Task and standard input (stdin)
+++++++++++++++++++++++++++++++

:meth:`.Task.shell` and :meth:`.Task.run` have a new ``stdin`` boolean
argument which if set to ``False`` prevents the use of stdin by sending
EOF at first read, like if it is connected to /dev/null.

If not specified, its value is managed by the :ref:`defaults-config`.
Its default value in :class:`.Defaults` is set to ``True`` for backward
compatibility, but could change in a future major release.

If your program doesn't plan to listen to stdin, it is recommended to set
``stdin=False`` when calling these two methods.

.. highlight:: console

Packaging changes
"""""""""""""""""

We recommend that package maintainers use separate subpackages for Python 2
and Python 3, to install ClusterShell modules and related command line tools.
The Python 2 and Python 3 stacks should be fully installable in parallel.

For the RPM packaging, there is now two subpackages
``python2-clustershell`` and ``python3-clustershell`` (or
``python34-clustershell`` in EPEL), each providing
the library and tools for the corresponding version of Python.

The ``clustershell`` package includes the common configuration files and
documentation and requires ``python2-clustershell``, mainly because
Python 2 is still the default interpreter on most operating systems.

``vim-clustershell`` was confusing so we removed it and added the vim
extensions to the main ``clustershell`` subpackage.

Version 1.8 should be readily available as RPMs in the following
distributions or RPM repositories:

* EPEL 6 and 7
* Fedora 26 and 27
* openSUSE Factory and Leap

On a supported environment, you can expect a smooth upgrade from version 1.6+.

We also expect the packaging to be updated for Debian.

Version 1.7
-----------

It's just a small version bump from the well-known 1.6 version, but
ClusterShell 1.7 comes with some nice new features that we hope you'll enjoy!
Most of these features have already been tested on some very large Linux
production systems.

Version 1.7 and possible future minor versions 1.7.x are compatible with
Python 2.4 up to Python 2.7 (for example: from RedHat EL5 to EL7). Upgrade
from version 1.6 to 1.7 should be painless and is fully supported.


Version 1.7.3
^^^^^^^^^^^^^

This update contains a few bug fixes and some interesting performance
improvements. This is also the first release published under the
GNU Lesser General Public License, version 2.1 or later (`LGPL v2.1+`_).
Previous releases were published under the `CeCILL-C V1`_.

Quite a bit of work has been done on the *fanout* of processes that the library
uses to execute commands. We implemenented a basic per-worker *fanout* to fix
the broken behaviour in tree mode. Thanks to this, it is now possible to use
fanout=1 with gateways. The :ref:`documentation <clush-tree-fanout>` has also
been clarified.

An issue that led to broken pipe errors but also affected performance has been
fixed in :ref:`tree mode <clush-tree>` when copying files.

An issue with :ref:`clush-tool` -L where nodes weren't always properly sorted
has been fixed.

The performance of :class:`.MsgTree`, the class used by the library to
aggregate identical command outputs, has been improved. We have seen up to 75%
speed improvement in some cases.

Finally, a :ref:`cluset <cluset-tool>` command has been added to avoid a
conflict with `xCAT`_ nodeset command. It is the same command as
:ref:`nodeset-tool`.

For more details, please have a look at `GitHub Issues for 1.7.3 milestone`_.

ClusterShell 1.7.3 is compatible with Python 2.4 up to Python 2.7 (for
example: from RedHat EL5 to EL7). Upgrades from versions 1.6 or 1.7 are
supported.

Version 1.7.2
^^^^^^^^^^^^^

This minor version fixes a defect in :ref:`tree mode <clush-tree>` that led
to broken pipe errors or unwanted backtraces.

The :class:`.NodeSet` class now supports the empty string as input. In
practice, you may now safely reuse the output of a
:ref:`nodeset <nodeset-tool>` command as input argument for another
:ref:`nodeset <nodeset-tool>` command, even if the result is an empty string.

A new option ``--pick`` is available for :ref:`clush <clush-pick>` and
:ref:`nodeset <nodeset-pick>` to pick N node(s) at random from the resulting
node set.

For more details, please have a look at `GitHub Issues for 1.7.2 milestone`_.

ClusterShell 1.7.2 is compatible with Python 2.4 up to Python 2.7 (for
example: from RedHat EL5 to EL7). Upgrades from versions 1.6 or 1.7 are
supported.

Version 1.7.1
^^^^^^^^^^^^^

This minor version contains a few bug fixes, mostly related to
:ref:`guide-NodeSet`.

This version also contains bug fixes and performance improvements in tree
propagation mode.

For more details, please have a look at `GitHub Issues for 1.7.1 milestone`_.

ClusterShell 1.7.1 is compatible with Python 2.4 up to Python 2.7 (for
example: from RedHat EL5 to EL7). Upgrades from versions 1.6 or 1.7 are
supported.

Main changes in 1.7
^^^^^^^^^^^^^^^^^^^

This new version comes with a refreshed documentation, based on the Sphinx
documentation generator, available on http://clustershell.readthedocs.org.

The main new features of version 1.7 are described below.

Multidimensional nodesets
"""""""""""""""""""""""""

The :class:`.NodeSet` class and :ref:`nodeset <nodeset-tool>` command-line
have been improved to support multidimentional node sets with folding
capability. The use of nD naming scheme is sometimes used to map node names to
physical location like ``name-<rack>-<position>`` or node position within the
cluster interconnect network topology.

A first example of 3D nodeset expansion is a good way to start::

    $ nodeset -e gpu-[1,3]-[4-5]-[0-6/2]
    gpu-1-4-0 gpu-1-4-2 gpu-1-4-4 gpu-1-4-6 gpu-1-5-0 gpu-1-5-2 gpu-1-5-4
    gpu-1-5-6 gpu-3-4-0 gpu-3-4-2 gpu-3-4-4 gpu-3-4-6 gpu-3-5-0 gpu-3-5-2
    gpu-3-5-4 gpu-3-5-6

You've probably noticed the ``/2`` notation of the last dimension. It's called
a step and behaves as one would expect, and is fully supported with nD
nodesets.

All other :ref:`nodeset <nodeset-tool>` commands and options are supported
with nD nodesets. For example, it's always useful to have a quick way to count
the number of nodes in a nodeset::

    $ nodeset -c gpu-[1,3]-[4-5]-[0-6/2]
    16

Then to show the most interesting new capability of the underlying
:class:`.NodeSet` class in version 1.7, a folding example is probably
appropriate::

    $ nodeset -f compute-1-[1-34] compute-2-[1-34]
    compute-[1-2]-[1-34]

In the above example, nodeset will try to find a very compact nodesets
representation whenever possible. ClusterShell is probably the first and only
cluster tool capable of doing such complex nodeset folding.

Attention, as not all cluster tools are supporting this kind of complex
nodesets, even for nodeset expansion, we added an ``--axis`` option to select
to fold along some desired dimension::

    $ nodeset --axis 2 -f compute-[1-2]-[1-34]
    compute-1-[1-34],compute-2-[1-34]

The last dimension can also be selected using ``-1``::

    $ nodeset --axis -1 -f compute-[1-2]-[1-34]
    compute-1-[1-34],compute-2-[1-34]

All set-like operations are also supported with several dimensions, for
example *difference* (``-x``)::

    $ nodeset -f c-[1-10]-[1-44] -x c-[5-10]-[1-34]
    c-[1-4]-[1-44],c-[5-10]-[35-44]

Hard to follow? Don't worry, ClusterShell does it for you!

File-based node groups
""""""""""""""""""""""

Cluster node groups have been a great success of previous version of
ClusterShell and are now widely adopted. So we worked on improving it even
more for version 1.7.

For those of you who use the file ``/etc/clustershell/group`` to describe
node groups, that is still supported in 1.7 and upgrade from your 1.6 setup
should work just fine. However, for new 1.7 installations, we have put this
file in a different location by default::

    $ vim /etc/clustershell/groups.d/local.cfg

Especially if you're starting a new setup, you have also the choice to switch
to a more advanced groups YAML configuration file that can define multiple
*sources* in a single file (equivalent to separate namespaces for node
groups). The YAML format possibly allows you to edit the file content with
YAML tools but it's also a file format convenient to edit just using the vim
editor. To enable the example file, you need to rename it first as it needs to
have the **.yaml** extension::

    $ cd /etc/clustershell/groups.d
    $ mv cluster.yaml.example cluster.yaml

You can make the first dictionary found on this file (named *roles*) to be the
**default** source by changing ``default: local`` to ``default: roles`` in
``/etc/clustershell/groups.conf`` (main config file for groups).

For more info about the YAML group files, please see :ref:`group-file-based`.

Please also see :ref:`node groups configuration <groups-config>` for node
groups configuration in general.

nodeset -L/--list-all option
""""""""""""""""""""""""""""

Additionally, the :ref:`nodeset <nodeset-tool>` command also has a new option
``-L`` or ``--list-all`` to list groups from all sources (``-l`` only lists
groups from the **default** source). This can be useful when configuring
ClusterShell and/or troubleshooting node group sources::

    $ nodeset -LL
    @adm example0
    @all example[2,4-5,32-159]
    @compute example[32-159]
    @gpu example[156-159]
    @io example[2,4-5]
    @racks:new example[4-5,156-159]
    @racks:old example[0,2,32-159]
    @racks:rack1 example[0,2]
    @racks:rack2 example[4-5]
    @racks:rack3 example[32-159]
    @racks:rack4 example[156-159]
    @cpu:hsw example[64-159]
    @cpu:ivy example[32-63]

Special group @*
""""""""""""""""

The special group syntax ``@*`` (or ``@source:*`` if using explicit source
selection) has been added and can be used in configuration files or with
command line tools. This special group is always available for file-based node
groups (return the content of the **all** group, or all groups from the source
otherwise). For external sources, it is available when either the **all**
upcall is defined or both **map** and **list** upcalls are defined. The all
special group is also used by ``clush -a`` and ``nodeset -a``. For example,
the two following commands are equivalent::

    $ nodeset -a -f
    example[2,4-5,32-159]

    $ nodeset -f @*
    example[2,4-5,32-159]

Exec worker
"""""""""""

Version 1.7 introduces a new generic execution worker named
:class:`.ExecWorker` as the new base class for most exec()-based worker
classes. In practice with :ref:`clush-tool`, you can now specify the worker in
command line using ``--worker`` or ``-R`` and use **exec**. It also supports
special placeholders for the node (**%h**) or rank (**%n**). For example, the
following command will execute *ping* commands in parallel, each with a
different host from hosts *cs01*, etc. to *cs05* as argument and then
aggregate the results::

    $ clush -R exec -w cs[01-05] -bL 'ping -c1 %h >/dev/null && echo ok'
    cs[01-04]: ok
    clush: cs05: exited with exit code 1

This feature allows the system administrator to use non cluster-aware tools in
a more efficient way. You may also want to explicitly set the fanout (using
``-f``) to limit the number of parallel local commands launched.

Please see also :ref:`clush worker selection <clush-worker>`.

Rsh worker
""""""""""

Version 1.7 adds support for ``rsh`` or any of its variants like ``krsh`` or
``mrsh``.
``rsh`` and ``ssh`` also share a lot of common mechanisms. Worker Rsh was
added moving a lot of Worker Ssh code into it.

For ``clush``, please see :ref:`clush worker selection <clush-worker>` to
enable ``rsh``.

To use ``rsh`` by default instead of ``ssh`` at the library level, install the
provided example file named ``defaults.conf-rsh`` to
``/etc/clustershell/defaults.conf``.

Tree Propagation Mode
"""""""""""""""""""""

The ClusterShell Tree Mode allows you to send commands to target nodes through
a set of predefined gateways (using ssh by default). It can be useful to
access servers that are behind some other servers like bastion hosts, or to
scale on very large clusters when the flat mode (eg. sliding window of ssh
commands) is not enough anymore.

The tree mode is now :ref:`documented <clush-tree>`, it has been improved and
is enabled by default when a ``topology.conf`` file is found. While it is still
a work in progress, the tree mode is known to work pretty well when all gateways
are online. We'll continue to improve it and make it more robust in the next
versions.

Configuration files
"""""""""""""""""""

When ``$XDG_CONFIG_HOME`` is defined, ClusterShell will use it to search for
additional configuration files.

PIP user installation support
"""""""""""""""""""""""""""""

ClusterShell 1.7 is now fully compatible with PIP and supports user
configuration files::

    $ pip install --user clustershell

Please see :ref:`install-pip-user`.

.. _GitHub Issues for 1.7.1 milestone: https://github.com/cea-hpc/clustershell/issues?utf8=%E2%9C%93&q=is%3Aissue+milestone%3A1.7.1
.. _GitHub Issues for 1.7.2 milestone: https://github.com/cea-hpc/clustershell/issues?utf8=%E2%9C%93&q=is%3Aissue+milestone%3A1.7.2
.. _GitHub Issues for 1.7.3 milestone: https://github.com/cea-hpc/clustershell/issues?utf8=%E2%9C%93&q=is%3Aissue+milestone%3A1.7.3
.. _GitHub Issues for 1.8 milestone: https://github.com/cea-hpc/clustershell/issues?utf8=%E2%9C%93&q=is%3Aissue+milestone%3A1.8
.. _GitHub Issues for 1.8.1 milestone: https://github.com/cea-hpc/clustershell/issues?utf8=%E2%9C%93&q=is%3Aissue+milestone%3A1.8.1
.. _GitHub Issues for 1.8.2 milestone: https://github.com/cea-hpc/clustershell/issues?utf8=%E2%9C%93&q=is%3Aissue+milestone%3A1.8.2
.. _GitHub Issues for 1.8.3 milestone: https://github.com/cea-hpc/clustershell/issues?utf8=%E2%9C%93&q=is%3Aissue+milestone%3A1.8.3
.. _GitHub Issues for 1.8.4 milestone: https://github.com/cea-hpc/clustershell/issues?utf8=%E2%9C%93&q=is%3Aissue+milestone%3A1.8.4
.. _LGPL v2.1+: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
.. _CeCILL-C V1: http://www.cecill.info/licences/Licence_CeCILL-C_V1-en.html
.. _xCAT: https://xcat.org/
