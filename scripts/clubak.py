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
clubak formats clush/dsh/pdsh output for humans.

For help, type::
    $ clubak --help
"""

from itertools import imap
import optparse
import signal
import sys

from ClusterShell.NodeUtils import GroupResolverConfigError
from ClusterShell.NodeUtils import GroupResolverSourceError
from ClusterShell.NodeUtils import GroupSourceException
from ClusterShell.NodeUtils import GroupSourceNoUpcall
try:
    from ClusterShell.MsgTree import MsgTree
    from ClusterShell.NodeSet import NodeSet
    from ClusterShell.NodeSet import NodeSetExternalError, NodeSetParseError
    from ClusterShell import __version__
except GroupResolverConfigError, e:
    print >> sys.stderr, \
        "ERROR: ClusterShell Groups configuration error:\n\t%s" % e
    sys.exit(1)


# Start of clush.py common code

WHENCOLOR_CHOICES = ["never", "always", "auto"]

class Display(object):
    """
    Output display class for clush script.
    """
    COLOR_STDOUT_FMT = "\033[34m%s\033[0m"
    COLOR_STDERR_FMT = "\033[31m%s\033[0m"
    SEP = "-" * 15

    def __init__(self, color=True):
        self._color = color
        self._display = self._print_buffer
        self.out = sys.stdout
        self.err = sys.stderr
        self.label = True
        self.regroup = False
        self.groupsource = None
        if self._color:
            self.color_stdout_fmt = self.COLOR_STDOUT_FMT
            self.color_stderr_fmt = self.COLOR_STDERR_FMT
        else:
            self.color_stdout_fmt = self.color_stderr_fmt = "%s"
        self.noprefix = False

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
            self.out.write("%s\n", line)

    def print_line_error(self, nodeset, line):
        """Display an error line with optional label."""
        if self.label:
            prefix = self.color_stderr_fmt % ("%s: " % nodeset)
            self.err.write("%s%s\n" % (prefix, line))
        else:
            self.err.write("%s\n", line)

    def print_gather(self, nodeset, obj):
        """Generic method for displaying nodeset/content according to current
        object settings."""
        return self._display(nodeset, obj)

    def _print_buffer(self, nodeset, content):
        """Display a dshbak-like header block and content."""
        header = self.color_stdout_fmt % ("%s\n%s\n%s\n" % (self.SEP,
                                            self._format_header(nodeset),
                                            self.SEP))
        self.out.write("%s%s\n" % (header, content))
        
    def _print_lines(self, nodeset, msg):
        """Display a MsgTree buffer by line with prefixed header."""
        header = self.color_stdout_fmt % \
                    ("%s: " % self._format_header(nodeset))
        for line in msg:
            self.out.write("%s%s\n" % (header, line))

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

# End of clush.py common code

def display(tree, gather, disp):
    """Display results"""
    try:
        if gather:
            # lambda to create a NodeSet from keys list returned by walk()
            ns_getter = lambda x: NodeSet.fromlist(x[1])
            for nodeset in sorted(imap(ns_getter, tree.walk()),
                                  cmp=nodeset_cmp):
                disp.print_gather(nodeset, tree[nodeset[0]])
        else:
            # nodes are automagically sorted by NodeSet
            for node in NodeSet.fromlist(tree.keys()):
                disp.print_gather(node, tree[node])
    finally:
        sys.stdout.flush()

def clubak():
    """Main clubak script function"""
    #
    # Argument management
    #
    usage = "%prog [options]"
    parser = optparse.OptionParser(usage, version="%%prog %s" % __version__)

    # Set parsing to stop on the first non-option
    parser.disable_interspersed_args()

    parser.add_option("-b", "-c", action="store_true", dest="gather",
                      help="gather nodes with same output (-c is provided " \
                           "for dshbak compatibility)")
    parser.add_option("-d", "--debug", action="store_true", dest="debug",
                      help="output more messages for debugging purpose")
    parser.add_option("-L", action="store_true", dest="line_mode",
                      help="disable header block and order output by nodes")
    parser.add_option("-r", "--regroup", action="store_true", dest="regroup",
                      default=False, help="fold nodeset using node groups")
    parser.add_option("-s", "--groupsource", action="store", dest="groupsource",
                      help="optional groups.conf(5) group source to use")
    parser.add_option("-G", "--groupbase", action="store_true",
                      dest="groupbase", default=False, help="do not display " \
                      "group source prefix")
    parser.add_option("-S", "--separator", action="store", dest="separator",
                      default=':', help="node / line content separator " \
                      "string (default: ':')")
    parser.add_option("--color", action="store", dest="whencolor",
                      choices=WHENCOLOR_CHOICES,
                      help="whether to use ANSI colors (never, always or auto)")
    options = parser.parse_args()[0]

    # Create new message tree
    tree = MsgTree()

    # Feed the tree from standard input lines
    for line in sys.stdin:
        node, content = line.rstrip('\r\n').split(options.separator, 1)
        node = node.strip()
        if not node:
            raise ValueError("No node found for line: %s" % line.rstrip('\r\n'))
        tree.add(node, content)

    if options.debug:
        print >> sys.stderr, "clubak: line_mode=%s gather=%s tree_depth=%d" % \
            (bool(options.line_mode), bool(options.gather), tree._depth())

    # Should we use ANSI colors?
    color = False
    if options.whencolor == "auto":
        color = sys.stdout.isatty()
    elif options.whencolor == "always":
        color = True

    # Display results
    disp = Display(color)
    disp.line_mode = options.line_mode
    disp.label = True
    disp.regroup = options.regroup
    disp.groupsource = options.groupsource
    disp.noprefix = options.groupbase
    display(tree, options.gather, disp)
    sys.exit(0)

if __name__ == '__main__':
    try:
        clubak()
    except NodeSetExternalError, e:
        print >> sys.stderr, "clubak: external error:", e
        sys.exit(1)
    except NodeSetParseError, e:
        print >> sys.stderr, "clubak: parse error:", e
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
        sys.exit(1)     # exit with error on broken pipe
    except KeyboardInterrupt, e:
        sys.exit(128 + signal.SIGINT)
    except ValueError, e:
        print >> sys.stderr, "clubak:", e
        sys.exit(1)
        
