#!/usr/bin/env python
#
# Copyright CEA/DAM/DIF (2008, 2009, 2010)
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
Usage: nodeset [COMMAND] [OPTIONS] [ns1 [-ixX] ns2|...]

Commands:
    --count, -c <nodeset> [nodeset ...]
        Return the number of nodes in nodesets.
    --expand, -e <nodeset> [nodeset ...]
        Expand nodesets to separate nodes.
    --fold, -f <nodeset> [nodeset ...]
        Compact/fold nodesets (or separate nodes) into one nodeset.
    --list, -l
        List node groups (compatible with --namespace).
    --regroup, -r <nodeset> [nodeset ...]
        Fold nodes using node groups (compatible with --namespace).
Options:
    --autostep=<number>, -a <number>
        Specify auto step threshold number when folding nodesets.
        If not specified, auto step is disabled.
        Example: autostep=4, "node2 node4 node6" folds in node[2,4,6]
                 autostep=3, "node2 node4 node6" folds in node[2-6/2]
    --help, -h
        This help page.
    --quiet, -q
        Quiet mode, hide any parse error messages (on stderr).
    --namespace, -n
        Group namespace (section to use in groups.conf(5)).
    --rangeset, -R
        Switch to RangeSet instead of NodeSet. Useful when working on
        numerical cluster ranges, eg. 1,5,18-31.
    --separator=<string>, -S <string>
        Use specified separator string when expanding nodesets (default
        is ' ').
    --version, -v
        Show ClusterShell version and exit.
Operations (default is union):
        The default operation is the union of node or nodeset.
    --exclude=<nodeset>, -x <nodeset>
        Exclude provided node or nodeset.
    --intersection, -i
        Calculate nodesets intersection.
    --xor, -X
        Calculate symmetric difference (XOR) between two nodesets.
"""

import getopt
import signal
import sys

from ClusterShell.NodeUtils import GroupResolverConfigError
from ClusterShell.NodeUtils import GroupResolverSourceError
try:
    from ClusterShell.NodeSet import NodeSet, NodeSetParseError
    from ClusterShell.NodeSet import RangeSet, RangeSetParseError
    from ClusterShell.NodeSet import grouplist, STD_GROUP_RESOLVER
    from ClusterShell import __version__
except GroupResolverConfigError, e:
    print >> sys.stderr, \
        "ERROR: ClusterShell Groups configuration error:\n\t%s" % e
    sys.exit(1)


def process_stdin(xset, autostep):
    """Process standard input and populate xset."""
    for line in sys.stdin.readlines():
        # Support multi-lines and multi-nodesets per line
        line = line[0:line.find('#')].strip()
        for node in line.split():
            xset.update(xset.__class__(node, autostep=autostep))

def compute_nodeset(xset, args, autostep):
    """Apply operations and operands from args on xset, an initial
    RangeSet or NodeSet."""
    class_set = xset.__class__
    # Process operations
    while args:
        arg = args.pop(0)
        if arg in ("-i", "--intersection"):
            xset.intersection_update(class_set(args.pop(0),
                                               autostep=autostep))
        elif arg in ("-x", "--exclude"):
            xset.difference_update(class_set(args.pop(0),
                                             autostep=autostep))
        elif arg in ("-X", "--xor"):
            xset.symmetric_difference_update(class_set(args.pop(0),
                                                       autostep=autostep))
        elif arg == '-':
            process_stdin(xset, autostep)
        else:
            xset.update(class_set(arg, autostep=autostep))

    return xset

def error_exit(progname, message, status=1):
    print >> sys.stderr, message
    print >> sys.stderr, "Try `%s -h' for more information." % progname
    sys.exit(status)
    
def run_nodeset(args):
    """
    Main script function.
    """
    autostep = None
    command = None
    verbosity = 1
    class_set = NodeSet
    separator = ' '
    namespace = None
    progname = args[0]
    multcmds_errstr = "ERROR: multiple commands not allowed"

    # Parse getoptable options
    try:
        opts, args = getopt.getopt(args[1:], "a:cdefhln:qvrRS:",
            ["autostep=", "count", "debug", "expand", "fold", "help",
             "list", "namespace=", "quiet", "regroup", "rangeset",
             "version", "separator="])
    except getopt.error, err:
        if err.opt in [ "i", "intersection", "x", "exclude", "X", "xor" ]:
            message = "option -%s not allowed here" % err.opt
        else:
            message = err.msg
        error_exit(progname, message, 2)

    for k, val in opts:
        if k in ("-a", "--autostep"):
            try:
                autostep = int(val)
            except ValueError, exc:
                print >> sys.stderr, exc
        elif k in ("-c", "--count"):
            if command:
                error_exit(progname, multcmds_errstr, 2)
            command = "count"
        elif k in ("-d", "--debug"):
            verbosity = 2
        elif k in ("-e", "--expand"):
            if command:
                error_exit(progname, multcmds_errstr, 2)
            command = "expand"
        elif k in ("-f", "--fold"):
            if command:
                error_exit(progname, multcmds_errstr, 2)
            command = "fold"
        elif k in ("-h", "--help"):
            print __doc__
            sys.exit(0)
        elif k in ("-l", "--list"):
            if command:
                error_exit(progname, multcmds_errstr, 2)
            command = "list"
        elif k in ("-n", "--namespace"):
            namespace = val
        elif k in ("-q", "--quiet"):
            verbosity = 0
        elif k in ("-r", "--regroup"):
            if command:
                error_exit(progname, multcmds_errstr, 2)
            command = "regroup"
        elif k in ("-R", "--rangeset"):
            class_set = RangeSet
        elif k in ("-S", "--separator"):
            separator = val
        elif k in ("-v", "--version"):
            print __version__
            sys.exit(0)

    # Check for command presence
    if not command:
        print >> sys.stderr, "ERROR: no command specified."
        print >> sys.stderr, __doc__
        sys.exit(1)

    # The list command doesn't need any NodeSet, check for it first.
    if command == "list":
        for group in grouplist(namespace):
            if namespace:
                print "@%s:%s" % (namespace, group)
            else:
                print "@%s" % group
        return

    try:
        if verbosity > 1:
            STD_GROUP_RESOLVER.set_verbosity(1)

        # Instantiate RangeSet or NodeSet object
        xset = class_set()

        # No need to specify '-' to read stdin if no argument at all
        if not args:
            process_stdin(xset, autostep)
        
        # Finish xset computing from args
        compute_nodeset(xset, args, autostep)

        # Interprate special characters (may raise SyntaxError)
        separator = eval('\'%s\'' % separator, {"__builtins__":None}, {})

        # Display result according to command choice
        if command == "expand":
            print separator.join(xset)
        elif command == "fold":
            print xset
        elif command == "regroup":
            print xset.regroup(namespace)
        else:
            print len(xset)

    except (NodeSetParseError, RangeSetParseError), exc:
        if verbosity > 0:
            print >> sys.stderr, "%s parse error:" % class_set.__name__, exc
        sys.exit(1)


if __name__ == '__main__':
    try:
        run_nodeset(sys.argv)
        sys.exit(0)
    except AssertionError, e:
        print >> sys.stderr, "ERROR:", e
        sys.exit(1)
    except IndexError:
        print >> sys.stderr, "ERROR: syntax error"
        sys.exit(1)
    except SyntaxError:
        print >> sys.stderr, "ERROR: invalid separator"
        sys.exit(1)
    except GroupResolverSourceError, e:
        print >> sys.stderr, "ERROR: unknown group namespace: \"%s\"" % e
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(128 + signal.SIGINT)
