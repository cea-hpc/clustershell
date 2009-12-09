#!/usr/bin/env python
#
# Copyright CEA/DAM/DIF (2008, 2009)
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
Usage: nodeset [options] [command]

Commands:
    --count, -c <nodeset> [nodeset ...]
        Return the number of nodes in nodesets.
    --expand, -e <nodeset> [nodeset ...]
        Expand nodesets to separate nodes.
    --fold, -f <nodeset> [nodeset ...]
        Compact/fold nodesets (or separate nodes) into one nodeset.
Options:
    --autostep=<number>, -a <number>
        Specify auto step threshold number when folding nodesets.
        If not specified, auto step is disabled.
        Example: autostep=4, "node2 node4 node6" folds in node[2,4,6]
                 autostep=3, "node2 node4 node6" folds in node[2-6/2]
    --exclude=<nodeset>, -x <nodeset>
        Exclude provided node or nodeset from result. Can be specified
        several times.
    --help, -h
        This help page.
    --intersection, -i
        Calculate nodesets intersection before processing command. This
        means that only nodes that are in every provided nodesets are
        used.
    --separator=<string>, -S <string>
        Use specified separator string when expanding nodesets (default
        is ' ').
    --xor, -X
        Calculate symmetric difference (XOR) between two nodesets before
        processing command. This means that nodes present in only one of
        the nodesets are used.
    --rangeset, -R
        Switch to RangeSet instead of NodeSet. Useful when working on
        numerical cluster ranges, eg. 1,5,18-31.
    --quiet, -q
        Quiet mode, hide any parse error messages (on stderr).
    --version, -v
        Show ClusterShell version and exit.
"""

import getopt
import signal
import sys

sys.path.insert(0, '../lib')

from ClusterShell.NodeSet import NodeSet, NodeSetParseError
from ClusterShell.NodeSet import RangeSet, RangeSetParseError
from ClusterShell import __version__


def run_nodeset(args):
    """
    Main script function.
    """
    autostep = None
    command = None
    preprocess = None
    quiet = False
    class_set = NodeSet
    separator = ' '

    # Parse command options using getopt
    try:
        opts, args = getopt.getopt(args[1:], "a:cefhiqvx:RS:X",
            ["autostep=", "count", "expand", "fold", "help",
            "intersection", "quiet", "rangeset", "version", "exclude=",
            "separator=", "xor"])
    except getopt.error, msg:
        print >>sys.stderr, msg
        print >>sys.stderr, "Try `%s -h' for more information." % args[0]
        sys.exit(2)

    # Search for RangeSet switch in options
    for opt in [ "-R", "--rangeset" ]:
        if opt in [k for k, v in opts]:
            class_set = RangeSet

    # Initialize excludes set
    excludes = class_set()

    # Parse other options
    for k, v in opts:
        if k in ("-a", "--autostep"):
            try:
                autostep = int(v)
            except ValueError, e:
                print >>sys.stderr, e
        elif k in ("-c", "--count"):
            command = "count"
        elif k in ("-e", "--expand"):
            command = "expand"
        elif k in ("-f", "--fold"):
            command = "fold"
        elif k in ("-h", "--help"):
            print __doc__
            sys.exit(0)
        elif k in ("-i", "--intersection"):
            if preprocess and preprocess != class_set.intersection_update:
                print >>sys.stderr, "ERROR: Conflicting options."
                sys.exit(2)
            preprocess = class_set.intersection_update
        elif k in ("-q", "--quiet"):
            quiet = True
        elif k in ("-v", "--version"):
            print __version__
            sys.exit(0)
        elif k in ("-x", "--exclude"):
            excludes.update(class_set(v))
        elif k in ("-X", "--xor"):
            if preprocess and preprocess != class_set.symmetric_difference_update:
                print >>sys.stderr, "ERROR: Conflicting options."
                sys.exit(2)
            preprocess = class_set.symmetric_difference_update
        elif k in ("-S", "--separator"):
            separator = v

    # Check for command presence
    if not command:
        print >>sys.stderr, "ERROR: no command specified."
        print __doc__
        sys.exit(1)

    try:
        # Check for nodeset argument(s)
        read_stdin = len(args) < 1
        ns = None

        if len(args):
            if '-' in args:
                # Special argument '-' means read from stdin
                read_stdin = True
                args.remove('-')
        if len(args):
            # Parse arguments
            if not preprocess:
                preprocess = class_set.update
            # Create a base nodeset from first argument (do not use an
            # empty nodeset as it wouldn't work when preprocess is
            # intersection)
            ns = class_set(args[0], autostep=autostep)
            for arg in args[1:]:
                preprocess(ns, class_set(arg, autostep=autostep))

        if read_stdin:
            # Read standard input when argument is missing or when
            # the special argument '-' is specified.
            if not preprocess:
                preprocess = class_set.update
            # Support multi-lines and multi-nodesets per line
            for line in sys.stdin.readlines():
                line = line[0:line.find('#')].strip()
                for node in line.split():
                    if not ns:
                        ns = class_set(node, autostep=autostep)
                    else:
                        preprocess(ns, class_set(node, autostep=autostep))

        # Finally, remove excluding nodes
        if excludes:
            ns.difference_update(excludes)
        # Display result according to command choice
        if command == "expand":
            print eval('\'%s\'' % separator).join(ns)
        elif command == "fold":
            print ns
        else:
            print len(ns)
    except (NodeSetParseError, RangeSetParseError), e:
        if not quiet:
            print >>sys.stderr, "%s parse error:" % class_set.__name__, e
            # In some case, NodeSet might report the part of the string
            # that causes problem.  For RangeSet it is always included
            # in the error message.
            if hasattr(e, 'part') and e.part:
                print >>sys.stderr, ">>", e.part
        sys.exit(1)

if __name__ == '__main__':
    try:
        run_nodeset(sys.argv)
    except AssertionError, e:
        print >>sys.stderr, "ERROR:", e
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(128 + signal.SIGINT)
    sys.exit(0)
