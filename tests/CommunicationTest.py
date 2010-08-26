#!/usr/bin/env python
# ClusterShell communication test suite
# Written by H. Doreau
# $Id$


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

from ClusterShell.Communication import XMLMsgHandler
from ClusterShell.Communication import CSMessageFactory
from ClusterShell.Communication import CommunicationChannel
from ClusterShell.Communication import CommunicationDriver
from ClusterShell.Communication import MessageProcessingError
from ClusterShell.Communication import ConfigurationMessage
from ClusterShell.Communication import ControlMessage
from ClusterShell.Communication import ACKMessage
from ClusterShell.Communication import ErrorMessage



def gen_cfg():
    """return a generic configuration message instance"""
    msg = ConfigurationMessage()
    msg.id = 0
    msg.src = 'admin'
    msg.dst = 'gateway'
    msg.data = 'KGxwMApJMQphSTIKYUkzCmEu'
    return msg

def gen_ctl():
    """return a generic control message instance"""
    msg = ControlMessage()
    msg.id = 0
    msg.src = 'admin'
    msg.dst = 'gateway'
    msg.action_type = 'shell'
    msg.action_target = 'node[0-10]'
    msg.params['cmd'] = 'uname -a'
    return msg

def gen_ack():
    """return a generic acknowledgement message instance"""
    msg = ACKMessage()
    msg.id = 0
    msg.src = 'admin'
    msg.dst = 'gateway'
    msg.ack_id = 123
    return msg

def gen_err():
    """return a generic error message instance"""
    msg = ErrorMessage()
    msg.id = 0
    msg.src = 'admin'
    msg.dst = 'gateway'
    msg.reason = 'bad stuff'
    return msg

# sample message generators
gen_map = {
    ConfigurationMessage.ident: gen_cfg,
    ControlMessage.ident: gen_ctl,
    ACKMessage.ident: gen_ack,
    ErrorMessage.ident: gen_err
}


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
        ref = '<message msgid="0" type="CTL">'\
                '<action type="shell" target="node[0-10]">'\
                '<param cmd="uname -a"></param></action></message>'
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

    def testBuildingInvalidMessage(self):
        """test building invalid messages and ensure exceptions are raised"""
        factory = CSMessageFactory()
        self.assertRaises(MessageProcessingError, factory.new, {'foo': 'bar'})
        self.assertRaises(MessageProcessingError, factory.new, {'type': -1})

    def testReadTimeout(self):
        """test read timeout"""
        raise NotImplementedError('This test has not been implemented yet')

    def testInvalidMsgStreams(self):
        """test detecting invalid messages"""
        patterns = [
            '<message type="BLA" msgid="-1"></message>',
            '<message type="ACK"></message>',
            '<message type="ACK" msgid="0" ack="12"><foo></foo></message>',
            '<message type="ACK" msgid="0" ack="12">some stuff</message>',
            '<message type="ACK" msgid="123"></message>',
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
        ]
        for msg_xml in patterns:
            parser = xml.sax.make_parser(['IncrementalParser'])
            parser.setContentHandler(XMLMsgHandler())
            
            parser.feed('<?xml version="1.0" encoding="UTF-8"?>\n')
            parser.feed('<channel src="localhost" dst="localhost">\n')
            
            try:
                parser.feed(msg_xml)
            except MessageProcessingError, m:
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

    def testCommunicationChannel(self):
        """schyzophrenic self communication test"""
        class _TestingDriver(CommunicationDriver):
            """internal driver that handle read messages"""
            def __init__(self, src, dst):
                """
                """
                CommunicationDriver.__init__(self, src, dst)
                self.queue = []
                self._counter = 0
                self._last_id = 0

            def read_msg(self, msg):
                """process an incoming messages"""
                self._last_id = msg.id
                self.queue.append(msg)

            def next_msg(self):
                """send a messgae if any"""
                self._counter += 1
                if self._counter > 1:
                    self._counter = 0
                    return None
                msg = ACKMessage()
                msg.ack_id = self._last_id
                return msg

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
        ftest.write('<channel src="localhost" dst="localhost">\n')
        for mtype, count in spec.iteritems():
            for i in xrange(count):
                sample = gen_map[mtype]()
                sample.id = i
                ftest.write(sample.xml() + '\n')
        ftest.write('</channel>\n')

        ## write data on the disk
        # actually we should do more but this seems sufficient
        ftest.flush()

        driver = _TestingDriver('localhost', 'localhost')
        chan = CommunicationChannel(driver)
        task = task_self()
        task.shell('cat ' + ftest.name, nodes='localhost', handler=chan)
        task.resume()
        ftest.close()
        self.assertEquals(driver.validate(spec), True)


def main():
    suite = unittest.TestLoader().loadTestsFromTestCase(CommunicationTest)
    unittest.TextTestRunner(verbosity=2).run(suite)

if __name__ == '__main__':
    #cProfile.run('main()')
    main()

