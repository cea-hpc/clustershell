#!/usr/bin/env python
#
# Copyright CEA/DAM/DIF (2010-2015)
#  Contributor: Henri DOREAU <henri.doreau@cea.fr>
#  Contributor: Stephane THIELL <sthiell@stanford.edu>
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
from ClusterShell.Worker.Worker import StreamWorker
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
        # For messages grooming
        qdelay = task.info("grooming_delay")
        self.timer = task.timer(qdelay, self, qdelay, autoclose=True)
        self.logger = logging.getLogger(__name__)
        self.logger.debug("WorkerTreeResponder: initialized")
        # self-managed retcodes
        self.retcodes = {}

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
            logger.debug("iter(stderr): %s: %d bytes" % \
                (nodes, len(msg_elem.message())))
            self.gwchan.send(StdErrMessage(nodes, msg_elem.message(), \
                                           self.srcwkr))
        for msg_elem, nodes in self.worker.iter_buffers():
            logger.debug("iter(stdout): %s: %d bytes" % \
                (nodes, len(msg_elem.message())))
            self.gwchan.send(StdOutMessage(nodes, msg_elem.message(), \
                                           self.srcwkr))
        # empty internal MsgTree buffers
        self.worker.flush_buffers()
        self.worker.flush_errors()

        # specifically manage retcodes to periodically return latest
        # retcodes to parent node, instead of doing it at ev_hup (no msg
        # aggregation) or at ev_close (no parent node live updates)
        for rc, nodes in self.retcodes.iteritems():
            self.logger.debug("iter(rc): %s: rc=%d" % (nodes, rc))
            self.gwchan.send(RetcodeMessage(nodes, rc, self.srcwkr))
        self.retcodes.clear()

    def ev_error(self, worker):
        self.logger.debug("WorkerTreeResponder: ev_error %s" % \
            worker.current_errmsg)

    def ev_timeout(self, worker):
        """Received timeout event: some nodes did timeout"""
        self.gwchan.send(TimeoutMessage( \
            NodeSet._fromlist1(worker.iter_keys_timeout()), self.srcwkr))

    def ev_hup(self, worker):
        """Received end of command from one node"""
        if worker.current_rc in self.retcodes:
            self.retcodes[worker.current_rc].add(worker.current_node)
        else:
            self.retcodes[worker.current_rc] = NodeSet(worker.current_node)

    def ev_close(self, worker):
        """End of CTL responder"""
        self.logger.debug("WorkerTreeResponder: ev_close")
        # finalize grooming
        self.ev_timer(None)
        self.timer.invalidate()


class GatewayChannel(Channel):
    """high level logic for gateways"""
    def __init__(self, task):
        """
        """
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
        self.logger.debug('\n%s' % self.topology)
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
                self.logger.debug('GatewayChannel write: %d bytes', \
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
    logger.debug("environ=%s" % os.environ)


    set_nonblock_flag(sys.stdin.fileno())
    set_nonblock_flag(sys.stdout.fileno())
    set_nonblock_flag(sys.stderr.fileno())

    task = task_self()

    # Pre-enable MsgTree buffering on gateway (FIXME)
    task.set_default("stdout_msgtree", True)
    task.set_default("stderr_msgtree", True)

    if sys.stdin.isatty():
        logger.critical('Gateway failure: sys.stdin.isatty() is True')
        sys.exit(1)

    gateway = GatewayChannel(task)
    worker = StreamWorker(handler=gateway)
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
        logger.debug('Broken pipe (%s)' % exc)
        raise
    except Exception, exc:
        logger.exception('Gateway failure: %s' % exc)
    logger.debug('-------- The End --------')

if __name__ == '__main__':
    __name__ = 'ClusterShell.Gateway'
    # To enable gateway profiling:
    #import cProfile
    #cProfile.run('gateway_main()', '/tmp/gwprof')
    gateway_main()
