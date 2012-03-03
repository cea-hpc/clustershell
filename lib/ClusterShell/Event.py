#
# Copyright CEA/DAM/DIF (2007, 2008, 2009, 2010, 2011, 2012)
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
Event handler support

EventHandler's derived classes may implement ev_* methods to listen on
worker's events.
"""

class EventHandler(object):
    """
    Base class EventHandler.
    """
    def ev_start(self, worker):
        """
        Called to indicate that a worker has just started.
        """

    def ev_read(self, worker):
        """
        Called to indicate that a worker has data to read.
        """

    def ev_error(self, worker):
        """
        Called to indicate that a worker has error to read (on stderr).
        """

    def ev_written(self, worker):
        """
        Called to indicate that writing has been done.
        """

    def ev_hup(self, worker):
        """
        Called to indicate that a worker's connection has been closed.
        """

    def ev_timeout(self, worker):
        """
        Called to indicate that a worker has timed out (worker timeout only).
        """

    def ev_close(self, worker):
        """
        Called to indicate that a worker has just finished (it may already
        have failed on timeout).
        """

    def ev_msg(self, port, msg):
        """
        Handle port message.

        @param port: The port object on which a message is available.
        """

    def ev_timer(self, timer):
        """
        Handle firing timer.

        @param timer: The timer that is firing. 
        """

    def _ev_routing(self, worker, arg):
        """
        Routing event (private). Called to indicate that a (meta)worker has just
        updated one of its route path. You can safely ignore this event.
        """

