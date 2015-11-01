#!/usr/bin/env python
#
# Copyright CEA/DAM/DIF (2010-2015)
#  Contributor: Stephane THIELL <sthiell@stanford.edu>
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
