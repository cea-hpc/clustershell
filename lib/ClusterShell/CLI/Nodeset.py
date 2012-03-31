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

import sys

from ClusterShell.CLI.Error import GENERIC_ERRORS, handle_generic_error
from ClusterShell.CLI.OptionParser import OptionParser
from ClusterShell.CLI.Utils import NodeSet  # safe import

from ClusterShell.NodeSet import RangeSet, grouplist, RESOLVER_STD_GROUP


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

def command_list(options, xset):
    """List (-l/-ll/-lll) command handler."""
    list_level = options.list
    # list groups of some specified nodes?
    if options.all or xset or \
        options.and_nodes or options.sub_nodes or options.xor_nodes:
        # When some node sets are provided as argument, the list command
        # retrieves node groups these nodes belong to, thanks to the
        # groups() method (new in 1.6). Note: stdin support is enabled
        # when the '-' special character is encountered.
        groups = xset.groups(options.groupsource, options.groupbase)
        for group, (gnodes, inodes) in groups.iteritems():
            if list_level == 1:         # -l
                print group
            elif list_level == 2:       # -ll
                print "%s %s" % (group, inodes)
            else:                       # -lll
                print "%s %s %d/%d" % (group, inodes, len(inodes), \
                                       len(gnodes))
        return
    # "raw" group list when no argument at all
    for group in grouplist(options.groupsource):
        if options.groupsource and not options.groupbase:
            nsgroup = "@%s:%s" % (options.groupsource, group)
        else:
            nsgroup = "@%s" % group
        if list_level == 1:         # -l
            print nsgroup
        else:
            nodes = NodeSet(nsgroup)
            if list_level == 2:     # -ll
                print "%s %s" % (nsgroup, nodes)
            else:                   # -lll
                print "%s %s %d" % (nsgroup, nodes, len(nodes))

def nodeset():
    """script subroutine"""
    class_set = NodeSet
    usage = "%prog [COMMAND] [OPTIONS] [ns1 [-ixX] ns2|...]"

    parser = OptionParser(usage)
    parser.install_nodeset_commands()
    parser.install_nodeset_operations()
    parser.install_nodeset_options()
    (options, args) = parser.parse_args()

    if options.debug:
        RESOLVER_STD_GROUP.set_verbosity(1)

    # Check for command presence
    cmdcount = int(options.count) + int(options.expand) + \
               int(options.fold) + int(bool(options.list)) + \
               int(options.regroup) + int(options.groupsources)
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

    if options.groupsource and not options.quiet and \
       (class_set == RangeSet or options.groupsources):
        print >> sys.stderr, "WARNING: option group source \"%s\" ignored" \
                                % options.groupsource

    # The groupsources command simply lists group sources.
    if options.groupsources:
        if options.quiet:
            dispdefault = ""    # don't show (default) if quiet is set
        else:
            dispdefault = " (default)"
        for src in RESOLVER_STD_GROUP.sources():
            print "%s%s" % (src, dispdefault)
            dispdefault = ""
        return

    # We want -s <groupsource> to act as a substition of default groupsource
    # (ie. it's not necessary to prefix group names by this group source).
    if options.groupsource:
        RESOLVER_STD_GROUP.default_sourcename = options.groupsource

    # Instantiate RangeSet or NodeSet object
    xset = class_set(autostep=options.autostep)

    if options.all:
        # Include all nodes from external node groups support.
        xset.update(NodeSet.fromall()) # uses default_sourcename

    if not args and not options.all and not options.list:
        # No need to specify '-' to read stdin in these cases
        process_stdin(xset.update, xset.__class__, options.autostep)

    # Apply first operations (before first non-option)
    for nodes in options.and_nodes:
        if nodes == '-':
            process_stdin(xset.intersection_update, xset.__class__,
                          options.autostep)
        else:
            xset.intersection_update(class_set(nodes,
                                               autostep=options.autostep))
    for nodes in options.sub_nodes:
        if nodes == '-':
            process_stdin(xset.difference_update, xset.__class__,
                          options.autostep)
        else:
            xset.difference_update(class_set(nodes, autostep=options.autostep))
    for nodes in options.xor_nodes:
        if nodes == '-':
            process_stdin(xset.symmetric_difference_update, xset.__class__,
                          options.autostep)
        else:
            xset.symmetric_difference_update(class_set(nodes, \
                                             autostep=options.autostep))

    # Finish xset computing from args
    compute_nodeset(xset, args, options.autostep)

    # The list command has a special handling
    if options.list > 0:
        return command_list(options, xset)

    # Interprete special characters (may raise SyntaxError)
    separator = eval('\'%s\'' % options.separator, {"__builtins__":None}, {})

    if options.slice_rangeset:
        _xset = class_set()
        for sli in RangeSet(options.slice_rangeset).slices():
            _xset.update(xset[sli])
        xset = _xset

    # Display result according to command choice
    if options.expand:
        xsubres = lambda x: separator.join(x.striter())
    elif options.fold:
        xsubres = lambda x: x
    elif options.regroup:
        xsubres = lambda x: x.regroup(options.groupsource, \
                                      noprefix=options.groupbase)
    else:
        xsubres = len

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
    except AssertionError, ex:
        print >> sys.stderr, "ERROR:", ex
        sys.exit(1)
    except IndexError:
        print >> sys.stderr, "ERROR: syntax error"
        sys.exit(1)
    except SyntaxError:
        print >> sys.stderr, "ERROR: invalid separator"
        sys.exit(1)
    except GENERIC_ERRORS, ex:
        sys.exit(handle_generic_error(ex))

    sys.exit(0)


if __name__ == '__main__':
    main()
