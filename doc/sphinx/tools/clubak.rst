.. _clubak-tool:

clubak
------

.. highlight:: console

Overview
^^^^^^^^

*clubak* is another utility provided with the ClusterShell library that try to
gather and sort such dsh-like output::

    node17: MD5 (cstest.py) = 62e23bcf2e11143d4875c9826ef6183f
    node14: MD5 (cstest.py) = 62e23bcf2e11143d4875c9826ef6183f
    node16: MD5 (cstest.py) = e88f238673933b08d2b36904e3a207df
    node15: MD5 (cstest.py) = 62e23bcf2e11143d4875c9826ef6183f

If *file* content is made of such output, you got the following result::

    $ clubak -b < file
    ---------------
    node[14-15,17] (3)
    ---------------
     MD5 (cstest.py) = 62e23bcf2e11143d4875c9826ef6183f
    ---------------
    node16
    ---------------
     MD5 (cstest.py) = e88f238673933b08d2b36904e3a207df

Or with ``-L`` display option to disable header block::

    $ clubak -bL < file
    node[14-15,17]:  MD5 (cstest.py) = 62e23bcf2e11143d4875c9826ef6183f
    node16:  MD5 (cstest.py) = e88f238673933b08d2b36904e3a207df

Indeed, *clubak* formats text from standard input containing lines of the form
*node: output*.  It is fully backward compatible with *dshbak(1)* available
with *pdsh* but provides additional features. For instance, *clubak* always
displays its results sorted by node/nodeset.

But you do not need to execute *clubak* when using *clush* as all output
formatting features are already included in *clush* (see *clush -b / -B / -L*
examples, :ref:`clush-oneshot`). There are several advantages of having
*clubak* features included in *clush*: for example, it is possible, with
*clush*, to still get partial results when interrupted during command
execution (eg. with *Control-C*), thing not possible by just piping commands
together.

Most *clubak* options are the same as *clush*. For instance, to try to resolve
node groups in results, use ``-r, --regroup``::

    $ clubak -br < file

Like *clush*, *clubak* uses the :mod:`ClusterShell.MsgTree` module of the ClusterShell
library.

Tree trace mode (-T)
^^^^^^^^^^^^^^^^^^^^

A special option ``-T, --tree``, only available with \clubak, can switch on
:class:`.MsgTree` trace mode (all keys/nodes are kept for each message element
of the tree, thus allowing special output display). This mode has been first
added to replace *padb* [#]_ in some cases to display a whole cluster job
digested backtrace.

For example::

    $ cat trace_test
    node3: first_func()
    node1: first_func()
    node2: first_func()
    node5: first_func()
    node1: second_func()
    node4: first_func()
    node3: bis_second_func()
    node2: second_func()
    node5: second_func()
    node4: bis_second_func()

    $ cat trace_test | clubak -TL
    node[1-5]:
     first_func()
    node[1-2,5]:
       second_func()
    node[3-4]:
       bis_second_func()


.. [#] *padb*, a parallel application debugger (http://padb.pittman.org.uk/)

.. _ticket #166: https://github.com/cea-hpc/clustershell/issues/166
.. _ticket: https://github.com/cea-hpc/clustershell/issues/new

