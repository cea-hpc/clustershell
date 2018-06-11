.. _guide-NodeSet:

Node sets handling
==================

.. highlight:: python

.. _class-NodeSet:

NodeSet class
-------------

:class:`.NodeSet` is a class to represent an ordered set of node names
(optionally indexed). It's a convenient way to deal with cluster nodes and
ease their administration. :class:`.NodeSet` is implemented with the help of
two other ClusterShell public classes, :class:`.RangeSet` and
:class:`.RangeSetND`, which implement methods to manage a set of numeric
ranges in one or multiple dimensions. :class:`.NodeSet`, :class:`.RangeSet`
and :class:`.RangeSetND` APIs match standard Python sets.  A command-line
interface (:ref:`nodeset-tool`) which implements most of :class:`.NodeSet`
features, is also available.

Other classes of the ClusterShell library makes use of the :class:`.NodeSet`
class when they come to deal with distant nodes.

Using NodeSet
^^^^^^^^^^^^^

If you are used to `Python sets`_, :class:`.NodeSet` interface will be easy
for you to learn. The main conceptual difference is that :class:`.NodeSet`
iterators always provide ordered results (and also
:meth:`.NodeSet.__getitem__()` by index or slice is allowed). Furthermore,
:class:`.NodeSet` provides specific methods like
:meth:`.NodeSet.split()`, :meth:`.NodeSet.contiguous()` (see below), or
:meth:`.NodeSet.groups()`, :meth:`.NodeSet.regroup()` (these last two are
related to :ref:`class-NodeSet-groups`). The following code snippet shows you
a basic usage of the :class:`.NodeSet` class::

    >>> from ClusterShell.NodeSet import NodeSet
    >>> nodeset = NodeSet()
    >>> nodeset.add("node7")
    >>> nodeset.add("node6")
    >>> print nodeset
    node[6-7]

:class:`.NodeSet` class provides several object constructors::

    >>> print NodeSet("node[1-5]")
    node[1-5]
    >>> print NodeSet.fromlist(["node1", "node2", "node3"])
    node[1-3]
    >>> print NodeSet.fromlist(["node[1-5]", "node[6-10]"])
    node[1-10]
    >>> print NodeSet.fromlist(["clu-1-[1-4]", "clu-2-[1-4]"])
    clu-[1-2]-[1-4]

All corresponding Python sets operations are available, for example::

    >>> from ClusterShell.NodeSet import NodeSet
    >>> ns1 = NodeSet("node[10-42]")
    >>> ns2 = NodeSet("node[11-16,18-39]")
    >>> print ns1.difference(ns2)
    node[10,17,40-42]
    >>> print ns1 - ns2
    node[10,17,40-42]
    >>> ns3 = NodeSet("node[1-14,40-200]")
    >>> print ns3.intersection(ns1)
    node[10-14,40-42]


Unlike Python sets, it is important to notice that :class:`.NodeSet` is
somewhat not so strict about the type of element used for set operations. Thus
when a string object is encountered, it is automatically converted to a
NodeSet object for convenience. The following example shows an example of
this (set operation is working with either a native nodeset or a string)::

    >>> nodeset = NodeSet("node[1-10]")
    >>> nodeset2 = NodeSet("node7")
    >>> nodeset.difference_update(nodeset2)
    >>> print nodeset
    node[1-6,8-10]
    >>> 
    >>> nodeset.difference_update("node8")
    >>> print nodeset
    node[1-6,9-10]

NodeSet ordered content leads to the following being allowed::

    >>> nodeset = NodeSet("node[10-49]")
    >>> print nodeset[0]
    node10
    >>> print nodeset[-1]
    node49
    >>> print nodeset[10:]
    node[20-49]
    >>> print nodeset[:5]
    node[10-14]
    >>> print nodeset[::4]
    node[10,14,18,22,26,30,34,38,42,46]

And it works for node names without index, for example::

    >>> nodeset = NodeSet("lima,oscar,zulu,alpha,delta,foxtrot,tango,x-ray")
    >>> print nodeset
    alpha,delta,foxtrot,lima,oscar,tango,x-ray,zulu
    >>> print nodeset[0]
    alpha
    >>> print nodeset[-2]
    x-ray

And also for multidimensional node sets::

    >>> nodeset = NodeSet("clu1-[1-10]-ib[0-1],clu2-[1-10]-ib[0-1]")
    >>> print nodeset
    clu[1-2]-[1-10]-ib[0-1]
    >>> print nodeset[0]
    clu1-1-ib0
    >>> print nodeset[-1]
    clu2-10-ib1
    >>> print nodeset[::2]
    clu[1-2]-[1-10]-ib0

.. _class-NodeSet-split:

To split a NodeSet object into *n* subsets, use the :meth:`.NodeSet.split()`
method, for example::

    >>> for nodeset in NodeSet("node[10-49]").split(2):
    ...     print nodeset
    ... 
    node[10-29]
    node[30-49]

.. _class-NodeSet-contiguous:

To split a NodeSet object into contiguous subsets, use the
:meth:`.NodeSet.contiguous()` method, for example::

    >>> for nodeset in NodeSet("node[10-49,51-53,60-64]").contiguous():
    ...     print nodeset
    ... 
    node[10-49]
    node[51-53]
    node[60-64]

For further details, please use the following command to see full
:class:`.NodeSet` API documentation.


.. _class-NodeSet-nD:

Multidimensional considerations
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Version 1.7 introduces full support of multidimensional NodeSet (eg.
*da[2-5]c[1-2]p[0-1]*). The :class:`.NodeSet` interface is the same,
multidimensional patterns are automatically detected by the parser and
processed internally. While expanding a multidimensional NodeSet is easily
solved by performing a cartesian product of all dimensions, folding nodes is
much more complex and time consuming. To reduce the performance impact of such
feature, the :class:`.NodeSet` class still relies on :class:`.RangeSet` when
only one dimension is varying (see :ref:`class-RangeSet`).  Otherwise, it uses
a new class named :class:`.RangeSetND` for full multidimensional support (see
:ref:`class-RangeSetND`).

.. _class-NodeSet-extended-patterns:

Extended String Pattern
^^^^^^^^^^^^^^^^^^^^^^^

:class:`.NodeSet` class parsing engine recognizes an *extended string
pattern*, adding support for union (with special character *","*), difference
(with special character *"!"*), intersection (with special character *"&"*)
and symmetric difference (with special character *"^"*) operations. String
patterns are read from left to right, by proceeding any character operators
accordingly. The following example shows how you can use this feature::

    >>> print NodeSet("node[10-42],node46!node10")
    node[11-42,46]


.. _class-NodeSet-groups:

Node groups
-----------

Node groups are very useful and are needed to group similar cluster nodes in
terms of configuration, installed software, available resources, etc. A node
can be a member of more than one node group.

Using node groups
^^^^^^^^^^^^^^^^^

Node groups are prefixed with **@** character. Please see
:ref:`nodeset-groupsexpr` for more details about node group expression/syntax
rules.

Please also have a look at :ref:`Node groups configuration <groups-config>` to
learn how to configure external node group bingings (sources). Once setup
(please use the :ref:`nodeset-tool` command to check your configuration), the
NodeSet parsing engine automatically resolves node groups. For example::

    >>> print NodeSet("@oss")
    example[4-5]
    >>> print NodeSet("@compute")
    example[32-159]
    >>> print NodeSet("@compute,@oss")
    example[4-5,32-159]

That is, all NodeSet-based applications share the same system-wide node group
configuration (unless explicitly disabled --- see
:ref:`class-NodeSet-disable-group`).

When the **all** group upcall is configured (:ref:`node groups configuration
<groups-config>`), you can also use the following :class:`.NodeSet`
constructor::

    >>> print NodeSet.fromall()
    example[4-6,32-159]

When group upcalls are not properly configured, this constructor will raise a
*NodeSetExternalError* exception.

.. _class-NodeSet-groups-finding:

Finding node groups
^^^^^^^^^^^^^^^^^^^

In order to find node groups a specified node set belongs to, you can use the
:meth:`.NodeSet.groups()` method. This method is used by ``nodeset -l
<nodeset>`` command (see :ref:`nodeset-group-finding`). It returns a Python
dictionary where keys are groups found and values, provided for convenience,
are tuples of the form *(group_nodeset, contained_nodeset)*. For example::

    >>> for group, (group_nodes, contained_nodes) in NodeSet("@oss").groups().iteritems():
    ...     print group, group_nodes, contained_nodes
    ... 
    @all example[4-6,32-159] example[4-5]
    @oss example[4-5] example[4-5]


More usage examples follow::

    >>> print NodeSet("example4").groups().keys()
    ['@all', '@oss']
    >>> print NodeSet("@mds").groups().keys()
    ['@all', '@mds']
    >>> print NodeSet("dummy0").groups().keys()
    []

.. _class-NodeSet-regroup:

Regrouping node sets
^^^^^^^^^^^^^^^^^^^^

If needed group configuration conditions are met (cf. :ref:`node groups
configuration <groups-config>`), you can use the :meth:`.NodeSet.regroup()`
method to reduce node sets using matching groups, whenever possible::

    >>> print NodeSet("example[4-6]").regroup()
    @mds,@oss

The nodeset command makes use of the :meth:`.NodeSet.regroup()` method when
using the *-r* switch (see :ref:`nodeset-regroup`).


.. _class-NodeSet-groups-override:

Overriding default groups configuration
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

It is possible to override the libary default groups configuration by changing
the default :class:`.NodeSet` *resolver* object. Usually, this is done for
testing or special purposes. Here is an example of how to override the
*resolver* object using :func:`.NodeSet.set_std_group_resolver()` in order to
use another configuration file::

    >>> from ClusterShell.NodeSet import NodeSet, set_std_group_resolver
    >>> from ClusterShell.NodeUtils import GroupResolverConfig
    >>> set_std_group_resolver(GroupResolverConfig("/other/groups.conf"))
    >>> print NodeSet("@oss")
    other[10-20]

It is possible to restore :class:`.NodeSet` *default group resolver* by
passing None to the :func:`.NodeSet.set_std_group_resolver()` module function,
for example::

    >>> from ClusterShell.NodeSet import set_std_group_resolver
    >>> set_std_group_resolver(None)


.. _class-NodeSet-disable-group:

Disabling node group resolution
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If for any reason, you want to disable host groups resolution, you can use the
special resolver value *RESOLVER_NOGROUP*. In that case, :class:`.NodeSet`
parsing engine will not recognize **@** group characters anymore, for
instance::

    >>> from ClusterShell.NodeSet import NodeSet, RESOLVER_NOGROUP
    >>> print NodeSet("@oss")
    example[4-5]
    >>> print NodeSet("@oss", resolver=RESOLVER_NOGROUP)
    @oss

Any attempts to use a group-based method (like :meth:`.NodeSet.groups()` or
:meth:`.NodeSet.regroups()`) on such "no group" NodeSet will raise a
*NodeSetExternalError* exception.


NodeSet object serialization
----------------------------

The :class:`.NodeSet` class supports object serialization through the standard
*pickling*. Group resolution is done before *pickling*.



.. _Python sets: http://docs.python.org/library/sets.html
