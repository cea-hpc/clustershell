#!/usr/bin/env python
#
# Copyright (C) 2010-2015 CEA/DAM
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
CLI utility functions
"""

import sys

# CLI modules might safely import the NodeSet class from here.
from ClusterShell.NodeUtils import GroupResolverConfigError
try:
    from ClusterShell.NodeSet import NodeSet
except GroupResolverConfigError, exc:
    print >> sys.stderr, \
        "ERROR: ClusterShell node groups configuration error:\n\t%s" % exc
    sys.exit(1)

(KIBI, MEBI, GIBI, TEBI) = (1024.0, 1024.0 ** 2, 1024.0 ** 3, 1024.0 ** 4)

def human_bi_bytes_unit(value):
    """
    Format numerical `value` to display it using human readable unit with
    binary prefix like (KiB, MiB, GiB, ...).
    """
    if value >= TEBI:
        fmt = "%.2f TiB" % (value / TEBI)
    elif value >= GIBI:
        fmt = "%.2f GiB" % (value / GIBI)
    elif value >= MEBI:
        fmt = "%.2f MiB" % (value / MEBI)
    elif value >= KIBI:
        fmt = "%.2f KiB" % (value / KIBI)
    else:
        fmt = "%d B" % value
    return fmt

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

def bufnodeset_cmp(bn1, bn2):
    """Convenience function to compare 2 (buf, nodeset) tuples by their
    nodeset length (we want larger nodeset first) and then by first
    node."""
    # Extract nodesets and call nodeset_cmp
    return nodeset_cmp(bn1[1], bn2[1])
