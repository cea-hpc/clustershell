# ClusterShell communication test suite
# Written by H. Doreau

"""Unit test for Communication"""

import sys
import unittest
import tempfile
import xml

# profiling imports
#import cProfile
#from guppy import hpy
# ---

sys.path.insert(0, '../lib')

from ClusterShell.Task import task_self
from ClusterShell.Worker.Worker import WorkerSimple
from ClusterShell.Communication import XMLReader, Channel
from ClusterShell.Communication import MessageProcessingError
from ClusterShell.Communication import ConfigurationMessage, ControlMessage
from ClusterShell.Communication import ACKMessage, ErrorMessage
from ClusterShell.Communication import StdOutMessage, StdErrMessage



def gen_cfg():
    """return a generic configuration message instance"""
    msg = ConfigurationMessage()
    msg.msgid = 0
    msg.data = 'KGxwMApJMQphSTIKYUkzCmEu'
    return msg

def gen_ctl():
    """return a generic control message instance"""
    msg = ControlMessage()
    msg.msgid = 0
    msg.action = 'shell'
    msg.target = 'node[0-10]'
    params = {'cmd': 'uname -a'}
    msg.data_encode(params)
    return msg

def gen_ack():
    """return a generic acknowledgement message instance"""
    msg = ACKMessage()
    msg.msgid = 0
    msg.ack = 123
    return msg

def gen_err():
    """return a generic error message instance"""
    msg = ErrorMessage()
    msg.msgid = 0
    msg.reason = 'bad stuff'
    return msg

def gen_out():
    """return a generic output message instance"""
    msg = StdOutMessage()
    msg.msgid = 0
    msg.output = "node5"
    msg.output = "Linux galion25 2.6.18-92.el5 #1 SMP Tue Apr 29 " \
                 "03:13:37 EDT 2008 x86_64 x86_64 x86_64 GNU/Linux"
    return msg

# sample message generators
gen_map = {
    ConfigurationMessage.ident: gen_cfg,
    ControlMessage.ident: gen_ctl,
    ACKMessage.ident: gen_ack,
    ErrorMessage.ident: gen_err,
    StdOutMessage.ident: gen_out,
}

class _TestingChannel(Channel):
    """internal channel that handle read messages"""
    def __init__(self):
        """
        """
        Channel.__init__(self)
        self.queue = []
        self._counter = 1
        self._last_id = 0

    def recv(self, msg):
        """process an incoming messages"""
        self._last_id = msg.msgid
        self.queue.append(msg)
        msg = ACKMessage()
        msg.ack = self._last_id
        self.send(msg)
        self._counter += 1
        if self._counter == 4:
            self.exit = True
            self._close()

    def start(self):
        """
        """
        self._open()

    def validate(self, spec):
        """check whether the test was successful or not by comparing the
        current state with the test specifications
        """
        for msg_type in spec.iterkeys():
            elemt = [p for p in self.queue if p.type == msg_type]
            if len(elemt) != spec[msg_type]:
                print '%d %s messages but %d expected!' % (len(elemt), \
                    msg_type, spec[msg_type])
                return False
        return True

class CommunicationTest(unittest.TestCase):
    ## -------------
    # TODO : get rid of the following hardcoded messages
    # ---
    def testXMLConfigurationMessage(self):
        """test configuration message XML serialization"""
        res = gen_cfg().xml()
        ref = '<message msgid="0" type="CFG">KGxwMApJMQphSTIKYUkzCmEu</message>'
        self.assertEquals(res, ref)

    def testXMLControlMessage(self):
        """test control message XML serialization"""
        res = gen_ctl().xml()
        ref = '<message action="shell" msgid="0" srcid="0" target="node[0-10]" type="CTL">' \
            'KGRwMQpTJ2NtZCcKcDIKUyd1bmFtZSAtYScKcDMKcy4=</message>'
        self.assertEquals(res, ref)

    def testXMLACKMessage(self):
        """test acknowledgement message XML serialization"""
        res = gen_ack().xml()
        ref = '<message ack="123" msgid="0" type="ACK"></message>'
        self.assertEquals(res, ref)

    def testXMLErrorMessage(self):
        """test error message XML serialization"""
        res = gen_err().xml()
        ref = '<message msgid="0" reason="bad stuff" type="ERR"></message>'
        self.assertEquals(res, ref)

    def testXMLOutputMessage(self):
        """test output message XML serialization"""
        res = gen_out().xml()
        ref = '<message msgid="0" nodes="" output=' \
        '"Linux galion25 2.6.18-92.el5 #1 SMP Tue Apr 29 03:13:37 EDT 2008 x86_64 x86_64 x86_64 GNU/Linux"' \
        ' srcid="0" type="OUT"></message>'
        self.assertEquals(res, ref)

    def testInvalidMsgStreams(self):
        """test detecting invalid messages"""
        patterns = [
            '<message type="BLA" msgid="-1"></message>',
            '<message type="ACK"></message>',
            '<message type="ACK" msgid="0" ack="12"><foo></foo></message>',
            '<message type="ACK" msgid="0" ack="12">some stuff</message>',
            '<message type="ACK" msgid="123"></message>',
            '<message type="OUT" msgid="123" reason="foo"></message>',
            '<message type="OUT" msgid="123" output="foo" nodes="bar">shoomp</message>',
            '<message type="CFG" msgid="123"><foo></bar></message>',
            '<message type="CFG" msgid="123"><foo></message>',
            '<message type="CTL" msgid="123"><param></param></message>',
            '<message type="CTL" msgid="123"></message>',
            '<message type="CTL" msgid="123"><param><action target="node123" type="foobar"></action></param></message>',
            '<message type="CTL" msgid="123"><action type="foobar"></message>',
            '<message type="CTL" msgid="123"><action type="foobar" target="node1"><param cmd="yeepee"></param></action></message>',
            '<message type="CTL" msgid="123"><action type="foobar"><param cmd="echo fnords"></param></action></message>',
            '<message type="CTL" msgid="123"><action type="shell" target="node1"></action></message>',
            '<message type="CTL" msgid="123"><action type="" target="node1"><param cmd="echo fnords"></param></action></message>',
            '<param cmd=""></param></message>',
            '<message type="ERR" msgid="123"></message>',
            '<message type="ERR" msgid="123" reason="blah">unexpected payload</message>',
            '<message type="ERR" msgid="123" reason="blah"><foo bar="boo"></foo></message>',
        ]
        for msg_xml in patterns:
            parser = xml.sax.make_parser(['IncrementalParser'])
            parser.setContentHandler(XMLReader())

            parser.feed('<?xml version="1.0" encoding="UTF-8"?>\n')
            parser.feed('<channel>\n')

            try:
                parser.feed(msg_xml)
            except MessageProcessingError as m:
                # actually this is Ok, we want this exception to be raised
                pass
            else:
                self.fail('Invalid message goes undetected: %s' % msg_xml)

    def testConfigMsgEncoding(self):
        """test configuration message serialization abilities"""
        msg = gen_cfg()
        msg.data = ''
        inst = {'foo': 'plop', 'blah': 123, 'fnords': 456}
        msg.data_encode(inst)
        self.assertEquals(inst, msg.data_decode())

    def testChannelAbstractMethods(self):
        """test driver interface"""
        c = Channel()
        self.assertRaises(NotImplementedError, c.recv, None)
        self.assertRaises(NotImplementedError, c.start)

    def testDistantChannel(self):
        """schyzophrenic self communication test over SSH"""
        # create a bunch of messages
        spec = {
            # msg type: number of samples
            ConfigurationMessage.ident: 1,
            ControlMessage.ident: 1,
            ACKMessage.ident: 1,
            ErrorMessage.ident: 1
        }
        ftest = tempfile.NamedTemporaryFile()
        ftest.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        ftest.write('<channel>\n')
        for mtype, count in spec.items():
            for i in range(count):
                sample = gen_map[mtype]()
                sample.msgid = i
                ftest.write(sample.xml() + '\n')
        ftest.write('</channel>\n')

        ## write data on the disk
        # actually we should do more but this seems sufficient
        ftest.flush()

        task = task_self()
        chan = _TestingChannel()
        task.shell('cat ' + ftest.name, nodes='localhost', handler=chan)
        task.resume()

        ftest.close()
        self.assertEquals(chan.validate(spec), True)

    def testLocalChannel(self):
        """schyzophrenic self local communication"""
        # create a bunch of messages
        spec = {
            # msg type: number of samples
            ConfigurationMessage.ident: 1,
            ControlMessage.ident: 1,
            ACKMessage.ident: 1,
            ErrorMessage.ident: 1
        }
        ftest = tempfile.NamedTemporaryFile()
        ftest.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        ftest.write('<channel>\n')
        for mtype, count in spec.items():
            for i in range(count):
                sample = gen_map[mtype]()
                sample.msgid = i
                ftest.write(sample.xml() + '\n')
        ftest.write('</channel>\n')

        ## write data on the disk
        # actually we should do more but this seems sufficient
        ftest.flush()

        fin = open(ftest.name)
        fout = open('/dev/null', 'w')

        chan = _TestingChannel()
        worker = WorkerSimple(fin, fout, None, None, handler=chan)

        task = task_self()
        task.schedule(worker)
        task.resume()

        ftest.close()
        fin.close()
        fout.close()
        self.assertEquals(chan.validate(spec), True)

    def testInvalidCommunication(self):
        """test detecting invalid data upon reception"""
        ftest = tempfile.NamedTemporaryFile()
        ftest.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        ftest.write('This is an invalid line\n')
        ftest.write('<channel>\n')
        ftest.write('</channel>\n')

        ## write data on the disk
        # actually we should do more but this seems sufficient
        ftest.flush()

        chan = _TestingChannel()
        task = task_self()

        fin = open(ftest.name)
        fout = open('/dev/null', 'w')
        worker = WorkerSimple(fin, fout, None, None, handler=chan)
        task.schedule(worker)

        self.assertRaises(MessageProcessingError, task.resume)

        fin.close()
        fout.close()
        ftest.close()

    def testPrintableRepresentations(self):
        """test printing messages"""
        msg = gen_cfg()
        self.assertEquals(str(msg), 'Message CFG (msgid: 0, type: CFG)')
