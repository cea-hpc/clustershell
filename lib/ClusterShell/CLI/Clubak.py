#
# Copyright (C) 2010-2012 CEA/DAM
# Copyright (C) 2017-2018 Stephane Thiell <sthiell@stanford.edu>
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

from __future__ import print_function

import sys

from ClusterShell.MsgTree import MsgTree, MODE_DEFER, MODE_TRACE
from ClusterShell.NodeSet import NodeSet, NodeSetParseError, std_group_resolver
from ClusterShell.NodeSet import set_std_group_resolver_config

from ClusterShell.CLI.Display import Display, THREE_CHOICES
from ClusterShell.CLI.Display import sys_stdin, sys_stdout
from ClusterShell.CLI.Error import GENERIC_ERRORS, handle_generic_error
from ClusterShell.CLI.OptionParser import OptionParser
from ClusterShell.CLI.Utils import nodeset_cmpkey


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
            nodeset = NodeSet.fromlist(keys)
            if line_mode:
                out.write(str(nodeset).encode() + b':\n')
            else:
                out.write(disp.format_header(nodeset, reldepth))
        out.write(b' ' * reldepth + msgline + b'\n')
        togh = nchildren != 1

def display(tree, disp, gather, trace_mode, enable_nodeset_key):
    """nicely display MsgTree instance `tree' content according to
    `disp' Display object and `gather' boolean flag"""
    out = sys_stdout()
    try:
        if trace_mode:
            display_tree(tree, disp, out)
        else:
            if gather:
                if enable_nodeset_key:
                    # lambda to create a NodeSet from keys returned by walk()
                    ns_getter = lambda x: NodeSet.fromlist(x[1])
                    for nodeset in sorted((ns_getter(item) for item in tree.walk()),
                                          key=nodeset_cmpkey):
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
    parser.install_groupsconf_option()
    parser.install_display_options(verbose_options=True,
                                   separator_option=True,
                                   dshbak_compat=True,
                                   msgtree_mode=True)
    options = parser.parse_args()[0]

    set_std_group_resolver_config(options.groupsconf)

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

    separator = options.separator.encode()

    # Feed the tree from standard input lines
    for line in sys_stdin():
        try:
            linestripped = line.rstrip(b'\r\n')
            if options.verbose or options.debug:
                sys_stdout().write(b'INPUT ' + linestripped + b'\n')
            key, content = linestripped.split(separator, 1)
            key = key.strip().decode()  # NodeSet requires encoded string
            if not key:
                raise ValueError("no node found")
            if enable_nodeset_key is False:  # interpret-keys=never?
                keyset = [ key ]
            else:
                try:
                    keyset = NodeSet(key)
                except NodeSetParseError:
                    if enable_nodeset_key:  # interpret-keys=always?
                        raise
                    enable_nodeset_key = False  # auto => switch off
                    keyset = [ key ]
            if fast_mode:
                for node in keyset:
                    preload_msgs.setdefault(node, []).append(content)
            else:
                for node in keyset:
                    tree.add(node, content)
        except ValueError as ex:
            raise ValueError('%s: "%s"' % (ex, linestripped.decode()))

    if fast_mode:
        # Messages per node have been aggregated, now add to tree one
        # full msg per node
        for key, wholemsg in preload_msgs.items():
            tree.add(key, b'\n'.join(wholemsg))

    # Display results
    try:
        disp = Display(options)
        if options.debug:
            std_group_resolver().set_verbosity(1)
            print("clubak: line_mode=%s gather=%s tree_depth=%d"
                  % (bool(options.line_mode), bool(disp.gather), tree._depth()),
                  file=sys.stderr)
        display(tree, disp, disp.gather or disp.regroup, \
                options.trace_mode, enable_nodeset_key is not False)
    except ValueError as exc:
        parser.error("option mismatch (%s)" % exc)

def main():
    """main script function"""
    try:
        clubak()
    except GENERIC_ERRORS as ex:
        sys.exit(handle_generic_error(ex))
    except ValueError as ex:
        print("%s:" % sys.argv[0], ex, file=sys.stderr)
        sys.exit(1)

    sys.exit(0)


if __name__ == '__main__':
    main()
