#!/usr/bin/env python
#
# Copyright CEA/DAM/DIF (2010, 2011, 2012)
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
CLI error handling helper functions
"""

import os.path
import signal
import sys

from ClusterShell.Engine.Engine import EngineNotSupportedError
from ClusterShell.CLI.Utils import GroupResolverConfigError  # dummy but safe
from ClusterShell.NodeUtils import GroupResolverIllegalCharError
from ClusterShell.NodeUtils import GroupResolverSourceError
from ClusterShell.NodeUtils import GroupSourceError
from ClusterShell.NodeUtils import GroupSourceNoUpcall
from ClusterShell.NodeSet import NodeSetExternalError, NodeSetParseError
from ClusterShell.NodeSet import RangeSetParseError
from ClusterShell.Topology import TopologyError
from ClusterShell.Worker.Worker import WorkerError

GENERIC_ERRORS = (EngineNotSupportedError,
                  NodeSetExternalError,
                  NodeSetParseError,
                  RangeSetParseError,
                  GroupResolverIllegalCharError,
                  GroupResolverSourceError,
                  GroupSourceError,
                  GroupSourceNoUpcall,
                  TopologyError,
                  TypeError,
                  IOError,
                  KeyboardInterrupt,
                  WorkerError)

def handle_generic_error(excobj, prog=os.path.basename(sys.argv[0])):
    """handle error given `excobj' generic script exception"""
    try:
        raise excobj
    except EngineNotSupportedError, exc:
        print >> sys.stderr, "%s: I/O events engine '%s' not supported on " \
            "this host" % (prog, exc.engineid)
    except NodeSetExternalError, exc:
        print >> sys.stderr, "%s: External error:" % prog, exc
    except (NodeSetParseError, RangeSetParseError), exc:
        print >> sys.stderr, "%s: Parse error:" % prog, exc
    except GroupResolverIllegalCharError, exc:
        print >> sys.stderr, "%s: Illegal group character: \"%s\"" % (prog, exc)
    except GroupResolverSourceError, exc:
        print >> sys.stderr, "%s: Unknown group source: \"%s\"" % (prog, exc)
    except GroupSourceNoUpcall, exc:
        print >> sys.stderr, "%s: No %s upcall defined for group " \
            "source \"%s\"" % (prog, exc, exc.group_source.name)
    except GroupSourceError, exc:
        print >> sys.stderr, "%s: Group error:" % prog, exc
    except TopologyError, exc:
        print >> sys.stderr, "%s: TREE MODE:" % prog, exc
    except (TypeError, WorkerError), exc:
        print >> sys.stderr, "%s: %s" % (prog, exc)
    except IOError:
        # ignore broken pipe
        pass
    except KeyboardInterrupt, exc:
        return 128 + signal.SIGINT
    except:
        assert False, "wrong GENERIC_ERRORS"

    # Exit with error code 1 (generic failure)
    return 1
