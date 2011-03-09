#!/usr/bin/env python
#
# Copyright CEA/DAM/DIF (2010, 2011)
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
format dsh/pdsh-like output for humans and more

For help, type::
    $ clubak --help
"""

from itertools import imap
import sys

from ClusterShell.MsgTree import MsgTree
from ClusterShell.NodeSet import STD_GROUP_RESOLVER

from ClusterShell.CLI.Display import Display
from ClusterShell.CLI.Error import GENERIC_ERRORS, handle_generic_error
from ClusterShell.CLI.OptionParser import OptionParser
from ClusterShell.CLI.Utils import NodeSet, nodeset_cmp


def display_tree(tree, disp, out):
    """display sub-routine for clubak -T (msgtree trace mode)"""
    togh = True
    offset = 2
    reldepth = -offset
    reldepths = {}
    line_mode = disp.line_mode
    for msgline, keys, depth, nchildren in tree.walk_trace():
        if togh:
            if depth in reldepths:
                reldepth = reldepths[depth]
            else:
                reldepth = reldepths[depth] = reldepth + offset
            if line_mode:
                out.write("%s:\n" % NodeSet.fromlist(keys))
            else:
                out.write("%s\n" % \
                    (disp.format_header(NodeSet.fromlist(keys), reldepth)))
        out.write("%s%s\n" % (" " * reldepth, msgline))
        togh = nchildren != 1

def display(tree, disp, gather, tree_mode):
    """nicely display MsgTree instance `tree' content according to
    `disp' Display object and `gather' boolean flag"""
    out = sys.stdout
    try:
        if tree_mode:
            display_tree(tree, disp, out)
        else:
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
        out.flush()

def clubak():
    """script subroutine"""

    # Argument management
    parser = OptionParser("%prog [options]")
    parser.install_display_options(separator_option=True,
                                   dshbak_compat=True,
                                   msgtree_trace=True)
    options = parser.parse_args()[0]

    # Create new message tree
    tree = MsgTree(trace=options.tree_mode)

    # Feed the tree from standard input lines
    for line in sys.stdin:
        try:
            linestripped = line.rstrip('\r\n')
            node, content = linestripped.split(options.separator, 1)
            node = node.strip()
            if not node:
                raise ValueError("no node found")
            tree.add(node, content)
        except ValueError, ex:
            raise ValueError("%s (\"%s\")" % (ex, linestripped))

    if options.debug:
        STD_GROUP_RESOLVER.set_verbosity(1)
        print >> sys.stderr, "clubak: line_mode=%s gather=%s tree_depth=%d" % \
            (bool(options.line_mode), bool(options.gather), tree._depth())

    # Display results
    disp = Display(options)
    display(tree, disp, options.gather or disp.regroup, options.tree_mode)

def main():
    """main script function"""
    try:
        clubak()
    except GENERIC_ERRORS, ex:
        sys.exit(handle_generic_error(ex))
    except ValueError, ex:
        print >> sys.stderr, "%s:" % sys.argv[0], ex
        sys.exit(1)

    sys.exit(0)


if __name__ == '__main__':
    main()
