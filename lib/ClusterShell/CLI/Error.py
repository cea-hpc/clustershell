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
CLI error handling helper functions
"""

import signal
import sys


from ClusterShell.NodeUtils import GroupResolverConfigError
from ClusterShell.NodeUtils import GroupResolverSourceError
from ClusterShell.NodeUtils import GroupSourceException
from ClusterShell.NodeUtils import GroupSourceNoUpcall
try:
    from ClusterShell.NodeSet import NodeSetExternalError, NodeSetParseError
    from ClusterShell.NodeSet import RangeSetParseError
except GroupResolverConfigError, e:
    print >> sys.stderr, \
        "ERROR: ClusterShell Groups configuration error:\n\t%s" % e
    sys.exit(1)


GENERIC_ERRORS = (NodeSetExternalError,
                  NodeSetParseError,
                  RangeSetParseError,
                  GroupResolverSourceError,
                  GroupSourceNoUpcall,
                  GroupSourceException,
                  IOError,
                  KeyboardInterrupt)

def handle_generic_error(excobj, prog=sys.argv[0]):
    try:
        raise excobj
    except NodeSetExternalError, e:
        print >> sys.stderr, "%s: External error:" % prog, e
    except (NodeSetParseError, RangeSetParseError), e:
        print >> sys.stderr, "%s: Parse error:" % prog, e
    except GroupResolverSourceError, e:
        print >> sys.stderr, "%s: Unknown group source: \"%s\"" % (prog, e)
    except GroupSourceNoUpcall, e:
        print >> sys.stderr, "%s: No %s upcall defined for group " \
            "source \"%s\"" % (prog, e, e.group_source.name)
    except GroupSourceException, e:
        print >> sys.stderr, "%s: Other group error:" % prog, e
    except IOError:
        # ignore broken pipe
        pass
    except KeyboardInterrupt, e:
        return 128 + signal.SIGINT
    except: assert False, "wrong GENERIC_ERRORS"

    # Exit with error code 1 (generic failure)
    return 1
        
