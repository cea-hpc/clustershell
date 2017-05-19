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

from __future__ import print_function

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
    except EngineNotSupportedError as exc:
        msgfmt = "%s: I/O events engine '%s' not supported on this host"
        print(msgfmt % (prog, exc.engineid), file=sys.stderr)
    except EngineClientError as exc:
        print("%s: EngineClientError: %s" % (prog, exc), file=sys.stderr)
    except NodeSetExternalError as exc:
        print("%s: External error:" % (prog, exc), file=sys.stderr)
    except (NodeSetParseError, RangeSetParseError) as exc:
        print("%s: Parse error:" % (prog, exc), file=sys.stderr)
    except GroupResolverIllegalCharError as exc:
        print('%s: Illegal group character: "%s"' % (prog, exc), file=sys.stderr)
    except GroupResolverSourceError as exc:
        print('%s: Unknown group source: "%s"' % (prog, exc), file=sys.stderr)
    except GroupSourceNoUpcall as exc:
        msgfmt = '%s: No %s upcall defined for group source "%s"'
        print(msgfmt % (prog, exc, exc.group_source.name), file=sys.stderr)
    except GroupSourceError as exc:
        print("%s: Group error:" % (prog, exc), file=sys.stderr)
    except TopologyError as exc:
        print("%s: TREE MODE:" % (prog, exc), file=sys.stderr)
    except (TypeError, WorkerError) as exc:
        print("%s: %s" % (prog, exc), file=sys.stderr)
    except IOError:
        # ignore broken pipe
        pass
    except KeyboardInterrupt as exc:
        return 128 + signal.SIGINT
    except:
        assert False, "wrong GENERIC_ERRORS"

    # Exit with error code 1 (generic failure)
    return 1
