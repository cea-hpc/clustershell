#
# Copyright (C) 2008-2016 CEA/DAM
# Copyright (C) 2015-2018 Stephane Thiell <sthiell@stanford.edu>
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
compute advanced nodeset operations

The nodeset command is an utility command provided with the
ClusterShell library which implements some features of the NodeSet
and RangeSet classes.
"""

from __future__ import print_function

import logging
import math
import random
import sys

from ClusterShell.CLI.Error import GENERIC_ERRORS, handle_generic_error
from ClusterShell.CLI.OptionParser import OptionParser

from ClusterShell.NodeSet import NodeSet, RangeSet, std_group_resolver
from ClusterShell.NodeSet import grouplist, set_std_group_resolver_config
from ClusterShell.NodeUtils import GroupSourceNoUpcall


def process_stdin(xsetop, xsetcls, autostep):
    """Process standard input and operate on xset."""
    # Build temporary set (stdin accumulator)
    tmpset = xsetcls(autostep=autostep)
    for line in sys.stdin:  # read lines of text stream (not bytes)
        # Support multi-lines and multi-nodesets per line
        line = line[0:line.find('#')].strip()
        for elem in line.split():
            # Do explicit object creation for RangeSet
            tmpset.update(xsetcls(elem, autostep=autostep))
    # Perform operation on xset
    if tmpset:
        xsetop(tmpset)

def compute_nodeset(xset, args, autostep):
    """Apply operations and operands from args on xset, an initial
    RangeSet or NodeSet."""
    class_set = xset.__class__
    # Process operations from command arguments.
    # The special argument string "-" indicates to read stdin.
    # We also take care of multiline shell arguments (#394).
    while args:
        arg = args.pop(0)
        if arg in ("-i", "--intersection"):
            val = args.pop(0)
            if val == '-':
                process_stdin(xset.intersection_update, class_set, autostep)
            else:
                xset.intersection_update(class_set.fromlist(val.splitlines(),
                                                            autostep=autostep))
        elif arg in ("-x", "--exclude"):
            val = args.pop(0)
            if val == '-':
                process_stdin(xset.difference_update, class_set, autostep)
            else:
                xset.difference_update(class_set.fromlist(val.splitlines(),
                                                          autostep=autostep))
        elif arg in ("-X", "--xor"):
            val = args.pop(0)
            if val == '-':
                process_stdin(xset.symmetric_difference_update, class_set,
                              autostep)
            else:
                xset.symmetric_difference_update(
                    class_set.fromlist(val.splitlines(), autostep=autostep))
        elif arg == '-':
            process_stdin(xset.update, xset.__class__, autostep)
        else:
            xset.update(class_set.fromlist(arg.splitlines(), autostep=autostep))

    return xset

def print_source_groups(source, level, xset, opts):
    """
    Print groups from a source, a level of verbosity and an optional
    nodeset acting as a filter.
    """
    # list groups of some specified nodes?
    if opts.all or xset or opts.and_nodes or opts.sub_nodes or opts.xor_nodes:
        # When some node sets are provided as argument, the list command
        # retrieves node groups these nodes belong to, thanks to the
        # groups() method.
        # Note: stdin support is enabled when '-' is found.
        groups = xset.groups(source, opts.groupbase)
        # sort by group name
        for group, (gnodes, inodes) in sorted(groups.items()):
            if level == 1:
                print(group)
            elif level == 2:
                print("%s %s" % (group, inodes))
            else:
                print("%s %s %d/%d" % (group, inodes, len(inodes),
                                       len(gnodes)))
    else:
        # "raw" group list when no argument at all
        for group in grouplist(source):
            if source and not opts.groupbase:
                nsgroup = "@%s:%s" % (source, group)
            else:
                nsgroup = "@%s" % group
            if level == 1:
                print(nsgroup)
            else:
                nodes = NodeSet(nsgroup)
                if level == 2:
                    print("%s %s" % (nsgroup, nodes))
                else:
                    print("%s %s %d" % (nsgroup, nodes, len(nodes)))

def command_list(options, xset, group_resolver):
    """List command handler (-l/-ll/-lll/-L/-LL/-LLL)."""
    list_level = options.list + options.listall
    if options.listall:
        # useful: sources[0] is always the default or selected source
        sources = group_resolver.sources()
        # do not print name of default group source unless -s specified
        if sources and not options.groupsource:
            sources[0] = None
    else:
        sources = [options.groupsource]

    for source in sources:
        try:
            print_source_groups(source, list_level, xset, options)
        except GroupSourceNoUpcall as exc:
            if not options.listall:
                raise
            # missing list upcall is not fatal with -L
            msgfmt = "Warning: No %s upcall defined for group source %s"
            print(msgfmt % (exc, source), file=sys.stderr)

def nodeset():
    """script subroutine"""
    class_set = NodeSet
    usage = "%prog [COMMAND] [OPTIONS] [ns1 [-ixX] ns2|...]"

    parser = OptionParser(usage)
    parser.install_groupsconf_option()
    parser.install_nodeset_commands()
    parser.install_nodeset_operations()
    parser.install_nodeset_options()
    (options, args) = parser.parse_args()

    set_std_group_resolver_config(options.groupsconf)
    group_resolver = std_group_resolver()

    if options.debug:
        logging.basicConfig(level=logging.DEBUG)

    # Check for command presence
    cmdcount = int(options.count) + int(options.expand) + \
               int(options.fold) + int(bool(options.list)) + \
               int(bool(options.listall)) + int(options.regroup) + \
               int(options.groupsources)
    if not cmdcount:
        parser.error("No command specified.")
    elif cmdcount > 1:
        parser.error("Multiple commands not allowed.")

    if options.rangeset:
        class_set = RangeSet

    if options.all or options.regroup:
        if class_set != NodeSet:
            parser.error("-a/-r only supported in NodeSet mode")

    if options.maxsplit is not None and options.contiguous:
        parser.error("incompatible splitting options (split, contiguous)")

    if options.maxsplit is None:
        options.maxsplit = 1

    if options.axis and (not options.fold or options.rangeset):
        parser.error("--axis option is only supported when folding nodeset")

    if options.groupsource and not options.quiet and class_set == RangeSet:
        print("WARNING: option group source \"%s\" ignored"
              % options.groupsource, file=sys.stderr)

    # We want -s <groupsource> to act as a substition of default groupsource
    # (ie. it's not necessary to prefix group names by this group source).
    if options.groupsource:
        group_resolver.default_source_name = options.groupsource

    # The groupsources command simply lists group sources.
    if options.groupsources:
        if options.quiet:
            dispdefault = ""    # don't show (default) if quiet is set
        else:
            dispdefault = " (default)"
        for src in group_resolver.sources():
            print("%s%s" % (src, dispdefault))
            dispdefault = ""
        return

    autostep = options.autostep

    # Do not use autostep for computation when a percentage or the special
    # value 'auto' is specified. Real autostep value is set post-process.
    if isinstance(autostep, float) or autostep == 'auto':
        autostep = None

    # Instantiate RangeSet or NodeSet object
    xset = class_set(autostep=autostep)

    if options.all:
        # Include all nodes from external node groups support.
        xset.update(NodeSet.fromall()) # uses default_source when set

    if not args and not options.all and not (options.list or options.listall):
        # No need to specify '-' to read stdin in these cases
        process_stdin(xset.update, xset.__class__, autostep)

    if not xset and (options.and_nodes or options.sub_nodes or
                     options.xor_nodes) and not options.quiet:
        print('WARNING: empty left operand for set operation', file=sys.stderr)

    # Apply first operations (before first non-option)
    for nodes in options.and_nodes:
        if nodes == '-':
            process_stdin(xset.intersection_update, xset.__class__, autostep)
        else:
            xset.intersection_update(class_set(nodes, autostep=autostep))
    for nodes in options.sub_nodes:
        if nodes == '-':
            process_stdin(xset.difference_update, xset.__class__, autostep)
        else:
            xset.difference_update(class_set(nodes, autostep=autostep))
    for nodes in options.xor_nodes:
        if nodes == '-':
            process_stdin(xset.symmetric_difference_update, xset.__class__,
                          autostep)
        else:
            xset.symmetric_difference_update(class_set(nodes,
                                                       autostep=autostep))

    # Finish xset computing from args
    compute_nodeset(xset, args, autostep)

    # The list command has a special handling
    if options.list > 0 or options.listall > 0:
        return command_list(options, xset, group_resolver)

    # Interpret special characters (may raise SyntaxError)
    separator = eval('\'\'\'%s\'\'\'' % options.separator,
                     {"__builtins__":None}, {})

    if options.slice_rangeset:
        _xset = class_set()
        for sli in RangeSet(options.slice_rangeset).slices():
            _xset.update(xset[sli])
        xset = _xset

    if options.autostep == 'auto':
        # Simple implementation of --autostep=auto
        # if we have at least 3 nodes, all index should be foldable as a-b/n
        xset.autostep = max(3, len(xset))
    elif isinstance(options.autostep, float):
        # at least % of nodes should be foldable as a-b/n
        autofactor = float(options.autostep)
        xset.autostep = int(math.ceil(float(len(xset)) * autofactor))

    # user-specified nD-nodeset fold axis
    if options.axis:
        if not options.axis.startswith('-'):
            # axis are 1-indexed in nodeset CLI (0 ignored)
            xset.fold_axis = tuple(x-1 for x in RangeSet(options.axis) if x > 0)
        else:
            # negative axis index (only single number supported)
            xset.fold_axis = [int(options.axis)]

    if options.pick and options.pick < len(xset):
        # convert to string for sample as nsiter() is slower for big
        # nodesets; and we assume options.pick will remain small-ish
        keep = random.sample(list(xset), options.pick)
        # explicit class_set creation and str() conversion for RangeSet
        keep = class_set(','.join([str(x) for x in keep]))
        xset.intersection_update(keep)

    fmt = options.output_format # default to '%s'

    # Display result according to command choice
    if options.expand:
        xsubres = lambda x: separator.join((fmt % s for s in x.striter()))
    elif options.fold:
        # Special case when folding using NodeSet and format is set (#277)
        if class_set is NodeSet and fmt != '%s':
            # Create a new set after format has been applied to each node
            xset = class_set._fromlist1((fmt % xnodestr for xnodestr in xset),
                                        autostep=xset.autostep)
            xsubres = lambda x: x
        else:
            xsubres = lambda x: fmt % x
    elif options.regroup:
        xsubres = lambda x: fmt % x.regroup(options.groupsource,
                                            noprefix=options.groupbase)
    else:
        xsubres = lambda x: fmt % len(x)

    if not xset or options.maxsplit <= 1 and not options.contiguous:
        print(xsubres(xset))
    else:
        if options.contiguous:
            xiterator = xset.contiguous()
        else:
            xiterator = xset.split(options.maxsplit)
        for xsubset in xiterator:
            print(xsubres(xsubset))

def main():
    """main script function"""
    try:
        nodeset()
    except (AssertionError, IndexError, ValueError) as ex:
        print("ERROR: %s" % ex, file=sys.stderr)
        sys.exit(1)
    except SyntaxError:
        print("ERROR: invalid separator", file=sys.stderr)
        sys.exit(1)
    except GENERIC_ERRORS as ex:
        sys.exit(handle_generic_error(ex))

    sys.exit(0)


if __name__ == '__main__':
    main()
