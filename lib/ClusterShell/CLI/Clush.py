#!/usr/bin/env python
#
# Copyright CEA/DAM/DIF (2007, 2008, 2009, 2010, 2011, 2012)
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
import logging
import os
import resource
import sys
import signal
import threading

from ClusterShell.CLI.Config import ClushConfig, ClushConfigError
from ClusterShell.CLI.Display import Display
from ClusterShell.CLI.Display import VERB_QUIET, VERB_STD, VERB_VERB, VERB_DEBUG
from ClusterShell.CLI.OptionParser import OptionParser
from ClusterShell.CLI.Error import GENERIC_ERRORS, handle_generic_error
from ClusterShell.CLI.Utils import NodeSet, bufnodeset_cmp

from ClusterShell.Event import EventHandler
from ClusterShell.MsgTree import MsgTree
from ClusterShell.NodeSet import RESOLVER_NOGROUP, RESOLVER_STD_GROUP
from ClusterShell.NodeSet import NodeSetParseError
from ClusterShell.Task import Task, task_self


class UpdatePromptException(Exception):
    """Exception used by the signal handler"""

class StdInputHandler(EventHandler):
    """Standard input event handler class."""
    def __init__(self, worker):
        EventHandler.__init__(self)
        self.master_worker = worker

    def ev_msg(self, port, msg):
        """invoked when a message is received from port object"""
        if not msg:
            self.master_worker.set_write_eof()
            return
        # Forward messages to master worker
        self.master_worker.write(msg)

class OutputHandler(EventHandler):
    """Base class for clush output handlers."""

    def __init__(self):
        EventHandler.__init__(self)
        self._runtimer = None

    def runtimer_init(self, task, ntotal):
        """Init timer for live command-completed progressmeter."""
        self._runtimer = task.timer(2.0, RunTimer(task, ntotal),
                                    interval=1./3., autoclose=True)

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
        node = worker.current_node or worker.key
        self._display.print_line(node, worker.current_msg)

    def ev_error(self, worker):
        node = worker.current_node or worker.key
        self._display.print_line_error(node, worker.current_errmsg)

    def ev_hup(self, worker):
        node = worker.current_node or worker.key
        rc = worker.current_rc
        if rc > 0:
            verb = VERB_QUIET
            if self._display.maxrc:
                verb = VERB_STD
            self._display.vprint_err(verb, \
                "clush: %s: exited with exit code %d" % (node, rc))

    def ev_timeout(self, worker):
        self._display.vprint_err(VERB_QUIET, "clush: %s: command timeout" % \
            NodeSet._fromlist1(worker.iter_keys_timeout()))

    def ev_close(self, worker):
        self.update_prompt(worker)

class CopyOutputHandler(DirectOutputHandler):
    """Copy output event handler."""
    def __init__(self, display, reverse=False):
        DirectOutputHandler.__init__(self, display)
        self.reverse = reverse

    def ev_close(self, worker):
        """A copy worker has finished."""
        for rc, nodes in worker.iter_retcodes():
            if rc == 0:
                if self.reverse:
                    self._display.vprint(VERB_VERB, "%s:`%s' -> `%s'" % \
                        (nodes, worker.source, worker.dest))
                else:
                    self._display.vprint(VERB_VERB, "`%s' -> %s:`%s'" % \
                        (worker.source, nodes, worker.dest))
                break
        # multiple copy workers may be running (handled by this task's thread)
        copies = worker.task.default("USER_copies") - 1
        worker.task.set_default("USER_copies", copies)
        if copies == 0:
            self._runtimer_finalize(worker)
            self.update_prompt(worker)

class GatherOutputHandler(OutputHandler):
    """Gathered output event handler class."""

    def __init__(self, display):
        OutputHandler.__init__(self)
        self._display = display

    def ev_read(self, worker):
        if self._display.verbosity == VERB_VERB:
            node = worker.current_node or worker.key
            self._display.print_line(node, worker.current_msg)

    def ev_error(self, worker):
        self._runtimer_clean()
        self._display.print_line_error(worker.current_node,
                                       worker.current_errmsg)
        self._runtimer_set_dirty()

    def ev_close(self, worker):
        # Worker is closing -- it's time to gather results...
        self._runtimer_finalize(worker)
        assert worker.current_node is not None, "cannot gather local command"
        # Display command output, try to order buffers by rc
        nodesetify = lambda v: (v[0], NodeSet._fromlist1(v[1]))
        cleaned = False
        for rc, nodelist in sorted(worker.iter_retcodes()):
            # Then order by node/nodeset (see bufnodeset_cmp)
            for buf, nodeset in sorted(map(nodesetify,
                                           worker.iter_buffers(nodelist)),
                                       cmp=bufnodeset_cmp):
                if not cleaned:
                    # clean runtimer line before printing first result
                    self._runtimer_clean()
                    cleaned = True
                self._display.print_gather(nodeset, buf)
        self._display.flush()

        self._close_common(worker)

        # Notify main thread to update its prompt
        self.update_prompt(worker)

    def _close_common(self, worker):
        verbexit = VERB_QUIET
        if self._display.maxrc:
            verbexit = VERB_STD
        # Display return code if not ok ( != 0)
        for rc, nodelist in worker.iter_retcodes():
            if rc != 0:
                ns = NodeSet._fromlist1(nodelist)
                self._display.vprint_err(verbexit, \
                    "clush: %s: exited with exit code %d" % (ns, rc))

        # Display nodes that didn't answer within command timeout delay
        if worker.num_timeout() > 0:
            self._display.vprint_err(verbexit, "clush: %s: command timeout" % \
                NodeSet._fromlist1(worker.iter_keys_timeout()))

class LiveGatherOutputHandler(GatherOutputHandler):
    """Live line-gathered output event handler class."""

    def __init__(self, display, nodes):
        assert nodes is not None, "cannot gather local command"
        GatherOutputHandler.__init__(self, display)
        self._nodes = NodeSet(nodes)
        self._nodecnt = dict.fromkeys(self._nodes, 0)
        self._mtreeq = []
        self._offload = 0

    def ev_read(self, worker):
        # Read new line from node
        node = worker.current_node
        self._nodecnt[node] += 1
        cnt = self._nodecnt[node]
        if len(self._mtreeq) < cnt:
            self._mtreeq.append(MsgTree())
        self._mtreeq[cnt - self._offload - 1].add(node, worker.current_msg)
        self._live_line(worker)

    def ev_hup(self, worker):
        if self._mtreeq and worker.current_node not in self._mtreeq[0]:
            # forget a node that doesn't answer to continue live line
            # gathering anyway
            self._nodes.remove(worker.current_node)
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
    """Running progress timer event handler"""
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

    def finalize(self, force_cr):
        """finalize display of runtimer"""
        if not self.started:
            return
        # display completed/total clients
        fmt = 'clush: %*d/%*d'
        if force_cr:
            fmt += '\n'
        else:
            fmt += '\r'
        sys.stderr.write(fmt % (self.tslen, self.total, self.tslen, self.total))


def signal_handler(signum, frame):
    """Signal handler used for main thread notification"""
    if signum == signal.SIGUSR1:
        signal.signal(signal.SIGUSR1, signal.SIG_IGN)
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

def ttyloop(task, nodeset, timeout, display):
    """Manage the interactive prompt to run command"""
    readline_avail = False
    if task.default("USER_interactive"):
        try:
            import readline
            readline_setup()
            readline_avail = True
        except ImportError:
            pass
        display.vprint(VERB_STD, \
            "Enter 'quit' to leave this interactive mode")

    rc = 0
    ns = NodeSet(nodeset)
    ns_info = True
    cmd = ""
    while task.default("USER_running") or cmd.lower() != 'quit':
        try:
            if task.default("USER_interactive") and \
                    not task.default("USER_running"):
                if ns_info:
                    display.vprint(VERB_QUIET, \
                                   "Working with nodes: %s" % ns)
                    ns_info = False
                prompt = "clush> "
            else:
                prompt = ""
            # Set SIGUSR1 handler if needed
            if task.default("USER_handle_SIGUSR1"):
                signal.signal(signal.SIGUSR1, signal_handler)
            try:
                cmd = raw_input(prompt)
            finally:
                signal.signal(signal.SIGUSR1, signal.SIG_IGN)
        except EOFError:
            print
            return
        except UpdatePromptException:
            if task.default("USER_interactive"):
                continue
            return
        except KeyboardInterrupt, kbe:
            if display.gather:
                # Suspend task, so we can safely access its data from
                # the main thread
                task.suspend()

                print_warn = False

                # Display command output, but cannot order buffers by rc
                nodesetify = lambda v: (v[0], NodeSet._fromlist1(v[1]))
                for buf, nodeset in sorted(map(nodesetify, task.iter_buffers()),
                                            cmp=bufnodeset_cmp):
                    if not print_warn:
                        print_warn = True
                        display.vprint_err(VERB_STD, \
                            "Warning: Caught keyboard interrupt!")
                    display.print_gather(nodeset, buf)
                    
                # Return code handling
                verbexit = VERB_QUIET
                if display.maxrc:
                    verbexit = VERB_STD
                ns_ok = NodeSet()
                for rc, nodelist in task.iter_retcodes():
                    ns_ok.add(NodeSet._fromlist1(nodelist))
                    if rc != 0:
                        # Display return code if not ok ( != 0)
                        ns = NodeSet._fromlist1(nodelist)
                        display.vprint_err(verbexit, \
                            "clush: %s: exited with exit code %s" % (ns, rc))
                # Add uncompleted nodeset to exception object
                kbe.uncompleted_nodes = ns - ns_ok

                # Display nodes that didn't answer within command timeout delay
                if task.num_timeout() > 0:
                    display.vprint_err(verbexit, \
                        "clush: %s: command timeout" % \
                            NodeSet._fromlist1(task.iter_keys_timeout()))
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
            display.vprint_err(VERB_QUIET, "clush: interrupt (^C to " \
                "abort task)\nclush: in progress(%d): %s%s" % (len(ns_reg), \
                ns_reg, pending))
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
                    display.gather = not display.gather
                    if display.gather:
                        display.vprint(VERB_STD, \
                            "Switching to gathered output format")
                    else:
                        display.vprint(VERB_STD, \
                            "Switching to standard output format")
                    task.set_default("stdout_msgtree", \
                                     display.gather or display.line_mode)
                    ns_info = False
                    continue
                elif not cmdl.startswith('?'): # if ?, just print ns_info
                    ns_info = False
            except NodeSetParseError:
                display.vprint_err(VERB_QUIET, \
                    "clush: nodeset parse error (ignoring)")

            if ns_info:
                continue

            if cmdl.startswith('!') and len(cmd.strip()) > 0:
                run_command(task, cmd[1:], None, timeout, display)
            elif cmdl != "quit":
                if not cmd:
                    continue
                if readline_avail:
                    readline.write_history_file(get_history_file())
                run_command(task, cmd, ns, timeout, display)
    return rc

def _stdin_thread_start(stdin_port):
    """Standard input reader thread entry point."""
    # Note: read length should be larger and a multiple of 4096 for best
    # performance to avoid excessive unreg/register of writer fd in
    # engine; however, it shouldn't be too large.
    bufsize = 4096 * 8
    # thread loop: blocking read stdin + send messages to specified
    #              port object
    buf = sys.stdin.read(bufsize)
    while buf:
        # send message to specified port object (with ack)
        stdin_port.msg(buf)
        buf = sys.stdin.read(bufsize)
    # send a None message to indicate EOF
    stdin_port.msg(None)

def bind_stdin(worker):
    """Create a stdin->port->worker binding: connect specified worker
    to stdin with the help of a reader thread and a ClusterShell Port
    object."""
    assert not sys.stdin.isatty()
    # Create a ClusterShell Port object bound to worker's task. This object
    # is able to receive messages in a thread-safe manner and then will safely
    # trigger ev_msg() on a specified event handler.
    port = worker.task.port(handler=StdInputHandler(worker), autoclose=True)
    # Launch a dedicated thread to read stdin in blocking mode. Indeed stdin
    # can be a file, so we cannot use a WorkerSimple here as polling on file
    # may result in different behaviors depending on selected engine.
    threading.Thread(None, _stdin_thread_start, args=(port,)).start()

def run_command(task, cmd, ns, timeout, display):
    """
    Create and run the specified command line, displaying
    results in a dshbak way when gathering is used.
    """    
    task.set_default("USER_running", True)

    if display.verbosity >= VERB_VERB and task.topology:
        print Display.COLOR_RESULT_FMT % '-' * 15
        print Display.COLOR_RESULT_FMT % task.topology,
        print Display.COLOR_RESULT_FMT % '-' * 15

    if (display.gather or display.line_mode) and ns is not None:
        if display.gather and display.line_mode:
            handler = LiveGatherOutputHandler(display, ns)
        else:
            handler = GatherOutputHandler(display)

        if display.verbosity == VERB_STD or display.verbosity == VERB_VERB:
            handler.runtimer_init(task, len(ns))

        worker = task.shell(cmd, nodes=ns, handler=handler, timeout=timeout)
    else:
        worker = task.shell(cmd, nodes=ns, handler=DirectOutputHandler(display),
                            timeout=timeout)
    if ns is None:
        worker.set_key('LOCAL')
    if task.default("USER_stdin_worker"):
        bind_stdin(worker)
 
    task.resume()

def run_copy(task, sources, dest, ns, timeout, preserve_flag, display):
    """
    run copy command
    """
    task.set_default("USER_running", True)
    task.set_default("USER_copies", len(sources))

    copyhandler = CopyOutputHandler(display)
    if display.verbosity == VERB_STD or display.verbosity == VERB_VERB:
        copyhandler.runtimer_init(task, len(ns) * len(sources))

    # Sources check
    for source in sources:
        if not os.path.exists(source):
            display.vprint_err(VERB_QUIET, "ERROR: file \"%s\" not found" % \
                                           source)
            clush_exit(1)
        task.copy(source, dest, ns, handler=copyhandler, timeout=timeout,
                  preserve=preserve_flag)
    task.resume()

def run_rcopy(task, sources, dest, ns, timeout, preserve_flag, display):
    """
    run reverse copy command
    """
    task.set_default("USER_running", True)
    task.set_default("USER_copies", len(sources))

    # Sanity checks
    if not os.path.exists(dest):
        display.vprint_err(VERB_QUIET, "ERROR: directory \"%s\" not found" % \
                                       dest)
        clush_exit(1)
    if not os.path.isdir(dest):
        display.vprint_err(VERB_QUIET, \
            "ERROR: destination \"%s\" is not a directory" % dest)
        clush_exit(1)

    copyhandler = CopyOutputHandler(display, True)
    if display.verbosity == VERB_STD or display.verbosity == VERB_VERB:
        copyhandler.runtimer_init(task, len(ns) * len(sources))
    for source in sources:
        task.rcopy(source, dest, ns, handler=copyhandler, timeout=timeout,
                   preserve=preserve_flag)
    task.resume()

def set_fdlimit(fd_max, display):
    """Make open file descriptors soft limit the max."""
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    if hard < fd_max:
        display.vprint(VERB_DEBUG, "Warning: Consider increasing max open " \
            "files hard limit (%d)" % hard)
    rlim_max = min(hard, fd_max)
    if soft != rlim_max:
        display.vprint(VERB_DEBUG, "Modifying max open files soft limit: " \
            "%d -> %d" % (soft, rlim_max))
        resource.setrlimit(resource.RLIMIT_NOFILE, (rlim_max, hard))

def clush_exit(status):
    """Flush stdio buffers and exit script."""
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
            print >> sys.stderr, \
                "Keyboard interrupt (%s did not complete)." % uncomp_nodes
        else:
            print >> sys.stderr, "Keyboard interrupt."
        clush_exit(128 + signal.SIGINT)
    except OSError, value:
        print >> sys.stderr, "ERROR: %s" % value
        if value.errno == errno.EMFILE:
            print >> sys.stderr, "ERROR: current `nofile' limits: " \
                "soft=%d hard=%d" % resource.getrlimit(resource.RLIMIT_NOFILE)
        clush_exit(1)
    except GENERIC_ERRORS, exc:
        clush_exit(handle_generic_error(exc))

    # Error not handled
    task_self().default_excepthook(extype, value, traceback)

def main():
    """clush script entry point"""
    sys.excepthook = clush_excepthook

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

    (options, args) = parser.parse_args()

    #
    # Load config file and apply overrides
    #
    config = ClushConfig(options)

    # Should we use ANSI colors for nodes?
    if config.color == "auto":
        color = sys.stdout.isatty() and (options.gatherall or \
                                         sys.stderr.isatty())
    else:
        color = config.color == "always"

    try:
        # Create and configure display object.
        display = Display(options, config, color)
    except ValueError, exc:
        parser.error("option mismatch (%s)" % exc)

    #
    # Compute the nodeset
    #
    if options.nodes:
        nodeset_base = NodeSet.fromlist(options.nodes)
    if options.exclude:
        nodeset_exclude = NodeSet.fromlist(options.exclude)

    if options.groupsource:
        # Be sure -a/g -s source work as espected.
        RESOLVER_STD_GROUP.default_sourcename = options.groupsource

    # FIXME: add public API to enforce engine
    Task._std_default['engine'] = options.engine

    # Do we have nodes group?
    task = task_self()
    task.set_info("debug", config.verbosity >= VERB_DEBUG)
    if config.verbosity == VERB_DEBUG:
        RESOLVER_STD_GROUP.set_verbosity(1)
    if options.nodes_all:
        all_nodeset = NodeSet.fromall()
        display.vprint(VERB_DEBUG, "Adding nodes from option -a: %s" % \
                                   all_nodeset)
        nodeset_base.add(all_nodeset)

    if options.group:
        grp_nodeset = NodeSet.fromlist(options.group,
                                       resolver=RESOLVER_NOGROUP)
        for grp in grp_nodeset:
            addingrp = NodeSet("@" + grp)
            display.vprint(VERB_DEBUG, \
                "Adding nodes from option -g %s: %s" % (grp, addingrp))
            nodeset_base.update(addingrp)

    if options.exgroup:
        grp_nodeset = NodeSet.fromlist(options.exgroup,
                                       resolver=RESOLVER_NOGROUP)
        for grp in grp_nodeset:
            removingrp = NodeSet("@" + grp)
            display.vprint(VERB_DEBUG, \
                "Excluding nodes from option -X %s: %s" % (grp, removingrp))
            nodeset_exclude.update(removingrp)

    # Do we have an exclude list? (-x ...)
    nodeset_base.difference_update(nodeset_exclude)
    if len(nodeset_base) < 1:
        parser.error('No node to run on.')

    # Set open files limit.
    set_fdlimit(config.fd_max, display)

    #
    # Task management
    #
    # check for clush interactive mode
    interactive = not len(args) and \
                  not (options.copy or options.rcopy)
    # check for foreground ttys presence (input)
    stdin_isafgtty = sys.stdin.isatty() and \
        os.tcgetpgrp(sys.stdin.fileno()) == os.getpgrp()
    # check for special condition (empty command and stdin not a tty)
    if interactive and not stdin_isafgtty:
        # looks like interactive but stdin is not a tty:
        # switch to non-interactive + disable ssh pseudo-tty
        interactive = False
        # SSH: disable pseudo-tty allocation (-T)
        ssh_options = config.ssh_options or ''
        ssh_options += ' -T'
        config._set_main("ssh_options", ssh_options)
    if options.nostdin and interactive:
        parser.error("illegal option `--nostdin' in that case")

    # Force user_interaction if Clush._f_user_interaction for test purposes
    user_interaction = hasattr(sys.modules[__name__], '_f_user_interaction')
    if not options.nostdin:
        # Try user interaction: check for foreground ttys presence (ouput)
        stdout_isafgtty = sys.stdout.isatty() and \
            os.tcgetpgrp(sys.stdout.fileno()) == os.getpgrp()
        user_interaction |= stdin_isafgtty and stdout_isafgtty
    display.vprint(VERB_DEBUG, "User interaction: %s" % user_interaction)
    if user_interaction:
        # Standard input is a terminal and we want to perform some user
        # interactions in the main thread (using blocking calls), so
        # we run cluster commands in a new ClusterShell Task (a new
        # thread is created).
        task = Task()
    # else: perform everything in the main thread

    # Handle special signal only when user_interaction is set
    task.set_default("USER_handle_SIGUSR1", user_interaction)

    task.excepthook = sys.excepthook
    task.set_default("USER_stdin_worker", not (sys.stdin.isatty() or \
                                               options.nostdin or \
                                               user_interaction))
    display.vprint(VERB_DEBUG, "Create STDIN worker: %s" % \
                               task.default("USER_stdin_worker"))

    if config.verbosity >= VERB_DEBUG:
        task.set_info("debug", True)
        logging.basicConfig(level=logging.DEBUG)
        logging.debug("clush: STARTING DEBUG")

    task.set_info("fanout", config.fanout)

    if options.topofile:
        if config.verbosity >= VERB_VERB:
            print Display.COLOR_RESULT_FMT % \
                "Enabling TREE MODE (technology preview)"
        task.set_default("auto_tree", True)
        task.set_topology(options.topofile)

    if options.grooming_delay:
        if config.verbosity >= VERB_VERB:
            print Display.COLOR_RESULT_FMT % ("Grooming delay: %f" % \
                                              options.grooming_delay)
        task.set_info("grooming_delay", options.grooming_delay)

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

    # Enable stdout/stderr separation
    task.set_default("stderr", not options.gatherall)

    # Disable MsgTree buffering if not gathering outputs
    task.set_default("stdout_msgtree", display.gather or display.line_mode)

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

    if (options.copy or options.rcopy) and not args:
        parser.error("--[r]copy option requires at least one argument")
    if options.copy:
        if not options.dest_path:
            options.dest_path = os.path.dirname(os.path.abspath(args[0]))
        op = "copy sources=%s dest=%s" % (args, options.dest_path)
    elif options.rcopy:
        if not options.dest_path:
            options.dest_path = os.path.dirname(os.path.abspath(args[0]))
        op = "rcopy sources=%s dest=%s" % (args, options.dest_path)
    else:
        op = "command=\"%s\"" % ' '.join(args)

    # print debug values (fanout value is get from the config object
    # and not task itself as set_info() is an asynchronous call.
    display.vprint(VERB_DEBUG, "clush: nodeset=%s fanout=%d [timeout " \
                   "conn=%.1f cmd=%.1f] %s" %  (nodeset_base, config.fanout,
                                                task.info("connect_timeout"),
                                                task.info("command_timeout"),
                                                op))
    if not task.default("USER_interactive"):
        if options.copy:
            run_copy(task, args, options.dest_path, nodeset_base, 0,
                     options.preserve_flag, display)
        elif options.rcopy:
            run_rcopy(task, args, options.dest_path, nodeset_base, 0,
                      options.preserve_flag, display)
        else:
            run_command(task, ' '.join(args), nodeset_base, timeout, display)

    if user_interaction:
        ttyloop(task, nodeset_base, timeout, display)
    elif task.default("USER_interactive"):
        display.vprint_err(VERB_QUIET, \
            "ERROR: interactive mode requires a tty")
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
