#
# Copyright (C) 2010-2015 CEA/DAM
#
# This file is part of ClusterShell.
#
# ClusterShell is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# ClusterShell is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with ClusterShell; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

"""
CLI results display class
"""

from __future__ import print_function

import difflib
import sys

from ClusterShell.NodeSet import NodeSet

# Display constants
VERB_QUIET = 0
VERB_STD = 1
VERB_VERB = 2
VERB_DEBUG = 3
THREE_CHOICES = ["never", "always", "auto"]
WHENCOLOR_CHOICES = THREE_CHOICES   # deprecated; use THREE_CHOICES

# Python 3 compat: wrappers for standard streams
def sys_stdin():
    return getattr(sys.stdin, 'buffer', sys.stdin)

def sys_stdout():
    return getattr(sys.stdout, 'buffer', sys.stdout)

def sys_stderr():
    return getattr(sys.stderr, 'buffer', sys.stderr)


class Display(object):
    """
    Output display class for command line scripts.
    """
    COLOR_RESULT_FMT = "\033[92m%s\033[0m"
    COLOR_STDOUT_FMT = "\033[94m%s\033[0m"
    COLOR_STDERR_FMT = "\033[91m%s\033[0m"
    COLOR_DIFFHDR_FMT = "\033[1m%s\033[0m"
    COLOR_DIFFHNK_FMT = "\033[96m%s\033[0m"
    COLOR_DIFFADD_FMT = "\033[92m%s\033[0m"
    COLOR_DIFFDEL_FMT = "\033[91m%s\033[0m"
    SEP = "-" * 15

    class _KeySet(set):
        """Private NodeSet substition to display raw keys"""
        def __str__(self):
            return ",".join(self)

    def __init__(self, options, config=None, color=None):
        """Initialize a Display object from CLI.OptionParser options
        and optional CLI.ClushConfig.

        If `color' boolean flag is not specified, it is auto detected
        according to options.whencolor.
        """
        if options.diff:
            self._print_buffer = self._print_diff
        else:
            self._print_buffer = self._print_content
        self._display = self._print_buffer
        self._diffref = None
        # diff implies at least -b
        self.gather = options.gatherall or options.gather or options.diff
        self.progress = getattr(options, 'progress', False) # only in clush
        # check parameter compatibility
        if options.diff and options.line_mode:
            raise ValueError("diff not supported in line_mode")
        self.line_mode = options.line_mode
        self.label = options.label
        self.regroup = options.regroup
        self.groupsource = options.groupsource
        self.noprefix = options.groupbase
        # display may change when 'max return code' option is set
        self.maxrc = getattr(options, 'maxrc', False)

        if color is None:
            # Should we use ANSI colors?
            color = False
            if not options.whencolor or options.whencolor == "auto":
                color = sys.stdout.isatty()
            elif options.whencolor == "always":
                color = True

        self._color = color
        self.out = sys_stdout()
        self.err = sys_stderr()

        if self._color:
            self.color_stdout_fmt = self.COLOR_STDOUT_FMT
            self.color_stderr_fmt = self.COLOR_STDERR_FMT
            self.color_diffhdr_fmt = self.COLOR_DIFFHDR_FMT
            self.color_diffctx_fmt = self.COLOR_DIFFHNK_FMT
            self.color_diffadd_fmt = self.COLOR_DIFFADD_FMT
            self.color_diffdel_fmt = self.COLOR_DIFFDEL_FMT
        else:
            self.color_stdout_fmt = self.color_stderr_fmt = \
                self.color_diffhdr_fmt = self.color_diffctx_fmt = \
                self.color_diffadd_fmt = self.color_diffdel_fmt = "%s"

        # Set display verbosity
        if config:
            # config object does already apply options overrides
            self.node_count = config.node_count
            self.verbosity = config.verbosity
        else:
            self.node_count = True
            self.verbosity = VERB_STD
            if hasattr(options, 'quiet') and options.quiet:
                self.verbosity = VERB_QUIET
            if hasattr(options, 'verbose') and options.verbose:
                self.verbosity = VERB_VERB
            if hasattr(options, 'debug') and options.debug:
                self.verbosity = VERB_DEBUG

    def flush(self):
        """flush display object buffers"""
        # only used to reset diff display for now
        self._diffref = None

    def _getlmode(self):
        """line_mode getter"""
        return self._display == self._print_lines

    def _setlmode(self, value):
        """line_mode setter"""
        if value:
            self._display = self._print_lines
        else:
            self._display = self._print_buffer
    line_mode = property(_getlmode, _setlmode)

    def _format_nodeset(self, nodeset):
        """Sub-routine to format nodeset string."""
        if self.regroup:
            return nodeset.regroup(self.groupsource, noprefix=self.noprefix)
        return str(nodeset)

    def format_header(self, nodeset, indent=0):
        """Format nodeset-based header."""
        if not self.label:
            return b""
        indstr = " " * indent
        nodecntstr = ""
        if self.verbosity >= VERB_STD and self.node_count and len(nodeset) > 1:
            nodecntstr = " (%d)" % len(nodeset)
        hdr = self.color_stdout_fmt % ("%s%s\n%s%s%s\n%s%s" % \
            (indstr, self.SEP,
             indstr, self._format_nodeset(nodeset), nodecntstr,
             indstr, self.SEP))
        return hdr.encode('ascii') + b'\n'

    def print_line(self, nodeset, line):
        """Display a line with optional label."""
        if self.label:
            prefix = self.color_stdout_fmt % ("%s: " % nodeset)
            self.out.write(prefix.encode('ascii') + line + b'\n')
        else:
            self.out.write(line + b'\n')

    def print_line_error(self, nodeset, line):
        """Display an error line with optional label."""
        if self.label:
            prefix = self.color_stderr_fmt % ("%s: " % nodeset)
            self.err.write(prefix.encode('ascii') + line + b'\n')
        else:
            self.err.write(line + b'\n')

    def print_gather(self, nodeset, obj):
        """Generic method for displaying nodeset/content according to current
        object settings."""
        return self._display(NodeSet(nodeset), obj)

    def print_gather_finalize(self, nodeset):
        """Finalize display of diff-like gathered contents."""
        if self._display == self._print_diff and self._diffref:
            return self._display(nodeset, '')

    def print_gather_keys(self, keys, obj):
        """Generic method for displaying raw keys/content according to current
        object settings (used by clubak)."""
        return self._display(self.__class__._KeySet(keys), obj)

    def _print_content(self, nodeset, content):
        """Display a dshbak-like header block and content."""
        self.out.write(self.format_header(nodeset) + bytes(content) + b'\n')

    def _print_diff(self, nodeset, content):
        """Display unified diff between remote gathered outputs."""
        if self._diffref is None:
            self._diffref = (nodeset, content)
        else:
            nodeset_ref, content_ref = self._diffref
            nsstr_ref = self._format_nodeset(nodeset_ref)
            nsstr = self._format_nodeset(nodeset)
            if self.verbosity >= VERB_STD and self.node_count:
                if len(nodeset_ref) > 1:
                    nsstr_ref += " (%d)" % len(nodeset_ref)
                if len(nodeset) > 1:
                    nsstr += " (%d)" % len(nodeset)

            alist = [aline.decode('utf-8', 'ignore') for aline in content_ref]
            blist = [bline.decode('utf-8', 'ignore') for bline in content]
            udiff = difflib.unified_diff(alist, blist, fromfile=nsstr_ref,
                                         tofile=nsstr, lineterm='')
            output = ''
            for line in udiff:
                if line.startswith('---') or line.startswith('+++'):
                    output += self.color_diffhdr_fmt % line.rstrip()
                elif line.startswith('@@'):
                    output += self.color_diffctx_fmt % line
                elif line.startswith('+'):
                    output += self.color_diffadd_fmt % line
                elif line.startswith('-'):
                    output += self.color_diffdel_fmt % line
                else:
                    output += line
                output += '\n'
            self.out.write(output.encode('ascii'))

    def _print_lines(self, nodeset, msg):
        """Display a MsgTree buffer by line with prefixed header."""
        out = self.out
        if self.label:
            header = self.color_stdout_fmt % \
                        ("%s: " % self._format_nodeset(nodeset))
            for line in msg:
                out.write(header.encode('ascii') + line + b'\n')
        else:
            for line in msg:
                out.write(line + b'\n')

    def vprint(self, level, message):
        """Utility method to print a message if verbose level is high
        enough."""
        if self.verbosity >= level:
            print(message)

    def vprint_err(self, level, message):
        """Utility method to print a message on stderr if verbose level
        is high enough."""
        if self.verbosity >= level:
            print(message, file=sys.stderr)

