#
# Copyright (C) 2010-2015 CEA/DAM
# Copyright (C) 2018 Stephane Thiell <sthiell@stanford.edu>
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

def nodeset_cmpkey(nodeset):
    """We want larger nodeset first, then sorted by first node index."""
    return -len(nodeset), nodeset[0]

def bufnodeset_cmpkey(buf):
    """Helper to get nodeset compare key from a buffer (buf, nodeset)"""
    return nodeset_cmpkey(buf[1])
