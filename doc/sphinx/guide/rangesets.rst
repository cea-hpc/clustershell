Range sets
==========

.. highlight:: python

Cluster node names being typically indexed, common node sets rely heavily on
numerical range sets. The :mod:`.RangeSet` module provides two public classes
to deal directly with such range sets, :class:`.RangeSet` and
:class:`.RangeSetND`, presented in the following sections.

.. _class-RangeSet:

RangeSet class
--------------

The :class:`.RangeSet` class implements a mutable, ordered set of cluster node
indexes (one dimension) featuring a fast range-based API. This class is used
by the :class:`.NodeSet` class (see :ref:`class-NodeSet`). Since version 1.6,
:class:`.RangeSet` really derives from standard Python set class (`Python
sets`_), and thus provides methods like :meth:`.RangeSet.union`,
:meth:`.RangeSet.intersection`, :meth:`.RangeSet.difference`,
:meth:`.RangeSet.symmetric_difference` and their in-place versions
:meth:`.RangeSet.update`, :meth:`.RangeSet.intersection_update`,
:meth:`.RangeSet.difference_update()` and
:meth:`.RangeSet.symmetric_difference_update`.

Since v1.6, padding of ranges (eg. *003-009*) can be managed through a public
:class:`.RangeSet` instance variable named padding. It may be changed at any
time. Padding is a simple display feature per RangeSet object, thus current
padding value is not taken into account when computing set operations. Also
since v1.6, :class:`.RangeSet` is itself an iterator over its items as
integers (instead of strings). To iterate over string items as before (with
optional padding), you can now use the :meth:`.RangeSet.striter()` method.

.. _class-RangeSetND:

RangeSetND class
----------------

The :class:`.RangeSetND` class builds a N-dimensional RangeSet mutable object
and provides the common set methods. This class is public and may be used
directly, however we think it is less convenient to manipulate that
:class:`.NodeSet` and does not necessarily provide the same one-dimension
optimization (see :ref:`class-NodeSet-nD`). Several constructors are
available, using RangeSet objects, strings or individual multidimensional
tuples, for instance::

    >>> from ClusterShell.RangeSet import RangeSet, RangeSetND
    >>> r1 = RangeSet("1-5/2")
    >>> r2 = RangeSet("10-12")
    >>> r3 = RangeSet("0-4/2")
    >>> r4 = RangeSet("10-12")
    >>> print r1, r2, r3, r4
    1,3,5 10-12 0,2,4 10-12
    >>> rnd = RangeSetND([[r1, r2], [r3, r4]])
    >>> print rnd
    0-5; 10-12

    >>> print list(rnd)
    [(0, 10), (0, 11), (0, 12), (1, 10), (1, 11), (1, 12), (2, 10), (2, 11), (2, 12), (3, 10), (3, 11), (3, 12), (4, 10), (4, 11), (4, 12), (5, 10), (5, 11), (5, 12)]
    >>> r1 = RangeSetND([(0, 4), (0, 5), (1, 4), (1, 5)])
    >>> len(r1)
    4
    >>> str(r1)
    '0-1; 4-5\n'
    >>> r2 = RangeSetND([(1, 4), (1, 5), (1, 6), (2, 5)])
    >>> str(r2)
    '1; 4-6\n2; 5\n'
    >>> r = r1 & r2
    >>> str(r)
    '1; 4-5\n'
    >>> list(r)
    [(1, 4), (1, 5)]


.. _Python sets: http://docs.python.org/library/sets.html
