#!/usr/bin/env python
#
# Copyright CEA/DAM/DIF (2010, 2011, 2012)
#  Contributor: Henri DOREAU <henri.doreau@gmail.com>
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
ClusterShell agent launched on remote gateway nodes. This script reads messages
on stdin via the SSH connexion, interprets them, takes decisions, and prints out
replies on stdout.
"""

import os
import sys
import fcntl
import time

import logging

from ClusterShell.Event import EventHandler
from ClusterShell.Task import task_self, _getshorthostname
from ClusterShell.Engine.Engine import EngineAbortException
from ClusterShell.Worker.Worker import WorkerSimple
from ClusterShell.Worker.Tree import WorkerTree
from ClusterShell.Communication import Channel, ConfigurationMessage, \
    ControlMessage, ACKMessage, ErrorMessage, EndMessage, StdOutMessage, \
    StdErrMessage, RetcodeMessage


class WorkerTreeResponder(EventHandler):
    """Gateway WorkerTree handler"""
    def __init__(self, task, gwchan, srcwkr):
        EventHandler.__init__(self)
        self.gwchan = gwchan    # gateway channel
        self.srcwkr = srcwkr    # id of distant parent WorkerTree
        self.worker = None      # local WorkerTree instance
        # For messages grooming
        qdelay = task.info("grooming_delay")
        self.timer = task.timer(qdelay, self, qdelay, autoclose=True)

    def ev_start(self, worker):
        logging.debug("WorkerTreeResponder: ev_start")
        self.worker = worker

    def ev_timer(self, timer):
        """perform gateway traffic grooming"""
        if not self.worker:
            return
        # check grooming opportunities
        for buf, nodes in self.worker.iter_errors():
            logging.debug("iter(stderr): %s: %d bytes" % (nodes, len(buf)))
            self.gwchan.send(StdErrMessage(nodes, buf, self.srcwkr))
        for buf, nodes in self.worker.iter_buffers():
            logging.debug("iter(stdout): %s: %d bytes" % (nodes, len(buf)))
            self.gwchan.send(StdOutMessage(nodes, buf, self.srcwkr))
        self.worker.flush_buffers()

    def ev_error(self, worker):
        logging.debug("WorkerTreeResponder: ev_error %s" % worker.current_errmsg)

    def ev_close(self, worker):
        logging.debug("WorkerTreeResponder: ev_close")
        # finalize grooming
        self.ev_timer(None)
        # send retcodes
        for rc, nodes in self.worker.iter_retcodes():
            logging.debug("iter(rc): %s: rc=%d" % (nodes, rc))
            self.gwchan.send(RetcodeMessage(nodes, rc, self.srcwkr))
        self.timer.invalidate()
        # clean channel closing
        ####self.gwchan.close()


class GatewayChannel(Channel):
    """high level logic for gateways"""
    def __init__(self, task, hostname):
        """
        """
        Channel.__init__(self)
        self.task = task
        self.hostname = hostname
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
        logging.debug('entering config state')

    def close(self):
        """close gw channel"""
        logging.debug('closing gw channel')
        self._close()
        self.current_state = None

    def recv(self, msg):
        """handle incoming message"""
        try:
            logging.debug('handling incoming message: %s' % str(msg))
            if msg.ident == EndMessage.ident:
                logging.debug('recv: got EndMessage')
                self.worker.abort()
            else:
                self.current_state(msg)
        except Exception, ex:
            logging.exception('on recv(): %s' % str(ex))
            self.send(ErrorMessage(str(ex)))

    def _state_cfg(self, msg):
        """receive topology configuration"""
        if msg.type == ConfigurationMessage.ident:
            self.topology = msg.data_decode()
            logging.debug('decoded propagation tree')
            logging.debug('%s' % str(self.topology))
            self._ack(msg)
            self.current_state = self.states['CTL']
            logging.debug('entering control state')
        else:
            logging.error('unexpected message: %s' % str(msg))

    def _state_ctl(self, msg):
        """receive control message with actions to perform"""
        if msg.type == ControlMessage.ident:
            logging.debug('GatewayChannel._state_ctl')
            self._ack(msg)
            if msg.action == 'shell':
                data = msg.data_decode()
                cmd = data['cmd']
                stderr = data['stderr']

                #self.propagation.invoke_gateway = data['invoke_gateway']
                logging.debug('decoded gw invoke (%s)' % data['invoke_gateway'])

                taskinfo = data['taskinfo']
                task_self()._info = taskinfo
                task_self()._engine.info = taskinfo

                logging.debug('assigning task infos (%s)' % \
                    str(data['taskinfo']))

                logging.debug('inherited fanout value=%d' % task_self().info("fanout"))

                #self.current_state = self.states['GTR']
                logging.debug('launching execution/entering gathering state')

                responder = WorkerTreeResponder(task_self(), self, msg.srcid)

                self.propagation = WorkerTree(msg.target, responder, 0,
                                              command=cmd,
                                              topology=self.topology,
                                              newroot=self.hostname,
                                              stderr=stderr)
                self.propagation.upchannel = self
                task.schedule(self.propagation)
                logging.debug("WorkerTree scheduled")
        else:
            logging.error('unexpected message: %s' % str(msg))

    def _state_gtr(self, msg):
        """gather outputs"""
        # TODO!!
        logging.debug('GatewayChannel._state_gtr')
        logging.debug('incoming output msg: %s' % str(msg))
        pass

    def _ack(self, msg):
        """acknowledge a received message"""
        self.send(ACKMessage(msg.msgid))


if __name__ == '__main__':
    host = _getshorthostname()
    ######################## DEBUG ############################
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s %(levelname)s %(message)s',
        filename=os.path.expanduser("~/dbg/%s.gw" % host), # FIXME DEBUG
        filemode='a+'
    )
    logging.debug('Starting gateway')
    ###########################################################
    flags = fcntl.fcntl(sys.stdin.fileno(), fcntl.F_GETFL)
    fcntl.fcntl(sys.stdin.fileno(), fcntl.F_SETFL, flags | os.O_NONBLOCK)
    flags = fcntl.fcntl(sys.stdout.fileno(), fcntl.F_GETFL)
    fcntl.fcntl(sys.stdout.fileno(), fcntl.F_SETFL, flags | os.O_NONBLOCK)
    flags = fcntl.fcntl(sys.stderr.fileno(), fcntl.F_GETFL)
    fcntl.fcntl(sys.stderr.fileno(), fcntl.F_SETFL, flags | os.O_NONBLOCK)

    task = task_self()
    # Enable MsgTree buffering on gateways FIXME: unless no grooming set?
    task.set_default("stdout_msgtree", True)
    task.set_default("stderr_msgtree", True)

    chan = GatewayChannel(task, host)
    if sys.stdin.isatty():
        logging.debug('sys.stdin.isatty OK')
        worker = WorkerSimple(sys.stdout, sys.stdin, None, None, handler=chan)
    else:
        logging.debug('!sys.stdin.isatty')
        worker = WorkerSimple(sys.stdin, sys.stdout, sys.stderr, None, handler=chan)
    task.schedule(worker)
    logging.debug('Starting task')
    try:
        task.resume()
        logging.debug('Task performed')
    except EngineAbortException, e:
        pass
    except IOError, e:
        logging.debug('Broken pipe (%s)' % e)
        raise
    except Exception, e:
        logging.exception('Gateway failure: %s' % e)
