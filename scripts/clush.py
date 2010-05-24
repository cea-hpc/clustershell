#!/usr/bin/env python
#
# Copyright CEA/DAM/DIF (2007, 2008, 2009, 2010)
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
Utility program to run commands on a cluster using the ClusterShell
library.

clush is a pdsh-like command which benefits from the ClusterShell
library and its Ssh worker. It features an integrated output results
gathering system (dshbak-like), can get node groups by running
predefined external commands and can redirect lines read on its
standard input to the remote commands.

When no command are specified, clush runs interactively.

"""

import fcntl
import optparse
import os
import sys
import signal
import ConfigParser

from ClusterShell.NodeUtils import GroupResolverConfigError
from ClusterShell.NodeUtils import GroupResolverSourceError
from ClusterShell.NodeUtils import GroupSourceException
from ClusterShell.NodeUtils import GroupSourceNoUpcall
try:
    from ClusterShell.Event import EventHandler
    from ClusterShell.NodeSet import NodeSet, STD_GROUP_RESOLVER
    from ClusterShell.NodeSet import NodeSetExternalError, NodeSetParseError
    from ClusterShell.Task import Task, task_self
    from ClusterShell.Worker.Worker import WorkerSimple
    from ClusterShell import __version__
except GroupResolverConfigError, e:
    print >> sys.stderr, \
        "ERROR: ClusterShell Groups configuration error:\n\t%s" % e
    sys.exit(1)

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
        result = worker.last_read()
        if type(result) is tuple:
            (ns, buf) = result
        else:
            buf = result
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
            print >> sys.stderr, "%s: %s" % (ns, buf)
        else:
            print >> sys.stderr,"%s" % buf

    def ev_hup(self, worker):
        if hasattr(worker, "last_retcode"):
            ns, rc = worker.last_retcode()
        else:
            ns = "local"
            rc = worker.retcode()
        if rc > 0:
            print >> sys.stderr, "clush: %s: exited with exit code %d" % (ns, rc) 

    def ev_timeout(self, worker):
        print >> sys.stderr, "clush: %s: command timeout" % \
                NodeSet.fromlist(worker.iter_keys_timeout())

    def ev_close(self, worker):
        # If needed, notify main thread to update its prompt by sending
        # a SIGUSR1 signal. We use task-specific user-defined variable
        # to record current states (prefixed by USER_).
        worker.task.set_default("USER_running", False)
        if worker.task.default("USER_handle_SIGUSR1"):
            os.kill(os.getpid(), signal.SIGUSR1)

class GatherOutputHandler(EventHandler):
    """Gathered output event handler class."""

    def __init__(self, label, gather_info, runtimer):
        self._label = label
        self._gather_print, self._regroup, self._groupsource = gather_info
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
            print >> sys.stderr, "%s: %s" % (ns, buf)
        else:
            print >> sys.stderr,"%s" % buf
        if self._runtimer:
            # Force redisplay of counter
            self._runtimer.eh.set_dirty()

    def ev_close(self, worker):
        # Worker is closing -- it's time to gather results...
        if self._runtimer:
            self._runtimer.eh.finalize(worker.task.default("USER_interactive"))

        # Display command output, try to order buffers by rc
        nodesetify = lambda v: (v[0], NodeSet.fromlist(v[1]))
        for rc, nodelist in worker.iter_retcodes():
            # Then order by node/nodeset (see bufnodeset_cmp)
            for buf, nodeset in sorted(map(nodesetify,
                                           worker.iter_buffers(nodelist)),
                                       cmp=bufnodeset_cmp):
                self._gather_print(nodeset, buf, self._regroup, self._groupsource)

        # Display return code if not ok ( != 0)
        for rc, nodelist in worker.iter_retcodes():
            if rc != 0:
                ns = NodeSet.fromlist(nodelist)
                print >> sys.stderr, "clush: %s: exited with exit code %s" % (ns, rc)

        # Display nodes that didn't answer within command timeout delay
        if worker.num_timeout() > 0:
            print >> sys.stderr, "clush: %s: command timeout" % \
                    NodeSet.fromlist(worker.iter_keys_timeout())

        # Notify main thread to update its prompt
        worker.task.set_default("USER_running", False)
        if worker.task.default("USER_handle_SIGUSR1"):
            os.kill(os.getpid(), signal.SIGUSR1)

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
        cnt = len(self.task._engine.clients())
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
        Exception.__init__(self)
        self.section = section
        self.option = option
        self.msg = msg

    def __str__(self):
        return "(Config %s.%s): %s" % (self.section, self.option, self.msg)

class ClushConfig(ConfigParser.ConfigParser):
    """Config class for clush (specialized ConfigParser)"""

    main_defaults = { "fanout" : "64",
                      "connect_timeout" : "30",
                      "command_timeout" : "0",
                      "history_size" : "100",
                      "verbosity" : "%d" % VERB_STD }

    def __init__(self):
        ConfigParser.ConfigParser.__init__(self)
        # create Main section with default values
        self.add_section("Main")
        for key, value in ClushConfig.main_defaults.iteritems():
            self.set("Main", key, value)
        # config files override defaults values
        self.read(['/etc/clustershell/clush.conf', os.path.expanduser('~/.clush.conf')])

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


def signal_handler(signum, frame):
    """Signal handler used for main thread notification"""
    if signum == signal.SIGUSR1:
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

# Start of clubak.py common functions

def print_buffer(nodeset, content, regroup, groupsource):
    """Display a dshbak-like header block and content."""
    sep = "-" * 15
    if regroup:
        header = nodeset.regroup(groupsource)
    else:
        header = str(nodeset)
    sys.stdout.write("%s\n%s\n%s\n%s\n" % (sep, header, sep, content))

def print_lines(nodeset, msg, regroup, groupsource):
    """Display a MsgTree buffer by line with prefixed header."""
    if regroup:
        header = nodeset.regroup(groupsource)
    else:
        header = str(nodeset)
    for line in msg:
        sys.stdout.write("%s: %s\n" % (header, line))

def nodeset_cmp(ns1, ns2):
    """Compare 2 nodesets by their length (we want larger nodeset
    first) and then by first node."""
    len_cmp = cmp(len(ns2), len(ns1))
    if not len_cmp:
        smaller = NodeSet.fromlist([ns1[0], ns2[0]])[0]
        if smaller == ns1[0]:
            return -1
        else:
            return 1
    return len_cmp

# End of clubak.py common functions

def bufnodeset_cmp(bn1, bn2):
    """Convenience function to compare 2 (buf, nodeset) tuples by their
    nodeset length (we want larger nodeset first) and then by first
    node."""
    # Extract nodesets and call nodeset_cmp
    return nodeset_cmp(bn1[1], bn2[1])

def ttyloop(task, nodeset, gather, timeout, label, verbosity,
            (gather_print, regroup, groupsource)):
    """Manage the interactive prompt to run command"""
    readline_avail = False
    if task.default("USER_interactive"):
        assert sys.stdin.isatty()
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
    while task.default("USER_running") or cmd.lower() != 'quit':
        try:
            if task.default("USER_interactive") and not task.default("USER_running"):
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
            if task.default("USER_interactive"):
                continue
            return
        except KeyboardInterrupt, e:
            signal.signal(signal.SIGUSR1, signal.SIG_IGN)
            if gather:
                # Suspend task, so we can safely access its data from
                # the main thread
                task.suspend()

                print_warn = False

                # Display command output, but cannot order buffers by rc
                nodesetify = lambda v: (v[0], NodeSet.fromlist(v[1]))
                for buf, nodeset in sorted(map(nodesetify, task.iter_buffers()),
                                            cmp=bufnodeset_cmp):
                    if not print_warn:
                        print_warn = True
                        print >> sys.stderr, "Warning: Caught keyboard interrupt!"
                    gather_print(nodeset, buf, regroup, groupsource)
                    
                # Return code handling
                ns_ok = NodeSet()
                for rc, nodelist in task.iter_retcodes():
                    ns_ok.add(NodeSet.fromlist(nodelist))
                    if rc != 0:
                        # Display return code if not ok ( != 0)
                        ns = NodeSet.fromlist(nodelist)
                        print >> sys.stderr, \
                            "clush: %s: exited with exit code %s" % (ns, rc)
                # Add uncompleted nodeset to exception object
                e.uncompleted_nodes = ns - ns_ok

                # Display nodes that didn't answer within command timeout delay
                if task.num_timeout() > 0:
                    print >> sys.stderr, "clush: %s: command timeout" % \
                            NodeSet.fromlist(task.iter_keys_timeout())
            raise e

        if task.default("USER_running"):
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
            print >> sys.stderr, "clush: interrupt (^C to abort task)\n" \
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
                print >> sys.stderr, "clush: nodeset parse error (ignoring)"

            if ns_info:
                continue

            if cmdl.startswith('!') and len(cmd.strip()) > 0:
                run_command(task, cmd[1:], None, gather, timeout, None,
                            verbosity, (gather_print, regroup, groupsource))
            elif cmdl != "quit":
                if not cmd:
                    continue
                if readline_avail:
                    readline.write_history_file(get_history_file())
                run_command(task, cmd, ns, gather, timeout, label, verbosity,
                            (gather_print, regroup, groupsource))
    return rc

def bind_stdin(worker):
    """Create a ClusterShell stdin-reader worker bound to specified
    worker."""
    assert not sys.stdin.isatty()
    # Switch stdin to non blocking mode
    fcntl.fcntl(sys.stdin, fcntl.F_SETFL, \
        fcntl.fcntl(sys.stdin, fcntl.F_GETFL) | os.O_NDELAY)

    # Create a simple worker attached to stdin in autoclose mode
    worker_stdin = WorkerSimple(sys.stdin, None, None, None,
            handler=StdInputHandler(worker), timeout=-1, autoclose=True)

    # Add stdin worker to the same task than given worker
    worker.task.schedule(worker_stdin)

def run_command(task, cmd, ns, gather, timeout, label, verbosity, gather_info):
    """
    Create and run the specified command line, displaying
    results in a dshbak way when gathering is used.
    """    
    task.set_default("USER_running", True)

    if gather:
        runtimer = None
        if verbosity == VERB_STD or verbosity == VERB_VERB:
            # Create a ClusterShell timer used to display in live the
            # number of completed commands
            runtimer = task.timer(2.0, RunTimer(task, len(ns)), interval=1./3.,
                                  autoclose=True)
        worker = task.shell(cmd, nodes=ns, handler=GatherOutputHandler(label,
                            gather_info, runtimer), timeout=timeout)
    else:
        worker = task.shell(cmd, nodes=ns, handler=DirectOutputHandler(label),
                            timeout=timeout)

    if task.default("USER_stdin_worker"):
        bind_stdin(worker)
 
    task.resume()

def run_copy(task, source, dest, ns, timeout, preserve_flag):
    """
    run copy command
    """
    task.set_default("USER_running", True)

    # Source check
    if not os.path.exists(source):
        print >> sys.stderr, "ERROR: file \"%s\" not found" % source
        clush_exit(1)

    task.copy(source, dest, ns, handler=DirectOutputHandler(),
              timeout=timeout, preserve=preserve_flag)

    task.resume()

def clush_exit(status):
    # Flush stdio buffers
    for stream in [sys.stdout, sys.stderr]:
        stream.flush()
    # Use os._exit to avoid threads cleanup
    os._exit(status)

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

    parser.add_option("--nostdin", action="store_true", dest="nostdin",
                      help="don't watch for possible input from stdin")

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

    optgrp.add_option("-L", action="store_true", dest="line_mode", default=False,
                      help="disable header block and order output by nodes")
    optgrp.add_option("-N", action="store_false", dest="label", default=True,
                      help="disable labeling of command line")
    optgrp.add_option("-S", action="store_true", dest="maxrc",
                      help="return the largest of command return codes")
    optgrp.add_option("-b", "--dshbak", action="store_true", dest="gather",
                      default=False, help="display gathered results in a dshbak-like way")
    optgrp.add_option("-B", action="store_true", dest="gatherall",
                      default=False, help="like -b but including standard error")
    optgrp.add_option("-r", "--regroup", action="store_true", dest="regroup",
                      default=False, help="fold nodeset using node groups")
    optgrp.add_option("-s", "--groupsource", action="store", dest="groupsource",
                      help="optional groups.conf(5) group source to use")
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
    config = ClushConfig()

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
    if config.get_verbosity() > 1:
        STD_GROUP_RESOLVER.set_verbosity(1)
    if options.nodes_all:
        all_nodeset = NodeSet.fromall()
        config.verbose_print(VERB_DEBUG, \
            "Adding nodes from option -a: %s" % all_nodeset)
        nodeset_base.add(all_nodeset)

    if options.group:
        grp_nodeset = NodeSet()
        for grpopt in options.group:
            for grp in grpopt.split(','):
                addingrp = NodeSet("@" + grp)
                config.verbose_print(VERB_DEBUG, \
                    "Adding nodes from option -g %s: %s" % (grp, addingrp))
                nodeset_base.update(addingrp)

    if options.exgroup:
        for grpopt in options.exgroup:
            for grp in grpopt.split(','):
                removingrp = NodeSet("@" + grp)
                config.verbose_print(VERB_DEBUG, \
                    "Excluding nodes from option -X %s: %s" % (grp, removingrp))
                nodeset_exclude.update(removingrp)

    # Do we have an exclude list? (-x ...)
    nodeset_base.difference_update(nodeset_exclude)
    if len(nodeset_base) < 1:
        parser.error('No node to run on.')

    config.verbose_print(VERB_DEBUG, "Final NodeSet: %s" % nodeset_base)

    #
    # Task management
    #
    interactive = not len(args) and not options.source_path
    if options.nostdin and interactive:
        parser.error("illegal option `--nostdin' in interactive mode")

    user_interaction = not options.nostdin and sys.stdin.isatty() and \
                       sys.stdout.isatty()
    config.verbose_print(VERB_DEBUG, "User interaction: %s" % user_interaction)
    if user_interaction:
        # Standard input is a terminal and we want to perform some user
        # interactions in the main thread (using blocking calls), so
        # we run cluster commands in a new ClusterShell Task (a new
        # thread is created).
        task = Task()
        signal.signal(signal.SIGUSR1, signal_handler)
        task.set_default("USER_handle_SIGUSR1", True)
    else:
        # Perform everything in main thread.
        task.set_default("USER_handle_SIGUSR1", False)

    task.set_default("USER_stdin_worker", not (sys.stdin.isatty() or
                                               options.nostdin))
    config.verbose_print(VERB_DEBUG, "Create STDIN worker: %s" % \
                                        task.default("USER_stdin_worker"))

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

    gather = options.gatherall or options.gather
    # Enable stdout/stderr separation
    task.set_default("stderr", not options.gatherall)

    # Disable MsgTree buffering if not gathering outputs
    task.set_default("stdout_msgtree", gather)
    # Always disable stderr MsgTree buffering
    task.set_default("stderr_msgtree", False)

    # Set timeout at worker level when command_timeout is defined.
    if command_timeout > 0:
        timeout = command_timeout
    else:
        timeout = -1

    # Configure task custom status
    task.set_default("USER_interactive", interactive)
    task.set_default("USER_running", False)

    if options.source_path:
        if not options.dest_path:
            options.dest_path = os.path.dirname(options.source_path)
        op = "copy source=%s dest=%s" % (options.source_path, options.dest_path)
    else:
        op = "command=\"%s\"" % ' '.join(args)

    # print debug values (fanout value is get from the config object and not task
    # itself as set_info() is an asynchronous call.
    config.verbose_print(VERB_VERB, "clush: nodeset=%s fanout=%d [timeout conn=%.1f " \
            "cmd=%.1f] %s" %  (nodeset_base, config.get_fanout(),
                task.info("connect_timeout"),
                task.info("command_timeout"), op))

    # Select gather-mode print function
    if options.line_mode:
        gather_info = print_lines, options.regroup, options.groupsource
    else:
        gather_info = print_buffer, options.regroup, options.groupsource

    if not task.default("USER_interactive"):
        if options.source_path:
            run_copy(task, options.source_path, options.dest_path, nodeset_base,
                    0, options.preserve_flag)
        else:
            run_command(task, ' '.join(args), nodeset_base, gather, timeout,
                        options.label, config.get_verbosity(), gather_info)

    if user_interaction:
        ttyloop(task, nodeset_base, gather, timeout, options.label,
                config.get_verbosity(), gather_info)
    elif task.default("USER_interactive"):
        print >> sys.stderr, "ERROR: interactive mode requires a tty"
        clush_exit(1)

    rc = 0
    if options.maxrc:
        # Instead of clush return code, return commands retcode
        rc = task.max_retcode()
        if task.num_timeout() > 0:
            rc = 255
    clush_exit(rc)

if __name__ == '__main__':
    try:
        clush_main(sys.argv)
    except ClushConfigError, e:
        print >> sys.stderr, "ERROR: %s" % e
        sys.exit(1)
    except NodeSetExternalError, e:
        print >> sys.stderr, "clush: external error:", e
        sys.exit(1)
    except NodeSetParseError, e:
        print >> sys.stderr, "clush: parse error:", e
        sys.exit(1)
    except GroupResolverSourceError, e:
        print >> sys.stderr, "ERROR: unknown group source: \"%s\"" % e
        sys.exit(1)
    except GroupSourceNoUpcall, e:
        print >> sys.stderr, "ERROR: no %s upcall defined for group " \
            "source \"%s\"" % (e, e.group_source.name)
        sys.exit(1)
    except GroupSourceException, e:
        print >> sys.stderr, "ERROR: other group error:", e
        sys.exit(1)
    except IOError:
        # Ignore broken pipe
        os._exit(1)
    except KeyboardInterrupt, e:
        uncomp_nodes = getattr(e, 'uncompleted_nodes', None)
        if uncomp_nodes:
            print >> sys.stderr, "Keyboard interrupt (%s did not complete)." \
                                    % uncomp_nodes
        else:
            print >> sys.stderr, "Keyboard interrupt."
        clush_exit(128 + signal.SIGINT)

