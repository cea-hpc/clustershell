#!/usr/bin/env python
#
# Copyright CEA/DAM/DIF (2010, 2011)
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
ClusterShell Propagation module. Use the topology tree to send commands
through gateways and gather results.
"""

import logging
import socket

from ClusterShell.Event import EventHandler
from ClusterShell.NodeSet import NodeSet
from ClusterShell.Task import task_self
from ClusterShell.Communication import Channel
from ClusterShell.Communication import ControlMessage, StdOutMessage
from ClusterShell.Communication import StdErrMessage, RetcodeMessage
from ClusterShell.Communication import EndMessage
from ClusterShell.Communication import ConfigurationMessage

from ClusterShell.Topology import TopologyParser


class RouteResolvingError(Exception):
    """error raised on invalid conditions during routing operations"""

class PropagationTreeRouter(object):
    """performs routes resolving operations within a propagation tree.
    This object provides a next_hop method, that will look for the best
    directly connected node to use to forward a message to a remote
    node.

    Upon instanciation, the router will parse the topology tree to
    generate its routing table.
    """
    def __init__(self, root, topology):
        """
        """
        self.topology = topology
        self.fanout = task_self().info('fanout')
        self.nodes_fanin = {}
        self.table = None
        self.root = root

        self.table_generate(root, topology)
        self._unreachable_hosts = NodeSet()

    def table_generate(self, root, topology):
        """The router relies on a routing table. The keys are the
        destination nodes and the values are the next hop gateways to
        use to reach these nodes.
        """
        self.table = {}
        root_group = None

        for entry in topology.groups:
            if root in entry.nodeset:
                root_group = entry
                break

        if root_group is None:
            raise RouteResolvingError('Invalid admin node: %s' % root)

        for group in root_group.children():
            self.table[group.nodeset] = NodeSet()
            stack = [group]
            while len(stack) > 0:
                curr = stack.pop()
                self.table[group.nodeset].add(curr.children_ns())
                stack += curr.children()

        # reverse table (it was crafted backward)
        self.table = dict((v, k) for k, v in self.table.iteritems())

    def dispatch(self, dst):
        """dispatch nodes from a target nodeset to the directly
        connected gateways.

        The method acts as an iterator, returning a gateway and the
        associated hosts. It should provide a rather good load balancing
        between the gateways.
        """
        # Check for directly connected targets
        res = [tmp & dst for tmp in self.table.values()]
        nexthop = NodeSet()
        [nexthop.add(x) for x in res]
        if len(nexthop) > 0:
            yield nexthop, nexthop

        # Check for remote targets, that require a gateway to be reached
        for network in self.table.iterkeys():
            dst_inter = network & dst
            for host in [NodeSet(h) for h in dst_inter]:
                dst.difference_update(host)
                yield self.next_hop(host), host

    def next_hop(self, dst):
        """perform the next hop resolution. If several hops are
        available, then, the one with the least number of current jobs
        will be returned
        """
        if dst in self._unreachable_hosts:
            raise RouteResolvingError(
                'Invalid destination: %s, host is unreachable' % dst)

        # can't resolve if source == destination
        if self.root == dst:
            raise RouteResolvingError(
                'Invalid resolution request: %s -> %s' % (self.root, dst))

        ## ------------------
        # the routing table is organized this way:
        # 
        #  NETWORK    | NEXT HOP
        # ------------+-----------
        # node[0-9]   | gateway0
        # node[10-19] | gateway[1-2]
        #            ...
        # ---------
        for network, nexthops in self.table.iteritems():
            # destination contained in current network
            if dst in network:
                res = self._best_next_hop(nexthops)
                if res is None:
                    raise RouteResolvingError('No route available to %s' % \
                        str(dst))
                self.nodes_fanin[res] += len(dst)
                return res
            # destination contained in current next hops (ie. directly
            # connected)
            if dst in nexthops:
                return dst

        raise RouteResolvingError(
            'No route from %s to host %s' % (self.root, dst))

    def mark_unreachable(self, dst):
        """mark node dst as unreachable and don't advertise routes
        through it anymore. The cache will be updated only when
        necessary to avoid performing expensive traversals.
        """
        # Simply mark dst as unreachable in a dedicated NodeSet. This
        # list will be consulted by the resolution method
        self._unreachable_hosts.add(dst)

    def _best_next_hop(self, candidates):
        """find out a good next hop gateway"""
        backup = None
        backup_connections = 1e400 # infinity

        candidates = candidates.difference(self._unreachable_hosts)

        for host in candidates:
            # the router tracks established connections in the
            # nodes_fanin table to avoid overloading a gateway
            connections = self.nodes_fanin.setdefault(host, 0)
            # FIXME
            #if connections < self.fanout:
            #    # currently, the first one is the best
            #    return host
            if backup_connections > connections:
                backup = host
                backup_connections = connections
        return backup


class EdgeHandler(EventHandler):
    """
    """
    def __init__(self, ptree):
        self.ptree = ptree

    def ev_read(self, worker):
        node, buf = worker.last_read()
        logging.debug('EdgeHandler ev_read %s: %s' % (node, buf))
        self.ptree.upchannel.send(StdOutMessage(node, buf))

    def ev_error(self, worker):
        node, buf = worker.last_error()
        logging.debug('EdgeHandler ev_error %s: %s' % (node, buf))
        self.ptree.upchannel.send(StdErrMessage(node, buf))

    def ev_hup(self, worker):
        node, rc = worker.last_retcode()
        logging.debug('EdgeHandler ev_hup %s: %d' % (node, rc))
        self.ptree.upchannel.send(RetcodeMessage(node, rc))

    def ev_close(self, worker):
        self.ptree.notify_close()


class PropagationEventHandler(object):
    def on_message(self, node, message):
        pass
    def on_errmessage(self, node, message):
        pass
    def on_retcode(self, node, retcode):
        pass


class PropagationTree(object):
    """This class represents the complete propagation tree and provides
    the ability to propagate tasks through it.
    """
    def __init__(self, topology, admin='', handler=None):
        """
        """
        # set topology tree
        if topology:
            self.topology = topology
        else:
            # when not specified, let the library instantiate a
            # topology by itself
            parser = TopologyParser()
            parser.load("/etc/clustershell/topology.conf")
            self.topology = parser.tree(socket.gethostname().split('.')[0]) # XXX need helper func

        # name of the administration node, at the root of the tree
        self.admin = admin or str(self.topology.root.nodeset)
        self.handler = handler

        # builtin router
        self.router = PropagationTreeRouter(self.admin, topology)
        # command to invoke remote communication endpoint
        import os
        #self.invoke_gateway = 'python -m CluserShell/Gateway'
        self.invoke_gateway = 'cd %s/../lib; python -m ClusterShell/Gateway -Bu' % os.getcwd()

        # worker reference counter (for remote execution or not)
        self.wrefcnt = 0
        self.upchannel = None
        self.edgehandler = EdgeHandler(self)

    def execute(self, cmd, nodes, fanout=None, timeout=10):
        """execute `cmd' on the nodeset specified at loading"""
        task = task_self()
        if fanout is None:
            fanout = self.router.fanout
        task.set_info('fanout', fanout)

        next_hops = self._distribute(fanout, NodeSet(nodes))
        for gw, target in next_hops.iteritems():
            if gw == target:
                task = task_self()
                logging.debug('task.shell cmd=%s nodes=%s timeout=%d' % (cmd, nodes, timeout))
                task.shell(cmd, nodes=target, timeout=timeout, handler=self.edgehandler)
                # increment worker ref counter
                self.wrefcnt += 1
            else:
                self._execute_remote(cmd, target, gw, timeout)

        if not task.running():
            logging.debug('task.resume() in execute')
            task.resume()

        return task

    def launch(self, cmd, nodes, task, timeout): 
        """launch `cmd' on the nodeset specified at loading"""
        next_hops = self._distribute(task.info('fanout'), NodeSet(nodes))
        for gw, target in next_hops.iteritems():
            if gw == target:
                logging.debug('launch task.shell cmd=%s nodes=%s timeout=%d' % (cmd, nodes, timeout))
                task.shell(cmd, nodes=target, timeout=timeout, handler=self.edgehandler)
                # increment worker ref counter
                self.wrefcnt += 1
            else:
                self._execute_remote(cmd, target, gw, timeout)


    def _distribute(self, fanout, dst_nodeset):
        """distribute target nodes between next hop gateways"""
        distribution = {}
        self.router.fanout = fanout

        for gw, dstset in self.router.dispatch(dst_nodeset):
            if distribution.has_key(gw):
                distribution[gw].add(dstset)
            else:
                distribution[gw] = dstset
        return distribution

    def _execute_remote(self, cmd, target, gateway, timeout):
        """run command against a remote node via a gateway"""
        task = task_self()

        # tunnelled message passing
        chan = PropagationChannel(cmd, target, self)
        logging.debug("_execute_remote gateway=%s" % gateway)

        # invoke remote gateway engine
        task.shell(self.invoke_gateway, nodes=gateway, handler=chan, \
            timeout=timeout)
        # increment worker ref counter
        self.wrefcnt += 1

    def next_hop(self, dst):
        """routing operation: resolve next hop gateway"""
        return self.router.next_hop(dst)

    def mark_unreachable(self, dst):
        """routing operation: mark an host as unreachable"""
        return self.router.mark_unreachable(dst)

    def notify_close(self):
        self.wrefcnt -= 1
        assert self.wrefcnt >= 0
        if self.wrefcnt == 0:
            if self.upchannel:
                self.upchannel.close()


class PropagationChannel(Channel):
    """Admin node propagation logic. Instances are able to handle
    incoming messages from a directly connected gateway, process them
    and reply.

    In order to take decisions, the instance acts as a finite states
    machine, whose current state evolves according to received data.

    -- INTERNALS --
    Instance can be in one of the 4 different states:
      - init (implicit)
        This is the very first state. The instance enters the init
        state at start() method, and will then send the configuration
        to the remote node.  Once the configuration is sent away, the
        state changes to cfg.

      - cfg
        During this second state, the instance will wait for a valid
        acknowledgement from the gateway to the previously sent
        configuration message. If such a message is delivered, the
        control message (the one that contains the actions to perform)
        is sent, and the state is set to ctl.

      - ctl
        Third state, the instance is waiting for a valid ack for from
        the gateway to the ctl packet. Then, the state switch to gtr
        (gather).

      - gtr
        Final state: wait for results from the subtree and store them.
    """
    def __init__(self, cmd, target, ptree):
        """
        """
        Channel.__init__(self)
        self.cmd = cmd
        self.target = target
        self.ptree = ptree

        self.current_state = None
        self.states = {
            'STATE_CFG': self._state_config,
            'STATE_CTL': self._state_control,
            'STATE_GTR': self._state_gather,
        }

        self._history = {} # track informations about previous states

    def start(self):
        """initial actions"""
        #print '[DBG] start'
        self._open()
        cfg = ConfigurationMessage()
        cfg.data_encode(self.ptree.topology)
        self._history['cfg_id'] = cfg.msgid
        self.send(cfg)
        self.current_state = self.states['STATE_CFG']

    def recv(self, msg):
        """process incoming messages"""
        logging.debug("[DBG] rcvd %s" % str(msg))
        if msg.ident == EndMessage.ident:
            self.ptree.notify_close()
            logging.debug("closing")
            # abort worker (now working)
            self.worker.abort()
        else:
            self.current_state(msg)

    def _state_config(self, msg):
        """handle incoming messages for state 'propagate configuration'"""
        if msg.type == 'ACK' and msg.ack == self._history['cfg_id']:
            self.current_state = self.states['STATE_CTL']

            ctl = ControlMessage()
            ctl.action = 'shell'
            ctl.target = self.target

            ctl_data = {
                'cmd': self.cmd,
                'invoke_gateway': self.ptree.invoke_gateway,
                'taskinfo': task_self()._info,
            }
            ctl.data_encode(ctl_data)

            self._history['ctl_id'] = ctl.msgid
            self.send(ctl)
        else:
            print str(msg)

    def _state_control(self, msg):
        """handle incoming messages for state 'control'"""
        if msg.type == 'ACK' and msg.ack == self._history['ctl_id']:
            self.current_state = self.states['STATE_GTR']
        else:
            print str(msg)

    def _state_gather(self, msg):
        """handle incoming messages for state 'gather results'"""
        # FIXME
        if self.ptree.upchannel:
            logging.debug("_state_gather ->upchan %s" % msg)
            self.ptree.upchannel.send(msg)
        else:
            if msg.type == StdOutMessage.ident:
                if self.ptree.handler:
                    self.ptree.handler.on_message(msg.nodes, msg.output)
            elif msg.type == StdErrMessage.ident:
                if self.ptree.handler:
                    self.ptree.handler.on_errmessage(msg.nodes, msg.output)
            elif msg.type == RetcodeMessage.ident:
                if self.ptree.handler:
                    self.ptree.handler.on_retcode(msg.nodes, msg.retcode)
 
    def ev_close(self, worker):
        worker.flush_buffers()

