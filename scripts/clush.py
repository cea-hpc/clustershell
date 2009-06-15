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
import sys
import signal
import thread
from optparse import OptionParser

sys.path.insert(0, '../lib')
from ClusterShell.Event import EventHandler
from ClusterShell.NodeSet import NodeSet
from ClusterShell.Task import Task, task_self, task_wait
from ClusterShell.Worker.Worker import WorkerSimple
from ClusterShell import version

class UpdatePromptException(Exception):
    """Exception used by the signal handler"""

class StdInputHandler(EventHandler):
    """Standard input event handler class."""
    def __init__(self, worker):
        self.master_worker = worker
    def ev_read(self, worker):
        self.master_worker.write(worker.last_read() + '\n')
    def ev_close(self, worker):
        self.master_worker.set_write_eof()

class DirectOutputHandler(EventHandler):
    """Direct output event handler class."""
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
    def ev_close(self, worker):
        # Notify main thread to update its prompt
        worker.task.set_info("USER_running", False)
        if worker.task.info("USER_handle_SIGHUP"):
            os.kill(os.getpid(), signal.SIGHUP)

class GatherOutputHandler(EventHandler):
    """Gathered output event handler class."""
    def ev_close(self, worker):
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

        # Notify main thread to update its prompt
        worker.task.set_info("USER_running", False)
        if worker.task.info("USER_handle_SIGHUP"):
            os.kill(os.getpid(), signal.SIGHUP)

def signal_handler(signum, frame):
    """Signal handler used for main thread notification"""
    if signum == signal.SIGHUP:
        raise UpdatePromptException()

def get_history_file():
    """Turn the history file path"""
    return os.path.join(os.environ["HOME"], ".clush_history")

def readline_setup():
    """
    Configure readline to automatically load and save a history file
    named .clush_history
    """
    import readline
    try:
        readline.read_history_file(get_history_file())
    except IOError:
        pass

def ttyloop(task, nodeset, gather, timeout, label):
    """Manage the interactive prompt to run command"""
    if task.info("USER_interactive"):
        import readline
        assert sys.stdin.isatty()
        readline_setup()
        print "Enter 'quit' to leave this interactive mode"

    rc = 0
    ns = NodeSet(nodeset)
    cmd = ""
    while task.info("USER_running") or cmd.lower() != 'quit':
        try:
            if task.info("USER_interactive") and not task.info("USER_running"):
                print "Working with nodes: %s" % ns
                prompt = "clush> "
            else:
                prompt = ""
            cmd = raw_input(prompt)
        except EOFError:
            return
        except UpdatePromptException:
            if task.info("USER_interactive"):
                continue
            return
        if task.info("USER_running"):
            ns_reg, ns_unreg = NodeSet(), NodeSet()
            for c in task._engine.clients():
                if c.registered:
                    ns_reg.add(c.key)
                else:
                    ns_unreg.add(c.key)
            if ns_unreg:
                pending = "\nclush: pending(%d): %s" % (len(ns_unreg), ns_unreg)
            else:
                pending = ""
            print >>sys.stderr, "clush: interrupt (^C to abort task)\n" \
                    "clush: in progress(%d): %s%s" % (len(ns_reg), ns_reg, pending)
        else:
            cmdl = cmd.lower()
            if cmdl.startswith('+'):
                ns.add(cmdl[1:])
            elif cmdl.startswith('-'):
                ns.remove(cmdl[1:])
            elif cmdl.startswith('='):
                ns = NodeSet(cmdl[1:])
            elif cmdl != "quit":
                if not cmd:
                    continue
                readline.write_history_file(get_history_file())
                run_command(task, cmd, ns, gather, timeout, label)
    return rc

def run_command(task, cmd, ns, gather, timeout, label):
    """
    Create and run the specified command line, displaying
    results in a dshbak way if gathering is used.
    """    
    task.set_info("USER_running", True)

    if gather:
        worker = task.shell(cmd, nodes=ns, handler=GatherOutputHandler(), timeout=timeout)
    else:
        worker = task.shell(cmd, nodes=ns, handler=DirectOutputHandler(label), timeout=timeout)

    if not sys.stdin.isatty():
        # Switch stdin to non blocking mode
        fcntl.fcntl(sys.stdin, fcntl.F_SETFL, os.O_NDELAY)

        # Create a simple worker attached to stdin in autoclose mode
        worker_stdin = WorkerSimple(sys.stdin, None, None, None,
                handler=StdInputHandler(worker), timeout=-1, autoclose=True)

        # Add stdin worker to current task
        task.schedule(worker_stdin)
 
    task.resume()

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
    stdin_isatty = sys.stdin.isatty()
    if stdin_isatty:
        # Standard input is a terminal and we want to perform some user
        # interactions in the main thread (using blocking calls), so
        # we run cluster commands in a new ClusterShell Task (a new
        # thread is created).
        task = Task()
        signal.signal(signal.SIGHUP, signal_handler)
        task.set_info("USER_handle_SIGHUP", True)
    else:
        # Perform everything in main thread.
        task = task_self()
        task.set_info("USER_handle_SIGHUP", False)

    timeout = 0
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
            
    # Configure custom task related status
    task.set_info("USER_interactive", len(args) == 0)
    task.set_info("USER_running", False)

    if not task.info("USER_interactive"):
        run_command(task, ' '.join(args), nodeset_base, options.gather, timeout, options.label)

    if stdin_isatty:
        ttyloop(task, nodeset_base, options.gather, timeout, options.label)
    elif task.info("USER_interactive"):
        print >>sys.stderr, "ERROR: interactive mode requires a tty"
        os_.exit(1)

    # return the command retcode
    if options.maxrc:
        os._exit(task.max_retcode())
    # return clush retcode
    else:
        os._exit(0)

if __name__ == '__main__':
    try:
        clush_main(sys.argv)
    except KeyboardInterrupt:
        print "Keyboard interrupt."
        # Use os._exit to avoid threads cleanup
        os._exit(128 + signal.SIGINT)

