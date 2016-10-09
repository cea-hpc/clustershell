#
# Copyright (C) 2009-2016 CEA/DAM
# Copyright (C) 2016 Stephane Thiell <sthiell@stanford.edu>
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
Engine Factory to select the best working event engine for the current
version of Python and Operating System.
"""

import logging

from ClusterShell.Engine.Engine import EngineNotSupportedError

# Available event engines
from ClusterShell.Engine.EPoll import EngineEPoll
from ClusterShell.Engine.Poll import EnginePoll
from ClusterShell.Engine.Select import EngineSelect


class PreferredEngine(object):
    """
    Preferred Engine selection metaclass (DP Abstract Factory).
    """

    engines = {EngineEPoll.identifier: EngineEPoll,
               EnginePoll.identifier: EnginePoll,
               EngineSelect.identifier: EngineSelect}

    def __new__(cls, hint, info):
        """
        Create a new preferred Engine.
        """
        if not hint or hint == 'auto':
            # in order or preference
            for engine_class in [EngineEPoll, EnginePoll, EngineSelect]:
                try:
                    return engine_class(info)
                except EngineNotSupportedError:
                    pass
            raise RuntimeError("FATAL: No supported ClusterShell.Engine found")
        else:
            # User overriding engine selection
            engines = cls.engines.copy()
            try:
                tryengine = engines.pop(hint)
                while True:
                    try:
                        return tryengine(info)
                    except EngineNotSupportedError:
                        if len(engines) == 0:
                            raise
                    tryengine = engines.popitem()[1]
            except KeyError:
                msg = "Invalid engine identifier: %s" % hint
                logging.getLogger(__name__).error(msg)
                raise
