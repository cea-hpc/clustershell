Going further
=============

.. highlight:: console

Running the test suite
----------------------

The *tests* directory of the source archive (not the RPM) contains all
non-regression tests. To run all tests, use the following::

    $ cd tests
    $ nosetests -sv --all-modules .

Some tests assume that *ssh(1)* to localhost is allowed for the current user.
Some tests use *bc(1)*. And some tests need *pdsh(1)* installed.

Bug reports
-----------

We use `Github Issues`_ as issue tracking system for the ClusterShell
development project. There, you can report bugs or suggestions after logged in
with your Github account.


.. _Github Issues: {https://github.com/cea-hpc/clustershell/issues
