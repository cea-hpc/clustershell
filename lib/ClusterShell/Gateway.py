#!/usr/bin/env python
#
# Copyright (C) 2010-2016 CEA/DAM
# Copyright (C) 2010-2011 Henri Doreau <henri.doreau@cea.fr>
# Copyright (C) 2015-2016 Stephane Thiell <sthiell@stanford.edu>
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
ClusterShell agent launched on remote gateway nodes. This script reads messages
on stdin via the SSH connection, interprets them, takes decisions, and prints
out replies on stdout.
"""

import logging
import os
import sys
import traceback

from ClusterShell.Event import EventHandler
from ClusterShell.NodeSet import NodeSet
from ClusterShell.Task import task_self, _getshorthostname
from ClusterShell.Engine.Engine import EngineAbortException
from ClusterShell.Worker.fastsubprocess import set_nonblock_flag
from ClusterShell.Worker.Worker import StreamWorker, FANOUT_UNLIMITED
from ClusterShell.Worker.Tree import WorkerTree
from ClusterShell.Communication import Channel, ConfigurationMessage, \
    ControlMessage, ACKMessage, ErrorMessage, StartMessage, EndMessage, \
    StdOutMessage, StdErrMessage, RetcodeMessage, TimeoutMessage, \
    MessageProcessingError


def _gw_print_debug(task, line):
    """Default gateway task debug printing function"""
    logging.getLogger(__name__).debug(line)

def gateway_excepthook(exc_type, exc_value, tb):
    """
    Default excepthook for Gateway to redirect any unhandled exception
    to logger instead of stderr.
    """
    tbexc = traceback.format_exception(exc_type, exc_value, tb)
    logging.getLogger(__name__).error(''.join(tbexc))


class WorkerTreeResponder(EventHandler):
    """Gateway WorkerTree handler"""

    def __init__(self, task, gwchan, srcwkr):
        EventHandler.__init__(self)
        self.gwchan = gwchan    # gateway channel
        self.srcwkr = srcwkr    # id of distant parent WorkerTree
        self.worker = None      # local WorkerTree instance
        self.retcodes = {}      # self-managed retcodes
        self.logger = logging.getLogger(__name__)

        # Grooming initialization
        self.timer = None
        qdelay = task.info("grooming_delay")
        if qdelay > 1.0e-3:
            # Enable messages and rc grooming - enable msgtree (#181)
            task.set_default("stdout_msgtree", True)
            task.set_default("stderr_msgtree", True)
            # create auto-closing timer object for grooming
            self.timer = task.timer(qdelay, self, qdelay, autoclose=True)

        self.logger.debug("WorkerTreeResponder initialized grooming=%f", qdelay)

    def ev_start(self, worker):
        self.logger.debug("WorkerTreeResponder: ev_start")
        self.worker = worker

    def ev_timer(self, timer):
        """perform gateway traffic grooming"""
        if not self.worker:
            return
        logger = self.logger

        # check for grooming opportunities for stdout/stderr
        for msg_elem, nodes in self.worker.iter_errors():
            logger.debug("iter(stderr): %s: %d bytes", nodes,
                         len(msg_elem.message()))
            self.gwchan.send(StdErrMessage(nodes, msg_elem.message(),
                                           self.srcwkr))
        for msg_elem, nodes in self.worker.iter_buffers():
            logger.debug("iter(stdout): %s: %d bytes", nodes,
                         len(msg_elem.message()))
            self.gwchan.send(StdOutMessage(nodes, msg_elem.message(),
                                           self.srcwkr))
        # empty internal MsgTree buffers
        self.worker.flush_buffers()
        self.worker.flush_errors()

        # specifically manage retcodes to periodically return latest
        # retcodes to parent node, instead of doing it at ev_hup (no msg
        # aggregation) or at ev_close (no parent node live updates)
        for rc, nodes in self.retcodes.iteritems():
            self.logger.debug("iter(rc): %s: rc=%d", nodes, rc)
            self.gwchan.send(RetcodeMessage(nodes, rc, self.srcwkr))
        self.retcodes.clear()

    def ev_read(self, worker):
        """message received on stdout"""
        if self.timer is None:
            self.gwchan.send(StdOutMessage(worker.current_node,
                                           worker.current_msg,
                                           self.srcwkr))

    def ev_error(self, worker):
        """message received on stderr"""
        self.logger.debug("WorkerTreeResponder: ev_error %s %s",
                          worker.current_node,
                          worker.current_errmsg)
        if self.timer is None:
            self.gwchan.send(StdErrMessage(worker.current_node,
                                           worker.current_errmsg,
                                           self.srcwkr))

    def ev_timeout(self, worker):
        """Received timeout event: some nodes did timeout"""
        msg = TimeoutMessage(NodeSet._fromlist1(worker.iter_keys_timeout()),
                             self.srcwkr)
        self.gwchan.send(msg)

    def ev_hup(self, worker):
        """Received end of command from one node"""
        if self.timer is None:
            self.gwchan.send(RetcodeMessage(worker.current_node,
                                            worker.current_rc,
                                            self.srcwkr))
        else:
            # retcode grooming
            if worker.current_rc in self.retcodes:
                self.retcodes[worker.current_rc].add(worker.current_node)
            else:
                self.retcodes[worker.current_rc] = NodeSet(worker.current_node)

    def ev_close(self, worker):
        """End of CTL responder"""
        self.logger.debug("WorkerTreeResponder: ev_close")
        if self.timer is not None:
            # finalize grooming
            self.ev_timer(None)
            self.timer.invalidate()


class GatewayChannel(Channel):
    """high level logic for gateways"""
    def __init__(self, task):
        Channel.__init__(self, error_response=True)
        self.task = task
        self.nodename = None
        self.topology = None
        self.propagation = None
        self.logger = logging.getLogger(__name__)

    def start(self):
        """initialization"""
        # prepare communication
        self._init()
        self.logger.debug('ready to accept channel communication')

    def close(self):
        """close gw channel"""
        self.logger.debug('closing gateway channel')
        self._close()

    def recv(self, msg):
        """handle incoming message"""
        try:
            self.logger.debug('handling incoming message: %s', str(msg))
            if msg.type == EndMessage.ident:
                self.logger.debug('recv: got EndMessage')
                self._close()
            elif self.setup:
                self.recv_ctl(msg)
            elif self.opened:
                self.recv_cfg(msg)
            elif msg.type == StartMessage.ident:
                self.logger.debug('got start message %s', msg)
                self.opened = True
                self._open()
                self.logger.debug('channel started (version %s on remote end)',
                                  self._xml_reader.version)
            else:
                self.logger.error('unexpected message: %s', str(msg))
                raise MessageProcessingError('unexpected message: %s' % msg)
        except MessageProcessingError, ex:
            self.logger.error('on recv(): %s', str(ex))
            self.send(ErrorMessage(str(ex)))
            self._close()

        except EngineAbortException:
            # gateway task abort: don't handle like other exceptions
            raise

        except Exception, ex:
            self.logger.exception('on recv(): %s', str(ex))
            self.send(ErrorMessage(str(ex)))
            self._close()

    def recv_cfg(self, msg):
        """receive cfg/topology configuration"""
        if msg.type != ConfigurationMessage.ident:
            raise MessageProcessingError('unexpected message: %s' % msg)

        self.logger.debug('got channel configuration')

        # gw node name
        hostname = _getshorthostname()
        if not msg.gateway:
            self.nodename = hostname
            self.logger.warn('gw name not provided, using system hostname %s',
                             self.nodename)
        else:
            self.nodename = msg.gateway

        self.logger.debug('using gateway node name %s', self.nodename)
        if self.nodename.lower() != hostname.lower():
            self.logger.debug('gw name %s does not match system hostname %s',
                              self.nodename, hostname)

        # topology
        task_self().topology = self.topology = msg.data_decode()
        self.logger.debug('decoded propagation tree')
        self.logger.debug('\n%s', self.topology)
        self.setup = True
        self._ack(msg)

    def recv_ctl(self, msg):
        """receive control message with actions to perform"""
        if msg.type == ControlMessage.ident:
            self.logger.debug('GatewayChannel._state_ctl')
            if msg.action == 'shell':
                data = msg.data_decode()
                cmd = data['cmd']

                stderr = data['stderr']
                timeout = data['timeout']
                remote = data['remote']

                #self.propagation.invoke_gateway = data['invoke_gateway']
                self.logger.debug('decoded gw invoke (%s)',
                                  data['invoke_gateway'])

                taskinfo = data['taskinfo']
                self.logger.debug('assigning task infos (%s)', data['taskinfo'])

                task = task_self()
                task._info.update(taskinfo)
                task.set_info('print_debug', _gw_print_debug)

                if task.info('debug'):
                    self.logger.setLevel(logging.DEBUG)

                self.logger.debug('inherited fanout value=%d',
                                  task.info("fanout"))

                self.logger.debug('launching execution/enter gathering state')

                responder = WorkerTreeResponder(task, self, msg.srcid)

                self.propagation = WorkerTree(msg.target, responder, timeout,
                                              command=cmd,
                                              topology=self.topology,
                                              newroot=self.nodename,
                                              stderr=stderr,
                                              remote=remote)
                # FIXME ev_start-not-called workaround
                responder.worker = self.propagation
                self.propagation.upchannel = self
                task.schedule(self.propagation)
                self.logger.debug("WorkerTree scheduled")
                self._ack(msg)
            elif msg.action == 'write':
                data = msg.data_decode()
                self.logger.debug('GatewayChannel write: %d bytes',
                                  len(data['buf']))
                self.propagation.write(data['buf'])
                self._ack(msg)
            elif msg.action == 'eof':
                self.logger.debug('GatewayChannel eof')
                self.propagation.set_write_eof()
                self._ack(msg)
            else:
                self.logger.error('unexpected CTL action: %s', msg.action)
        else:
            self.logger.error('unexpected message: %s', str(msg))

    def _ack(self, msg):
        """acknowledge a received message"""
        self.send(ACKMessage(msg.msgid))

    def ev_close(self, worker):
        """Gateway (parent) channel is closing.

        We abort the whole gateway task to stop other running workers.
        This avoids any unwanted remaining processes on gateways.
        """
        self.logger.debug('GatewayChannel: ev_close')
        self.worker.task.abort()


def gateway_main():
    """ClusterShell gateway entry point"""
    host = _getshorthostname()
    # configure root logger
    logdir = os.path.expanduser(os.environ.get('CLUSTERSHELL_GW_LOG_DIR', \
                                               '/tmp'))
    loglevel = os.environ.get('CLUSTERSHELL_GW_LOG_LEVEL', 'INFO')
    logging.basicConfig(level=getattr(logging, loglevel.upper(), logging.INFO),
                        format='%(asctime)s %(name)s %(levelname)s %(message)s',
                        filename=os.path.join(logdir, "%s.gw.log" % host))
    logger = logging.getLogger(__name__)
    sys.excepthook = gateway_excepthook

    logger.debug('Starting gateway on %s', host)
    logger.debug("environ=%s", os.environ)


    set_nonblock_flag(sys.stdin.fileno())
    set_nonblock_flag(sys.stdout.fileno())
    set_nonblock_flag(sys.stderr.fileno())

    task = task_self()

    # Disable MsgTree buffering, it is enabled later when needed
    task.set_default("stdout_msgtree", False)
    task.set_default("stderr_msgtree", False)

    if sys.stdin.isatty():
        logger.critical('Gateway failure: sys.stdin.isatty() is True')
        sys.exit(1)

    gateway = GatewayChannel(task)
    worker = StreamWorker(handler=gateway)
    # Define worker._fanout to not rely on the engine's fanout, and use
    # the special value FANOUT_UNLIMITED to always allow registration
    worker._fanout = FANOUT_UNLIMITED
    worker.set_reader(gateway.SNAME_READER, sys.stdin)
    worker.set_writer(gateway.SNAME_WRITER, sys.stdout, retain=False)
    # must stay disabled for now (see #274)
    #worker.set_writer(gateway.SNAME_ERROR, sys.stderr, retain=False)
    task.schedule(worker)
    logger.debug('Starting task')
    try:
        task.resume()
        logger.debug('Task performed')
    except EngineAbortException, exc:
        logger.debug('EngineAbortException')
    except IOError, exc:
        logger.debug('Broken pipe (%s)', exc)
        raise
    except Exception, exc:
        logger.exception('Gateway failure: %s', exc)
    logger.debug('-------- The End --------')

if __name__ == '__main__':
    __name__ = 'ClusterShell.Gateway'
    # To enable gateway profiling:
    #import cProfile
    #cProfile.run('gateway_main()', '/tmp/gwprof')
    gateway_main()
