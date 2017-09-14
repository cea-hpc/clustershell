Going further
=============

.. highlight:: console

Running the test suite
----------------------

Get the latest :ref:`install-source` code first.

.. note:: "The intent of regression testing is to assure that in the process of
   fixing a defect no existing functionality has been broken. Non-regression
   testing is performed to test that an intentional change has had the desired
   effect." (from `Wikipedia`_)

The *tests* directory of the source archive (not the RPM) contains all
regression and non-regression tests. To run all tests with Python 2, use the
following commands::

    $ cd tests
    $ nosetests -sv --all-modules .

Or run all tests with Python 3 by using the following command instead::

    $ nosetests-3 -sv --all-modules .

Some tests assume that *ssh(1)* to localhost is allowed for the current user.
Some tests use *bc(1)*. And some tests need *pdsh(1)* installed.

Bug reports
-----------

We use `Github Issues`_ as issue tracking system for the ClusterShell
development project. There, you can report bugs or suggestions after logged in
with your Github account.


.. _Wikipedia: https://en.wikipedia.org/wiki/Non-regression_testing
.. _Github Issues: https://github.com/cea-hpc/clustershell/issues
