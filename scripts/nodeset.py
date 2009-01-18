#!/usr/bin/env python
# Copyright (C) 2008, 2009 CEA
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
    --quiet, -q
        Quiet mode, hide any parse error messages (on stderr).
"""

import getopt
import sys

sys.path.append('../lib')

from ClusterShell.NodeSet import NodeSet, NodeSetParseError


def runNodeSetCommand(args):
    """
    Main script function.
    """
    autostep = None
    command = None
    intersect = False
    quiet = False
    excludes = NodeSet()

    try:
        opts, args = getopt.getopt(args[1:], "a:cefhiqx:", ["autostep=",
            "count", "exclude=", "expand", "fold", "help", "intersection",
            "quiet"])
    except getopt.error, msg:
        print msg
        print "Try `%s -h' for more information." % args[0]
        sys.exit(2)

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
            intersect = True
        elif k in ("-q", "--quiet"):
            quiet = True
        elif k in ("-x", "--exclude"):
            excludes.update(v)

    if command is None or len(args) < 1:
        print __doc__
        sys.exit(1)

    try:
        if intersect:
            ns = NodeSet(args[0], autostep)
            for arg in args[1:]:
                ns.intersection_update(arg)
        else:
            ns = NodeSet.fromlist(args, autostep)
    except NodeSetParseError, e:
        if not quiet:
            print >>sys.stderr, "NodeSet parse error:", e
        sys.exit(1)
    else:
        ns.difference_update(excludes)
        if command == "expand":
            print " ".join(ns)
        elif command == "fold":
            print ns
        else:
            print len(ns)

    sys.exit(0)

if __name__ == '__main__':
    runNodeSetCommand(sys.argv)
