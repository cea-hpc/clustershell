#!/usr/bin/env python
#
# Copyright CEA/DAM/DIF (2008, 2009, 2010, 2011, 2012)
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

"""
compute advanced nodeset operations

The nodeset command is an utility command provided with the
ClusterShell library which implements some features of the NodeSet
and RangeSet classes.
"""

import math
import sys

from ClusterShell.CLI.Error import GENERIC_ERRORS, handle_generic_error
from ClusterShell.CLI.OptionParser import OptionParser
from ClusterShell.CLI.Utils import NodeSet  # safe import

from ClusterShell.NodeSet import RangeSet, grouplist, std_group_resolver
from ClusterShell.NodeUtils import GroupSourceNoUpcall


def process_stdin(xsetop, xsetcls, autostep):
    """Process standard input and operate on xset."""
    # Build temporary set (stdin accumulator)
    tmpset = xsetcls(autostep=autostep)
    for line in sys.stdin.readlines():
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
    # Process operations
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
        for group, (gnodes, inodes) in groups.iteritems():
            if level == 1:
                print group
            elif level == 2:
                print "%s %s" % (group, inodes)
            else:
                print "%s %s %d/%d" % (group, inodes, len(inodes),
                                       len(gnodes))
    else:
        # "raw" group list when no argument at all
        for group in grouplist(source):
            if source and not opts.groupbase:
                nsgroup = "@%s:%s" % (source, group)
            else:
                nsgroup = "@%s" % group
            if level == 1:
                print nsgroup
            else:
                nodes = NodeSet(nsgroup)
                if level == 2:
                    print "%s %s" % (nsgroup, nodes)
                else:
                    print "%s %s %d" % (nsgroup, nodes, len(nodes))

def command_list(options, xset, group_resolver):
    """List command handler (-l/-ll/-lll/-L/-LL/-LLL)."""
    list_level = options.list + options.listall
    if options.listall:
        # useful: sources[0] is always the default or selected source
        sources = group_resolver.sources()
        # do not print name of default group source unless -s specified
        if not options.groupsource:
            sources[0] = None
    else:
        sources = [options.groupsource]

    for source in sources:
        try:
            print_source_groups(source, list_level, xset, options)
        except GroupSourceNoUpcall, exc:
            if not options.listall:
                raise
            # missing list upcall is not fatal with -L
            msgfmt = "Warning: No %s upcall defined for group source %s"
            print >>sys.stderr, msgfmt % (exc, source)

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
        group_resolver.set_verbosity(1)

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
        print >> sys.stderr, "WARNING: option group source \"%s\" ignored" \
                                % options.groupsource

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
            print "%s%s" % (src, dispdefault)
            dispdefault = ""
        return

    autostep = options.autostep

    # Do not use autostep for computation when a percentage or the special
    # value 'auto' is specified. Real autostep value is set post-process.
    if type(autostep) is float or autostep == 'auto':
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

    # The list command has a special handling
    if options.list > 0 or options.listall > 0:
        return command_list(options, xset, group_resolver)

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
    elif type(options.autostep) is float:
        # at least % of nodes should be foldable as a-b/n
        autofactor = float(options.autostep)
        xset.autostep = int(math.ceil(float(len(xset)) * autofactor))

    # user-specified nD-nodeset fold axis
    if options.axis:
        if not options.axis.startswith('-'):
            # axis are 1-indexed in nodeset CLI (0 ignored)
            xset.fold_axis = tuple(x - 1 for x in RangeSet(options.axis) if x > 0)
        else:
            # negative axis index (only single number supported)
            xset.fold_axis = [int(options.axis)]

    fmt = options.output_format # default to '%s'

    # Display result according to command choice
    if options.expand:
        xsubres = lambda x: separator.join((fmt % s for s in x.striter()))
    elif options.fold:
        xsubres = lambda x: fmt % x
    elif options.regroup:
        xsubres = lambda x: fmt % x.regroup(options.groupsource,
                                            noprefix=options.groupbase)
    else:
        xsubres = lambda x: fmt % len(x)

    if not xset or options.maxsplit <= 1 and not options.contiguous:
        print xsubres(xset)
    else:
        if options.contiguous:
            xiterator = xset.contiguous()
        else:
            xiterator = xset.split(options.maxsplit)
        for xsubset in xiterator:
            print xsubres(xsubset)

def main():
    """main script function"""
    try:
        nodeset()
    except (AssertionError, IndexError, ValueError), ex:
        print >> sys.stderr, "ERROR:", ex
        sys.exit(1)
    except SyntaxError:
        print >> sys.stderr, "ERROR: invalid separator"
        sys.exit(1)
    except GENERIC_ERRORS, ex:
        sys.exit(handle_generic_error(ex))

    sys.exit(0)


if __name__ == '__main__':
    main()
