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
execute cluster commands in parallel

clush is an utility program to run commands on a cluster which benefits
from the ClusterShell library and its Ssh worker. It features an
integrated output results gathering system (dshbak-like), can get node
groups by running predefined external commands and can redirect lines
read on its standard input to the remote commands.

When no command are specified, clush runs interactively.

"""

import errno
import fcntl
import os
import resource
import sys
import signal

from ClusterShell.CLI.Config import ClushConfig, ClushConfigError
from ClusterShell.CLI.Config import VERB_STD, VERB_VERB, VERB_DEBUG
from ClusterShell.CLI.Display import Display
from ClusterShell.CLI.OptionParser import OptionParser
from ClusterShell.CLI.Error import GENERIC_ERRORS, handle_generic_error
from ClusterShell.CLI.Utils import NodeSet, bufnodeset_cmp

from ClusterShell.Event import EventHandler
from ClusterShell.MsgTree import MsgTree
from ClusterShell.NodeSet import NOGROUP_RESOLVER, STD_GROUP_RESOLVER
from ClusterShell.NodeSet import NodeSetParseError
from ClusterShell.Task import Task, task_self
from ClusterShell.Worker.Worker import WorkerSimple


class UpdatePromptException(Exception):
    """Exception used by the signal handler"""

class StdInputHandler(EventHandler):
    """Standard input event handler class."""

    def __init__(self, worker):
        EventHandler.__init__(self)
        self.master_worker = worker

    def ev_read(self, worker):
        self.master_worker.write(worker.last_read() + '\n')

    def ev_close(self, worker):
        self.master_worker.set_write_eof()

class OutputHandler(EventHandler):
    """Base class for clush output handlers."""
    def update_prompt(self, worker):
        """
        If needed, notify main thread to update its prompt by sending
        a SIGUSR1 signal. We use task-specific user-defined variable
        to record current states (prefixed by USER_).
        """
        worker.task.set_default("USER_running", False)
        if worker.task.default("USER_handle_SIGUSR1"):
            os.kill(os.getpid(), signal.SIGUSR1)
        
class DirectOutputHandler(OutputHandler):
    """Direct output event handler class."""

    def __init__(self, display):
        OutputHandler.__init__(self)
        self._display = display

    def ev_read(self, worker):
        res = worker.last_read()
        if len(res) == 2:
            ns, buf = res
        else:
            buf = res
            ns = "LOCAL"
        self._display.print_line(ns, buf)

    def ev_error(self, worker):
        res = worker.last_error()
        if len(res) == 2:
            ns, buf = res
        else:
            buf = res
            ns = "LOCAL"
        self._display.print_line_error(ns, buf)

    def ev_hup(self, worker):
        if hasattr(worker, "last_retcode"):
            ns, rc = worker.last_retcode()
        else:
            ns = "LOCAL"
            rc = worker.retcode()
        if rc > 0:
            print >> sys.stderr, "clush: %s: exited with exit code %d" \
                                    % (ns, rc) 

    def ev_timeout(self, worker):
        print >> sys.stderr, "clush: %s: command timeout" % \
                NodeSet.fromlist(worker.iter_keys_timeout())

    def ev_close(self, worker):
        self.update_prompt(worker)

class GatherOutputHandler(OutputHandler):
    """Gathered output event handler class."""

    def __init__(self, display, runtimer):
        OutputHandler.__init__(self)
        self._display = display
        self._runtimer = runtimer

    def ev_error(self, worker):
        ns, buf = worker.last_error()
        self._runtimer_clean()
        self._display.print_line_error(ns, buf)
        self._runtimer_set_dirty()

    def _runtimer_clean(self):
        """Hide runtimer counter"""
        if self._runtimer:
            self._runtimer.eh.erase_line()

    def _runtimer_set_dirty(self):
        """Force redisplay of counter"""
        if self._runtimer:
            self._runtimer.eh.set_dirty()

    def _runtimer_finalize(self, worker):
        """Finalize display of runtimer counter"""
        if self._runtimer:
            self._runtimer.eh.finalize(worker.task.default("USER_interactive"))

    def ev_close(self, worker):
        # Worker is closing -- it's time to gather results...
        self._runtimer_finalize(worker)

        # Display command output, try to order buffers by rc
        nodesetify = lambda v: (v[0], NodeSet.fromlist(v[1]))
        for rc, nodelist in worker.iter_retcodes():
            # Then order by node/nodeset (see bufnodeset_cmp)
            for buf, nodeset in sorted(map(nodesetify,
                                           worker.iter_buffers(nodelist)),
                                       cmp=bufnodeset_cmp):
                self._display.print_gather(nodeset, buf)

        self._close_common(worker)

        # Notify main thread to update its prompt
        self.update_prompt(worker)

    def _close_common(self, worker):
        # Display return code if not ok ( != 0)
        for rc, nodelist in worker.iter_retcodes():
            if rc != 0:
                ns = NodeSet.fromlist(nodelist)
                print >> sys.stderr, "clush: %s: exited with exit code %s" \
                                        % (ns, rc)

        # Display nodes that didn't answer within command timeout delay
        if worker.num_timeout() > 0:
            print >> sys.stderr, "clush: %s: command timeout" % \
                    NodeSet.fromlist(worker.iter_keys_timeout())

class LiveGatherOutputHandler(GatherOutputHandler):
    """Live line-gathered output event handler class."""

    def __init__(self, display, runtimer, nodes):
        GatherOutputHandler.__init__(self, display, runtimer)
        self._nodes = NodeSet(nodes)
        self._nodecnt = dict.fromkeys(self._nodes, 0)
        self._mtreeq = []
        self._offload = 0

    def ev_read(self, worker):
        # Read new line from node
        node, line = worker.last_read()
        self._nodecnt[node] += 1
        cnt = self._nodecnt[node]
        if len(self._mtreeq) < cnt:
            self._mtreeq.append(MsgTree())
        self._mtreeq[cnt - self._offload - 1].add(node, line)
        self._live_line(worker)

    def ev_hup(self, worker):
        if self._mtreeq and worker.last_node() not in self._mtreeq[0]:
            # forget a node that doesn't answer to continue live line
            # gathering anyway
            self._nodes.remove(worker.last_node())
            self._live_line(worker)

    def _live_line(self, worker):
        # if all nodes have replied, display gathered line
        while self._mtreeq and len(self._mtreeq[0]) == len(self._nodes):
            mtree = self._mtreeq.pop(0)
            self._offload += 1
            self._runtimer_clean()
            nodesetify = lambda v: (v[0], NodeSet.fromlist(v[1]))
            for buf, nodeset in sorted(map(nodesetify, mtree.walk()),
                                       cmp=bufnodeset_cmp):
                self._display.print_gather(nodeset, buf)
            self._runtimer_set_dirty()

    def ev_close(self, worker):
        # Worker is closing -- it's time to gather results...
        self._runtimer_finalize(worker)

        for mtree in self._mtreeq:
            nodesetify = lambda v: (v[0], NodeSet.fromlist(v[1]))
            for buf, nodeset in sorted(map(nodesetify, mtree.walk()),
                                       cmp=bufnodeset_cmp):
                self._display.print_gather(nodeset, buf)

        self._close_common(worker)

        # Notify main thread to update its prompt
        self.update_prompt(worker)

class RunTimer(EventHandler):
    def __init__(self, task, total):
        EventHandler.__init__(self)
        self.task = task
        self.total = total
        self.cnt_last = -1
        self.tslen = len(str(self.total))
        self.wholelen = 0
        self.started = False

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
            self.started = True

    def finalize(self, cr):
        if not self.started:
            return
        # display completed/total clients
        fmt = 'clush: %*d/%*d'
        if cr:
            fmt += '\n'
        else:
            fmt += '\r'
        sys.stderr.write(fmt % (self.tslen, self.total, self.tslen, self.total))


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

def ttyloop(task, nodeset, gather, timeout, verbosity, display):
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
            if task.default("USER_interactive") and \
                    not task.default("USER_running"):
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
        except KeyboardInterrupt, kbe:
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
                        print >> sys.stderr, \
                                "Warning: Caught keyboard interrupt!"
                    display.print_gather(nodeset, buf)
                    
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
                kbe.uncompleted_nodes = ns - ns_ok

                # Display nodes that didn't answer within command timeout delay
                if task.num_timeout() > 0:
                    print >> sys.stderr, "clush: %s: command timeout" % \
                            NodeSet.fromlist(task.iter_keys_timeout())
            raise kbe

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
                run_command(task, cmd[1:], None, gather, timeout, verbosity,
                            display)
            elif cmdl != "quit":
                if not cmd:
                    continue
                if readline_avail:
                    readline.write_history_file(get_history_file())
                run_command(task, cmd, ns, gather, timeout, verbosity, display)
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

def run_command(task, cmd, ns, gather, timeout, verbosity, display):
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
        if display.line_mode:
            handler = LiveGatherOutputHandler(display, runtimer, ns)
        else:
            handler = GatherOutputHandler(display, runtimer)

        worker = task.shell(cmd, nodes=ns, handler=handler, timeout=timeout)
    else:
        worker = task.shell(cmd, nodes=ns,
                            handler=DirectOutputHandler(display),
                            timeout=timeout)

    if task.default("USER_stdin_worker"):
        bind_stdin(worker)
 
    task.resume()

def run_copy(task, source, dest, ns, timeout, preserve_flag, display):
    """
    run copy command
    """
    task.set_default("USER_running", True)

    # Source check
    if not os.path.exists(source):
        print >> sys.stderr, "ERROR: file \"%s\" not found" % source
        clush_exit(1)

    task.copy(source, dest, ns, handler=DirectOutputHandler(display),
              timeout=timeout, preserve=preserve_flag)

    task.resume()

def clush_exit(status):
    # Flush stdio buffers
    for stream in [sys.stdout, sys.stderr]:
        stream.flush()
    # Use os._exit to avoid threads cleanup
    os._exit(status)

def clush_excepthook(extype, value, traceback):
    """Exceptions hook for clush: this method centralizes exception
    handling from main thread and from (possible) separate task thread.
    This hook has to be previously installed on startup by overriding
    sys.excepthook and task.excepthook."""
    try:
        raise extype, value
    except ClushConfigError, econf:
        print >> sys.stderr, "ERROR: %s" % econf
    except KeyboardInterrupt, kbe:
        uncomp_nodes = getattr(kbe, 'uncompleted_nodes', None)
        if uncomp_nodes:
            print >> sys.stderr, "Keyboard interrupt (%s did not complete)." \
                                    % uncomp_nodes
        else:
            print >> sys.stderr, "Keyboard interrupt."
        clush_exit(128 + signal.SIGINT)
    except OSError, value:
        print >> sys.stderr, "ERROR: %s" % value
        if value.errno == errno.EMFILE:
            print >> sys.stderr, "ERROR: current `nofile' limits: " \
                "soft=%d hard=%d" % resource.getrlimit(resource.RLIMIT_NOFILE)
    except GENERIC_ERRORS, exc:
        clush_exit(handle_generic_error(exc))

    # Error not handled
    task_self().default_excepthook(extype, value, traceback)

def main(args=sys.argv):
    """clush script entry point"""
    #sys.excepthook = clush_excepthook

    # Default values
    nodeset_base, nodeset_exclude = NodeSet(), NodeSet()

    #
    # Argument management
    #
    usage = "%prog [options] command"

    parser = OptionParser(usage)

    parser.add_option("--nostdin", action="store_true", dest="nostdin",
                      help="don't watch for possible input from stdin")

    parser.install_nodes_options()
    parser.install_display_options(verbose_options=True)
    parser.install_filecopy_options()
    parser.install_ssh_options()

    (options, args) = parser.parse_args(args[1:])

    #
    # Load config file and apply overrides
    #
    config = ClushConfig(options)

    #
    # Compute the nodeset
    #
    if options.nodes:
        nodeset_base = NodeSet.fromlist(options.nodes)
    if options.exclude:
        nodeset_exclude = NodeSet.fromlist(options.exclude)

    if options.groupsource:
        # Be sure -a/g -s source work as espected.
        STD_GROUP_RESOLVER.default_sourcename = options.groupsource

    # Do we have nodes group?
    task = task_self()
    task.set_info("debug", config.verbosity > 1)
    if config.verbosity > 1:
        STD_GROUP_RESOLVER.set_verbosity(1)
    if options.nodes_all:
        all_nodeset = NodeSet.fromall()
        config.verbose_print(VERB_DEBUG, \
            "Adding nodes from option -a: %s" % all_nodeset)
        nodeset_base.add(all_nodeset)

    if options.group:
        grp_nodeset = NodeSet.fromlist(options.group,
                                       resolver=NOGROUP_RESOLVER)
        for grp in grp_nodeset:
            addingrp = NodeSet("@" + grp)
            config.verbose_print(VERB_DEBUG, \
                "Adding nodes from option -g %s: %s" % (grp, addingrp))
            nodeset_base.update(addingrp)

    if options.exgroup:
        grp_nodeset = NodeSet.fromlist(options.exgroup,
                                       resolver=NOGROUP_RESOLVER)
        for grp in grp_nodeset:
            removingrp = NodeSet("@" + grp)
            config.verbose_print(VERB_DEBUG, \
                "Excluding nodes from option -X %s: %s" % (grp, removingrp))
            nodeset_exclude.update(removingrp)

    # Do we have an exclude list? (-x ...)
    nodeset_base.difference_update(nodeset_exclude)
    if len(nodeset_base) < 1:
        parser.error('No node to run on.')

    config.verbose_print(VERB_DEBUG, "Final NodeSet: %s" % nodeset_base)

    # Make soft fd limit the max.
    config.max_fdlimit()

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

    task.excepthook = sys.excepthook
    task.set_default("USER_stdin_worker", not (sys.stdin.isatty() or
                                               options.nostdin))
    config.verbose_print(VERB_DEBUG, "Create STDIN worker: %s" % \
                                        task.default("USER_stdin_worker"))

    task.set_info("debug", config.verbosity >= VERB_DEBUG)
    task.set_info("fanout", config.fanout)

    if config.ssh_user:
        task.set_info("ssh_user", config.ssh_user)
    if config.ssh_path:
        task.set_info("ssh_path", config.ssh_path)
    if config.ssh_options:
        task.set_info("ssh_options", config.ssh_options)

    # Set detailed timeout values
    task.set_info("connect_timeout", config.connect_timeout)
    command_timeout = config.command_timeout
    task.set_info("command_timeout", command_timeout)

    gather = options.gatherall or options.gather
    # Enable stdout/stderr separation
    task.set_default("stderr", not options.gatherall)

    # Disable MsgTree buffering if not gathering outputs
    task.set_default("stdout_msgtree", gather and not options.line_mode)
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

    # print debug values (fanout value is get from the config object
    # and not task itself as set_info() is an asynchronous call.
    config.verbose_print(VERB_VERB, "clush: nodeset=%s fanout=%d [timeout " \
            "conn=%.1f cmd=%.1f] %s" %  (nodeset_base, config.fanout,
                task.info("connect_timeout"),
                task.info("command_timeout"), op))

    # Should we use ANSI colors for nodes?
    if config.color == "auto":
        color = sys.stdout.isatty() and (options.gatherall or \
                                         sys.stderr.isatty())
    else:
        color = config.color == "always"

    # Create and configure display object.
    display = Display(options, color)

    if not task.default("USER_interactive"):
        if options.source_path:
            if not args:
                run_copy(task, options.source_path, options.dest_path,
                         nodeset_base, 0, options.preserve_flag, display)
            else:
                parser.error("please use `--dest' to specify a different " \
                             "destination")
        else:
            run_command(task, ' '.join(args), nodeset_base, gather, timeout,
                        config.verbosity, display)

    if user_interaction:
        ttyloop(task, nodeset_base, gather, timeout, config.verbosity, display)
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
    main()
