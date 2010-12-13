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
compute advanced nodeset operations

The nodeset command is an utility command provided with the
ClusterShell library which implements some features of the NodeSet
and RangeSet classes.
"""

import sys

from ClusterShell.CLI.Error import GENERIC_ERRORS, handle_generic_error
from ClusterShell.CLI.OptionParser import OptionParser
from ClusterShell.CLI.Utils import NodeSet  # safe import

from ClusterShell.NodeSet import RangeSet, grouplist, STD_GROUP_RESOLVER


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
        STD_GROUP_RESOLVER.set_verbosity(1)

    # Check for command presence
    cmdcount = int(options.count) + int(options.expand) + \
               int(options.fold) + int(options.list) + \
               int(options.regroup) + int(options.groupsources)
    if not cmdcount:
        parser.error("No command specified.")
    elif cmdcount > 1:
        parser.error("Multiple commands not allowed.")

    if options.rangeset:
        class_set = RangeSet

    if options.all or options.regroup:
        assert class_set == NodeSet, "-a/-r only supported in NodeSet mode"

    if options.groupsource and not options.quiet and \
       (class_set == RangeSet or options.groupsources):
        print >> sys.stderr, "WARNING: option group source \"%s\" ignored" \
                                % options.groupsource

    # The list command doesn't need any NodeSet, check for it first.
    if options.list:
        for group in grouplist(options.groupsource):
            if options.groupsource and not options.groupbase:
                print "@%s:%s" % (options.groupsource, group)
            else:
                print "@%s" % group
        return
    # Also, the groupsources command simply lists group sources.
    elif options.groupsources:
        if options.quiet:
            dispdefault = ""    # don't show (default) if quiet is set
        else:
            dispdefault = " (default)"
        for src in STD_GROUP_RESOLVER.sources():
            print "%s%s" % (src, dispdefault)
            dispdefault = ""
        return

    # We want -s <groupsource> to act as a substition of default groupsource
    # (ie. it's not necessary to prefix group names by this group source).
    if options.groupsource:
        STD_GROUP_RESOLVER.default_sourcename = options.groupsource

    # Instantiate RangeSet or NodeSet object
    xset = class_set()

    if options.all:
        # Include all nodes from external node groups support.
        xset.update(NodeSet.fromall()) # uses default_sourcename
        # FIXME: only union operation is supported when using -a due to
        # current options handling.
    elif not args:
        # No need to specify '-' to read stdin if no argument at all.
        process_stdin(xset, options.autostep)
    
    # Finish xset computing from args
    compute_nodeset(xset, args, options.autostep)

    # Interprate special characters (may raise SyntaxError)
    separator = eval('\'%s\'' % options.separator, {"__builtins__":None}, {})

    # Display result according to command choice
    if options.expand:
        xsubres = separator.join
    elif options.fold:
        xsubres = lambda x: x
    elif options.regroup:
        xsubres = lambda x: x.regroup(options.groupsource, \
                                      noprefix=options.groupbase)
    else:
        xsubres = len

    if not xset:
        print xsubres(xset)
    else:
        for xsubset in xset.split(options.maxsplit):
            print xsubres(xsubset)

def main():
    """main script function"""
    try:
        nodeset()
    except AssertionError, e:
        print >> sys.stderr, "ERROR:", e
        sys.exit(1)
    except IndexError:
        print >> sys.stderr, "ERROR: syntax error"
        sys.exit(1)
    except SyntaxError:
        print >> sys.stderr, "ERROR: invalid separator"
        sys.exit(1)
    except GENERIC_ERRORS, e:
        sys.exit(handle_generic_error(e))

    sys.exit(0)


if __name__ == '__main__':
    main()
