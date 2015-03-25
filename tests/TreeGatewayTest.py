#!/usr/bin/env python
# ClusterShell.Gateway test suite

import logging
import os
import unittest
import xml.sax

from ClusterShell.Communication import ConfigurationMessage, ControlMessage
from ClusterShell.Communication import StdOutMessage, RetcodeMessage, ACKMessage
from ClusterShell.Communication import StartMessage, EndMessage, ErrorMessage
from ClusterShell.Communication import XMLReader
from ClusterShell.Gateway import GatewayChannel
from ClusterShell.NodeSet import NodeSet
from ClusterShell.Task import Task, task_self
from ClusterShell.Topology import TopologyGraph
from ClusterShell.Worker.Tree import WorkerTree
from ClusterShell.Worker.Worker import StreamWorker

from TLib import HOSTNAME

# live logging with nosetests --nologcapture
logging.basicConfig(level=logging.DEBUG)


class Gateway(object):
    """Gateway special test class.

    Initialize a GatewayChannel through a R/W StreamWorker like a real
    remote ClusterShell Gateway but:
        - using fake gateway remote host (gwhost),
        - using pipes to communicate,
        - running on a dedicated task/thread.
    """

    def __init__(self, gwhost):
        """init Gateway bound objects"""
        self.task = Task()
        self.gwhost = gwhost
        self.channel = GatewayChannel(self.task, gwhost)
        self.worker = StreamWorker(handler=self.channel)
        # create communication pipes
        self.pipe_stdin = os.pipe()
        self.pipe_stdout = os.pipe()
        # avoid nonblocking flag as we want recv/read() to block
        self.worker.set_reader('r-stdin', self.pipe_stdin[0])
        self.worker.set_writer('w-stdout', self.pipe_stdout[1], retain=False)
        self.task.schedule(self.worker)
        self.task.resume()

    def send(self, msg):
        """send msg to pseudo stdin"""
        os.write(self.pipe_stdin[1], msg + '\n')

    def recv(self):
        """recv buf from pseudo stdout (blocking call)"""
        return os.read(self.pipe_stdout[0], 4096)

    def wait(self):
        """wait for task/thread termination"""
        # can be blocked indefinitely if StreamWorker doesn't complete
        self.task.join()

    def close(self):
        """close parent fds"""
        os.close(self.pipe_stdout[0])
        os.close(self.pipe_stdin[1])

    def destroy(self):
        """abort task/thread"""
        self.task.abort(kill=True)


class TreeGatewayBaseTest(unittest.TestCase):
    """base test class"""

    def setUp(self):
        """setup gateway and topology for each test"""
        # gateway
        self.gateway = Gateway('n1')
        self.chan = self.gateway.channel
        # topology
        graph = TopologyGraph()
        graph.add_route(NodeSet(HOSTNAME), NodeSet('n[1-2]'))
        graph.add_route(NodeSet('n1'), NodeSet('n[10-49]'))
        graph.add_route(NodeSet('n2'), NodeSet('n[50-89]'))
        self.topology = graph.to_tree(HOSTNAME)
        # xml parser with Communication.XMLReader as content handler
        self.xml_reader = XMLReader()
        self.parser = xml.sax.make_parser(["IncrementalParser"])
        self.parser.setContentHandler(self.xml_reader)

    def tearDown(self):
        """destroy gateway after each test"""
        self.gateway.destroy()
        self.gateway = None

    #
    # Send to GW
    #
    def channel_send_start(self):
        """send starting channel tag"""
        self.gateway.send("<channel>")

    def channel_send_stop(self):
        """send channel ending tag"""
        self.gateway.send("</channel>")

    def channel_send_cfg(self):
        """send configuration part of channel"""
        # code snippet from PropagationChannel.start()
        cfg = ConfigurationMessage()
        cfg.data_encode(self.topology)
        self.gateway.send(cfg.xml())

    #
    # Receive from GW
    #
    def assert_isinstance(self, msg, msg_class):
        """helper to check a message instance"""
        self.assertTrue(isinstance(msg, msg_class),
                        "%s is not a %s" % (type(msg), msg_class))

    def _recvxml(self):
        while not self.xml_reader.msg_available():
            xml_msg = self.gateway.recv()
            if len(xml_msg) == 0:
                return None
            self.parser.feed(xml_msg)

        return self.xml_reader.pop_msg()

    def recvxml(self, expected_msg_class=None):
        msg = self._recvxml()
        if expected_msg_class is None:
            self.assertEqual(msg, None)
        else:
            self.assert_isinstance(msg, expected_msg_class)
        return msg


class TreeGatewayTest(TreeGatewayBaseTest):

    def test_basic_noop(self):
        """test gateway channel open/close"""
        self.channel_send_start()
        self.recvxml(StartMessage)
        self.assertEqual(self.chan.opened, True)
        self.assertEqual(self.chan.setup, False)

        self.channel_send_stop()
        self.recvxml(EndMessage)
        self.assertEqual(self.chan.opened, False)
        self.assertEqual(self.chan.setup, False)
        # ending tag should abort gateway worker without delay
        self.gateway.wait()
        self.gateway.close()

    def test_channel_err_dup(self):
        """test gateway channel duplicate tags"""
        self.channel_send_start()
        msg = self.recvxml(StartMessage)
        self.assertEqual(self.chan.opened, True)
        self.assertEqual(self.chan.setup, False)

        # send an unexpected second channel tag
        self.channel_send_start()
        msg = self.recvxml(ErrorMessage)
        self.assertEqual(msg.type, 'ERR')
        reason = 'unexpected message: Message CHA '
        self.assertEqual(msg.reason[:len(reason)], reason)

        # gateway should terminate channel session
        msg = self.recvxml(EndMessage)
        self.assertEqual(self.chan.opened, False)
        self.assertEqual(self.chan.setup, False)
        self.gateway.wait()
        self.gateway.close()

    def _check_channel_err(self, sendmsg, errback, openchan=True,
                           setupchan=False):
        """helper to ease test of erroneous messages sent to gateway"""
        if openchan:
            self.channel_send_start()
            msg = self.recvxml(StartMessage)
            self.assertEqual(self.chan.opened, True)
            self.assertEqual(self.chan.setup, False)

        if setupchan:
            # send channel configuration
            self.channel_send_cfg()
            msg = self.recvxml(ACKMessage)
            self.assertEqual(self.chan.setup, True)

        # send the erroneous message and test gateway reply
        self.gateway.send(sendmsg)
        msg = self.recvxml(ErrorMessage)
        self.assertEqual(msg.type, 'ERR')
        self.assertEqual(msg.reason, errback)

        # gateway should terminate channel session
        if openchan:
            msg = self.recvxml(EndMessage)
            self.assertEqual(msg.type, 'END')
        else:
            self.recvxml()

        # flags should be reset
        self.assertEqual(self.chan.opened, False)
        self.assertEqual(self.chan.setup, False)

        # gateway task should exit properly
        self.gateway.wait()
        self.gateway.close()

    def test_err_start_with_ending_tag(self):
        """test gateway missing opening channel tag"""
        self._check_channel_err('</channel>',
                                'Parse error: not well-formed (invalid token)',
                                openchan=False)

    def test_err_channel_end_msg(self):
        """test gateway channel missing opening message tag"""
        self._check_channel_err('</message>',
                                'Parse error: mismatched tag')

    def test_err_channel_end_msg_setup(self):
        """test gateway channel missing opening message tag (setup)"""
        self._check_channel_err('</message>',
                                'Parse error: mismatched tag',
                                setupchan=True)

    def test_err_unknown_tag(self):
        """test gateway unknown tag"""
        self._check_channel_err('<foobar></footbar>',
                                'Invalid starting tag foobar',
                                openchan=False)

    def test_channel_err_unknown_tag(self):
        """test gateway unknown tag in channel"""
        self._check_channel_err('<foo></foo>', 'Invalid starting tag foo')

    def test_channel_err_unknown_tag(self):
        """test gateway unknown tag in channel (setup)"""
        self._check_channel_err('<foo></foo>',
                                'Invalid starting tag foo',
                                setupchan=True)

    def test_err_unknown_msg(self):
        """test gateway unknown message"""
        self._check_channel_err('<message msgid="24" type="ABC"></message>',
                                'Unknown message type',
                                openchan=False)

    def test_channel_err_unknown_msg(self):
        """test gateway channel unknown message"""
        self._check_channel_err('<message msgid="24" type="ABC"></message>',
                                'Unknown message type')

    def test_err_xml_malformed(self):
        """test gateway malformed xml message"""
        self._check_channel_err('<message type="ABC"</message>',
                                'Parse error: not well-formed (invalid token)',
                                openchan=False)

    def test_channel_err_xml_malformed(self):
        """test gateway channel malformed xml message"""
        self._check_channel_err('<message type="ABC"</message>',
                                'Parse error: not well-formed (invalid token)')

    def test_channel_err_xml_malformed_setup(self):
        """test gateway channel malformed xml message"""
        self._check_channel_err('<message type="ABC"</message>',
                                'Parse error: not well-formed (invalid token)',
                                setupchan=True)

    def test_channel_err_xml_bad_char(self):
        """test gateway channel malformed xml message (bad chars)"""
        self._check_channel_err('\x11<message type="ABC"></message>',
                                'Parse error: not well-formed (invalid token)')

    def test_channel_err_missingattr(self):
        """test gateway channel message bad attributes"""
        self._check_channel_err(
            '<message msgid="24" type="RET"></message>',
            'Invalid "message" attributes: missing key "srcid"')

    def test_channel_err_unexpected(self):
        """test gateway channel unexpected message"""
        self._check_channel_err(
            '<message type="ACK" ack="2" msgid="2"></message>',
            'unexpected message: Message ACK (ack: 2, msgid: 2, type: ACK)')

    def test_channel_err_missing_pl(self):
        """test gateway channel message missing payload"""
        self._check_channel_err(
            '<message msgid="14" type="CFG"></message>',
            'Message CFG has an invalid payload')

    def test_channel_err_unexpected_pl(self):
        """test gateway channel message unexpected payload"""
        self._check_channel_err(
            '<message msgid="14" type="ERR" reason="test">FOO</message>',
            'Got unexpected payload for Message ERR', setupchan=True)

    def test_channel_err_badenc_pl(self):
        """test gateway channel message badly encoded payload"""
        self._check_channel_err(
            '<message msgid="14" type="CFG">bar</message>',
            'Incorrect padding')

    def test_channel_basic_abort(self):
        """test gateway channel aborted while opened"""
        self.channel_send_start()
        self.recvxml(StartMessage)
        self.assertEqual(self.chan.opened, True)
        self.assertEqual(self.chan.setup, False)
        self.gateway.close()
        self.gateway.wait()

    def test_channel_ctl_shell(self):
        """test gateway channel remote shell command"""
        self.channel_send_start()
        msg = self.recvxml(StartMessage)
        self.channel_send_cfg()
        msg = self.recvxml(ACKMessage)

        # test remote shell command request
        command = "echo ok"
        target = NodeSet("n10")
        timeout = -1
        workertree = WorkerTree(nodes=target, handler=None, timeout=timeout,
                                command=command)
        # code snippet from PropagationChannel.shell()
        ctl = ControlMessage(id(workertree))
        ctl.action = 'shell'
        ctl.target = target

        info = task_self()._info.copy()
        info['debug'] = False

        ctl_data = {
            'cmd': command,
            'invoke_gateway': workertree.invoke_gateway,
            'taskinfo': info,
            'stderr': False,
            'timeout': timeout,
        }
        ctl.data_encode(ctl_data)
        self.gateway.send(ctl.xml())

        self.recvxml(ACKMessage)

        msg = self.recvxml(StdOutMessage)
        self.assertEqual(msg.nodes, "n10")
        self.assertTrue("Name or service not known" in msg.data)

        msg = self.recvxml(RetcodeMessage)
        self.assertEqual(msg.retcode, 255)

        self.channel_send_stop()
        self.gateway.wait()
        self.gateway.close()
