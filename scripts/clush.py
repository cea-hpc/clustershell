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
Usage: clush [-d] [options] [-x|--exclude <nodeset>] -w|--nodes <nodeset> [cmd]

Pdsh-like with integrated dshbak command using the ClusterShell library.
"""

import getopt
import os
import sys
import readline

sys.path.append('../lib')

import ClusterShell

from ClusterShell.Event import EventHandler
from ClusterShell.NodeSet import NodeSet
from ClusterShell.Task import *
from ClusterShell import version

#
# TODO:
#  - Supports timeout as task.resume(timeout= ), ev_timeout in OutputHandler 
#  - Better handling of return codes
#

class OutputHandler(EventHandler):
    def ev_read(self, worker):
        print "%s: %s" % worker.last_read()
    def ev_hup(self, worker):
        ns, rc = worker.last_retcode()
        if rc > 0:
            print "clush: %s: exited with retcode %d" % (ns, rc) 
    def ev_timeout(self, worker):
        print "clush: %s: timeout reached" % worker.last_node()
        

def display_buffers(worker):

    # Display command output
    for buffer, nodeset in worker.iter_buffers():
        print "-" * 15
        print NodeSet.fromlist(nodeset, autostep=3)
        print "-" * 15
        print buffer

    # Display return code if not ok ( != 0)
    for rc, nodeset in worker.iter_retcodes():
        if rc != 0:
            ns = NodeSet.fromlist(nodeset, autostep=3)
            print "clush: %s: exited with exit code %s" % (ns, rc)

def run_command(task, cmd, ns, gather, timeout):
    """
    Create and run the specified command line, displaying
    results in a dshbak way if gathering is used.
    """    

    if gather:
        worker = task.shell(cmd, nodes=ns, timeout=timeout)
    else:
        worker = task.shell(cmd, nodes=ns, handler=OutputHandler(), timeout=timeout)
 
    task.resume()
    if gather:
       display_buffers(worker)
   
    return task.max_retcode()

def interactive(task, ns, gather, timeout):
   """Manage the interactive prompt to run command"""
   rc = 0
   cmd = ""
   while cmd.lower() != "quit":
        try:
            cmd = raw_input("clush> ")
        except EOFError:
            print
            break

        if cmd.lower() != "quit":
            rc = run_command(task, cmd, ns, gather, timeout)

   return rc

def usage(msg):
    print "error: %s" % (msg)
    print __doc__
    sys.exit(2)

def runClush(args):

    # Default values
    nodeset_base, nodeset_exclude = NodeSet(), NodeSet()
    debug = False
    fanout = 0
    connect_timeout = 0
    command_timeout = 0
    gather = True

    #
    # Argument management
    #
    try:
        opts, args = getopt.getopt(args[1:], "dDhf:t:u:x:w:v", ["debug", \
                "help", "fanout=", "connect_timeout=", "command_timeout=", \
                "exclude=", "nodes=", "version", "nogather"])
    except getopt.error, msg:
        usage(msg)

    try:
        for k, v in opts:
            if k in ("-w", "--nodes"):
                nodeset_base.update(v)
            if k in ("-x", "--exclude"):
                nodeset_exclude.update(v)
            elif k in ("-d", "--debug"):
                debug = True
            elif k in ("-f", "--fanout"):
                fanout = int(v)
            elif k in ("-t", "--connect_timeout"):
                connect_timeout = int(v)
            elif k in ("-u", "--command_timeout"):
                command_timeout = int(v)
            elif k in ("-D", "--nogather"):
                gather = False
            elif k in ("-v", "--version"):
                print "Version %s" % version
                sys.exit(0)
            elif k in ("-h", "--help"):
                print __doc__
                sys.exit(0)
    except ValueError, e:
        usage("Invalid argument: %s %s" % (k, v))

    #
    # Compute the nodeset
    #

    # De we have a exclude list? (-x ...)
    nodeset_base.difference_update(nodeset_exclude)
    if len(nodeset_base) < 1:
        usage("No node to run on.")

    #
    # Task management
    #

    timeout = 0
    task = task_self()
    if debug:
        task.set_info("debug", debug)
    if fanout:
        task.set_info("fanout", fanout)
    if connect_timeout:
        task.set_info("connect_timeout", connect_timeout)
        timeout = connect_timeout
    if command_timeout:
        task.set_info("command_timeout", command_timeout)
        timeout += timeout

    # Either we have no more arguments, so use interactive mode
    if len(args) == 0:

        rc = interactive(task, nodeset_base, gather, timeout)

    # If not, just prepare a command with the last args an run it
    else:

        rc = run_command(task, ' '.join(args), nodeset_base, gather, timeout)

    sys.exit(rc)


if __name__ == '__main__':
    try:
        runClush(sys.argv)
    except KeyboardInterrupt:
        print

