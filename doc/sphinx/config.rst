Configuration
=============

.. highlight:: ini

clush
-----

.. _clush-config:

clush.conf
^^^^^^^^^^

The *clush.conf* files are parsed with Python's `ConfigParser`_

Locations
"""""""""

The following configuration file defines system-wide default values for
several ``clush`` tool parameters::

    /etc/clustershell/clush.conf

``clush`` settings might then be overridden (globally, or per user) if one of
the following files is found, in priority order::

    $XDG_CONFIG_HOME/clustershell/clush.conf
    $HOME/.config/clustershell/clush.conf (only if $XDG_CONFIG_HOME is not defined)
    {sys.prefix}/etc/clustershell/clush.conf
    $HOME/.local/etc/clustershell/clush.conf
    $HOME/.clush.conf (deprecated, for 1.6 compatibility only)

.. note:: The path using `sys.prefix`_ was added in version 1.9.1 and is
   useful for Python virtual environments.

In addition, if the environment variable ``$CLUSTERSHELL_CFGDIR`` is defined and
valid, it will used instead. In such case, the following configuration file
will be tried first for ``clush``::

    $CLUSTERSHELL_CFGDIR/clush.conf

Settings
""""""""

Settings that apply to all ``clush`` :ref:`run modes <clushmode-config>` are
contained within the ``[Main]`` section.

The following table describes available ``clush`` config file settings.

+-----------------+----------------------------------------------------+
| Key             | Value                                              |
+=================+====================================================+
| fanout          | Size of the sliding window of connectors (eg. max  |
|                 | number of *ssh(1)* allowed to run at the same      |
|                 | time).                                             |
+-----------------+----------------------------------------------------+
| confdir         | Optional list of directory paths where ``clush``   |
|                 | should look for **.conf** files which define       |
|                 | :ref:`run modes <clushmode-config>` that can then  |
|                 | be activated with `--mode`. All other ``clush``    |
|                 | config file settings defined in this table might   |
|                 | be overridden in a run mode. Each mode section     |
|                 | should have a name prefixed by "mode:" to clearly  |
|                 | identify a section defining a mode. Duplicate      |
|                 | modes are not allowed in those files.              |
|                 | Configuration files that are not readable by the   |
|                 | current user are ignored. The variable `$CFGDIR`   |
|                 | is replaced by the path of the highest priority    |
|                 | configuration directory found (where *clush.conf*  |
|                 | resides). The default *confdir* value enables both |
|                 | system-wide and any installed user configuration   |
|                 | (thanks to `$CFGDIR`). Duplicate directory paths   |
|                 | are ignored.                                       |
+-----------------+----------------------------------------------------+
| connect_timeout | Timeout in seconds to allow a connection to        |
|                 | establish. This parameter is passed to *ssh(1)*.   |
|                 | If set to 0, no timeout occurs.                    |
+-----------------+----------------------------------------------------+
| command_prefix  | Command prefix. Generally used for specific        |
|                 | :ref:`run modes <clush-modes>`, for example to     |
|                 | implement *sudo(8)* support.                       |
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
|                 | permitted per ``clush`` process (soft resource     |
|                 | limit for open files). This limit can never exceed |
|                 | the system (hard) limit. The *fd_max* (soft) and   |
|                 | system (hard) limits should be high enough to      |
|                 | run ``clush``, although their values depend on     |
|                 | your fanout value.                                 |
+-----------------+----------------------------------------------------+
| history_size    | Set the maximum number of history entries saved in |
|                 | the GNU readline history list. Negative values     |
|                 | imply unlimited history file size.                 |
+-----------------+----------------------------------------------------+
| node_count      | Should ``clush`` display additional (node count)   |
|                 | information in buffer header? (yes/no)             |
+-----------------+----------------------------------------------------+
| maxrc           | Should ``clush`` return the largest of command     |
|                 | return codes? (yes/no)                             |
|                 | If set to no (the default), ``clush`` exit status  |
|                 | gives no information about command return codes,   |
|                 | but rather reports on ``clush`` execution itself   |
|                 | (zero indicating a successful run).                |
+-----------------+----------------------------------------------------+
| password_prompt | Enable password prompt and password forwarding to  |
|                 | stdin? (yes/no)                                    |
|                 | Generally used for specific                        |
|                 | :ref:`run modes <clush-modes>`, for example to     |
|                 | implement interactive *sudo(8)* support.           |
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

.. _clushmode-config:

Run modes
^^^^^^^^^

Since version 1.9, ``clush`` has support for run modes, which are special
:ref:`clush-config` settings with a given name. Two run modes are provided in
example configuration files that can be copied and modified. They implement
password-based authentication with *sshpass(1)* and support of interactive
*sudo(8)* with password.

To use a run mode with ``clush --mode``, install a configuration file in one
of :ref:`clush-config`'s ``confdir`` (usually ``clush.conf.d``).  Only
configuration files ending in **.conf** are scanned. If the user running
``clush`` doesn't have read access to a configuration file, it is ignored.
When ``--mode`` is specified, you can display all available run modes for
the current user by enabling debug mode (``-d``).

Example of a run mode configuration file (eg.
``/etc/clustershell/clush.conf.d/sudo.conf``) to add support for interactive
sudo::

    [mode:sudo]
    password_prompt: yes
    command_prefix: /usr/bin/sudo -S -p "''"

System administrators or users can easily create additional run modes by
adding configuration files to :ref:`clush-config`'s ``confdir``.

More details about using run modes can be found :ref:`here <clush-modes>`.

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

*groups.conf* settings might then be overridden (globally, or per user) if one
of the following files is found, in priority order::

    $XDG_CONFIG_HOME/clustershell/groups.conf
    $HOME/.config/clustershell/groups.conf (only if $XDG_CONFIG_HOME is not defined)
    {sys.prefix}/etc/clustershell/groups.conf
    $HOME/.local/etc/clustershell/groups.conf

.. note:: The path using `sys.prefix`_ was added in version 1.9.1 and is
   useful for Python virtual environments.

In addition, if the environment variable ``$CLUSTERSHELL_CFGDIR`` is defined and
valid, it will used instead. In such case, the following configuration file
will be tried first for *groups.conf*::

    $CLUSTERSHELL_CFGDIR/groups.conf

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

        servers:                         # example of yaml list syntax for nodes
            - 'server001'                # in a group
            - 'server002,server101'                
            - 'server[003-006]'

        cpu_only: '@compute!@gpu'        # example of inline set operation
                                         # define group @cpu_only with node[0009-0288]

        storage: '@lustre:mds,@lustre:oss' # example of external source reference

        all: '@login,@compute,@storage'  # special group used for clush/nodeset -a
                                         # only needed if not including all groups

    lustre:
        mds: 'mds[1-4]'
        oss: 'oss[0-15]'
        rbh: 'rbh[1-2]'


If you wish to define an empty group (with no nodes), you can either use an
empty string ``''`` or any valid YAML null value (``null`` or ``~``).

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

.. _group-external-caching:

Caching considerations
""""""""""""""""""""""

External command results are cached in memory, for a limited amount of time,
to avoid multiple similar calls.

The optional parameter **cache_time**, when specified within a group source
section, defines the number of seconds each upcall result is kept in cache,
in memory only. Please note that caching is actually only useful for
long-running programs (like daemons) that are using node groups, not for
one-shot commands like :ref:`clush <clush-tool>` or
:ref:`cluset <cluset-tool>`/:ref:`nodeset <nodeset-tool>`.

The default value of **cache_time** is 3600 seconds.

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

.. _group-slurm-bindings:

Slurm group bindings
""""""""""""""""""""

Enable Slurm node group bindings by renaming the example configuration file
usually installed as ``/etc/clustershell/groups.conf.d/slurm.conf.example`` to
``slurm.conf``. Three group sources are defined in this file and are detailed
below. Each section comes with a long and short names (for convenience), but
actually defines a same group source.

While examples below are based on the :ref:`nodeset-tool` tool, all Python
tools using ClusterShell and the :class:`.NodeSet`  class will automatically
benefit from these additional node groups.

.. highlight:: ini

The first section **slurmpart,sp** defines a group source based on Slurm
partitions. Each group is named after the partition name and contains the
partition's nodes::

    [slurmpart,sp]
    map: sinfo -h -o "%N" -p $GROUP
    all: sinfo -h -o "%N"
    list: sinfo -h -o "%R"
    reverse: sinfo -h -N -o "%R" -n $NODE

.. highlight:: console

Example of use with :ref:`nodeset <nodeset-tool>` on a cluster having two Slurm
partitions named *kepler* and *pascal*::

    $ nodeset -s sp -ll
    @sp:kepler cluster-[0001-0065]
    @sp:pascal cluster-[0066-0068]

.. highlight:: ini

The second section **slurmresv,sr** defines a group source based on Slurm
reservations. Each group is based on a different reservation and contains
the nodes currently in that reservation::

    [slurmresv,sr]
    map: scontrol -o show reservation $GROUP | grep -Po 'Nodes=\K[^ ]+'
    all: scontrol -o show reservation | grep -Po 'Nodes=\K[^ ]+'
    list: scontrol -o show reservation | grep -Po 'ReservationName=\K[^ ]+'
    cache_time: 60

.. highlight:: console

Example of use on a cluster having a reservation in place for an upcoming
system maintenance::

    $ nodeset -s slurmresv -l
    @slurmresv:Maintenance_2025-02-04
    $ clush -w @slurmresv:Maintenance_2025-02-04 uptime

.. highlight:: ini

The next section **slurmstate,st** defines a group source based on Slurm
node states. Each group is based on a different state name and contains the
nodes currently in that state::

    [slurmstate,st]
    map: sinfo -h -o "%N" -t $GROUP
    all: sinfo -h -o "%N"
    list: sinfo -h -o "%T" | tr -d '*~#$@+'
    reverse: sinfo -h -N -o "%T" -n $NODE | tr -d '*~#$@+'
    cache_time: 60

Here, :ref:`cache_time <group-external-caching>` is set to 60 seconds instead
of the default (3600s) to avoid caching results in memory for too long, in
case of state change (this is only useful for long-running processes, not
one-shot commands).

.. highlight:: console

Example of use with :ref:`nodeset <nodeset-tool>` to get the current nodes that
are in the Slurm state *drained*::

    $ nodeset -f @st:drained
    cluster-[0058,0067]

.. highlight:: ini

The next section **slurmjob,sj** defines a group source based on Slurm jobs.
Each group is based on a running job ID and contains the nodes currently
allocated for this job::

    [slurmjob,sj]
    map: squeue -h -j $GROUP -o "%N"
    list: squeue -h -o "%i" -t R
    reverse: squeue -h -w $NODE -o "%i"
    cache_time: 60

The next section **slurmuser,su** defines a group source based on Slurm users.
Each group is based on a username and contains the nodes currently
allocated for jobs belonging to the username::

    [slurmuser,su]
    map: squeue -h -u $GROUP -o "%N" -t R
    list: squeue -h -o "%u" -t R
    reverse: squeue -h -w $NODE -o "%i"
    cache_time: 60

.. highlight:: console

Example of use with :ref:`clush <clush-tool>` to execute a command on all nodes
with running jobs of username::

    $ clush -bw@su:username 'df -Ph /scratch'
    $ clush -bw@su:username 'du -s /scratch/username'

:ref:`cache_time <group-external-caching>` is also set to 60 seconds instead
of the default (3600s) to avoid caching results in memory for too long, because
this group source is likely very dynamic (this is only useful for long-running
processes, not one-shot commands).

.. highlight:: ini

The next section **slurmaccount,sa** defines a group source based on Slurm
accounts. Each group is based on a account and contains the nodes where there
are running jobs under this account::

    [slurmaccount,sa]
    map: squeue -h -A $GROUP -o "%N" -t R
    list: squeue -h -o "%a" -t R
    reverse: squeue -h -w $NODE -o "%a" 2>/dev/null || true
    cache_time: 60

.. highlight:: console

For example, to find all nodes that have running jobs from the account ``ruthm``::

    $ cluset -f @sa:ruthm
    sh02-01n57,sh03-09n51,sh03-11n10

.. highlight:: ini

The next section **slurmqos,sq** defines a group source based on Slurm QoS.
Each group is based on a qos and contains the nodes where there are running
jobs under this qos::

    [slurmqos,sq]
    map: squeue -h -q $GROUP -o "%N" -t R
    list: squeue -h -o "%q" -t R
    reverse: squeue -h -w $NODE -o "%q" 2>/dev/null || true
    cache_time: 60

.. highlight:: console

Then it is easy to find nodes currently running jobs in a specified qos, here
in qos ``long`` for example::

    $ cluset -f @slurmqos:long
    sh02-01n[01-02,16-17,45,51,56],sh03-01n[02,29,61]

.. _group-xcat-bindings:

xCAT group bindings
"""""""""""""""""""

Enable xCAT node group bindings by renaming the example configuration file
usually installed as ``/etc/clustershell/groups.conf.d/xcat.conf.example`` to
``xcat.conf``. A single group source is defined in this file and is detailed
below.

.. warning:: xCAT installs its own `nodeset`_ command which
   usually takes precedence over ClusterShell's :ref:`nodeset-tool` command.
   In that case, simply use :ref:`cluset <cluset-tool>` instead.

While examples below are based on the :ref:`cluset-tool` tool, all Python
tools using ClusterShell and the :class:`.NodeSet`  class will automatically
benefit from these additional node groups.

.. highlight:: ini

The section **xcat** defines a group source based on xCAT static node groups::

    [xcat]

    # list the nodes in the specified node group
    map: lsdef -s -t node $GROUP | cut -d' ' -f1
    
    # list all the nodes defined in the xCAT tables
    all: lsdef -s -t node | cut -d' ' -f1
    
    # list all groups
    list: lsdef -t group | cut -d' ' -f1

.. highlight:: console

Example of use with :ref:`cluset-tool`::

    $ lsdef -s -t node dtn
    sh-dtn01  (node)
    sh-dtn02  (node)
    
    $ cluset -s xcat -f @dtn
    sh-dtn[01-02]

.. highlight:: text

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

*defaults.conf* settings might then be overridden (globally, or per user) if
one of the following files is found, in priority order::

    $XDG_CONFIG_HOME/clustershell/defaults.conf
    $HOME/.config/clustershell/defaults.conf (only if $XDG_CONFIG_HOME is not defined)
    {sys.prefix}/etc/clustershell/defaults.conf
    $HOME/.local/etc/clustershell/defaults.conf

In addition, if the environment variable ``$CLUSTERSHELL_CFGDIR`` is defined and
valid, it will used instead. In such case, the following configuration file
will be tried first for ClusterShell defaults::

    $CLUSTERSHELL_CFGDIR/defaults.conf

Use case: rsh
^^^^^^^^^^^^^^

If your cluster uses a rsh variant like ``mrsh`` or ``krsh``, you may want to
change it in the library defaults.

An example file is usually available in
``/usr/share/doc/clustershell-*/examples/defaults.conf-rsh`` and could be
copied to ``/etc/clustershell/defaults.conf`` or to an alternate path
described above. Basically, the change consists in defining an alternate
distant worker by Python module name as follow::

    [task.default]
    distant_workername: Rsh


.. _defaults-config-slurm:

Use case: Slurm
^^^^^^^^^^^^^^^

If your cluster naming scheme has multiple dimensions, as in ``node-93-02``, we
recommend that you disengage some nD folding when using Slurm, which is
currently unable to detect some multidimensional node indexes when not
explicitly enclosed with square brackets.

To do so, define ``fold_axis`` to -1 in the :ref:`defaults-config` so that nD
folding is only computed on the last axis (seems to work best with Slurm)::

    [nodeset]
    fold_axis: -1

That way, node sets computed by ClusterShell tools can be passed to Slurm
without error.

.. _ConfigParser: http://docs.python.org/library/configparser.html
.. _nodeset: https://xcat-docs.readthedocs.io/en/stable/guides/admin-guides/references/man8/nodeset.8.html
.. _sys.prefix: https://docs.python.org/3/library/sys.html#sys.prefix
