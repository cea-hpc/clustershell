#!/usr/bin/env python
#
# Copyright CEA/DAM/DIF (2010)
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
clubak formats clush/dsh/pdsh output for humans.

For help, type:
    $ clubak --help
"""

from itertools import imap
import optparse
import signal
import sys

sys.path.insert(0, '../lib')

from ClusterShell.MsgTree import MsgTree
from ClusterShell.NodeSet import NodeSet, NodeSetParseError
from ClusterShell import __version__

def print_buffer(header, content):
    """Display a dshbak-like header block and content."""
    sep = "-" * 15
    sys.stdout.write("%s\n%s\n%s\n%s\n" % (sep, header, sep, content))

def print_lines(header, msg):
    """Display a MsgTree buffer by line with prefixed header."""
    for line in msg:
        sys.stdout.write("%s: %s\n" % (header, line))

def nodeset_cmp(ns1, ns2):
    """Compare 2 nodesets by their length (we want larger nodeset
    first) and then by first node."""
    len_cmp = cmp(len(ns2), len(ns1))
    if not len_cmp:
        smaller = NodeSet.fromlist([ns1[0], ns2[0]])[0]
        if smaller == ns1[0]:
            return -1
        else:
            return 1
    return len_cmp

def display(tree, line_mode, gather):
    """Display results"""
    try:
        if gather:
            # lambda to create a NodeSet from keys list returned by walk()
            ns_getter = lambda x: NodeSet.fromlist(x[1])

            for nodeset in sorted(imap(ns_getter, tree.walk()),
                                  cmp=nodeset_cmp):
                if line_mode:
                    print_lines(nodeset, tree[nodeset[0]])
                else:
                    print_buffer(NodeSet.fromlist(nodeset), tree[nodeset[0]])
        else:
            # automagically sorted by NodeSet
            nodes = NodeSet.fromlist(tree.keys())

            if line_mode:
                for node in nodes:
                    print_lines(node, tree[node])
            else:
                for node in nodes:
                    print_buffer(node, tree[node])
    finally:
        sys.stdout.flush()

def clubak():
    """Main clubak script function"""
    #
    # Argument management
    #
    usage = "%prog [-bcdL]"
    parser = optparse.OptionParser(usage, version="%%prog %s" % __version__)

    # Set parsing to stop on the first non-option
    parser.disable_interspersed_args()

    parser.add_option("-b", "-c", action="store_true", dest="gather",
                      help="gather nodes with same output (-c is provided for " \
                           "dshbak compatibility)")
    parser.add_option("-d", "--debug", action="store_true", dest="debug",
                      help="output more messages for debugging purpose")
    parser.add_option("-L", action="store_true", dest="line_mode",
                      help="disable header block and order output by nodes")
    options = parser.parse_args()[0]

    # Create new message tree
    tree = MsgTree()

    # Feed the tree from standard input lines
    for line in sys.stdin:
        tree.add(*tuple(line.rstrip('\r\n').split(': ', 1)))

    # Display results
    if options.debug:
        print >> sys.stderr, "clubak: line_mode=%s gather=%s tree_depth=%d" % \
            (bool(options.line_mode), bool(options.gather), tree._depth())
    display(tree, options.line_mode, options.gather)


if __name__ == '__main__':
    try:
        clubak()
        sys.exit(0)
    except NodeSetParseError, e:
        print >> sys.stderr, "clubak: parse error:", e
        sys.exit(1)
    except IOError:
        sys.exit(1)     # exit with error on broken pipe
    except KeyboardInterrupt, e:
        sys.exit(128 + signal.SIGINT)

