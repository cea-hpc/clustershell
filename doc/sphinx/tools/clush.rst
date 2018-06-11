.. _clush-tool:

clush
-------

.. highlight:: console

*clush* is a program for executing commands in parallel on a cluster and for
gathering their results. It can execute commands interactively or can be used
within shell scripts and other applications. It is a partial front-end to the
:class:`.Task` class of the ClusterShell library (cf. :ref:`class-Task`).
*clush* currently makes use of the Ssh worker of ClusterShell that only
requires *ssh(1)* (we tested with OpenSSH SSH client).

Some features of *clush* command line tool are:

* two modes of parallel cluster commands execution:

  + :ref:`flat mode <clush-flat>`: sliding window of local or remote (eg.
    *ssh(1)*) commands
  + :ref:`tree mode <clush-tree>`: commands propagated to the targets
    through a tree of pre-configured gateways; gateways are then using a
    sliding window of local or *ssh(1)* commands to reach the targets (if the
    target count per gateway is greater than the
    :ref:`fanout <clush-tree-fanout>` value)

* smart display of command results (integrated output gathering, sorting by
  node, nodeset or node groups)
* standard input redirection to remote nodes
* files copying in parallel
* *pdsh* [#]_ options backward compatibility

*clush* can be started non-interactively to run a shell command, or can be
invoked as an interactive shell. Both modes are discussed here (clush-oneshot
clush-interactive).

Target and filter nodes
^^^^^^^^^^^^^^^^^^^^^^^

*clush* offers different ways to select or filter target nodes through command
line options or files containing a list of hosts.

Command line options
""""""""""""""""""""

The ``-w`` option allows you to specify remote hosts by using ClusterShell
:class:`.NodeSet` syntax, including the node groups *@group* special syntax
(cf. :ref:`nodeset-groupsexpr`) and the Extended String Patterns syntax (see
:ref:`class-NodeSet-extended-patterns`) to benefits from :class:`.NodeSet`
basic arithmetic (like ``@Agroup&@Bgroup``). Additionally, the ``-x`` option
allows you to exclude nodes from remote hosts list (the same NodeSet syntax
can be used here). Nodes exclusion has priority over nodes addition.

Using node groups
"""""""""""""""""

If you have ClusterShell :ref:`node groups <groups-config>` configured on your
cluster, any node group syntax may be used in place of nodes for ``-w`` as
well as ``-x``.

For example::

    $ clush -w @rhel6 cat /proc/loadavg
    node26: 0.02 0.01 0.00 1/202 23042

For *pdsh* backward compatibility, *clush* supports two ``-g`` and ``-X``
options to respectively select and exclude nodes group(s), but only specified
by omitting any *"@"* group prefix (see example below). In general, though, it
is advised to use the *@*-prefixed group syntax as the non-prefixed notation
is only recognized by *clush* but not by other tools like *nodeset*.

For example::

    $ clush -g rhel6 cat /proc/loadavg
    node26: 0.02 0.01 0.00 1/202 23033

.. _clush-all-nodes:

Selecting all nodes
"""""""""""""""""""

The special option ``-a`` (without argument) can be used to select **all**
nodes, in the sense of ClusterShell node groups (see
:ref:`node groups configuration <groups-config>` for more details on special
**all** external shell command upcall).  If not properly configured, the
``-a`` option may lead to a runtime error like::

    clush: External error: Not enough working external calls (all, or map +
    list) defined to get all node

.. _clush-pick:

Picking node(s) at random
"""""""""""""""""""""""""

Use ``--pick`` with a maximum number of nodes you wish to pick randomly from
the targeted node set. **clush** will then run only on selected node(s). The
following example will run a script on a single random node picked from the
``@compute`` group::

    $ clush -w @compute --pick=1 ./nonreg-single-client-fs-io.sh

Host files
""""""""""

The option ``--hostfile`` (or ``--machinefile``)  may be used to specify a
path to a file containing a list of single hosts, node sets or node groups,
separated by spaces and lines.  It may be specified multiple times (one per
file).

For example::

    $ clush --hostfile ./host_file -b systemctl is-enabled httpd

This option has been added as backward compatibility with other parallel shell
tools. Indeed, ClusterShell provides a preferred way to provision node sets
from node group sources and flat files to all cluster tools using
:class:`.NodeSet` (including *clush*). Please see :ref:`node groups
configuration <groups-config>`.

.. note:: Use ``--debug`` or ``-d`` to see resulting node sets from host
   files.


.. _clush-flat:

Flat execution mode
^^^^^^^^^^^^^^^^^^^

The default execution mode is to launch commands (local or remote) in parallel,
up to a certain limit fixed by the :ref:`fanout <clush-fanout>` value,
which is the number of child processes allowed to run at a time. This "sliding
window" of active commands is a common technique used on large clusters to
conserve resources on the initiating host, while allowing some commands to
time out. If used with *ssh(1)*, this does actually limit the number of
concurrent ssh connections.

.. _clush-fanout:

Fanout (sliding window)
"""""""""""""""""""""""

The ``--fanout`` (or ``-f``) option of **clush** allows the user to change the
default *fanout* value defined in :ref:`clush.conf <clush-config>` or in the
:ref:`library defaults <defaults-config>` if not specified.

Indeed, it is sometimes useful to change the fanout value for a specific
command, for example to avoid flooding a remote service with concurrent
requests generated by that actual command.

The following example will launch up to ten *puppet* commands at a time on the
node group named *@compute*::

    $ clush -w @compute -f 10 puppet agent -t

If the fanout value is set to 1, commands are executed sequentially::

    $ clush -w node[40-42] -f 1 'date +%s; sleep 1'
    node40: 1505366138
    node41: 1505366139
    node42: 1505366140


.. _clush-tree:

Tree execution mode
^^^^^^^^^^^^^^^^^^^

ClusterShell's tree execution mode is a major horizontal scalability
improvement by providing a hierarchical command propagation scheme.

The Tree mode of ClusterShell has been the subject of `this paper`_ presented
at the Ottawa Linux Symposium Conference in 2012 and at the PyHPC 2013
workshop in Denver, USA.

.. highlight:: text

The diagram below illustrates the hierarchical command propagation principle
with a head node, gateways (GW) and target nodes::

                           .-----------.
                           | Head node |
                           '-----------'
                                /|\
                  .------------' | '--.-----------.
                 /               |     \           \
            .-----.           .-----.   \          .-----.
            | GW1 |           | GW2 |    \         | GW3 |
            '-----'           '-----'     \        '-----'
              /|\               /|\        \          |\
           .-' | '-.         .-' | '-.      \         | '---.
          /    |    \       /    |    \      \        |      \
       .---. .---. .---. .---. .---. .---.  .---.   .---.   .-----.
       '---' '---' '---' '---' '---' '---'  '---'   '---'   | GW4 |
                     target nodes                           '-----'
                                                               |
                                                              ...


The Tree mode is implemented at the library level, so that all applications
using ClusterShell may benefits from it. However, this section describes how
to use the tree mode with the **clush** command only.

.. _clush-tree-enabling:

Configuration
"""""""""""""

The system-wide library configuration file **/etc/clustershell/topology.conf**
defines the routes of default command propagation tree. It is recommended that
all connections between parent and children nodes are carefully
pre-configured, for example, to avoid any SSH warnings when connecting (if
using the default SSH remote worker, of course).

.. highlight:: ini

The content of the topology.conf file should look like this::

  [routes]
  rio0: rio[10-13]
  rio[10-11]: rio[100-240]
  rio[12-13]: rio[300-440]

.. highlight:: text

This file defines the following topology graph::

    rio0
    |- rio[10-11]
    |  `- rio[100-240]
    `- rio[12-13]
       `- rio[300-440]


At runtime, ClusterShell will pick an initial propagation tree from this
topology graph definition and the current root node. Multiple admin/root
nodes may be defined in the file.

.. note:: The algorithm used in Tree mode does not rely on gateway system
   hostnames anymore. In topology.conf, just use the hosts or aliases needed
   to connect to each node.

.. highlight:: console

Enabling tree mode
""""""""""""""""""

Since version 1.7, the tree mode is enabled by default when a configuration
file is present. When the configuration file
**/etc/clustershell/topology.conf** exists, *clush* will use it by default for
target nodes that are defined there. The topology file path can be changed
using the ``--topology`` command line option.

.. note:: If using ``clush -d`` (debug option), clush will display an ASCII
   representation of the initial propagation tree used. This is useful when
   working on Tree mode configuration.

Enabling tree mode should be as much transparent as possible to the end user.
Most **clush** options, including options defined in
:ref:`clush.conf <clush-config>` or specified using ``-O`` or ``-o`` (ssh
options) are propagated to the gateways and taken into account there.

.. _clush-tree-options:

Tree mode specific options
""""""""""""""""""""""""""

The ``--remote=yes|no`` command line option controls the remote execution
behavior:

* Default is **yes**, that will make *clush* establish connections up to the
  leaf nodes using a *distant worker* like *ssh*.
* Changing it to **no** will make *clush* establish connections up to the leaf
  parent nodes only, then the commands are executed locally on the gateways
  (like if it would be with ``--worker=exec`` on the gateways themselves).
  This execution mode allows users to schedule remote commands on gateways
  that take a node as an argument. On large clusters, this is useful to spread
  the load and resources used of one-shot monitoring, IPMI, or other commands
  on gateways. A simple example of use is::

      $ clush -w node[100-199] --remote=no /usr/sbin/ipmipower -h %h-ipmi -s

  This command is also valid if you don't have any tree configured, because
  in that case, ``--remote=no`` is an alias of ``--worker=exec`` worker.

The ``--grooming`` command line option allows users to change the grooming
delay (float, in seconds). This feature allows gateways to aggregate responses
received within a certain timeframe before transmitting them back to the root
node in a batch fashion. This contributes to reducing the load on the root
node by delegating the first steps of this CPU intensive task to the gateways.

.. _clush-tree-fanout:

Fanout considerations
"""""""""""""""""""""

ClusterShell uses a "sliding window" or  *fanout* of processes to avoid too
many concurrent connections and to conserve resources on the initiating hosts.
See :ref:`clush-flat` for more details about this.

In tree mode, the same *fanout* value is used on the head node and on each
gateway. That is, if the *fanout* is **16**, each gateway will initiate up to
**16** connections to their target nodes at the same time.

.. note:: This is likely to **change** in the future, as it makes the *fanout*
   behaviour different if you are using the tree mode or not. For example,
   some administrators are using a *fanout* value of 1 to "sequentialize" a
   command on the cluster. In tree mode, please note that in that case, each
   gateway will be able to run a command at the same time.

.. _clush-tree-python:

Remote Python executable
""""""""""""""""""""""""

You must use the same major version of Python on the gateways and the root
node. By default, the same python executable name than the one used on the
root node will be used to launch the gateways, that is, `python` or `python3`
(using relative path for added flexibility). You may override the selection
of the remote Python interpreter by defining the following environment
variable::

    $ export CLUSTERSHELL_GW_PYTHON_EXECUTABLE=/path/to/python3

.. note:: It is highly recommended to have the same Python interpeter
   installed on all gateways and the root node.

Debugging Tree mode
"""""""""""""""""""

To debug Tree mode, you can define the following environment variable before
running **clush** (or any other applications using ClusterShell)::

    $ export CLUSTERSHELL_GW_LOG_LEVEL=DEBUG  (default value is INFO)
    $ export CLUSTERSHELL_GW_LOG_DIR=/tmp     (default value is /tmp)

This will generate log files of the form ``$HOSTNAME.gw.log`` in
``CLUSTERSHELL_GW_LOG_DIR``.

.. _clush-oneshot:

Non-interactive (or one-shot) mode
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When *clush* is started non-interactively, the command is executed on the
specified remote hosts in parallel (given the current *fanout* value and the
number of commands to execute (see *fanout* library settings in
:ref:`class-Task-configure`).

.. _clush-gather:

Output gathering options
""""""""""""""""""""""""

If option ``-b`` or ``--dshbak`` is specified, *clush* waits for command
completion while displaying a :ref:`progress indicator <clush-progress>` and
then displays gathered output results. If standard output is redirected to a
file, *clush* detects it and disable any progress indicator.

.. warning:: *clush*  will only consolidate identical command outputs if the
   command return codes are also the same.

The following is a simple example of *clush* command used to execute ``uname
-r`` on *node40*, *node41* and *node42*, wait for their completion and finally
display digested output results::

    $ clush -b -w node[40-42] uname -r
    ---------------
    node[40-42]
    ---------------
    2.6.35.6-45.fc14.x86_64


It is common to cancel such command execution because a node is hang. When
using *pdsh* and *dshbak*, due to the pipe, all nodes output will be lost,
even if all nodes have successfully run the command. When you hit CTRL-C with
*clush*, the task is canceled but received output is not lost::

    $ clush -b -w node[1-5] uname -r
    Warning: Caught keyboard interrupt!
    ---------------
    node[2-4] (3)
    ---------------
    2.6.31.6-145.fc11
    ---------------
    node5
    ---------------
    2.6.18-164.11.1.el5
    Keyboard interrupt (node1 did not complete).

Performing *diff* of cluster-wide outputs
"""""""""""""""""""""""""""""""""""""""""

Since version 1.6, you can use the ``--diff`` *clush* option to show
differences between common outputs. This feature is implemented using `Python
unified diff`_. This special option implies ``-b`` (gather common stdout
outputs) but you don't need to specify it. Example::

    $ clush -w node[40-42] --diff dmidecode -s bios-version
    --- node[40,42] (2)
    +++ node41
    @@ -1,1 +1,1 @@
    -1.0.5S56
    +1.1c

A nodeset is automatically selected as the "reference nodeset" according to
these criteria:

#. lowest command return code (to discard failed commands)
#. largest nodeset with the same output result
#. otherwise the first nodeset is taken (ordered (1) by name and (2) lowest range indexes)

Standard input bindings
"""""""""""""""""""""""

Unless the option ``--nostdin`` (or ``-n``) is specified, *clush* detects when
its standard input is connected to a terminal (as determined by *isatty(3)*).
If actually connected to a terminal, *clush* listens to standard input when
commands are running, waiting for an Enter key press. Doing so will display the
status of current nodes. If standard input is not connected to a terminal, and
unless the option ``--nostdin`` (or ``-n``) is specified, *clush* binds the
standard input of the remote commands to its own standard input, allowing
scripting methods like::

    $ echo foo | clush -w node[40-42] -b cat
    ---------------
    node[40-42]
    ---------------
    foo

Another stdin-bound *clush* usage example::

    $ ssh node10 'ls /etc/yum.repos.d/*.repo' | clush -w node[11-14] -b xargs ls
    ---------------
    node[11-14] (4)
    ---------------
    /etc/yum.repos.d/cobbler-config.repo

.. note:: Use ``--nostdin`` (or ``-n``) in the same way you would use ``ssh -n``
   to disable standard input. Indeed, if this option is set, EOF is sent at
   first read, as if stdin were actually connected to /dev/null.


.. _clush-progress:

Progress indicator
""""""""""""""""""

In :ref:`output gathering mode <clush-gather>`, *clush* will display a live
progress indicator as a simple but convenient way to follow the completion of
parallel commands. It can be disabled just by using the ``-q`` or ``--quiet``
options. The progress indicator will appear after 1 to 2 seconds and should
look like this::

    clush: <command_completed>/<command_total>

If writing is performed to *clush* standard input, like in ``command |
clush``, the live progress indicator will display the global bandwidth of data
written to the target nodes.

Finally, the special option ``--progress`` can be used to force the display of
the live progress indicator. Using this option may interfere with some command
outputs, but it can be useful when using stdin while remote commands are
silent. As an example, the following command will copy a local file to
node[1-3] and display the global write bandwidth to the target nodes::

    $ dd if=/path/to/local/file | clush -w node[1-3] --progress 'dd of=/path/to/remote/file'
    clush: 0/3 write: 212.27 MiB/s

.. _clush-interactive:

Interactive mode
^^^^^^^^^^^^^^^^

If a command is not specified, *clush* runs interactively. In this mode,
*clush* uses the *GNU readline* library to read command lines from the
terminal. *Readline* provides commands for searching through the command
history for lines containing a specified string. For instance, you can type
*Control-R* to search in the history for the next entry matching the search
string typed so far.

Single-character interactive commands
"""""""""""""""""""""""""""""""""""""

*clush* also recognizes special single-character prefixes that allows the user
to see and modify the current nodeset (the nodes where the commands are
executed). These single-character interactive commands are detailed below:

+------------------------------+-----------------------------------------------+
| Interactive special commands | Comment                                       |
+==============================+===============================================+
| ``clush> ?``                 | show current nodeset                          |
+------------------------------+-----------------------------------------------+
| ``clush> +<NODESET>``        | add nodes to current nodeset                  |
+------------------------------+-----------------------------------------------+
| ``clush> -<NODESET>``        | remove nodes from current nodeset             |
+------------------------------+-----------------------------------------------+
| ``clush> @<NODESET>``        | set current nodeset                           |
+------------------------------+-----------------------------------------------+
| ``clush> !<COMMAND>``        | execute ``<COMMAND>`` on the local system     |
+------------------------------+-----------------------------------------------+
| ``clush> =``                 | toggle the ouput format (gathered or standard |
|                              | mode)                                         |
+------------------------------+-----------------------------------------------+

To leave an interactive session, type ``quit`` or *Control-D*. As of version
1.6, it is not possible to cancel a command while staying in *clush*
interactive session: for instance, *Control-C* is not supported and will abort
current *clush* interactive command (see `ticket #166`_).

Example of *clush* interactive session::

    $ clush -w node[11-14] -b
    Enter 'quit' to leave this interactive mode
    Working with nodes: node[11-14]
    clush> uname
    ---------------
    node[11-14] (4)
    ---------------
    Linux
    clush> !pwd
    LOCAL: /root
    clush> -node[11,13]
    Working with nodes: node[12,14]
    clush> uname
    ---------------
    node[12,14] (2)
    ---------------
    Linux
    clush> 

The interactive mode and commands described above are subject to change and
improvements in future releases. Feel free to open an enhancement `ticket`_ if
you use the interactive mode and have some suggestions.

File copying mode
^^^^^^^^^^^^^^^^^

When *clush* is started with  the ``-c``  or  ``--copy``  option, it will
attempt to copy specified file and/or directory to the provided target cluster
nodes. If the ``--dest`` option is specified, it will put the copied files
or directory there.

Here are some examples of file copying with *clush*::

    $ clush -v -w node[11-12] --copy /tmp/foo
    `/tmp/foo' -> node[11-12]:`/tmp'

    $ clush -v -w node[11-12] --copy /tmp/foo /tmp/bar
    `/tmp/bar' -> aury[11-12]:`/tmp'
    `/tmp/foo' -> aury[11-12]:`/tmp'

    $ clush -v -w node[11-12] --copy /tmp/foo --dest /var/tmp/
    `/tmp/foo' -> node[11-12]:`/var/tmp/'

Reverse file copying mode
^^^^^^^^^^^^^^^^^^^^^^^^^

When *clush* is started with the ``--rcopy`` option, it will attempt to
retrieve specified file and/or directory from provided cluster nodes. If the
``--dest`` option is specified, it must be a directory path where the files
will be stored with their hostname appended. If the destination path is not
specified, it will take the first file or dir basename directory as the local
destination, example::

    $ clush -v -w node[11-12] --rcopy /tmp/foo
    node[11-12]:`/tmp/foo' -> `/tmp'

    $ ls /tmp/foo.*
    /tmp/foo.node11  /tmp/foo.node12

Other options
^^^^^^^^^^^^^

Overriding clush.conf settings
""""""""""""""""""""""""""""""

*clush* default settings are found in a configuration described in
:ref:`clush configuration <clush-config>`. To override any settings, use the
``--option`` command line option (or ``-O`` for the shorter version), and
repeat as needed. Here is a simple example to disable the use colors in the
output nodeset header::

    $ clush -O color=never -w node[11-12] -b echo ok
    ---------------
    node[11-12] (2)
    ---------------
    ok


.. _clush-worker:

Worker selection
""""""""""""""""

By default, *clush* is using the default library worker configuration when
running commands or copying files. In most cases, this is *ssh* (See
:ref:`task-default-worker` for default worker selection).

Worker selection can be performed at runtime thanks to ``--worker`` command
line option (or ``-R`` for the shorter version in order to be compatible with
*pdsh* remote command selection option)::

    $ clush -w node[11-12] --worker=rsh echo ok
    node11: ok
    node12: ok

By default, ClusterShell supports the following worker identifiers:

* **exec**: this local worker supports parallel command execution, doesn't
  rely on any external tool and provides command line placeholders described
  below:

  * ``%h`` and ``%host`` are substitued with each *target hostname*
  * ``%hosts`` is substitued with the full *target nodeset*
  * ``%n`` and ``%rank`` are substitued with the remote *rank* (0 to n-1)

  For example, the following would request the exec worker to locally run
  multiple *ipmitool* commands across the hosts foo[0-10] and automatically
  aggregate output results (-b)::

      $ clush -R exec -w foo[0-10] -b ipmitool -H %h-ipmi chassis power status
      ---------------
      foo[0-10] (11)
      ---------------
      Chassis Power is on

* **rsh**: remote worker based on *rsh*
* **ssh**: remote worker based on *ssh* (default)
* **pdsh**: remote worker based on *pdsh* that requires *pdsh* to be
  installed; doesn't provide write support (eg. you cannot ``cat file | clush
  --worker pdsh``); it is primarily an 1-to-n worker example.


.. [#] LLNL parallel remote shell utility
   (https://computing.llnl.gov/linux/pdsh.html)

.. _seq(1): http://linux.die.net/man/1/seq
.. _Python unified diff:
   http://docs.python.org/library/difflib.html#difflib.unified_diff

.. _ticket #166: https://github.com/cea-hpc/clustershell/issues/166
.. _ticket: https://github.com/cea-hpc/clustershell/issues/new

.. _this paper: https://www.kernel.org/doc/ols/2012/ols2012-thiell.pdf
