#!/usr/bin/env python
# Copyright (C) 2007, 2008 CEA
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

Pdsh-like with integrated dshback command using the ClusterShell library.
"""

import fcntl
import getopt
import os
import sys

sys.path.append('../lib')

import ClusterShell

from ClusterShell.Event import EventHandler
from ClusterShell.NodeSet import NodeSet
from ClusterShell.Task import *

import socket

import pdb

def _prompt():
    sys.stdout.write("clush> ")
    sys.stdout.flush()

def _set_write_buffered():
    flag = fcntl.fcntl(sys.stdout, fcntl.F_GETFL)
    fcntl.fcntl(sys.stdout, fcntl.F_SETFL, flag & ~os.O_NDELAY)

def _set_write_nonblocking():
    fcntl.fcntl(sys.stdout, fcntl.F_SETFL, os.O_NDELAY)

class IShellHandler(EventHandler):
    def __init__(self):
        self.input_eh = None

    def ev_close(self, worker):
        _set_write_buffered()
        for buffer, nodeset in worker.iter_buffers():
            sys.stdout.write("----------------\n")
            sys.stdout.write(str(NodeSet.fromlist(nodeset, autostep=3)) + "\n")
            sys.stdout.write("----------------\n")
            sys.stdout.write(buffer)
        for rc, nodeset in worker.iter_retcodes():
            if rc != 0:
                ns = NodeSet.fromlist(nodeset, autostep=3)
                sys.stdout.write("%s: exited with exit code %s\n" % (ns, rc))
        _prompt()
        _set_write_nonblocking()
        self.input_eh.shell_worker = None

class IInputHandler(EventHandler):
    def __init__(self, nodes, eh):
        self.nodes = nodes
        self.shell_eh = eh
        self.shell_eh.input_eh = self
        self.shell_worker = None

    def ev_start(self, worker):
        _prompt()

    def ev_read(self, worker):
        if self.shell_worker is None:
            task = task_self()
            buf = worker.last_read()
            if len(buf) > 0:
                self.shell_worker = task.shell(buf, nodes=self.nodes, handler=self.shell_eh)
            else:
                _prompt()

def runClush(args):
    try:
        opts, args = getopt.getopt(args[1:], "dhf:t:u:x:w:", ["debug", \
                "help", "fanout=", "connect_timeout=", "command_timeout=", \
                "exclude=", "nodes="])
    except getopt.error, msg:
        print msg
        print "Try `python %s -h' for more information." % args[0]
        sys.exit(2)

    nodeset_base, nodeset_exclude = NodeSet(), NodeSet()
    debug = False
    fanout = 0
    connect_timeout = 0
    command_timeout = 0

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
        elif k in ("-h", "--help"):
            print __doc__
            sys.exit(0)

    nodeset_base.difference_update(nodeset_exclude)
    
    if len(nodeset_base) < 1:
        print __doc__
        sys.exit(0)

    task = task_self()

    if debug:
        task.set_info("debug", debug)
    if fanout:
        task.set_info("fanout", fanout)
    if connect_timeout:
        task.set_info("connect_timeout", connect_timeout)
    if command_timeout:
        task.set_info("command_timeout", command_timeout)

    if len(args) == 0:
        task.file(sys.stdin, handler=IInputHandler(nodeset_base, IShellHandler()))
        task.resume()
    else:
        worker = task.shell(' '.join(args), nodes=nodeset_base)

        task.resume()

        for buffer, nodeset in worker.iter_buffers():
            print "----------------"
            print NodeSet.fromlist(nodeset, autostep=3)
            print "----------------"
            print buffer,

        for rc, nodeset in worker.iter_retcodes():
            if rc != 0:
                ns = NodeSet.fromlist(nodeset, autostep=3)
                print "clush: %s: exited with exit code %s" % (ns, rc)

        sys.exit(task.max_retcode())

if __name__ == '__main__':
    try:
        runClush(sys.argv)
    except KeyboardInterrupt:
        print

