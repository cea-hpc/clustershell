#
# Copyright (C) 2007-2015 CEA/DAM
# Copyright (C) 2015-2017 Stephane Thiell <sthiell@stanford.edu>
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
ClusterShell Event handling.

This module contains the base class **EventHandler** which defines a simple
interface through methods to handle events coming from ClusterShell I/O Engine
clients. Events are generated by Worker, EngineTimer or EnginePort objects.
"""


import warnings


class EventHandler(object):
    """ClusterShell EventHandler interface.

    Derived class should implement the following methods to listen for Worker,
    EngineTimer or EnginePort chosen events.
    """

    def ev_start(self, worker):
        """
        Called to indicate that a worker has just started.

        :param worker: :class:`.Worker` object
        """

    def ev_pickup(self, worker, node):
        """
        Called to indicate that a worker command for a specific node (or key)
        has just started. Called for each node.

        :param worker: :class:`.Worker` object
        :param node: node (or key)
        """

    def ev_read(self, worker, node, sname, msg):
        """
        Called to indicate that a worker has data to read from a specific
        node (or key).

        :param worker: :class:`.Worker` object
        :param node: node (or key)
        :param sname: stream name
        :param msg: message
        """

    def ev_written(self, worker, node, sname, size):
        """
        Called to indicate that some writing has been done by the worker to a
        node on a given stream. This event is only generated when ``write()``
        is previously called on the worker.

        This handler may be called very often depending on the number of target
        nodes, the amount of data to write and the block size used by the
        worker.

        Note: up to ClusterShell 1.6, this event handler wasn't implemented. To
        properly handle ev_written after 1.6, the method signature must consist
        of the following parameters:

        :param worker: :class:`.Worker` object
        :param node: node (or) key
        :param sname: stream name
        :param size: amount of bytes that has just been written to node/stream
            associated with this event
        """

    def ev_hup(self, worker, node, rc):
        """
        Called to indicate that a worker command for a specific node has
        just finished. Called for each node with command-based workers,
        where return codes actually make sense).

        :param worker: :class:`.Worker` object
        :param node: node (or key)
        :param rc: command return code
        """

    def ev_close(self, worker, did_timeout):
        """
        Called to indicate that a worker has just finished.

        :param worker: :class:`.Worker` object
        :param did_timeout: boolean set to True if the worker has timed out
        """

    def ev_msg(self, port, msg):
        """
        Called to indicate that a message has been received on an EnginePort.

        Used to deliver messages reliably between tasks.

        :param port: EnginePort object on which a message has been received
        :param msg: the message object received
        """

    def ev_timer(self, timer):
        """
        Called to indicate that a timer is firing.

        :param timer: :class:`.EngineTimer` object that is firing
        """

    def _ev_routing(self, worker, arg):
        """
        Routing event (private). Called to indicate that a (meta)worker has just
        updated one of its route path. You can safely ignore this event.
        """


def _warn_signature(event_name):
    """used to warn for deprecated event method signature"""
    warnings.warn("%s() signature changed: see pydoc ClusterShell.Event"
                  % event_name, DeprecationWarning)
