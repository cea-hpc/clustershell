#
# Copyright (C) 2008-2016 CEA/DAM
# Copyright (C) 2015-2017 Stephane Thiell <sthiell@stanford.edu>
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
from ClusterShell.CLI.Utils import NodeSet  # safe import

from ClusterShell.NodeSet import RangeSet, grouplist, std_group_resolver
from ClusterShell.NodeSet import RESOLVER_NOGROUP
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
    """
    Apply operations and operands from args to xset, that can be either
    a RangeSet or a NodeSet object.
    """
    class_set = xset.__class__
    while args:
        arg = args.pop(0)
        if arg in ("-i", "--intersection"):
            val = args.pop(0)
            if val == '-':
                process_stdin(xset.intersection_update, class_set, autostep)
            else:
                xset.intersection_update(class_set(val, autostep=autostep))
        elif arg in ("-x", "--exclude"):
            val = args.pop(0)
            if val == '-':
                process_stdin(xset.difference_update, class_set, autostep)
            else:
                xset.difference_update(class_set(val, autostep=autostep))
        elif arg in ("-X", "--xor"):
            val = args.pop(0)
            if val == '-':
                process_stdin(xset.symmetric_difference_update, class_set,
                              autostep)
            else:
                xset.symmetric_difference_update(class_set(val,
                                                           autostep=autostep))
        elif arg == '-':
            process_stdin(xset.update, xset.__class__, autostep)
        else:
            xset.update(class_set(arg, autostep=autostep))

    return xset

def print_groups(groups, level, xset_provided):
    """
    Print groups from a NodeSet.groups()-like dict, a level of verbosity
    and a boolean to control how the node counter is printed.
    """
    # sort by group name
    for group, (gnodes, inodes) in sorted(groups.items()):
        if level == 1:
            print(group)
        elif level == 2:
            print("%s %s" % (group, inodes))
        elif not xset_provided:
            print("%s %s %d" % (group, inodes, len(inodes)))
        else:
            print("%s %s %d/%d" % (group, inodes, len(inodes), len(gnodes)))

def selected_sources(options, group_resolver):
    """
    Helper for the list command (-l) that returns a list of selected
    sources, taking into account the options passed to nodeset.
    """
    if options.listall:
        # useful: sources[0] is always the default or selected source
        sources = group_resolver.sources()
        # do not print name of default group source unless -s specified
        if not options.groupsource:
            sources[0] = None
    else:
        sources = [options.groupsource]

    return sources

def groups_from_source(opts, xset, source, level):
    """
    Helper for the list command (-l) that returns a dictionary of groups,
    similar to NodeSet.groups(), whose keys are group names and values are
    tuple (group_nodeset, intersection_nodeset), taking into account the
    options passed to nodeset.
    """
    # should we only return groups from specified nodes?
    if opts.all or xset or opts.and_nodes or opts.sub_nodes or opts.xor_nodes:
        # When some node sets are provided as argument, the list command
        # retrieves node groups these nodes belong to, thanks to the
        # groups() method.
        # Note: stdin support is enabled when '-' is found.
        groups = xset.groups(source, opts.groupbase)
    else:
        groups = {}
        # "raw" group list when no argument at all
        for group in grouplist(source):
            if source and not opts.groupbase:
                nsgroup = "@%s:%s" % (source, group)
            else:
                nsgroup = "@%s" % group

            if level == 1:
                groups[nsgroup] = (None, None)
            else:
                nodes = NodeSet(nsgroup)
                groups[nsgroup] = (nodes, nodes)
    return groups

def source_groups(options, xset, group_resolver):
    """
    Generator used by the list command (-l) to return tuples of individual
    source with associated groups, taking into account the options passed
    to nodeset. It makes use of both helper functions selected_sources()
    and groups_from_source().
    """
    level = options.list + options.listall

    for source in selected_sources(options, group_resolver):
        try:
            yield source, groups_from_source(options, xset, source, level)
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
    parser.install_nodeset_commands()
    parser.install_nodeset_operations()
    parser.install_nodeset_options()
    (options, args) = parser.parse_args()

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
        # At this point, only -l with -c/-e/-f makes sense
        if options.list + options.listall == 0 or \
           int(options.count) + int(options.expand) + int(options.fold) > 1:
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

    # The list command requires some special handlings
    if options.list > 0 or options.listall > 0:
        if not (options.count or options.expand or options.fold):
            # legacy list command (-l/-L)
            list_level = options.list + options.listall  # multiple -l/-L
            for source, groups in source_groups(options, xset, group_resolver):
                print_groups(groups, list_level, len(xset))
            return
        else:
            # list command (-l/-L) along with -c/-e/-f (1.8+)
            # build groupset from unresolved group names
            groupset = class_set()
            for source, groups in source_groups(options, xset, group_resolver):
                groupset.update(NodeSet.fromlist(groups.keys(),
                                                 resolver=RESOLVER_NOGROUP))
            # continue standard -c/-e/-f processing with groupset
            xset = groupset

    # Interprete special characters (may raise SyntaxError)
    separator = eval('\'%s\'' % options.separator, {"__builtins__":None}, {})

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
        # explicit class_set creation and str() convertion for RangeSet
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
