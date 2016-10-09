#!/usr/bin/env python
#
# Copyright (C) 2010-2012 CEA/DAM
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
from ClusterShell.Worker.EngineClient import EngineClientError
from ClusterShell.Worker.Worker import WorkerError

GENERIC_ERRORS = (EngineNotSupportedError,
                  EngineClientError,
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
        msgfmt = "%s: I/O events engine '%s' not supported on this host"
        print >> sys.stderr, msgfmt % (prog, exc.engineid)
    except EngineClientError, exc:
        print >> sys.stderr, "%s: EngineClientError: %s" % (prog, exc)
    except NodeSetExternalError, exc:
        print >> sys.stderr, "%s: External error:" % prog, exc
    except (NodeSetParseError, RangeSetParseError), exc:
        print >> sys.stderr, "%s: Parse error:" % prog, exc
    except GroupResolverIllegalCharError, exc:
        print >> sys.stderr, '%s: Illegal group character: "%s"' % (prog, exc)
    except GroupResolverSourceError, exc:
        print >> sys.stderr, '%s: Unknown group source: "%s"' % (prog, exc)
    except GroupSourceNoUpcall, exc:
        msgfmt = '%s: No %s upcall defined for group source "%s"'
        print >> sys.stderr, msgfmt % (prog, exc, exc.group_source.name)
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
