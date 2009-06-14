#!/usr/bin/env python
# Copyright (C) 2007, 2008, 2009 CEA
# Written by S. Thiell
#
# This file is part of ClusterShell
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
# $Id$


"""
Pdsh-like with integrated dshbak command using the ClusterShell library.
"""

import fcntl
import os
import readline
import sys
import signal
from optparse import OptionParser

sys.path.insert(0, '../lib')
from ClusterShell.Event import EventHandler
from ClusterShell.NodeSet import NodeSet
from ClusterShell.Task import task_self
from ClusterShell.Worker.Worker import WorkerSimple
from ClusterShell import version


class StdInputHandler(EventHandler):
    def __init__(self, worker):
        self.master_worker = worker
    def ev_read(self, worker):
        self.master_worker.write(worker.last_read() + '\n')
    def ev_close(self, worker):
        self.master_worker.set_write_eof()

class OutputHandler(EventHandler):
    def __init__(self, label):
        self._label = label
    def ev_read(self, worker):
        ns, buf = worker.last_read()
        if self._label:
          print "%s: %s" % (ns, buf)
        else:
          print "%s" % buf
    def ev_hup(self, worker):
        ns, rc = worker.last_retcode()
        if rc > 0:
            print "clush: %s: exited with exit code %d" % (ns, rc) 
    def ev_timeout(self, worker):
        print "clush: %s: command timeout" % worker.last_node()
        

def display_buffers(worker):

    # Display command output, try to order buffers by rc
    for rc, nodeset in worker.iter_retcodes():
        for buffer, nodeset in worker.iter_buffers(nodeset):
            print "-" * 15
            print NodeSet.fromlist(nodeset, autostep=3)
            print "-" * 15
            print buffer

    # Display return code if not ok ( != 0)
    for rc, nodeset in worker.iter_retcodes():
        if rc != 0:
            ns = NodeSet.fromlist(nodeset, autostep=3)
            print "clush: %s: exited with exit code %s" % (ns, rc)

def run_command(task, cmd, ns, gather, timeout, label):
    """
    Create and run the specified command line, displaying
    results in a dshbak way if gathering is used.
    """    

    if gather:
        worker = task.shell(cmd, nodes=ns, timeout=timeout)
    else:
        worker = task.shell(cmd, nodes=ns, handler=OutputHandler(label), timeout=timeout)

    if not sys.stdin.isatty():
        # Switch stdin to non blocking mode
        fcntl.fcntl(sys.stdin, fcntl.F_SETFL, os.O_NDELAY)

        # Create a simple worker attached to stdin in autoclose mode
        worker_stdin = WorkerSimple(sys.stdin, None, None, None,
                handler=StdInputHandler(worker), timeout=-1, autoclose=True)

        # Add stdin worker to current task
        task.schedule(worker_stdin)
 
    task.resume()

    if gather:
       display_buffers(worker)
   
    return task.max_retcode()

def interactive(task, ns, gather, timeout, label):
   """Manage the interactive prompt to run command"""
   rc = 0
   cmd = ""
   print "Enter 'quit' to leave this interactive mode"
   while cmd.lower() != "quit":
        try:
            cmd = raw_input("clush> ")
        except EOFError:
            print
            break

        if cmd.lower() != "quit":
            rc = run_command(task, cmd, ns, gather, timeout, label)

   return rc

def clush_main(args):
    """Main clush script function"""

    # Default values
    nodeset_base, nodeset_exclude = NodeSet(), NodeSet()

    #
    # Argument management
    #
    usage = "usage: %prog [options] -w RANGES command"

    parser = OptionParser(usage, version="%%prog %s" % version)
    parser.disable_interspersed_args()

    parser.add_option("-d", "--debug", action="store_true", dest="debug",
                      help="output more messages for debugging purpose")

    # Node selections
    parser.add_option("-w", action="store", dest="nodes",
                      help="node ranges where to run the command")
    parser.add_option("-x", action="store", dest="exclude",
                      help="exclude the node range from the node list")

    parser.add_option("-N", action="store_false", dest="label", default=True,
                      help="disable labeling of command line")
    parser.add_option("-l", "--user", action="store", dest="user",
                      help="execute remote command as user")
    parser.add_option("-S", action="store_true", dest="maxrc",
                      help="return the largest of command return codes")
    parser.add_option("-b", "--dshbak", action="store_true", dest="gather",
                      help="display results in a dshbak-like way")
    parser.add_option("-f", "--fanout", action="store", dest="fanout", 
                      help="use a specified fanout", type="int")

    # Timeouts
    parser.add_option("-t", "--connect_timeout", action="store", dest="connect_timeout", 
                      help="limit time to connect to a node" ,type="int")
    parser.add_option("-u", "--command_timeout", action="store", dest="command_timeout", 
                      help="limit time for command to run on the node", type="int")

    (options, args) = parser.parse_args()

    #
    # Compute the nodeset
    #
    nodeset_base = NodeSet(options.nodes)
    nodeset_exclude = NodeSet(options.exclude)

    # De we have an exclude list? (-x ...)
    nodeset_base.difference_update(nodeset_exclude)
    if len(nodeset_base) < 1:
        parser.error('No node to run on.')

    #
    # Task management
    #
    timeout = 0
    task = task_self()
    if options.debug:
        task.set_info("debug", options.debug)
    if options.fanout:
        task.set_info("fanout", options.fanout * 2)
    if options.user:
        task.set_info("ssh_user", options.user)
    if options.connect_timeout:
        task.set_info("connect_timeout", options.connect_timeout)
        timeout += options.connect_timeout
    if options.command_timeout:
        task.set_info("command_timeout", options.command_timeout)
        timeout += options.command_timeout

    # Either we have no more arguments, so use interactive mode
    if not len(args):
        rc = interactive(task, nodeset_base, options.gather, timeout, options.label)

    # If not, just prepare a command with the last args and run it
    else:
        rc = run_command(task, ' '.join(args), nodeset_base, options.gather, timeout, options.label)

    # return the command retcode
    if options.maxrc:
        sys.exit(rc)
    # return clush retcode
    else:
        sys.exit(0)

if __name__ == '__main__':
    try:
        clush_main(sys.argv)
    except KeyboardInterrupt:
        print "Keyboard interrupt."
        sys.exit(128 + signal.SIGINT)

