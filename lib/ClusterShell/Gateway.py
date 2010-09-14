#!/usr/bin/env python
#
# Copyright CEA/DAM/DIF (2007, 2008, 2009, 2010)
#  Contributor: Henri DOREAU <henri.doreau@gmail.com>
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
ClusterShell agent launched on remote gateway nodes. This script reads messages
on stdin via the SSH connexion, interprets them, takes decisions, and prints out
replies on stdout.
"""

import os
import sys
import fcntl
import socket
import traceback


from ClusterShell.Task import task_self
from ClusterShell.Worker.Worker import WorkerSimple
from ClusterShell.Propagation import PropagationTree
from ClusterShell.Communication import Channel, ConfigurationMessage
from ClusterShell.Communication import ControlMessage, ACKMessage, ErrorMessage


class GatewayChannel(Channel):
    """high level logic for gateways"""
    def __init__(self):
        """
        """
        Channel.__init__(self)
        self.hostname = socket.gethostname().split('.')[0]
        self.topology = None
        self.propagation = None

        self.current_state = None
        self.states = {
            'CFG': self._state_cfg,
            'CTL': self._state_ctl,
            'GTR': self._state_gtr,
        }

    def start(self):
        """initialization"""
        self._open()
        # prepare to receive topology configuration
        self.current_state = self.states['CFG']

    def recv(self, msg):
        """handle incoming message"""
        try:
            self.current_state(msg)
        except Exception, ex:
            self.send(ErrorMessage(str(ex) + traceback.format_exc()))

    def _state_cfg(self, msg):
        """receive topology configuration"""
        if msg.type == ConfigurationMessage.ident:
            self.topology = msg.data_decode()
            self.propagation = PropagationTree(self.topology, self.hostname)
            self._ack(msg)
            self.current_state = self.states['CTL']

    def _state_ctl(self, msg):
        """receive control message with actions to perform"""
        if msg.type == ControlMessage.ident:
            self._ack(msg)
            if msg.action == 'shell':
                data = msg.data_decode()
                cmd = data['cmd']
                self.current_state = self.states['GTR']
                self.propagation.execute(cmd, msg.target)

    def _state_gtr(self, msg):
        """gather outputs"""
        # TODO!!
        pass

    def _ack(self, msg):
        """acknowledge a received message"""
        self.send(ACKMessage(msg.msgid))

if __name__ == '__main__':
    fcntl.fcntl(sys.stdin.fileno(), fcntl.F_SETFL, os.O_NONBLOCK)
    task = task_self()
    chan = GatewayChannel()
    worker = WorkerSimple(sys.stdin, sys.stdout, sys.stderr, None, handler=chan)
    #task.set_info("debug", True)
    task.schedule(worker)
    task.resume()

