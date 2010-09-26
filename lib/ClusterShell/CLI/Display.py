#!/usr/bin/env python
#
# Copyright CEA/DAM/DIF (2010)
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
CLI results display class
"""

import sys

from ClusterShell.NodeSet import NodeSet


WHENCOLOR_CHOICES = ["never", "always", "auto"]

class Display(object):
    """
    Output display class for command line scripts.
    """
    COLOR_STDOUT_FMT = "\033[34m%s\033[0m"
    COLOR_STDERR_FMT = "\033[31m%s\033[0m"
    SEP = "-" * 15

    def __init__(self, options, color=None):
        """Initialize a Display object from CLI.OptionParser options.

        If `color' boolean flag is not specified, it is auto detected
        according to options.whencolor.
        """
        self._display = self._print_buffer
        self.line_mode = options.line_mode
        self.label = options.label
        self.regroup = options.regroup
        self.groupsource = options.groupsource
        self.noprefix = options.groupbase

        if color is None:
            # Should we use ANSI colors?
            color = False
            if options.whencolor == "auto":
                color = sys.stdout.isatty()
            elif options.whencolor == "always":
                color = True

        self._color = color

        self.out = sys.stdout
        self.err = sys.stderr
        if self._color:
            self.color_stdout_fmt = self.COLOR_STDOUT_FMT
            self.color_stderr_fmt = self.COLOR_STDERR_FMT
        else:
            self.color_stdout_fmt = self.color_stderr_fmt = "%s"

    def _getlmode(self):
        return self._display == self._print_lines

    def _setlmode(self, value):
        if value:
            self._display = self._print_lines
        else:
            self._display = self._print_buffer
    line_mode = property(_getlmode, _setlmode)

    def _format_header(self, nodeset):
        """Format nodeset-based header."""
        if self.regroup:
            return nodeset.regroup(self.groupsource, noprefix=self.noprefix)
        return str(nodeset)

    def print_line(self, nodeset, line):
        """Display a line with optional label."""
        if self.label:
            prefix = self.color_stdout_fmt % ("%s: " % nodeset)
            self.out.write("%s%s\n" % (prefix, line))
        else:
            self.out.write("%s\n" % line)

    def print_line_error(self, nodeset, line):
        """Display an error line with optional label."""
        if self.label:
            prefix = self.color_stderr_fmt % ("%s: " % nodeset)
            self.err.write("%s%s\n" % (prefix, line))
        else:
            self.err.write("%s\n" % line)

    def print_gather(self, nodeset, obj):
        """Generic method for displaying nodeset/content according to current
        object settings."""
        if type(nodeset) is str:
            nodeset = NodeSet(nodeset)
        return self._display(nodeset, obj)

    def _print_buffer(self, nodeset, content):
        """Display a dshbak-like header block and content."""
        header = self.color_stdout_fmt % ("%s\n%s\n%s\n" % (self.SEP,
                                            self._format_header(nodeset),
                                            self.SEP))
        self.out.write("%s%s\n" % (header, content))
        
    def _print_lines(self, nodeset, msg):
        """Display a MsgTree buffer by line with prefixed header."""
        if self.label:
            header = self.color_stdout_fmt % \
                        ("%s: " % self._format_header(nodeset))
            for line in msg:
                self.out.write("%s%s\n" % (header, line))
        else:
            for line in msg:
                self.out.write(line + '\n')

