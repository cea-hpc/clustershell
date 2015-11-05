.. highlight:: console

Release Notes
=============

Version 1.7
-----------

It's just a small version bump from the now well-known 1.6 version, but
ClusterShell 1.7 comes with some nice new features that we hope you'll enjoy!
Most of these features have already been tested on some very large Linux
production systems.

This new version also comes with a refreshed documentation, based on the
Sphinx documentation generator, available on
http://clustershell.readthedocs.org.

We hope this new release will help you manage your clusters, server farms or
cloud farms! Special thanks to the many of you that have sent us feedback on
Github!


Maintenance release
^^^^^^^^^^^^^^^^^^^

Version 1.7 and possible future minor versions 1.7.x are compatible with
Python 2.4 up to Python 2.7 (for example: from RedHat EL5 to EL7). Upgrade
from version 1.6 to 1.7 should be painless and are fully supported.

The next major version of ClusterShell will require at least Python 2.6. We
will also soon start working on Python 3 support.

New features
^^^^^^^^^^^^

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

    $ pip --user clustershell

Please see :ref:`install-pip-user`.
