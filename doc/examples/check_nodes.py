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


class CheckNodesResult(object):
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

    def ev_read(self, worker, node, sname, msg):
        """Read event from remote nodes"""
        # this is an example to demonstrate remote result parsing
        bootime = " ".join(msg.strip().split()[2:])
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

    def ev_close(self, worker, timedout):
        """Worker has finished (command done on all nodes)"""
        if timedout:
            nodeset = NodeSet.fromlist(worker.iter_keys_timeout())
            self.result.nodes_ko.add(nodeset)
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
                      default="128", help="Fanout window size (default 128)",
                      type=int)
    parser.add_option("-t", "--timeout", action="store", dest="timeout",
                      default="5", help="Timeout in seconds (default 5)",
                      type=float)
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
