.. _prog-examples:

Programming Examples
====================

.. highlight:: python

.. _prog-example-seq:

Remote command example (sequential mode)
----------------------------------------

The following example shows how to send a command on some nodes, how to get a
specific buffer and how to get gathered buffers::

    from ClusterShell.Task import task_self
    task = task_self()

    task.run("/bin/uname -r", nodes="green[36-39,133]")

    print task.node_buffer("green37")

    for buf, nodes in task.iter_buffers():
            print nodes, buf

    if task.max_retcode() != 0:
        print "An error occurred (max rc = %s)" % task.max_retcode()


Result::

    2.6.32-431.el6.x86_64
    ['green37', 'green38', 'green36', 'green39'] 2.6.32-431.el6.x86_64
    ['green133'] 3.10.0-123.20.1.el7.x86_64
    Max return code is 0

.. _prog-example-ev:

Remote command example with live output (event-based mode)
----------------------------------------------------------

The following example shows how to use the event-based programmation model by
installing an EventHandler and listening for :meth:`.EventHandler.ev_read`
(we've got a line to read) and :meth:`.EventHandler.ev_hup` (one command has
just completed) events. The goal here is to print standard outputs of ``uname
-a`` commands during their execution and also to notify the user of any
erroneous return codes::

    from ClusterShell.Task import task_self
    from ClusterShell.Event import EventHandler

    class MyHandler(EventHandler):

       def ev_read(self, worker):
           print "%s: %s" % (worker.current_node, worker.current_msg)

       def ev_hup(self, worker):
           if worker.current_rc != 0:
               print "%s: returned with error code %s" % (
                    worker.current_node, worker.current_rc)

    task = task_self()

    # Submit command, install event handler for this command and run task
    task.run("/bin/uname -a", nodes="fortoy[32-159]", handler=MyHandler())

.. _prog-example-script:

*check_nodes.py* example script
-------------------------------

The following script is available as an example in the source repository and
is usually packaged with ClusterShell::

    #!/usr/bin/python
    # check_nodes.py: ClusterShell simple example script.
    #
    # This script runs a simple command on remote nodes and report node
    # availability (basic health check) and also min/max boot dates.
    # It shows an example of use of Task, NodeSet and EventHandler objects.
    # Feel free to copy and modify it to fit your needs.
    #
    # Usage example: ./check_nodes.py -n node[1-99]

    import optparse
    from datetime import date, datetime
    import time

    from ClusterShell.Event import EventHandler
    from ClusterShell.NodeSet import NodeSet
    from ClusterShell.Task import task_self


    class CheckNodesResult:
        """Our result class"""
        def __init__(self):
            """Initialize result class"""
            self.nodes_ok = NodeSet()
            self.nodes_ko = NodeSet()
            self.min_boot_date = None
            self.max_boot_date = None

        def show(self):
            """Display results"""
            if self.nodes_ok:
                print "%s: OK (boot date: min %s, max %s)" % \
                    (self.nodes_ok, self.min_boot_date, self.max_boot_date)
            if self.nodes_ko:
                print "%s: FAILED" % self.nodes_ko

    class CheckNodesHandler(EventHandler):
        """Our ClusterShell EventHandler"""

        def __init__(self, result):
            """Initialize our event handler with a ref to our result object."""
            EventHandler.__init__(self)
            self.result = result

        def ev_read(self, worker):
            """Read event from remote nodes"""
            node = worker.current_node
            # this is an example to demonstrate remote result parsing
            bootime = " ".join(worker.current_msg.strip().split()[2:])
            date_boot = None
            for fmt in ("%Y-%m-%d %H:%M",): # formats with year
                try:
                    # datetime.strptime() is Python2.5+, use old method instead
                    date_boot = datetime(*(time.strptime(bootime, fmt)[0:6]))
                except ValueError:
                    pass
            for fmt in ("%b %d %H:%M",):    # formats without year
                try:
                    date_boot = datetime(date.today().year, \
                        *(time.strptime(bootime, fmt)[1:6]))
                except ValueError:
                    pass
            if date_boot:
                if not self.result.min_boot_date or \
                    self.result.min_boot_date > date_boot:
                    self.result.min_boot_date = date_boot
                if not self.result.max_boot_date or \
                    self.result.max_boot_date < date_boot:
                    self.result.max_boot_date = date_boot
                self.result.nodes_ok.add(node)
            else:
                self.result.nodes_ko.add(node)

        def ev_timeout(self, worker):
            """Timeout occurred on some nodes"""
            self.result.nodes_ko.add( \
                    NodeSet.fromlist(worker.iter_keys_timeout()))

        def ev_close(self, worker):
            """Worker has finished (command done on all nodes)"""
            self.result.show()

    def main():
        """ Main script function """
        # Initialize option parser
        parser = optparse.OptionParser()
        parser.add_option("-d", "--debug", action="store_true", dest="debug",
            default=False, help="Enable debug mode")
        parser.add_option("-n", "--nodes", action="store", dest="nodes",
            default="@all", help="Target nodes (default @all group)")
        parser.add_option("-f", "--fanout", action="store", dest="fanout",
            default="128", help="Fanout window size (default 128)", type=int)
        parser.add_option("-t", "--timeout", action="store", dest="timeout",
            default="5", help="Timeout in seconds (default 5)", type=float)
        options, _ = parser.parse_args()

        # Get current task (associated to main thread)
        task = task_self()
        nodes_target = NodeSet(options.nodes)
        task.set_info("fanout", options.fanout)
        if options.debug:
            print "nodeset : %s" % nodes_target
            task.set_info("debug", True)


        # Create ClusterShell event handler
        handler = CheckNodesHandler(CheckNodesResult())

        # Schedule remote command and run task (blocking call)
        task.run("who -b", nodes=nodes_target, handler=handler, \
            timeout=options.timeout)


    if __name__ == '__main__':
        main()

.. _prog-example-pp-sbatch:

Using NodeSet with Parallel Python Batch script using SLURM
-----------------------------------------------------------

The following example shows how to use the NodeSet class to expand
``$SLURM_NODELIST`` environment variable in a Parallel Python batch script
launched by SLURM. This variable may contain folded node sets. If ClusterShell
is not available system-wide on your compute cluster, you need to follow
:ref:`install-pip-user` first.

.. highlight:: bash

Example of SLURM ``pp.sbatch`` to submit using ``sbatch pp.sbatch``::

    #!/bin/bash

    #SBATCH -N 2
    #SBATCH --ntasks-per-node 1

    # run the servers
    srun ~/.local/bin/ppserver.py -w $SLURM_CPUS_PER_TASK -t 300 &
    sleep 10

    # launch the parallel processing
    python -u ./pp_jobs.py

.. highlight:: python

Example of a ``pp_jobs.py`` script::

    #!/usr/bin/env python

    import os, time
    import pp
    from ClusterShell.NodeSet import NodeSet

    # get the nodelist form Slurm
    nodeset = NodeSet(os.environ['SLURM_NODELIST'])

    # start the servers (ncpus=0 will make sure that none is started locally)
    # casting nodelist to tuple/list will correctly expand $SLURM_NODELIST
    job_server = pp.Server(ncpus=0, ppservers=tuple(nodelist))

    # make sure the servers have enough time to start
    time.sleep(5)

    # test function to execute on the remove nodes
    def test_func():
        print os.uname()

    # start the jobs
    job_1 = job_server.submit(test_func,(),(),("os",))
    job_2 = job_server.submit(test_func,(),(),("os",))

    # retrive the results
    print job_1()
    print job_2()

    # Cleanup
    job_server.print_stats()
    job_server.destroy()

