Configuration
=============

.. highlight:: ini

.. _clush-config:

clush
-----

The following configuration file defines system-wide default values for
several *clush* tool parameters::

    /etc/clustershell/clush.conf

*clush* settings might then be overridden per user if one of the following
files is found, in priority order::

    $XDG_CONFIG_HOME/clustershell/clush.conf
    $HOME/.config/clustershell/clush.conf (only if $XDG_CONFIG_HOME is not defined)
    $HOME/.local/etc/clustershell/clush.conf
    $HOME/.clush.conf (deprecated, for 1.6 compatibility only)

The following table describes available *clush* config file settings.

+-----------------+----------------------------------------------------+
| Key             | Value                                              |
+=================+====================================================+
| fanout          | Size of the sliding window of *ssh(1)* connectors. |
+-----------------+----------------------------------------------------+
| connect_timeout | Timeout in seconds to allow a connection to        |
|                 | establish. This parameter is passed to *ssh(1)*.   |
|                 | If set to 0, no timeout occurs.                    |
+-----------------+----------------------------------------------------+
| command_timeout | Timeout in seconds to allow a command to complete  |
|                 | since the connection has been established. This    |
|                 | parameter is passed to *ssh(1)*. In addition, the  |
|                 | ClusterShell library ensures that any commands     |
|                 | complete in less than (connect_timeout \+          |
|                 | command_timeout). If set to 0, no timeout occurs.  |
+-----------------+----------------------------------------------------+
| color           | Whether  to  use  ANSI  colors  to  surround node  |
|                 | or nodeset prefix/header with escape sequences to  |
|                 | display them in color on the terminal. Valid       |
|                 | arguments are *never*, *always* or *auto* (which   |
|                 | use color if standard output/error refer to a      |
|                 | terminal).                                         |
|                 | Colors are set to ``[34m`` (blue foreground text)  |
|                 | for stdout and ``[31m`` (red foreground text) for  |
|                 | stderr, and cannot be modified.                    |
+-----------------+----------------------------------------------------+
| fd_max          | Maximum  number  of  open  file descriptors        |
|                 | permitted per *clush* process (soft resource limit |
|                 | for open files). This limit can never exceed the   |
|                 | system (hard) limit. The *fd_max* (soft) and       |
|                 | system (hard) limits should be high enough to      |
|                 | run *clush*, although their values depend on       |
|                 | your fanout value.                                 |
+-----------------+----------------------------------------------------+
| history_size    | Set the maximum number of history entries saved in |
|                 | the GNU readline history list. Negative values     |
|                 | imply unlimited history file size.                 |
+-----------------+----------------------------------------------------+
| node_count      | Should *clush* display additional (node count)     |
|                 | information in buffer header? (yes/no)             |
+-----------------+----------------------------------------------------+
| verbosity       | Set the verbosity level: 0 (quiet), 1 (default),   |
|                 | 2 (verbose) or more (debug).                       |
+-----------------+----------------------------------------------------+
| ssh_user        | Set the *ssh(1)* user to use for remote connection |
|                 | (default is to not specify).                       |
+-----------------+----------------------------------------------------+
| ssh_path        | Set the *ssh(1)* binary path to use for remote     |
|                 | connection (default is *ssh*).                     |
+-----------------+----------------------------------------------------+
| ssh_options     | Set additional (raw) options to pass to the        |
|                 | underlying *ssh(1)* command.                       |
+-----------------+----------------------------------------------------+
| scp_path        | Set the *scp(1)* binary path to use for remote     |
|                 | copy (default is *scp*).                           |
+-----------------+----------------------------------------------------+
| scp_options     | Set additional options to pass to the underlying   |
|                 | *scp(1)* command. If not specified, *ssh_options*  |
|                 | are used instead.                                  |
+-----------------+----------------------------------------------------+
| rsh_path        | Set the *rsh(1)* binary path to use for remote     |
|                 | connection (default is *rsh*). You could easily    |
|                 | use *mrsh* or *krsh* by simply changing this       |
|                 | value.                                             |
+-----------------+----------------------------------------------------+
| rcp_path        | Same as *rsh_path* but for rcp command (default is |
|                 | *rcp*).                                            |
+-----------------+----------------------------------------------------+
| rsh_options     | Set additional options to pass to the underlying   |
|                 | rsh/rcp command.                                   |
+-----------------+----------------------------------------------------+


.. _groups-config:

Node groups
-----------

ClusterShell defines a *node group* syntax to represent a collection of nodes.
This is a convenient way to manipulate node sets, especially in HPC (High
Performance Computing) or with large server farms. This section explains how
to configure node group **sources**. Please see also :ref:`nodeset node groups
<nodeset-groups>` for specific usage examples.

.. _groups_config_conf:

groups.conf
^^^^^^^^^^^

ClusterShell loads *groups.conf* configuration files that define how to
obtain node groups configuration, ie. the way the library should access
file-based or external node group **sources**.

The following configuration file defines system-wide default values for
*groups.conf*::

    /etc/clustershell/groups.conf

*groups.conf* settings might then be overridden per user if one of the
following files is found, in priority order::

    $XDG_CONFIG_HOME/clustershell/groups.conf
    $HOME/.config/clustershell/groups.conf (only if $XDG_CONFIG_HOME is not defined)
    $HOME/.local/etc/clustershell/groups.conf

This makes possible for an user to have its own *node groups* configuration.
If no readable configuration file is found, group support will be disabled but
other node set operations will still work.

*groups.conf* defines configuration sub-directories, but may also define
source definitions by itself. These **sources** provide external calls that
are detailed in :ref:`group-external-sources`.

The following example shows the content of a *groups.conf* file where node
groups are bound to the source named *genders* by default::

    [Main]
    default: genders
    confdir: /etc/clustershell/groups.conf.d $CFGDIR/groups.conf.d
    autodir: /etc/clustershell/groups.d $CFGDIR/groups.d

    [genders]
    map: nodeattr -n $GROUP
    all: nodeattr -n ALL
    list: nodeattr -l

    [slurm]
    map: sinfo -h -o "%N" -p $GROUP
    all: sinfo -h -o "%N"
    list: sinfo -h -o "%P"
    reverse: sinfo -h -N -o "%P" -n $NODE

The *groups.conf* files are parsed with Python's `ConfigParser`_:

* The first section whose name is *Main* accepts the following keywords:

  * *default* defines a **default node group source** (eg. by referencing a
    valid section header)
  * *confdir* defines an optional list of directory paths where the
    ClusterShell library should look for **.conf** files which define group
    sources to use.  Each file in these directories with the .conf suffix
    should contain one or more node group source sections as documented below.
    These will be merged with the group sources defined in the main
    *groups.conf* to form the complete set of group sources to use. Duplicate
    group source sections are not allowed in those files. Configuration files
    that are not readable by the current user are ignored (except the one that
    defines the default group source). The variable `$CFGDIR` is replaced by
    the path of the highest priority configuration directory found (where
    *groups.conf* resides). The default *confdir* value enables both
    system-wide and any installed user configuration (thanks to `$CFGDIR`).
    Duplicate directory paths are ignored.
  * *autodir* defines an optional list of directories where the ClusterShell
    library should look for **.yaml** files that define in-file group
    dictionaries. No need to call external commands for these files, they are
    parsed by the ClusterShell library itself. Multiple group source
    definitions in the same file is supported. The variable `$CFGDIR` is
    replaced by the path of the highest priority configuration directory found
    (where *groups.conf* resides). The default *confdir* value enables both
    system-wide and any installed user configuration (thanks to `$CFGDIR`).
    Duplicate directory paths are ignored.

* Each following section (`genders`, `slurm`) defines a  group source. The
  map, all, list and reverse upcalls are explained below in
  :ref:`group-sources-upcalls`.

.. _group-file-based:

File-based group sources
^^^^^^^^^^^^^^^^^^^^^^^^

Version 1.7 introduces support for native handling of flat files with
different group sources to avoid the use of external upcalls for such static
configuration. This can be achieved through the *autodir* feature and YAML
files described below.

YAML group files
""""""""""""""""

Cluster node groups can be defined in straightforward YAML files. In such a
file, each YAML dictionary defines group to nodes mapping. **Different
dictionaries** are handled as **different group sources**.

For compatibility reasons with previous versions of ClusterShell, this is not
the default way to define node groups yet. So here are the steps needed to try
this out:

Rename the following file::

    /etc/clustershell/groups.d/cluster.yaml.example

to a file having the **.yaml** extension, for example::

  /etc/clustershell/groups.d/cluster.yaml


Ensure that *autodir* is set in :ref:`groups_config_conf`::

  autodir: /etc/clustershell/groups.d $CFGDIR/groups.d

In the following example, we also changed the default group source
to **roles** in :ref:`groups_config_conf` (the first dictionary defined in
the example), so that *@roles:groupname* can just be shorted *@groupname*.

.. highlight:: yaml

Here is an example of **/etc/clustershell/groups.d/cluster.yaml**::

    roles:
        adm: 'mgmt[1-2]'                 # define groups @roles:adm and @adm
        login: 'login[1-2]'
        compute: 'node[0001-0288]'
        gpu: 'node[0001-0008]'

        cpu_only: '@compute!@gpu'        # example of inline set operation
                                         # define group @cpu_only with node[0009-0288]

        storage: '@lustre:mds,@lustre:oss' # example of external source reference

        all: '@login,@compute,@storage'  # special group used for clush/nodeset -a
                                         # only needed if not including all groups

    lustre:
        mds: 'mds[1-4]'
        oss: 'oss[0-15]'
        rbh: 'rbh[1-2]'

.. highlight:: console

Testing the syntax of your group file can be quickly performed through the
``-L`` or ``--list-all`` command of :ref:`nodeset-tool`::

    $ nodeset -LL
    @adm mgmt[1-2]
    @all login[1-2],mds[1-4],node[0001-0288],oss[0-15],rbh[1-2]
    @compute node[0001-0288]
    @cpu_only node[0009-0288]
    @gpu node[0001-0008]
    @login login[1-2]
    @storage mds[1-4],oss[0-15],rbh[1-2]
    @sysgrp sysgrp[1-4]
    @lustre:mds mds[1-4]
    @lustre:oss oss[0-15]
    @lustre:rbh rbh[1-2]

.. _group-external-sources:

External group sources
^^^^^^^^^^^^^^^^^^^^^^

.. _group-sources-upcalls:

Group source upcalls
""""""""""""""""""""

Each node group source is defined by a section name (*source* name) and up to
four upcalls:

* **map**: External shell command used to resolve a group name into a node
  set, list of nodes or list of node sets (separated by space characters or by
  carriage returns). The variable *$GROUP* is replaced before executing the command.
* **all**: Optional external shell command that should return a node set, list
  of nodes or list of node sets of all nodes for this group source. If not
  specified, the library will try to resolve all nodes by using the **list**
  external command in the same group source followed by **map** for each
  available group. The notion of *all nodes* is used by ``clush -a`` and also
  by the special group name ``@*`` (or ``@source:*``).
* **list**: Optional external shell command that should return the list of all
  groups for this group source (separated by space characters or by carriage
  returns). If this upcall is not specified, ClusterShell won't be able to
  list any available groups (eg. with ``nodeset -l``), so it is highly
  recommended to set it.
* **reverse**: Optional external shell command used to find the group(s) of a
  single node. The variable *$NODE* is previously replaced. If this external
  call is not specified, the reverse operation is computed in memory by the
  library from the **list** and **map** external calls, if available. Also, if
  the number of nodes to reverse is greater than the number of available
  groups, the reverse external command is avoided automatically to reduce
  resolution time.

In addition to context-dependent *$GROUP* and *$NODE* variables described
above, the two following variables are always available and also replaced
before executing shell commands:

* *$CFGDIR* is replaced by *groups.conf* base directory path
* *$SOURCE* is replaced by current source name (see an usage example just
  below)

Multiple sources section
""""""""""""""""""""""""

.. highlight:: ini

Use a comma-separated list of source names in the section header if you want
to define multiple group sources with similar upcall commands. The special
variable `$SOURCE` is always replaced by the source name before command
execution (here `cluster`, `racks` and `cpu`), for example::

    [cluster,racks,cpu]
    map: get_nodes_from_source.sh $SOURCE $GROUP
    all: get_all_nodes_from_source.sh $SOURCE
    list: list_nodes_from_source.sh $SOURCE

is equivalent to::

    [cluster]
    map: get_nodes_from_source.sh cluster $GROUP
    all: get_all_nodes_from_source.sh cluster
    list: list_nodes_from_source.sh cluster

    [racks]
    map: get_nodes_from_source.sh racks $GROUP
    all: get_all_nodes_from_source.sh racks
    list: list_nodes_from_source.sh racks

    [cpu]
    map: get_nodes_from_source.sh cpu $GROUP
    all: get_all_nodes_from_source.sh cpu
    list: list_nodes_from_source.sh cpu

Return code of external calls
"""""""""""""""""""""""""""""

Each external command might return a non-zero return code when the operation
is not doable. But if the call return zero, for instance, for a non-existing
group, the user will not receive any error when trying to resolve such unknown
group. The desired behavior is up to the system administrator.


.. _defaults-config:

Library Defaults
----------------

.. warning:: Modifying library defaults is for advanced users only as that
   could change the behavior of tools using ClusterShell. Moreover, tools are
   free to enforce their own defaults, so changing library defaults may not
   change a global behavior as expected.

Since version 1.7, most defaults of the ClusterShell library may be overridden
in *defaults.conf*.

The following configuration file defines ClusterShell system-wide defaults::

    /etc/clustershell/defaults.conf

*defaults.conf* settings might then be overridden per user if one of the
following files is found, in priority order::

    $XDG_CONFIG_HOME/clustershell/defaults.conf
    $HOME/.config/clustershell/defaults.conf (only if $XDG_CONFIG_HOME is not defined)
    $HOME/.local/etc/clustershell/defaults.conf


.. _ConfigParser: http://docs.python.org/library/configparser.html
