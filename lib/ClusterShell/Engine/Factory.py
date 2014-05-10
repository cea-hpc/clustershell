#
# Copyright CEA/DAM/DIF (2009-2014)
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
Engine Factory to select the best working event engine for the current
version of Python and Operating System.
"""

import sys

from ClusterShell.Engine.Engine import EngineNotSupportedError

# Available event engines
from ClusterShell.Engine.EPoll import EngineEPoll
from ClusterShell.Engine.Poll import EnginePoll
from ClusterShell.Engine.Select import EngineSelect

class PreferredEngine(object):
    """
    Preferred Engine selection metaclass (DP Abstract Factory).
    """

    engines = { EngineEPoll.identifier: EngineEPoll,
                EnginePoll.identifier: EnginePoll,
                EngineSelect.identifier: EngineSelect }

    def __new__(cls, hint, info):
        """
        Create a new preferred Engine.
        """
        if not hint or hint == 'auto':
            # in order or preference
            for engine_class in [ EngineEPoll, EnginePoll, EngineSelect ]:
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
            except KeyError, exc:
                print >> sys.stderr, "Invalid engine identifier", exc
                raise
