.. _cluset-tool:

cluset
------

.. highlight:: console

.. note:: The **cluset** command is introduced in ClusterShell version 1.7.3 as
          an alternative to the :ref:`nodeset-tool` command to avoid conflicts
          with the **nodeset** command from xCAT. Users are encouraged to
          transition to using **cluset** for their range/node/group set
          management tasks.

The *cluset* command enables easy manipulation of node and range sets, as
well as node groups, at the command line level. As it is user-friendly and
efficient, the *cluset* command can quickly improve traditional cluster
shell scripts. It is also full-featured as it provides most of the
:class:`.NodeSet` and :class:`.RangeSet` class methods (see also
:ref:`class-NodeSet`, and :ref:`class-RangeSet`).

Most of the examples in this section are using simple indexed node sets,
however, *cluset* supports multidimensional node sets, like
``dc[1-2]n[1-99]``, introduced in version 1.7 (see :ref:`class-RangeSetND`
for more info).

This section will guide you through the basics and also more advanced features
of *cluset*.

Usage basics
^^^^^^^^^^^^

One exclusive command must be specified to *cluset*, for example::

    $ cluset --expand node[13-15,17-19]
    node13 node14 node15 node17 node18 node19

    $ cluset --count node[13-15,17-19]
    6

    $ cluset --fold node1-ipmi node2-ipmi node3-ipmi
    node[1-3]-ipmi


Commands with inputs
""""""""""""""""""""

Some *cluset* commands require input (eg. node names, node sets or node
groups), and some only give output. The following table shows commands that
require some input:

+-------------------+--------------------------------------------------------+
| Command           | Description                                            |
+===================+========================================================+
| ``-c``,           | Count and display the total number of nodes in node    |
| ``--count``       | sets or/and node groups.                               |
+-------------------+--------------------------------------------------------+
| ``-e``,           | Expand node sets or/and node groups as unitary node    |
| ``--expand``      | names separated by current separator string (see       |
|                   | ``--separator`` option described in                    |
|                   | :ref:`cluset-commands-formatting`).                    |
+-------------------+--------------------------------------------------------+
| ``-f``,           | Fold (compact) node sets or/and node groups into one   |
| ``--fold``        | set of nodes (by previously resolving any groups). The |
|                   | resulting node set is guaranteed to be free from node  |
|                   | ``--regroup`` below if you want to resolve node groups |
|                   | in result). Please note that folding may be time       |
|                   | consuming for multidimensional node sets.              |
+-------------------+--------------------------------------------------------+
| ``-r``,           | Fold (compact) node sets or/and node groups into one   |
| ``--regroup``     | set of nodes using node groups whenever possible (by   |
|                   | previously resolving any groups).                      |
|                   | See :ref:`cluset-groups`.                              |
+-------------------+--------------------------------------------------------+


There are three ways to give some input to the *cluset* command:

* from command line arguments,
* from standard input (enabled when no arguments are found on command line),
* from both command line and standard input, by using the dash special
  argument ``-`` meaning you need to use stdin instead.

The following example illustrates the three ways to feed *cluset*::

  $ cluset -f node1 node6 node7
  node[1,6-7]
  
  $ echo node1 node6 node7 | cluset -f
  node[1,6-7]
  
  $ echo node1 node6 node7 | cluset -f node0 -
  node[0-1,6-7]


Furthermore, *cluset*'s standard input reader is able to process multiple
lines and multiple node sets or groups per line. The following example shows a
simple use case::

    $ mount -t nfs | cut -d':' -f1
    nfsserv1
    nfsserv2
    nfsserv3
    
    $ mount -t nfs | cut -d':' -f1 | cluset -f
    nfsserv[1-3]


Other usage examples of *cluset* below show how it can be useful to provide
node sets from standard input (*sinfo* is a SLURM [#]_ command to view nodes
and partitions information and *sacct* is a command to display SLURM
accounting data)::

    $ sinfo -p cuda -o '%N' -h
    node[156-159]
    
    $ sinfo -p cuda -o '%N' -h | cluset -e
    node156 node157 node158 node159
    
    $ for node in $(sinfo -p cuda -o '%N' -h | cluset -e); do
            sacct -a -N $node > /tmp/cudajobs.$node;
      done

Previous rules also apply when working with node groups, for example when
using ``cluset -r`` reading from standard input (and a matching group is
found)::

    $ cluset -f @gpu
    node[156-159]
    
    $ sinfo -p cuda -o '%N' -h | cluset -r
    @gpu

Most commands described in this section produce output results that may be
formatted using ``--output-format`` and ``--separator`` which are described in
:ref:`cluset-commands-formatting`.

Commands with no input
""""""""""""""""""""""

The following table shows all other commands that are supported by
*cluset*. These commands don't support any input (like node sets), but can
still recognize options as specified below.

+--------------------+-----------------------------------------------------+
| Command w/o input  | Description                                         |
+====================+=====================================================+
| ``-l``, ``--list`` | List node groups from selected *group source* as    |
|                    | specified with ``-s`` or ``--groupsource``. If      |
|                    | not specified, node groups from the default *group  |
|                    | source* are listed (see :ref:`groups configuration  |
|                    | <groups-config>` for default *group source*         |
|                    | configuration).                                     |
+--------------------+-----------------------------------------------------+
| ``--groupsources`` | List all configured *group sources*, one per line,  |
|                    | as configured in *groups.conf* (see                 |
|                    | :ref:`groups configuration <groups-config>`).       |
|                    | The default *group source* is appended with         |
|                    | `` (default)``, unless the ``-q``, ``--quiet``      |
|                    | option is specified. This command is mainly here to |
|                    | avoid reading any configuration files, or to check  |
|                    | if all work fine when configuring *group sources*.  |
+--------------------+-----------------------------------------------------+

.. _cluset-commands-formatting:

Output result formatting
""""""""""""""""""""""""

When using the expand command (``-e, --expand``), a separator string is used
when displaying results. The option ``-S``, ``--separator`` allows you to
modify it. The specified string is interpreted, so that you can use special
characters as separator, like ``\n`` or ``\t``. The default separator is the
space character *" "*. This is an example showing such separator string
change::

    $ cluset -e --separator='\n' node[0-3]
    node0
    node1
    node2
    node3

The ``-O, --output-format`` option can be used to format output results of
most *cluset* commands. The string passed to this option is used as a base
format pattern applied to each node or each result (depending on the command
and other options requested). The default format string is *"%s"*.  Formatting
is performed using the Python builtin string formatting operator, so you must
use one format operator of the right type (*%s* is guaranteed to work in all
cases). Here is an output formatting example when using the expand command::

    $ cluset --output-format='%s-ipmi' -e node[1-2]x[1-2]
    node1x1-ipmi node1x2-ipmi node2x1-ipmi node2x2-ipmi

Output formatting and separator combined can be useful when using the expand
command, as shown here::

    $ cluset -O '%s-ipmi' -S '\n' -e node[1-2]x[1-2]
    node1x1-ipmi
    node1x2-ipmi
    node2x1-ipmi
    node2x2-ipmi

When using the output formatting option along with the folding command, the
format is applied to each node but the result is still folded::

    $ cluset -O '%s-ipmi' -f mgmt1 mgmt2 login[1-4]
    login[1-4]-ipmi,mgmt[1-2]-ipmi


.. _cluset-stepping:

Stepping and auto-stepping
^^^^^^^^^^^^^^^^^^^^^^^^^^

The *cluset* command, as does the *clush* command, is able to recognize by
default a factorized notation for range sets of the form *a-b/c*, indicating a
list of integers starting from *a*, less than or equal to *b* with the
increment (step) *c*.

For example, the *0-6/2* format indicates a range of 0-6 stepped by 2; that
is 0,2,4,6::

    $ cluset -e node[0-6/2]
    node0 node2 node4 node6

However, by default, *cluset* never uses this stepping notation in output
results, as other cluster tools seldom if ever support this feature. Thus, to
enable such factorized output in *cluset*, you must specify
``--autostep=AUTOSTEP`` to set an auto step threshold number when folding
nodesets (ie. when using ``-f`` or ``-r``). This threshold number
(AUTOSTEP) is the minimum occurrence of equally-spaced integers needed to
enable auto-stepping.

For example::

    $ cluset -f --autostep=3 node1 node3 node5
    node[1-5/2]
    
    $ cluset -f --autostep=4 node1 node3 node5
    node[1,3,5]

It is important to note that resulting node sets with enabled auto-stepping
never create overlapping ranges, for example::

    $ cluset -f --autostep=3 node1 node5 node9 node13
    node[1-13/4]

    $ cluset -f --autostep=3 node1 node5 node7 node9 node13
    node[1,5-9/2,13]

However, any ranges given as input may still overlap (in this case, *cluset*
will automatically spread them out so that they do not overlap), for example::

    $ cluset -f --autostep=3 node[1-13/4,7]
    node[1,5-9/2,13]


A minimum node count threshold **percentage** before autostep is enabled may
also be specified as autostep value (or ``auto`` which is currently 100%).  In
the two following examples, only the first 4 of the 7 indexes may be
represented using the step syntax (57% of them)::

    $ cluset -f --autostep=50% node[1,3,5,7,34,39,99]
    node[1-7/2,34,39,99]

    $ cluset -f --autostep=90% node[1,3,5,7,34,39,99]
    node[1,3,5,7,34,39,99]


.. _cluset-zeropadding:

Zero-padding
^^^^^^^^^^^^

Sometimes, cluster node names are padded with zeros (eg. *node007*). With
*cluset*, when leading zeros are used, resulting host names or node sets
are automatically padded with zeros as well. For example::

    $ cluset -e node[08-11]
    node08 node09 node10 node11

    $ cluset -f node001 node002 node003 node005
    node[001-003,005]

Zero-padding and stepping (as seen in :ref:`cluset-stepping`) together are
also supported, for example::

    $ cluset -e node[000-012/4]
    node000 node004 node008 node012

Since v1.9, mixed length padding is allowed, for example::

    $ cluset -f node2 node01 node001
    node[2,01,001]

When mixed length zero-padding is encountered, indexes with smaller padding
length are returned first, as you can see in the example above (``2`` comes
before ``01``).

Since v1.9, when using node sets with multiple dimensions, each dimension (or
axis) may also use mixed length zero-padding::

    $ cluset -f foo1bar1 foo1bar00 foo1bar01 foo004bar1 foo004bar00 foo004bar01
    foo[1,004]bar[1,00-01]


Leading and trailing digits
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Version 1.7 introduces improved support for bracket leading and trailing
digits. Those digits are automatically included within the range set,
allowing all node set operations to be fully supported.

Examples with bracket leading digits::

    $ cluset -f node-00[00-99]
    node-[0000-0099]

    $ cluset -f node-01[01,09,42]
    node-[0101,0109,0142]

Examples with bracket trailing digits::

    $ cluset -f node-[1-2]0-[0-2]5
    node-[10,20]-[05,15,25]

Examples with both bracket leading and trailing digits::

    $ cluset -f node-00[1-6]0
    node-[0010,0020,0030,0040,0050,0060]

    $ cluset --autostep=auto -f node-00[1-6]0
    node-[0010-0060/10]

Example with leading digit and mixed length zero padding (supported since
v1.9)::

    $ cluset -f node1[00-02,000-032/8]
    node[100-102,1000,1008,1016,1024,1032]

Using this syntax can be error-prone especially if used with node sets
without 0-padding or with the */step* syntax and also requires additional
processing by the parser. In general, we recommend writing the whole rangeset
inside the brackets.

.. warning:: Using the step syntax (seen above) within a bracket-delimited
   range set is not compatible with **trailing** digits. For instance, this is
   **not** supported: ``node-00[1-6/2]0``

.. _cluset-arithmetic:

Arithmetic operations
^^^^^^^^^^^^^^^^^^^^^

As a preamble to this section, keep in mind that all operations can be
repeated/mixed within the same *cluset* command line, they will be
processed from left to right.

Union operation
"""""""""""""""

Union is the easiest arithmetic operation supported by *cluset*: there is
no special command line option for that, just provide several node sets and
the union operation will be computed, for example::

    $ cluset -f node[1-3] node[4-7]
    node[1-7]

    $ cluset -f node[1-3] node[2-7] node[5-8]
    node[1-8]

Other operations
""""""""""""""""

As an extension to the above, other arithmetic operations are available by
using the following command-line options (*working set* is the node set
currently processed on the command line -- always from left to right):

+--------------------------------------------+---------------------------------+
| *cluset* command option                    | Operation                       |
+============================================+=================================+
| ``-x NODESET``, ``--exclude=NODESET``      | compute a new set with elements |
|                                            | in *working set* but not in     |
|                                            | ``NODESET``                     |
+--------------------------------------------+---------------------------------+
| ``-i NODESET``, ``--intersection=NODESET`` | compute a new set with elements |
|                                            | common to *working set* and     |
|                                            | ``NODESET``                     |
+--------------------------------------------+---------------------------------+
| ``-X NODESET``, ``--xor=NODESET``          | compute a new set with elements |
|                                            | that are in exactly one of the  |
|                                            | *working set* and ``NODESET``   |
+--------------------------------------------+---------------------------------+


If rangeset mode (``-R``) is turned on, all arithmetic operations are
supported by replacing ``NODESET`` by any ``RANGESET``. See
:ref:`cluset-rangeset` for more info about *cluset*'s rangeset mode.


Arithmetic operations usage examples::

    $ cluset -f node[1-9] -x node6
    node[1-5,7-9]
    
    $ cluset -f node[1-9] -i node[6-11]
    node[6-9]
    
    $ cluset -f node[1-9] -X node[6-11]
    node[1-5,10-11]
    
    $ cluset -f node[1-9] -x node6 -i node[6-12]
    node[7-9]

.. _cluset-extended-patterns:

*Extended patterns* support
"""""""""""""""""""""""""""

*cluset* does also support arithmetic operations through its "extended
patterns" (inherited from :class:`.NodeSet` extended pattern feature, see
:ref:`class-NodeSet-extended-patterns`, there is an example of use::

    $ cluset -f node[1-4],node[5-9]
    node[1-9]
    
    $ cluset -f node[1-9]\!node6
    node[1-5,7-9]

    $ cluset -f node[1-9]\&node[6-12]
    node[6-9]
    
    $ cluset -f node[1-9]^node[6-11]
    node[1-5,10-11]

.. _cluset-special:

Special operations
^^^^^^^^^^^^^^^^^^

A few special operations are currently available: node set slicing, splitting
on a predefined node count, splitting non-contiguous subsets, choosing fold
axis (for multidimensional node sets) and picking N nodes randomly. They are
all explained below.

.. _cluset-slice:

Slicing
"""""""

Slicing is a way to select elements from a node set by their index (or from a
range set when using ``-R`` toggle option, see :ref:`cluset-rangeset`. In
this case actually, and because *cluset*'s underlying :class:`.NodeSet` class
sorts elements as observed after folding (for example), the word *set* may
sound like a stretch of language (a *set* isn't usually sorted). Indeed,
:class:`.NodeSet` further guarantees that its iterator will traverse the set
in order, so we should see it as a *ordered set*. The following simple example
illustrates this sorting behavior::

    $ cluset -f b2 b1 b0 b c a0 a
    a,a0,b,b[0-2],c

Slicing is performed through the following command-line option:

+---------------------------------------+-----------------------------------+
| *cluset* command option               | Operation                         |
+=======================================+===================================+
| ``-I RANGESET``, ``--slice=RANGESET`` | *slicing*: get sliced off result, |
|                                       | selecting elements from provided  |
|                                       | rangeset's indexes                |
+---------------------------------------+-----------------------------------+

Some slicing examples are shown below::

    $ cluset -f -I 0 node[4-8]
    node4
    
    $ cluset -f --slice=0 bnode[0-9] anode[0-9]
    anode0
    
    $ cluset -f --slice=1,4,7,9,15 bnode[0-9] anode[0-9]
    anode[1,4,7,9],bnode5
    
    $ cluset -f --slice=0-18/2 bnode[0-9] anode[0-9]
    anode[0,2,4,6,8],bnode[0,2,4,6,8]


Splitting into *n* subsets
""""""""""""""""""""""""""

Splitting a node set into several parts is often useful to get separate groups
of nodes, for instance when you want to check MPI comm between nodes, etc.
Based on :meth:`.NodeSet.split` method, the *cluset* command provides the
following additional command-line option (since v1.4):

+--------------------------+--------------------------------------------+
| *cluset* command option  | Operation                                  |
+==========================+============================================+
| ``--split=MAXSPLIT``     | *splitting*: split result into a number of |
|                          | subsets                                    |
+--------------------------+--------------------------------------------+

``MAXSPLIT`` is an integer specifying the number of separate groups of nodes
to compute. Input's node set is divided into smaller groups, whenever possible
with the same size (only the last ones may be smaller due to rounding).
Obviously, if ``MAXSPLIT`` is higher than or equal to the number N of elements
in the set, then the set is split to N single sets.

Some node set splitting examples::

    $ cluset -f --split=4 node[0-7]
    node[0-1]
    node[2-3]
    node[4-5]
    node[6-7]
    
    $ cluset -f --split=4 node[0-6]
    node[0-1]
    node[2-3]
    node[4-5]
    node6
    
    $ cluset -f --split=10000 node[0-4]
    foo0
    foo1
    foo2
    foo3
    foo4
    
    $ cluset -f --autostep=3 --split=2 node[0-38/2]
    node[0-18/2]
    node[20-38/2]


Splitting off non-contiguous subsets
""""""""""""""""""""""""""""""""""""

It can be useful to split a node set into several contiguous subsets (with
same pattern name and contiguous range indexes, eg. *node[1-100]* or
*dc[1-4]node[1-100]*). The ``--contiguous`` option allows you to do that.  It
is based on  :meth:`.NodeSet.contiguous` method, and should be specified with
standard commands (fold, expand, count, regroup). The following example shows
how to split off non-contiguous subsets of a specified node set, and to
display each resulting contiguous node set in a folded manner to separated
lines::

    $ cluset -f --contiguous node[1-100,200-300,500]
    node[1-100]
    node[200-300]
    node500


Similarly, the following example shows how to display each resulting
contiguous node set in an expanded manner to separate lines::

    $ cluset -e --contiguous node[1-9,11-19]
    node1 node2 node3 node4 node5 node6 node7 node8 node9
    node11 node12 node13 node14 node15 node16 node17 node18 node19


Choosing fold axis (nD)
"""""""""""""""""""""""

The default folding behavior for multidimensional node sets is to fold along
all *nD* axis. However, other cluster tools barely support nD nodeset syntax,
so it may be useful to fold along one (or a few) axis only. The ``--axis``
option allows you to specify indexes of dimensions to fold. Using this
option, rangesets of unspecified axis there won't be folded. Please note
however that the obtained result may be suboptimal, this is because
:class:`.NodeSet` algorithms are optimized for folding along all axis.
``--axis`` value is a set of integers from 1 to n representing selected nD
axis, in the form of a number or a rangeset. A common case is to restrict
folding on a single axis, like in the following simple examples::

    $ cluset --axis=1 -f node1-ib0 node2-ib0 node1-ib1 node2-ib1
    node[1-2]-ib0,node[1-2]-ib1

    $ cluset --axis=2 -f node1-ib0 node2-ib0 node1-ib1 node2-ib1
    node1-ib[0-1],node2-ib[0-1]

Because a single nodeset may have several different dimensions, axis indices
are silently truncated to fall in the allowed range. Negative indices are
useful to fold along the last axis whatever number of dimensions used::

    $ cluset --axis=-1 -f comp-[1-2]-[1-36],login-[1-2]
    comp-1-[1-36],comp-2-[1-36],login-[1-2]

See also the :ref:`defaults-config-slurm` of Library Defaults for changing it
permanently.

.. _cluset-pick:

Picking N node(s) at random
"""""""""""""""""""""""""""

Use ``--pick`` with a maximum number of nodes you wish to pick randomly from
the resulting node set (or from the resulting range set with ``-R``)::

    $ cluset --pick=1 -f node11 node12 node13
    node12
    $ cluset --pick=2 -f node11 node12 node13
    node[11,13]


.. _cluset-groups:

Node groups
^^^^^^^^^^^

This section tackles the node groups feature available more particularly
through the *cluset* command-line tool. The ClusterShell library defines a
node groups syntax and allow you to bind these group sources to your
applications (cf. :ref:`node groups configuration <groups-config>`). Having
those group sources, group provisioning is easily done through user-defined
external shell commands.  Thus, node groups might be very dynamic and their
nodes might change very often. However, for performance reasons, external call
results are still cached in memory to avoid duplicate external calls during
*cluset* execution.  For example, a group source can be bound to a resource
manager or a custom cluster database.

For further details about using node groups in Python, please see
:ref:`class-NodeSet-groups`. For advanced usage, you should also be able to
define your own group source directly in Python (cf.
:ref:`class-NodeSet-groups-override`).

.. _cluset-groupsexpr:

Node group expression rules
"""""""""""""""""""""""""""

The general node group expression is ``@source:groupname``. For example,
``@slurm:bigmem`` represents the group *bigmem* of the group source *slurm*.
Moreover, a shortened expression is available when using the default group
source (defined by configuration); for instance ``@compute`` represents the
*compute* group of the default group source.

Valid group source names and group names can contain alphanumeric characters,
hyphens and underscores (no space allowed). Indeed, same rules apply to node
names.

Listing group sources
"""""""""""""""""""""

As already mentioned, the following *cluset* command is available to list
configured group sources and also display the default group source (unless
``-q`` is provided)::

    $ cluset --groupsources
    local (default)
    genders
    slurm

Listing group names
"""""""""""""""""""

It is always possible to list the groups from a group source if the source is
:ref:`file-based <group-file-based>`.
If the source is an :ref:`external group source <group-external-sources>`, the
**list** upcall must be configured (see also:
:ref:`node groups configuration <groups-config>`).

To list available groups *from the default source*, use the following command::

    $ cluset -l
    @mgnt
    @mds
    @oss
    @login
    @compute

To list groups *from a specific group source*, use *-l* in conjunction
with *-s* (or *--groupsource*)::

    $ cluset -l -s slurm
    @slurm:parallel
    @slurm:cuda

Or, to list groups *from all available group sources*, use *-L* (or
*--list-all*)::

    $ cluset -L
    @mgnt
    @mds
    @oss
    @login
    @compute
    @slurm:parallel
    @slurm:cuda

You can also use ``cluset -ll`` or ``cluset -LL`` to see each group's
associated node sets.

.. _cluset-rawgroupnames:

Listing group names in expressions
""""""""""""""""""""""""""""""""""

ClusterShell 1.9 introduces a new operator **@@** optionally followed by a
source name (e.g. **@@source**) to access the list of *raw group names* of
the source (without the **@** prefix). If no source is specified (as in *just*
**@@**), the default group source is used (see :ref:`groups_config_conf`).
The **@@** operator may be used in any node set expression to manipulate group
names as a node set.

Example with the default group source::

    $ cluset -l
    @mgnt
    @mds
    @oss
    @login
    @compute
    
    $ cluset -e @@
    compute login mds mgnt oss

Example with a group source "rack" that defines group names from rack
locations in a data center::

    $ cluset -l -s rack
    @rack:J1
    @rack:J2
    @rack:J3
    
    $ cluset -f @@rack
    J[1-3]

A set of valid, indexed group sources is also accepted by the **@@** operator
(e.g. **@@dc[1-3]**).


.. warning:: An error is generated when using **@@** in an expression if the
             source is not valid (e.g. invalid name, not configured or upcalls
             not currently working).


Using node groups in basic commands
"""""""""""""""""""""""""""""""""""

The use of node groups with the *cluset* command is very straightforward.
Indeed, any group name, prefixed by **@** as mentioned above, can be used in
lieu of a node name, where it will be substituted for all nodes in that group.

A first, simple example is a group expansion (using default source) with
*cluset*::

    $ cluset -e @oss
    node40 node41 node42 node43 node44 node45

The *cluset* count command works as expected::

    $ cluset -c @oss
    6

Also *cluset* folding command can always resolve node groups::

    $ cluset -f @oss
    node[40-45]

There are usually two ways to use a specific group source (need to be properly
configured)::

    $ cluset -f @slurm:parallel
    node[50-81]
    
    $ cluset -f -s slurm @parallel
    node[50-81]

.. _cluset-group-finding:

Finding node groups
"""""""""""""""""""

As an extension to the **list** command, you can search node groups that a
specified node set belongs to with ``cluset -l[ll]`` as follow::

    $ cluset -l node40
    @all
    @oss
    
    $ cluset -ll node40
    @all node[1-159]
    @oss node[40-45]

This feature is implemented with the help of the :meth:`.NodeSet.groups`
method (see :ref:`class-NodeSet-groups-finding` for further details).

.. _cluset-regroup:

Resolving node groups
"""""""""""""""""""""

If needed group configuration conditions are met (cf. :ref:`node groups
configuration <groups-config>`), you can try group lookups thanks to the ``-r,
--regroup`` command. This feature is implemented with the help of the
:meth:`.NodeSet.regroup()` method (see :ref:`class-NodeSet-regroup` for
further details). Only exact matching groups are returned (all containing
nodes needed), for example::

    $ cluset -r node[40-45]
    @oss
    
    $ cluset -r node[0,40-45]
    @mgnt,@oss


When resolving node groups, *cluset* always returns the largest groups
first, instead of several smaller matching groups, for instance::

    $ cluset -ll
    @login node[50-51]
    @compute node[52-81]
    @intel node[50-81]
    
    $ cluset -r node[50-81]
    @intel

If no matching group is found, ``cluset -r`` still returns folded result (as
does ``-f``)::

    $ cluset -r node40 node42
    node[40,42]

Indexed node groups
"""""""""""""""""""

Node groups are themselves some kind of group sets and can be indexable. To
use this feature, node groups external shell commands need to return indexed
group names (automatically handled by the library as needed). For example,
take a look at these indexed node groups::

    $ cluset -l
    @io1
    @io2
    @io3
    
    $ cluset -f @io[1-3]
    node[40-45]


Arithmetic operations on node groups
""""""""""""""""""""""""""""""""""""

Arithmetic and special operations (as explained for node sets in
:ref:`cluset-arithmetic` and :ref:`cluset-special`) are also supported with
node groups.
Any group name can be used in lieu of a node set, where it will be substituted
for all nodes in that group before processing requested operations. Some
typical examples are::

    $ cluset -f @lustre -x @mds
    node[40-45]
    
    $ cluset -r @lustre -x @mds
    @oss
    
    $ cluset -r -a -x @lustre
    @compute,@login,@mgnt

More advanced examples, with the use of node group sets, follow::

    $ cluset -r @io[1-3] -x @io2
    @io[1,3]
    
    $ cluset -f -I0 @io[1-3]
    node40
    
    $ cluset -f --split=3 @oss
    node[40-41]
    node[42-43]
    node[44-45]
    
    $ cluset -r --split=3 @oss
    @io1
    @io2
    @io3


*Extended patterns* support with node groups
""""""""""""""""""""""""""""""""""""""""""""

Even for node groups, the *cluset* command supports arithmetic operations
through its *extended pattern* feature (see
:ref:`class-NodeSet-extended-patterns`).
A first example illustrates node groups intersection, that can be used in
practice to get nodes available from two dynamic group sources at a given
time::

    $ cluset -f @db:prod\&@compute

The following fictive example computes a folded node set containing nodes
found in node group ``@gpu``  and ``@slurm:bigmem``, but not in both, minus
the nodes found in odd ``@chassis`` groups from 1 to 9 (computed from left to
right)::

    $ cluset -f @gpu^@slurm:bigmem\!@chassis[1-9/2]

Also, version 1.7 introduces a notation extension ``@*`` (or ``@SOURCE:*``)
that has been added to quickly represent *all nodes* (please refer to
:ref:`clush-all-nodes` for more details).


.. _cluset-all-nodes:

Selecting all nodes
"""""""""""""""""""

The option ``-a`` (without argument) can be used to select **all** nodes from
a group source (see :ref:`node groups configuration <groups-config>` for more
details on special **all** external shell command upcall). Example of use for
the default group source::

    $ cluset -a -f
    example[4-6,32-159]

Use ``-s/--groupsource`` to select another group source.

If not properly configured, the ``-a`` option may lead to runtime errors
like::

    $ cluset -s mybrokensource -a -f
    cluset: External error: Not enough working methods (all or map + list)
        to get all nodes

A similar option is available with :ref:`clush-tool`, see
:ref:`selecting all nodes with clush <clush-all-nodes>`.

.. _node-wildcards:

Node wildcards
""""""""""""""

ClusterShell 1.8 introduces node wildcards: ``*`` means match zero or more
characters of any type; ``?`` means match exactly one character of any type.

Any wildcard mask found is matched against **all** nodes from the group source
(see :ref:`cluset-all-nodes`).

This can be especially useful for server farms, or when cluster node names
differ.  Say that your :ref:`group configuration <groups-config>` is set to
return the following "all nodes"::

    $ cluset -f -a
    bckserv[1-2],dbserv[1-4],wwwserv[1-9]

Then, you can use wildcards to select particular nodes, as shown below::

    $ cluset -f 'www*'
    wwwserv[1-9]

    $ cluset -f 'www*[1-4]'
    wwwserv[1-4]

    $ cluset -f '*serv1'
    bckserv1,dbserv1,wwwserv1

Wildcard masks are resolved prior to
:ref:`extended patterns <cluset-extended-patterns>`, but each mask is
evaluated as a whole node set operand. In the example below, we select
all nodes matching ``*serv*`` before removing all nodes matching ``www*``::

    $ cluset  -f '*serv*!www*'
    bckserv[1-2],dbserv[1-4]

.. _cluset-rangeset:

Range sets
^^^^^^^^^^

Working with range sets
"""""""""""""""""""""""

By default, the *cluset* command works with node or group sets and its
functionality match most :class:`.NodeSet` class methods. Similarly, *cluset*
will match :class:`.RangeSet` methods when you make use of the ``-R`` option
switch. In that case, all operations are restricted to numerical ranges. For
example, to expand the range "``1-10``", you should use::

    $ cluset -e -R 1-10
    1 2 3 4 5 6 7 8 9 10

Almost all commands and operations available for node sets are also available
with range sets. The only restrictions are commands and operations related to
node groups. For instance, the following command options are **not** available
with ``cluset -R``:

* ``-r, --regroup`` as this feature is obviously related to node groups,
* ``-a / --all`` as the **all** external call is also related to node groups.


Using range sets instead of node sets doesn't change the general command
usage, like the need of one command option presence (cf. cluset-commands), or
the way to give some input (cf. cluset-stdin), for example::

    $ echo 3 2 36 0 4 1 37 | cluset -fR
    0-4,36-37
    
    $ echo 0-8/4 | cluset -eR -S'\n'
    0
    4
    8

Stepping and auto-stepping are supported (cf. :ref:`cluset-stepping`) and
also zero-padding (cf. cluset-zpad), which are both :class:`.RangeSet` class
features anyway.

The following examples illustrate these last points::

    $ cluset -fR 03 05 01 07 11 09
    01,03,05,07,09,11
    
    $ cluset -fR --autostep=3 03 05 01 07 11 09
    01-11/2

Arithmetic and special operations
"""""""""""""""""""""""""""""""""

All arithmetic operations, as seen for node sets (cf.
:ref:`cluset-arithmetic`:), are available for range sets, for example::

    $ cluset -fR 1-14 -x 10-20
    1-9
    
    $ cluset -fR 1-14 -i 10-20
    10-14
    
    $ cluset -fR 1-14 -X 10-20
    1-9,15-20

For now, there is no *extended patterns* syntax for range sets as for node
sets (cf. :ref:`cluset-extended-patterns`). However, as the union operator
``,`` is available natively by design, such expressions are still allowed::

    $ cluset -fR 4-10,1-2
    1-2,4-10


Besides arithmetic operations, special operations may be very convenient for
range sets also (cf. :ref:`cluset-special`:).
Below is an example with ``-I / --slice`` (cf. :ref:`cluset-slice`:)::

    $ cluset -fR -I 0 100-131
    100
    
    $ cluset -fR -I 0-15 100-131
    100-115

There is another special operation example with ``--split`` (cf.
cluset-splitting-n)::

    $ cluset -fR --split=2 100-131
    100-115
    116-131

Finally, an example of the special operation ``--contiguous`` (cf.
cluset-splitting-contiguous)::

    $ cluset -f -R --contiguous 1-9,11,13-19
    1-9
    11
    13-19

*rangeset* alias
""""""""""""""""

When using *cluset* with range sets intensively (eg. for scripting), it may
be convenient to create a local command alias, as shown in the following
example (Bourne shell), making it sort of a super `seq(1)`_ command::

    $ alias rangeset='cluset -R'
    $ rangeset -e 0-8/2
    0 2 4 6 8


.. [#] Slurm is an open-source resource manager (https://slurm.schedmd.com/overview.html)

.. _seq(1): http://linux.die.net/man/1/seq

