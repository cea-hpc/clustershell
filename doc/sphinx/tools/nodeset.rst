.. _nodeset-tool:

nodeset
-------

.. highlight:: console

The *nodeset* command enables easy manipulation of node sets, as well as
node groups, at the command line level. As it is very user-friendly and
efficient, the *nodeset* command can quickly improve traditional cluster
shell scripts. It is also full-featured as it provides most of the
:class:`.NodeSet` and :class:`.RangeSet` class methods (see also
:ref:`class-NodeSet`, and :ref:`class-RangeSet`).

Most of the examples in this section are using simple indexed node sets,
however, *nodeset* supports multidimensional node sets, like *dc[1-2]n[1-99]*,
introduced in version 1.7 (see :ref:`class-RangeSetND` for more info).

This section will guide you through the basics and also more advanced features
of *nodeset*.

Usage basics
^^^^^^^^^^^^

One exclusive command must be specified to *nodeset*, for example::

    $ nodeset --expand node[13-15,17-19]
    node13 node14 node15 node17 node18 node19

    $ nodeset --count node[13-15,17-19]
    6

    $ nodeset --fold node1-ipmi node2-ipmi node3-ipmi
    node[1-3]-ipmi


Commands with inputs
""""""""""""""""""""

Some *nodeset* commands require input (eg. node names, node sets or node
groups), and some only give output. The following table shows commands that
require some input:

+-------------------+--------------------------------------------------------+
| Command           | Description                                            |
+===================+========================================================+
| ``-c, --count``   | Count and display the total number of nodes in node    |
|                   | sets or/and node groups.                               |
+-------------------+--------------------------------------------------------+
| ``-e, --expand``  | Expand node sets or/and node groups as unitary node    |
|                   | names separated by current separator string (see       |
|                   | ``--separator`` option described in                    |
|                   | :ref:`nodeset-commands-formatting`).                   |
+-------------------+--------------------------------------------------------+
| ``-f, --fold``    | Fold (compact) node sets or/and node groups into one   |
|                   | set of nodes (by previously resolving any groups). The |
|                   | resulting node set is guaranteed to be free from node  |
|                   | ``--regroup`` below if you want to resolve node groups |
|                   | in result). Please note that folding may be time       |
|                   | consuming for multidimensional node sets.              |
+-------------------+--------------------------------------------------------+
| ``-r, --regroup`` | Fold (compact) node sets or/and node groups into one   |
|                   | set of nodes using node groups whenever possible (by   |
|                   | previously resolving any groups).                      |
|                   | See :ref:`nodeset-groups`.                             |
+-------------------+--------------------------------------------------------+


There are three ways to give some input to the *nodeset* command:

* from command line arguments,
* from standard input (enabled when no arguments are found on command line),
* from both command line and standard input, by using the dash special
  argument *"-"* meaning you need to use stdin instead.

The following example illustrates the three ways to feed *nodeset*::

  $ nodeset -f node1 node6 node7
  node[1,6-7]
  
  $ echo node1 node6 node7 | nodeset -f
  node[1,6-7]
  
  $ echo node1 node6 node7 | nodeset -f node0 -
  node[0-1,6-7]


Furthermore, *nodeset*'s standard input reader is able to process multiple
lines and multiple node sets or groups per line. The following example shows a
simple use case::

    $ mount -t nfs | cut -d':' -f1
    nfsserv1
    nfsserv2
    nfsserv3
    
    $ mount -t nfs | cut -d':' -f1 | nodeset -f
    nfsserv[1-3]


Other usage examples of *nodeset* below show how it can be useful to provide
node sets from standard input (*sinfo* is a SLURM [#]_ command to view nodes
and partitions information and *sacct* is a command to display SLURM
accounting data)::

    $ sinfo -p cuda -o '%N' -h
    node[156-159]
    
    $ sinfo -p cuda -o '%N' -h | nodeset -e
    node156 node157 node158 node159
    
    $ for node in $(sinfo -p cuda -o '%N' -h | nodeset -e); do
            sacct -a -N $node > /tmp/cudajobs.$node;
      done

Previous rules also apply when working with node groups, for example when
using ``nodeset -r`` reading from standard input (and a matching group is
found)::

    $ nodeset -f @gpu
    node[156-159]
    
    $ sinfo -p cuda -o '%N' -h | nodeset -r
    @gpu

Most commands described in this section produce output results that may be
formatted using ``--output-format`` and ``--separator`` which are described in
:ref:`nodeset-commands-formatting`.

Commands with no input
""""""""""""""""""""""

The following table shows all other commands that are supported by
*nodeset*. These commands don't support any input (like node sets), but can
still recognize options as specified below.

+--------------------+-----------------------------------------------------+
| Command w/o input  | Description                                         |
+====================+=====================================================+
| ``-l, --list``     | List node groups from selected *group source* as    |
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

.. _nodeset-commands-formatting:

Output result formatting
""""""""""""""""""""""""

When using the expand command (``-e, --expand``), a separator string is used
when displaying results. The option ``-S``, ``--separator`` allows you to
modify it. The specified string is interpreted, so that you can use special
characters as separator, like ``\n`` or ``\t``. The default separator is the
space character *" "*. This is an example showing such separator string
change::

    $ nodeset -e --separator='\n' node[0-3]
    node0
    node1
    node2
    node3

The ``-O, --output-format`` option can be used to format output results of
most *nodeset* commands. The string passed to this option is used as a base
format pattern applied to each node or each result (depending on the command
and other options requested). The default format string is *"%s"*.  Formatting
is performed using the Python builtin string formatting operator, so you must
use one format operator of the right type (*%s* is guaranteed to work in all
cases). Here is an output formatting example when using the expand command::

    $ nodeset --output-format='%s-ipmi' -e node[1-2]x[1-2]
    node1x1-ipmi node1x2-ipmi node2x1-ipmi node2x2-ipmi

Output formatting and separator combined can be useful when using the expand
command, as shown here::

    $ nodeset -O '%s-ipmi' -S '\n' -e node[1-2]x[1-2]
    node1x1-ipmi
    node1x2-ipmi
    node2x1-ipmi
    node2x2-ipmi

When using the output formatting option along with the folding command, the
format is applied to each node but the result is still folded::

    $ nodeset -O '%s-ipmi' -f mgmt1 mgmt2 login[1-4]
    login[1-4]-ipmi,mgmt[1-2]-ipmi


.. _nodeset-stepping:

Stepping and auto-stepping
^^^^^^^^^^^^^^^^^^^^^^^^^^

The *nodeset* command, as does the *clush* command, is able to recognize by
default a factorized notation for range sets of the form *a-b/c*, indicating a
list of integers starting from *a*, less than or equal to *b* with the
increment (step) *c*.

For example, the *0-6/2* format indicates a range of 0-6 stepped by 2; that
is 0,2,4,6::

    $ nodeset -e node[0-6/2]
    node0 node2 node4 node6

However, by default, *nodeset* never uses this stepping notation in output
results, as other cluster tools seldom if ever support this feature. Thus, to
enable such factorized output in *nodeset*, you must specify
``--autostep=AUTOSTEP`` to set an auto step threshold number when folding
nodesets (ie. when using ``-f`` or ``-r``). This threshold number
(AUTOSTEP) is the minimum occurrence of equally-spaced integers needed to
enable auto-stepping.

For example::

    $ nodeset -f --autostep=3 node1 node3 node5
    node[1-5/2]
    
    $ nodeset -f --autostep=4 node1 node3 node5
    node[1,3,5]

It is important to note that resulting node sets with enabled auto-stepping
never create overlapping ranges, for example::

    $ nodeset -f --autostep=3 node1 node5 node9 node13
    node[1-13/4]

    $ nodeset -f --autostep=3 node1 node5 node7 node9 node13
    node[1,5-9/2,13]

However, any ranges given as input may still overlap (in this case, *nodeset*
will automatically spread them out so that they do not overlap), for example::

    $ nodeset -f --autostep=3 node[1-13/4,7]
    node[1,5-9/2,13]


A minimum node count threshold **percentage** before autostep is enabled may
also be specified as autostep value (or ``auto`` which is currently 100%).  In
the two following examples, only the first 4 of the 7 indexes may be
represented using the step syntax (57% of them)::

    $ nodeset -f --autostep=50% node[1,3,5,7,34,39,99]
    node[1-7/2,34,39,99]

    $ nodeset -f --autostep=90% node[1,3,5,7,34,39,99]
    node[1,3,5,7,34,39,99]


Zero-padding
^^^^^^^^^^^^

Sometimes, cluster node names are padded with zeros (eg. *node007*). With
*nodeset*, when leading zeros are used, resulting host names or node sets
are automatically padded with zeros as well. For example::

    $ nodeset -e node[08-11]
    node08 node09 node10 node11
    
    $ nodeset -f node001 node002 node003 node005
    node[001-003,005]

Zero-padding and stepping (as seen in :ref:`nodeset-stepping`) together are
also supported, for example::

    $ nodeset -e node[000-012/4]
    node000 node004 node008 node012

Nevertheless, care should be taken when dealing with padding, as a zero-padded
node name has priority over a normal one, for example::

    $ nodeset -f node1 node02
    node[01-02]

To clarify, *nodeset* will always try to coalesce node names by their
numerical index first (without taking care of any zero-padding), and then will
use the first zero-padding rule encountered. In the following example, the
first zero-padding rule found is *node01*'s one::

    $ nodeset -f node01 node002
    node[01-02]

That said, you can see it is not possible to mix *node01* and *node001* in the
same node set (not supported by the :class:`.NodeSet` class), but that would
be a tricky case anyway!


Leading and trailing digits
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Version 1.7 introduces improved support for bracket leading and trailing
digits. Those digits are automatically included within the range set,
allowing all node set operations to be fully supported.

Examples with bracket leading digits::

    $ nodeset -f node-00[00-99]
    node-[0000-0099]

    $ nodeset -f node-01[01,09,42]
    node-[0101,0109,0142]

Examples with bracket trailing digits::

    $ nodeset -f node-[1-2]0-[0-2]5
    node-[10,20]-[05,15,25]

Examples with both bracket leading and trailing digits::

    $ nodeset -f node-00[1-6]0
    node-[0010,0020,0030,0040,0050,0060]

    $ nodeset --autostep=auto -f node-00[1-6]0
    node-[0010-0060/10]

Still, using this syntax can be error-prone especially if used with node sets
without 0-padding or with the */step* syntax and also requires additional
processing by the parser. In general, we recommend writing the whole rangeset
inside the brackets.

.. warning:: Using the step syntax (seen above) within a bracket-delimited
   range set is not compatible with **trailing** digits. For instance, this is
   **not** supported: ``node-00[1-6/2]0``

Arithmetic operations
^^^^^^^^^^^^^^^^^^^^^

As a preamble to this section, keep in mind that all operations can be
repeated/mixed within the same *nodeset* command line, they will be
processed from left to right.

Union operation
"""""""""""""""

Union is the easiest arithmetic operation supported by *nodeset*: there is
no special command line option for that, just provide several node sets and
the union operation will be computed, for example::

    $ nodeset -f node[1-3] node[4-7]
    node[1-7]
    
    $ nodeset -f node[1-3] node[2-7] node[5-8]
    node[1-8]

Other operations
""""""""""""""""

As an extension to the above, other arithmetic operations are available by
using the following command-line options (*working set* is the node set
currently processed on the command line -- always from left to right):

+--------------------------------------------+---------------------------------+
| *nodeset* command option                   | Operation                       |
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
:ref:`nodeset-rangeset` for more info about *nodeset*'s rangeset mode.


Arithmetic operations usage examples::

    $ nodeset -f node[1-9] -x node6
    node[1-5,7-9]
    
    $ nodeset -f node[1-9] -i node[6-11]
    node[6-9]
    
    $ nodeset -f node[1-9] -X node[6-11]
    node[1-5,10-11]
    
    $ nodeset -f node[1-9] -x node6 -i node[6-12]
    node[7-9]

.. _nodeset-extended-patterns:

*Extended patterns* support
"""""""""""""""""""""""""""

*nodeset* does also support arithmetic operations through its "extended
patterns" (inherited from :class:`.NodeSet` extended pattern feature, see
:ref:`class-NodeSet-extended-patterns`, there is an example of use::

    $ nodeset -f node[1-4],node[5-9]
    node[1-9]
    
    $ nodeset -f node[1-9]\!node6
    node[1-5,7-9]

    $ nodeset -f node[1-9]\&node[6-12]
    node[6-9]
    
    $ nodeset -f node[1-9]^node[6-11]
    node[1-5,10-11]

Special operations
^^^^^^^^^^^^^^^^^^

A few special operations are currently available: node set slicing, splitting
on a predefined node count, splitting non-contiguous subsets, choosing fold
axis (for multidimensional node sets) and picking N nodes randomly. They are
all explained below.

Slicing
"""""""

Slicing is a way to select elements from a node set by their index (or from a
range set when using ``-R`` toggle option, see :ref:`nodeset-rangeset`. In
this case actually, and because *nodeset*'s underlying :class:`.NodeSet` class
sorts elements as observed after folding (for example), the word *set* may
sound like a stretch of language (a *set* isn't usually sorted). Indeed,
:class:`.NodeSet` further guarantees that its iterator will traverse the set
in order, so we should see it as a *ordered set*. The following simple example
illustrates this sorting behavior::

    $ nodeset -f b2 b1 b0 b c a0 a
    a,a0,b,b[0-2],c

Slicing is performed through the following command-line option:

+---------------------------------------+-----------------------------------+
| *nodeset* command option              | Operation                         |
+=======================================+===================================+
| ``-I RANGESET``, ``--slice=RANGESET`` | *slicing*: get sliced off result, |
|                                       | selecting elements from provided  |
|                                       | rangeset's indexes                |
+---------------------------------------+-----------------------------------+

Some slicing examples are shown below::

    $ nodeset -f -I 0 node[4-8]
    node4
    
    $ nodeset -f --slice=0 bnode[0-9] anode[0-9]
    anode0
    
    $ nodeset -f --slice=1,4,7,9,15 bnode[0-9] anode[0-9]
    anode[1,4,7,9],bnode5
    
    $ nodeset -f --slice=0-18/2 bnode[0-9] anode[0-9]
    anode[0,2,4,6,8],bnode[0,2,4,6,8]


Splitting into *n* subsets
""""""""""""""""""""""""""

Splitting a node set into several parts is often useful to get separate groups
of nodes, for instance when you want to check MPI comm between nodes, etc.
Based on :meth:`.NodeSet.split` method, the *nodeset* command provides the
following additional command-line option (since v1.4):

+--------------------------+--------------------------------------------+
| *nodeset* command option | Operation                                  |
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

    $ nodeset -f --split=4 node[0-7]
    node[0-1]
    node[2-3]
    node[4-5]
    node[6-7]
    
    $ nodeset -f --split=4 node[0-6]
    node[0-1]
    node[2-3]
    node[4-5]
    node6
    
    $ nodeset -f --split=10000 node[0-4]
    foo0
    foo1
    foo2
    foo3
    foo4
    
    $ nodeset -f --autostep=3 --split=2 node[0-38/2]
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

    $ nodeset -f --contiguous node[1-100,200-300,500]
    node[1-100]
    node[200-300]
    node500


Similarly, the following example shows how to display each resulting
contiguous node set in an expanded manner to separate lines::

    $ nodeset -e --contiguous node[1-9,11-19]
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

    $ nodeset --axis=1 -f node1-ib0 node2-ib0 node1-ib1 node2-ib1
    node[1-2]-ib0,node[1-2]-ib1

    $ nodeset --axis=2 -f node1-ib0 node2-ib0 node1-ib1 node2-ib1
    node1-ib[0-1],node2-ib[0-1]

Because a single nodeset may have several different dimensions, axis indices
are silently truncated to fall in the allowed range. Negative indices are
useful to fold along the last axis whatever number of dimensions used::

    $ nodeset --axis=-1 -f comp-[1-2]-[1-36],login-[1-2]
    comp-1-[1-36],comp-2-[1-36],login-[1-2]

.. _nodeset-pick:

Picking N node(s) at random
"""""""""""""""""""""""""""

Use ``--pick`` with a maximum number of nodes you wish to pick randomly from
the resulting node set (or from the resulting range set with ``-R``)::

    $ nodeset --pick=1 -f node11 node12 node13
    node12
    $ nodeset --pick=2 -f node11 node12 node13
    node[11,13]


.. _nodeset-groups:

Node groups
^^^^^^^^^^^

This section tackles the node groups feature available more particularly
through the *nodeset* command-line tool. The ClusterShell library defines a
node groups syntax and allow you to bind these group sources to your
applications (cf. :ref:`node groups configuration <groups-config>`). Having
those group sources, group provisioning is easily done through user-defined
external shell commands.  Thus, node groups might be very dynamic and their
nodes might change very often. However, for performance reasons, external call
results are still cached in memory to avoid duplicate external calls during
*nodeset* execution.  For example, a group source can be bound to a resource
manager or a custom cluster database.

For further details about using node groups in Python, please see
:ref:`class-NodeSet-groups`. For advanced usage, you should also be able to
define your own group source directly in Python (cf.
:ref:`class-NodeSet-groups-override`).

.. _nodeset-groupsexpr:

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

As already mentioned, the following *nodeset* command is available to list
configured group sources and also display the default group source (unless
``-q`` is provided)::

    $ nodeset --groupsources
    local (default)
    genders
    slurm

Listing group names
"""""""""""""""""""

If the **list** external shell command is configured (see
:ref:`node groups configuration <groups-config>`), it is possible to list
available groups *from the default source* with the following commands::

    $ nodeset -l
    @mgnt
    @mds
    @oss
    @login
    @compute

Or, to list groups *from a specific group source*, use *-l* in conjunction
with *-s* (or *--groupsource*)::

    $ nodeset -l -s slurm
    @slurm:parallel
    @slurm:cuda

Or, to list groups *from all available group sources*, use *-L* (or
*--list-all*)::

    $ nodeset -L
    @mgnt
    @mds
    @oss
    @login
    @compute
    @slurm:parallel
    @slurm:cuda

You can also use ``nodeset -ll`` or ``nodeset -LL`` to see each group's
associated node sets.


Using node groups in basic commands
"""""""""""""""""""""""""""""""""""

The use of node groups with the *nodeset* command is very straightforward.
Indeed, any group name, prefixed by **@** as mentioned above, can be used in
lieu of a node name, where it will be substituted for all nodes in that group.

A first, simple example is a group expansion (using default source) with
*nodeset*::

    $ nodeset -e @oss
    node40 node41 node42 node43 node44 node45

The *nodeset* count command works as expected::

    $ nodeset -c @oss
    6

Also *nodeset* folding command can always resolve node groups::

    $ nodeset -f @oss
    node[40-45]

There are usually two ways to use a specific group source (need to be properly
configured)::

    $ nodeset -f @slurm:parallel
    node[50-81]
    
    $ nodeset -f -s slurm @parallel
    node[50-81]

.. _nodeset-group-finding:

Finding node groups
"""""""""""""""""""

As an extension to the **list** command, you can search node groups that a
specified node set belongs to with ``nodeset -l[ll]`` as follow::

    $ nodeset -l node40
    @all
    @oss
    
    $ nodeset -ll node40
    @all node[1-159]
    @oss node[40-45]

This feature is implemented with the help of the :meth:`.NodeSet.groups`
method (see :ref:`class-NodeSet-groups-finding` for further details).

.. _nodeset-regroup:

Resolving node groups
"""""""""""""""""""""

If needed group configuration conditions are met (cf. :ref:`node groups
configuration <groups-config>`), you can try group lookups thanks to the ``-r,
--regroup`` command. This feature is implemented with the help of the
:meth:`.NodeSet.regroup()` method (see :ref:`class-NodeSet-regroup` for
further details). Only exact matching groups are returned (all containing
nodes needed), for example::

    $ nodeset -r node[40-45]
    @oss
    
    $ nodeset -r node[0,40-45]
    @mgnt,@oss


When resolving node groups, *nodeset* always returns the largest groups
first, instead of several smaller matching groups, for instance::

    $ nodeset -ll
    @login node[50-51]
    @compute node[52-81]
    @intel node[50-81]
    
    $ nodeset -r node[50-81]
    @intel

If no matching group is found, ``nodeset -r`` still returns folded result (as
does ``-f``)::

    $ nodeset -r node40 node42
    node[40,42]

Indexed node groups
"""""""""""""""""""

Node groups are themselves some kind of group sets and can be indexable. To
use this feature, node groups external shell commands need to return indexed
group names (automatically handled by the library as needed). For example,
take a look at these indexed node groups::

    $ nodeset -l
    @io1
    @io2
    @io3
    
    $ nodeset -f @io[1-3]
    node[40-45]


Arithmetic operations on node groups
""""""""""""""""""""""""""""""""""""

Arithmetic and special operations (as explained for node sets in
nodeset-arithmetic and nodeset-special are also supported with node groups.
Any group name can be used in lieu of a node set, where it will be substituted
for all nodes in that group before processing requested operations. Some
typical examples are::

    $ nodeset -f @lustre -x @mds
    node[40-45]
    
    $ nodeset -r @lustre -x @mds
    @oss
    
    $ nodeset -r -a -x @lustre
    @compute,@login,@mgnt

More advanced examples, with the use of node group sets, follow::

    $ nodeset -r @io[1-3] -x @io2
    @io[1,3]
    
    $ nodeset -f -I0 @io[1-3]
    node40
    
    $ nodeset -f --split=3 @oss
    node[40-41]
    node[42-43]
    node[44-45]
    
    $ nodeset -r --split=3 @oss
    @io1
    @io2
    @io3


*Extended patterns* support with node groups
""""""""""""""""""""""""""""""""""""""""""""

Even for node groups, the *nodeset* command supports arithmetic operations
through its *extended pattern* feature (see
:ref:`class-NodeSet-extended-patterns`).
A first example illustrates node groups intersection, that can be used in
practice to get nodes available from two dynamic group sources at a given
time::

    $ nodeset -f @db:prod\&@compute

The following fictive example computes a folded node set containing nodes
found in node group ``@gpu``  and ``@slurm:bigmem``, but not in both, minus
the nodes found in odd ``@chassis`` groups from 1 to 9 (computed from left to
right)::

    $ nodeset -f @gpu^@slurm:bigmem\!@chassis[1-9/2]

Also, version 1.7 introduces a notation extension ``@*`` (or ``@SOURCE:*``)
that has been added to quickly represent *all nodes* (please refer to
:ref:`clush-all-nodes` for more details).


.. _nodeset-all-nodes:

Selecting all nodes
"""""""""""""""""""

The option ``-a`` (without argument) can be used to select **all** nodes from
a group source (see :ref:`node groups configuration <groups-config>` for more
details on special **all** external shell command upcall). Example of use for
the default group source::

    $ nodeset -a -f
    example[4-6,32-159]

Use ``-s/--groupsource`` to select another group source.

If not properly configured, the ``-a`` option may lead to runtime errors
like::

    $ nodeset -s mybrokensource -a -f
    nodeset: External error: Not enough working methods (all or map + list)
        to get all nodes

A similar option is available with :ref:`clush-tool`, see
:ref:`selecting all nodes with clush <clush-all-nodes>`.

Node wildcards
""""""""""""""

ClusterShell 1.8 introduces node wildcards: ``*`` means match zero or more
characters of any type; ``?`` means match exactly one character of any type.

Any wildcard mask found is matched against **all** nodes from the group source
(see :ref:`nodeset-all-nodes`).

This can be especially useful for server farms, or when cluster node names
differ.  Say that your :ref:`group configuration <groups-config>` is set to
return the following "all nodes"::

    $ nodeset -f -a
    bckserv[1-2],dbserv[1-4],wwwserv[1-9]

Then, you can use wildcards to select particular nodes, as shown below::

    $ nodeset -f 'www*'
    wwwserv[1-9]

    $ nodeset -f 'www*[1-4]'
    wwwserv[1-4]

    $ nodeset -f '*serv1'
    bckserv1,dbserv1,wwwserv1

Wildcard masks are resolved prior to
:ref:`extended patterns <nodeset-extended-patterns>`, but each mask is
evaluated as a whole node set operand. In the example below, we select
all nodes matching ``*serv*`` before removing all nodes matching ``www*``::

    $ nodeset  -f '*serv*!www*'
    bckserv[1-2],dbserv[1-4]

.. _nodeset-rangeset:

Range sets
^^^^^^^^^^

Working with range sets
"""""""""""""""""""""""

By default, the *nodeset* command works with node or group sets and its
functionality match most :class:`.NodeSet` class methods. Similarly, *nodeset*
will match :class:`.RangeSet` methods when you make use of the ``-R`` option
switch. In that case, all operations are restricted to numerical ranges. For
example, to expand the range "``1-10``", you should use::

    $ nodeset -e -R 1-10
    1 2 3 4 5 6 7 8 9 10

Almost all commands and operations available for node sets are also available
with range sets. The only restrictions are commands and operations related to
node groups. For instance, the following command options are **not** available
with ``nodeset -R``:

* ``-r, --regroup`` as this feature is obviously related to node groups,
* ``-a / --all`` as the **all** external call is also related to node groups.


Using range sets instead of node sets doesn't change the general command
usage, like the need of one command option presence (cf. nodeset-commands), or
the way to give some input (cf. nodeset-stdin), for example::

    $ echo 3 2 36 0 4 1 37 | nodeset -fR
    0-4,36-37
    
    $ echo 0-8/4 | nodeset -eR -S'\n'
    0
    4
    8

Stepping and auto-stepping are supported (cf. :ref:`nodeset-stepping`) and
also zero-padding (cf. nodeset-zpad), which are both :class:`.RangeSet` class
features anyway.

The following examples illustrate these last points::

    $ nodeset -fR 03 05 01 07 11 09
    01,03,05,07,09,11
    
    $ nodeset -fR --autostep=3 03 05 01 07 11 09
    01-11/2

Arithmetic and special operations
"""""""""""""""""""""""""""""""""

All arithmetic operations, as seen for node sets (cf. nodeset-arithmetic), are
available for range sets, for example::

    $ nodeset -fR 1-14 -x 10-20
    1-9
    
    $ nodeset -fR 1-14 -i 10-20
    10-14
    
    $ nodeset -fR 1-14 -X 10-20
    1-9,15-20

For now, there is no *extended patterns* syntax for range sets as for node
sets (cf. :ref:`nodeset-extended-patterns`). However, as the union operator
``,`` is available natively by design, such expressions are still allowed::

    $ nodeset -fR 4-10,1-2
    1-2,4-10


Besides arithmetic operations, special operations may be very convenient for
range sets also. Below is an example with ``-I / --slice`` (cf.
nodeset-slice)::

    $ nodeset -fR -I 0 100-131
    100
    
    $ nodeset -fR -I 0-15 100-131
    100-115

There is another special operation example with ``--split`` (cf.
nodeset-splitting-n)::

    $ nodeset -fR --split=2 100-131
    100-115
    116-131

Finally, an example of the special operation ``--contiguous`` (cf.
nodeset-splitting-contiguous)::

    $ nodeset -f -R --contiguous 1-9,11,13-19
    1-9
    11
    13-19

*rangeset* alias
""""""""""""""""

When using *nodeset* with range sets intensively (eg. for scripting), it may
be convenient to create a local command alias, as shown in the following
example (Bourne shell), making it sort of a super `seq(1)`_ command::

    $ alias rangeset='nodeset -R'
    $ rangeset -e 0-8/2
    0 2 4 6 8


.. [#] SLURM is an open-source resource manager (https://computing.llnl.gov/linux/slurm/)

.. _seq(1): http://linux.die.net/man/1/seq

