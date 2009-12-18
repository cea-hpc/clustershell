#!/usr/bin/env python
#
# Copyright CEA/DAM/DIF (2007, 2008, 2009)
#  Contributor: Stephane THIELL <stephane.thiell@cea.fr>
#
# This file is part of the ClusterShell library.
#
# This software is governed by the CeCILL-C license under French law and
# abiding by the rules of distribution of free software.  You can  use,
# modify and/ or redistribute the software under the terms of the CeCILL-C
# license as circulated by CEA, CNRS and INRIA at the following URL
# "http://www.cecill.info".
#
# As a counterpart to the access to the source code and  rights to copy,
# modify and redistribute granted by the license, users are provided only
# with a limited warranty  and the software's author,  the holder of the
# economic rights,  and the successive licensors  have only  limited
# liability.
#
# In this respect, the user's attention is drawn to the risks associated
# with loading,  using,  modifying and/or developing or reproducing the
# software by the user in light of its specific status of free software,
# that may mean  that it is complicated to manipulate,  and  that  also
# therefore means  that it is reserved for developers  and  experienced
# professionals having in-depth computer knowledge. Users are therefore
# encouraged to load and test the software's suitability as regards their
# requirements in conditions enabling the security of their systems and/or
# data to be ensured and,  more generally, to use and operate it in the
# same conditions as regards security.
#
# The fact that you are presently reading this means that you have had
# knowledge of the CeCILL-C license and that you accept its terms.
#
# $Id$

"""
Utility program to run commands on a cluster using the ClusterShell library.

clush is a pdsh-like command which benefits from the ClusterShell library
and its Ssh worker. It features an integrated output results gathering
system (dshbak-like), can get node groups by running predefined external
commands and can redirect lines read on its standard input to the remote
commands.

When no command are specified, clush runs interactively.

"""

import fcntl
import optparse
import os
import sys
import signal
import thread
import ConfigParser

sys.path.insert(0, '../lib')

from ClusterShell.Event import EventHandler
from ClusterShell.NodeSet import NodeSet, NodeSetParseError
from ClusterShell.Task import Task, task_self
from ClusterShell.Worker.Worker import WorkerSimple
from ClusterShell import __version__

VERB_QUIET = 0
VERB_STD = 1
VERB_VERB = 2
VERB_DEBUG = 3

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

    def __init__(self, label=None):
        self._label = label

    def ev_read(self, worker):
        t = worker.last_read()
        if type(t) is tuple:
            (ns, buf) = t
        else:
            buf = t
        if self._label:
          print "%s: %s" % (ns, buf)
        else:
          print "%s" % buf

    def ev_error(self, worker):
        t = worker.last_error()
        if type(t) is tuple:
            (ns, buf) = t
        else:
            buf = t
        if self._label:
          print >>sys.stderr, "%s: %s" % (ns, buf)
        else:
          print >>sys.stderr,"%s" % buf

    def ev_hup(self, worker):
        if hasattr(worker, "last_retcode"):
            ns, rc = worker.last_retcode()
        else:
            ns = "local"
            rc = worker.retcode()
        if rc > 0:
            print >>sys.stderr, "clush: %s: exited with exit code %d" % (ns, rc) 

    def ev_timeout(self, worker):
        print >>sys.stderr, "clush: %s: command timeout" % \
                NodeSet.fromlist(worker.iter_keys_timeout())

    def ev_close(self, worker):
        # Notify main thread to update its prompt
        worker.task.set_info("USER_running", False)
        if worker.task.info("USER_handle_SIGHUP"):
            os.kill(os.getpid(), signal.SIGHUP)

class GatherOutputHandler(EventHandler):
    """Gathered output event handler class."""

    def __init__(self, label, runtimer):
        self._label = label
        self._runtimer = runtimer

    def ev_error(self, worker):
        t = worker.last_error()
        if type(t) is tuple:
            (ns, buf) = t
        else:
            buf = t
        if self._runtimer:
            self._runtimer.eh.erase_line()
        if self._label:
          print >>sys.stderr, "%s: %s" % (ns, buf)
        else:
          print >>sys.stderr,"%s" % buf
        if self._runtimer:
            # Force redisplay of counter
            self._runtimer.eh.set_dirty()

    def ev_close(self, worker):
        # Worker is closing -- it's time to gather results...
        if self._runtimer:
            self._runtimer.eh.finalize(worker.task.info("USER_interactive"))

        # Display command output, try to order buffers by rc
        for rc, nodeset in worker.iter_retcodes():
            for buffer, nodeset in worker.iter_buffers(nodeset):
                print "-" * 15
                print NodeSet.fromlist(nodeset)
                print "-" * 15
                print buffer

        # Display return code if not ok ( != 0)
        for rc, nodeset in worker.iter_retcodes():
            if rc != 0:
                ns = NodeSet.fromlist(nodeset)
                print "clush: %s: exited with exit code %s" % (ns, rc)

        # Display nodes that didn't answer within command timeout delay
        if worker.num_timeout() > 0:
            print >>sys.stderr, "clush: %s: command timeout" % \
                    NodeSet.fromlist(worker.iter_keys_timeout())

        # Notify main thread to update its prompt
        worker.task.set_info("USER_running", False)
        if worker.task.info("USER_handle_SIGHUP"):
            os.kill(os.getpid(), signal.SIGHUP)

class RunTimer(EventHandler):
    def __init__(self, task, total):
        self.task = task
        self.total = total
        self.cnt_last = -1
        self.tslen = len(str(self.total))
        self.wholelen = 0

    def ev_timer(self, timer):
        self.update()

    def set_dirty(self):
        self.cnt_last = -1

    def erase_line(self):
        if self.wholelen:
            sys.stderr.write(' ' * self.wholelen + '\r')

    def update(self):
        clients = self.task._engine.clients()
        cnt = len(clients)
        if cnt != self.cnt_last:
            self.cnt_last = cnt
            # display completed/total clients
            towrite = 'clush: %*d/%*d\r' % (self.tslen, self.total - cnt,
                self.tslen, self.total)
            self.wholelen = len(towrite)
            sys.stderr.write(towrite)

    def finalize(self, cr):
        # display completed/total clients
        fmt = 'clush: %*d/%*d'
        if cr:
            fmt += '\n'
        else:
            fmt += '\r'
        sys.stderr.write(fmt % (self.tslen, self.total, self.tslen, self.total))

class ClushConfigError(Exception):
    """Exception used by the signal handler"""

    def __init__(self, section, option, msg):
        self.section = section
        self.option = option
        self.msg = msg

    def __str__(self):
        return "(Config %s.%s): %s" % (self.section, self.option, self.msg)

class ClushConfig(ConfigParser.ConfigParser):
    """Config class for clush (specialized ConfigParser)"""

    defaults = { "fanout" : "64",
                 "connect_timeout" : "30",
                 "command_timeout" : "0",
                 "history_size" : "100",
                 "verbosity" : "%d" % VERB_STD }

    def __init__(self, overrides):
        ConfigParser.ConfigParser.__init__(self, ClushConfig.defaults)
        self.read(['/etc/clustershell/clush.conf', os.path.expanduser('~/.clush.conf')])
        if not self.has_section("Main"):
            self.add_section("Main")

    def verbose_print(self, level, message):
        if self.get_verbosity() >= level:
            print message

    def set_main(self, option, value):
        self.set("Main", option, str(value))

    def getint(self, section, option):
        try:
            return ConfigParser.ConfigParser.getint(self, section, option)
        except (ConfigParser.Error, TypeError, ValueError), e:
            raise ClushConfigError(section, option, e)

    def getfloat(self, section, option):
        try:
            return ConfigParser.ConfigParser.getfloat(self, section, option)
        except (ConfigParser.Error, TypeError, ValueError), e:
            raise ClushConfigError(section, option, e)

    def _get_optional(self, section, option):
        try:
            return self.get(section, option)
        except ConfigParser.Error, e:
            pass

    def get_verbosity(self):
        try:
            return self.getint("Main", "verbosity")
        except ClushConfigError:
            return 0

    def get_fanout(self):
        return self.getint("Main", "fanout")
    
    def get_connect_timeout(self):
        return self.getfloat("Main", "connect_timeout")

    def get_command_timeout(self):
        return self.getfloat("Main", "command_timeout")

    def get_ssh_user(self):
        return self._get_optional("Main", "ssh_user")

    def get_ssh_path(self):
        return self._get_optional("Main", "ssh_path")

    def get_ssh_options(self):
        return self._get_optional("Main", "ssh_options")

    def get_nodes_all_command(self):
        section = "External"
        option = "nodes_all"
        try:
            return self.get(section, option)
        except ConfigParser.Error, e:
            raise ClushConfigError(section, option, e)

    def get_nodes_group_command(self, group):
        section = "External"
        option = "nodes_group"
        try:
            return self.get(section, option, 0, { "group" : group })
        except ConfigParser.Error, e:
            raise ClushConfigError(section, option, e)


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
    readline.parse_and_bind("tab: complete")
    readline.set_completer_delims("")
    try:
        readline.read_history_file(get_history_file())
    except IOError:
        pass

def ttyloop(task, nodeset, gather, timeout, label, verbosity):
    """Manage the interactive prompt to run command"""
    has_readline = False
    if task.info("USER_interactive"):
        assert sys.stdin.isatty()
        readline_avail = False
        try:
            import readline
            readline_setup()
            readline_avail = True
        except ImportError:
            pass
        if verbosity >= VERB_STD:
            print "Enter 'quit' to leave this interactive mode"

    rc = 0
    ns = NodeSet(nodeset)
    ns_info = True
    cmd = ""
    while task.info("USER_running") or cmd.lower() != 'quit':
        try:
            if task.info("USER_interactive") and not task.info("USER_running"):
                if ns_info:
                    print "Working with nodes: %s" % ns
                    ns_info = False
                prompt = "clush> "
            else:
                prompt = ""
            cmd = raw_input(prompt)
        except EOFError:
            print
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
            try:
                ns_info = True
                if cmdl.startswith('+'):
                    ns.update(cmdl[1:])
                elif cmdl.startswith('-'):
                    ns.difference_update(cmdl[1:])
                elif cmdl.startswith('@'):
                    ns = NodeSet(cmdl[1:])
                elif cmdl == '=':
                    gather = not gather
                    if verbosity >= VERB_STD:
                        if gather:
                            print "Switching to gathered output format"
                        else:
                            print "Switching to standard output format"
                    ns_info = False
                    continue
                elif not cmdl.startswith('?'): # if ?, just print ns_info
                    ns_info = False
            except NodeSetParseError:
                print >>sys.stderr, "clush: nodeset parse error (ignoring)"

            if ns_info:
                continue

            if cmdl.startswith('!'):
                run_command(task, cmd[1:], None, gather, timeout, None, verbosity)
            elif cmdl != "quit":
                if not cmd:
                    continue
                if readline_avail:
                    readline.write_history_file(get_history_file())
                run_command(task, cmd, ns, gather, timeout, label, verbosity)
    return rc

def bind_stdin(worker):
    assert not sys.stdin.isatty()
    # Switch stdin to non blocking mode
    fcntl.fcntl(sys.stdin, fcntl.F_SETFL, os.O_NDELAY)

    # Create a simple worker attached to stdin in autoclose mode
    worker_stdin = WorkerSimple(sys.stdin, None, None, None,
            handler=StdInputHandler(worker), timeout=-1, autoclose=True)

    # Add stdin worker to the same task than given worker
    worker.task.schedule(worker_stdin)

def run_command(task, cmd, ns, gather, timeout, label, verbosity):
    """
    Create and run the specified command line, displaying
    results in a dshbak way when gathering is used.
    """    
    task.set_info("USER_running", True)

    if gather:
        runtimer = None
        if verbosity == VERB_STD or verbosity == VERB_VERB:
            # Create a ClusterShell timer used to display the number of completed commands
            runtimer = task.timer(2.0, RunTimer(task, len(ns)), interval=1./3., autoclose=True)
        worker = task.shell(cmd, nodes=ns, handler=GatherOutputHandler(label, runtimer), timeout=timeout)
    else:
        worker = task.shell(cmd, nodes=ns, handler=DirectOutputHandler(label), timeout=timeout)

    if not sys.stdin.isatty():
        bind_stdin(worker)
 
    task.resume()

def run_copy(task, source, dest, ns, timeout, preserve_flag):
    """
    run copy command
    """
    task.set_info("USER_running", True)

    # Source check
    if not os.path.exists(source):
        print >>sys.stderr, "ERROR: file \"%s\" not found" % source
        clush_exit(1)

    worker = task.copy(source, dest, ns, handler=DirectOutputHandler(),
                timeout=timeout, preserve=preserve_flag)

    task.resume()

def clush_exit(n):
    # Flush stdio buffers
    for f in [sys.stdout, sys.stderr]:
        f.flush()
    # Use os._exit to avoid threads cleanup
    os._exit(n)

def clush_main(args):
    """Main clush script function"""

    # Default values
    nodeset_base, nodeset_exclude = NodeSet(), NodeSet()

    #
    # Argument management
    #
    usage = "%prog [options] command"

    parser = optparse.OptionParser(usage, version="%%prog %s" % __version__)
    parser.disable_interspersed_args()

    # Node selections
    optgrp = optparse.OptionGroup(parser, "Selecting target nodes")
    optgrp.add_option("-w", action="append", dest="nodes",
                      help="nodes where to run the command")
    optgrp.add_option("-x", action="append", dest="exclude",
                      help="exclude nodes from the node list")
    optgrp.add_option("-a", "--all", action="store_true", dest="nodes_all",
                      help="run command on all nodes")
    optgrp.add_option("-g", "--group", action="append", dest="group",
                      help="run command on a group of nodes")
    optgrp.add_option("-X", action="append", dest="exgroup",
                      help="exclude nodes from this group")
    parser.add_option_group(optgrp)

    # Output behaviour
    optgrp = optparse.OptionGroup(parser, "Output behaviour")
    optgrp.add_option("-q", "--quiet", action="store_true", dest="quiet",
                      help="be quiet, print essential output only")
    optgrp.add_option("-v", "--verbose", action="store_true", dest="verbose",
                      help="be verbose, print informative messages")
    optgrp.add_option("-d", "--debug", action="store_true", dest="debug",
                      help="output more messages for debugging purpose")

    optgrp.add_option("-N", action="store_false", dest="label", default=True,
                      help="disable labeling of command line")
    optgrp.add_option("-S", action="store_true", dest="maxrc",
                      help="return the largest of command return codes")
    optgrp.add_option("-b", "--dshbak", action="store_true", dest="gather",
                      help="display results in a dshbak-like way")
    parser.add_option_group(optgrp)

    # Copy
    optgrp = optparse.OptionGroup(parser, "File copying")
    optgrp.add_option("-c", "--copy", action="store", dest="source_path",
                      help="copy local file or directory to the nodes")
    optgrp.add_option("--dest", action="store", dest="dest_path",
                      help="destination file or directory on the nodes")
    optgrp.add_option("-p", action="store_true", dest="preserve_flag",
                      help="preserve modification times and modes")
    parser.add_option_group(optgrp)

    # Ssh options
    optgrp = optparse.OptionGroup(parser, "Ssh options")
    optgrp.add_option("-f", "--fanout", action="store", dest="fanout", 
                      help="use a specified fanout", type="int")
    optgrp.add_option("-l", "--user", action="store", dest="user",
                      help="execute remote command as user")
    optgrp.add_option("-o", "--options", action="store", dest="options",
                      help="can be used to give ssh options")
    optgrp.add_option("-t", "--connect_timeout", action="store", dest="connect_timeout", 
                      help="limit time to connect to a node" ,type="float")
    optgrp.add_option("-u", "--command_timeout", action="store", dest="command_timeout", 
                      help="limit time for command to run on the node", type="float")
    parser.add_option_group(optgrp)

    (options, args) = parser.parse_args()

    #
    # Load config file
    #
    config = ClushConfig(options)

    # Apply command line overrides
    if options.quiet:
        config.set_main("verbosity", VERB_QUIET)
    if options.verbose:
        config.set_main("verbosity", VERB_VERB)
    if options.debug:
        config.set_main("verbosity", VERB_DEBUG)
    if options.fanout:
        config.set_main("fanout", options.fanout)
    if options.user:
        config.set_main("ssh_user", options.user)
    if options.options:
        config.set_main("ssh_options", options.options)
    if options.connect_timeout:
        config.set_main("connect_timeout", options.connect_timeout)
    if options.command_timeout:
        config.set_main("command_timeout", options.command_timeout)

    #
    # Compute the nodeset
    #
    if options.nodes:
        nodeset_base = NodeSet.fromlist(options.nodes)
    if options.exclude:
        nodeset_exclude = NodeSet.fromlist(options.exclude)

    # Do we have nodes group?
    task = task_self()
    task.set_info("debug", config.get_verbosity() > 1)
    if options.nodes_all:
        command = config.get_nodes_all_command()
        task.shell(command, key="all")
    if options.group:
        for grp in options.group:
            command = config.get_nodes_group_command(grp)
            task.shell(command, key="group")
    if options.exgroup:
        for grp in options.exgroup:
            command = config.get_nodes_group_command(grp)
            task.shell(command, key="exgroup")

    # Run needed external commands
    task.resume()

    for buf, keys in task.iter_buffers(['all', 'group']):
        for line in buf.splitlines():
            config.verbose_print(VERB_DEBUG, "Adding nodes from option %s: %s" % (','.join(keys), buf))
            nodeset_base.add(line)
    for buf, keys in task.iter_buffers(['exgroup']):
        for line in buf.splitlines():
            config.verbose_print(VERB_DEBUG, "Excluding nodes from option %s: %s" % (','.join(keys), buf))
            nodeset_exclude.add(line)

    # Do we have an exclude list? (-x ...)
    nodeset_base.difference_update(nodeset_exclude)
    if len(nodeset_base) < 1:
        parser.error('No node to run on.')

    config.verbose_print(VERB_DEBUG, "Final NodeSet is %s" % nodeset_base)

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
        task.set_info("USER_handle_SIGHUP", False)

    task.set_info("debug", config.get_verbosity() >= VERB_DEBUG)
    task.set_info("fanout", config.get_fanout())

    ssh_user = config.get_ssh_user()
    if ssh_user:
        task.set_info("ssh_user", ssh_user)
    ssh_path = config.get_ssh_path()
    if ssh_path:
        task.set_info("ssh_path", ssh_path)
    ssh_options = config.get_ssh_options()
    if ssh_options:
        task.set_info("ssh_options", ssh_options)

    # Set detailed timeout values
    connect_timeout = config.get_connect_timeout()
    task.set_info("connect_timeout", connect_timeout)
    command_timeout = config.get_command_timeout()
    task.set_info("command_timeout", command_timeout)
    task.set_info("default_stderr", True)

    # Set timeout at worker level when command_timeout is defined.
    if command_timeout > 0:
        timeout = command_timeout
    else:
        timeout = -1

    # Configure custom task related status
    task.set_info("USER_interactive", len(args) == 0 and not options.source_path)
    task.set_info("USER_running", False)

    if options.source_path and not options.dest_path:
        options.dest_path = options.source_path

    if options.source_path:
        if not options.dest_path:
            options.dest_path = options.source_path
        op = "copy source=%s dest=%s" % (options.source_path, options.dest_path)
    else:
        op = "command=\"%s\"" % ' '.join(args)

    config.verbose_print(VERB_VERB, "clush: nodeset=%s fanout=%d [timeout conn=%.1f " \
            "cmd=%.1f] %s" %  (nodeset_base, task.info("fanout"),
                task.info("connect_timeout"),
                task.info("command_timeout"), op))

    if not task.info("USER_interactive"):
        if options.source_path:
            if not options.dest_path:
                options.dest_path = options.source_path
            run_copy(task, options.source_path, options.dest_path, nodeset_base,
                    0, options.preserve_flag)
        else:
            run_command(task, ' '.join(args), nodeset_base, options.gather,
                    timeout, options.label, config.get_verbosity())

    if stdin_isatty:
        ttyloop(task, nodeset_base, options.gather, timeout, options.label,
                config.get_verbosity())
    elif task.info("USER_interactive"):
        print >>sys.stderr, "ERROR: interactive mode requires a tty"
        clush_exit(1)

    # return the command retcode
    if options.maxrc:
        clush_exit(task.max_retcode())
    # return clush retcode
    else:
        clush_exit(0)

if __name__ == '__main__':
    try:
        clush_main(sys.argv)
    except KeyboardInterrupt:
        print "Keyboard interrupt."
        clush_exit(128 + signal.SIGINT)
    except ClushConfigError, e:
        print >>sys.stderr, "ERROR: %s" % e
        sys.exit(1)

