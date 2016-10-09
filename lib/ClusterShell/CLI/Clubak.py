#!/usr/bin/env python
#
# Copyright (C) 2010-2012 CEA/DAM
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
format dsh/pdsh-like output for humans and more

For help, type::
    $ clubak --help
"""

from itertools import imap
import sys

from ClusterShell.MsgTree import MsgTree, MODE_DEFER, MODE_TRACE
from ClusterShell.NodeSet import NodeSetParseError, std_group_resolver

from ClusterShell.CLI.Display import Display, THREE_CHOICES
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

def display(tree, disp, gather, trace_mode, enable_nodeset_key):
    """nicely display MsgTree instance `tree' content according to
    `disp' Display object and `gather' boolean flag"""
    out = sys.stdout
    try:
        if trace_mode:
            display_tree(tree, disp, out)
        else:
            if gather:
                if enable_nodeset_key:
                    # lambda to create a NodeSet from keys returned by walk()
                    ns_getter = lambda x: NodeSet.fromlist(x[1])
                    for nodeset in sorted(imap(ns_getter, tree.walk()),
                                          cmp=nodeset_cmp):
                        disp.print_gather(nodeset, tree[nodeset[0]])
                else:
                    for msg, key in tree.walk():
                        disp.print_gather_keys(key, msg)
            else:
                if enable_nodeset_key:
                    # nodes are automagically sorted by NodeSet
                    for node in NodeSet.fromlist(tree.keys()).nsiter():
                        disp.print_gather(node, tree[str(node)])
                else:
                    for key in tree.keys():
                        disp.print_gather_keys([ key ], tree[key])
    finally:
        out.flush()

def clubak():
    """script subroutine"""

    # Argument management
    parser = OptionParser("%prog [options]")
    parser.install_display_options(verbose_options=True,
                                   separator_option=True,
                                   dshbak_compat=True,
                                   msgtree_mode=True)
    options = parser.parse_args()[0]

    if options.interpret_keys == THREE_CHOICES[-1]: # auto?
        enable_nodeset_key = None # AUTO
    else:
        enable_nodeset_key = (options.interpret_keys == THREE_CHOICES[1])

    # Create new message tree
    if options.trace_mode:
        tree_mode = MODE_TRACE
    else:
        tree_mode = MODE_DEFER
    tree = MsgTree(mode=tree_mode)
    fast_mode = options.fast_mode
    if fast_mode:
        if tree_mode != MODE_DEFER or options.line_mode:
            parser.error("incompatible tree options")
        preload_msgs = {}

    # Feed the tree from standard input lines
    for line in sys.stdin:
        try:
            linestripped = line.rstrip('\r\n')
            if options.verbose or options.debug:
                print "INPUT %s" % linestripped
            key, content = linestripped.split(options.separator, 1)
            key = key.strip()
            if not key:
                raise ValueError("no node found")
            if enable_nodeset_key is False: # interpret-keys=never?
                keyset = [ key ]
            else:
                try:
                    keyset = NodeSet(key)
                except NodeSetParseError:
                    if enable_nodeset_key: # interpret-keys=always?
                        raise
                    enable_nodeset_key = False # auto => switch off
                    keyset = [ key ]
            if fast_mode:
                for node in keyset:
                    preload_msgs.setdefault(node, []).append(content)
            else:
                for node in keyset:
                    tree.add(node, content)
        except ValueError, ex:
            raise ValueError("%s (\"%s\")" % (ex, linestripped))

    if fast_mode:
        # Messages per node have been aggregated, now add to tree one
        # full msg per node
        for key, wholemsg in preload_msgs.iteritems():
            tree.add(key, '\n'.join(wholemsg))

    # Display results
    try:
        disp = Display(options)
        if options.debug:
            std_group_resolver().set_verbosity(1)
            print >> sys.stderr, \
                "clubak: line_mode=%s gather=%s tree_depth=%d" % \
                    (bool(options.line_mode), bool(disp.gather), tree._depth())
        display(tree, disp, disp.gather or disp.regroup, \
                options.trace_mode, enable_nodeset_key is not False)
    except ValueError, exc:
        parser.error("option mismatch (%s)" % exc)

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
