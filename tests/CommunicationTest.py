#!/usr/bin/env python
# ClusterShell communication test suite
# Written by H. Doreau
# $Id$


"""Unit test for Communication"""

import sys
import time
import unittest

# profiling imports
#import cProfile
#from guppy import hpy
# ---

from cStringIO import StringIO

sys.path.insert(0, '../lib')

from ClusterShell.Communication import CSMessageFactory, MessagesProcessor
from ClusterShell.Communication import MessageProcessingError
from ClusterShell.Communication import ConfigurationMessage
from ClusterShell.Communication import ControlMessage
from ClusterShell.Communication import ACKMessage
from ClusterShell.Communication import ExitMessage
from ClusterShell.Communication import ErrorMessage



def gen_cfg():
    """return a generic configuration message instance"""
    msg = ConfigurationMessage()
    msg.id = 0
    msg.src = 'admin'
    msg.dst = 'gateway'
    msg.data = 'azerty'
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

def gen_bye():
    """return a generic exit message instance"""
    msg = ExitMessage()
    msg.id = 0
    msg.src = 'admin'
    msg.dst = 'gateway'
    return msg

def gen_err():
    """return a generic error message instance"""
    msg = ErrorMessage()
    msg.id = 0
    msg.src = 'admin'
    msg.dst = 'gateway'
    msg.reason = 'something wrong happened'
    return msg


class CommunicationTest(unittest.TestCase):
    ## -------------
    # TODO : get rid of the following hardcoded messages
    # ---
    def testXMLConfigurationMessage(self):
        """test configuration message XML serialization"""
        res = gen_cfg().xml()
        ref = '<message src="admin" dst="gateway" type="CFG" id="0">azerty</message>'
        self.assertEquals(res, ref)
        
    def testXMLControlMessage(self):
        """test control message XML serialization"""
        res = gen_ctl().xml()
        ref = '<message src="admin" dst="gateway" type="CTL" id="0"><action' \
              ' type="shell" target="node[0-10]"><param cmd="uname -a"></param>' \
              '</action></message>'
        self.assertEquals(res, ref)
        
    def testXMLACKMessage(self):
        """test acknowledgement message XML serialization"""
        res = gen_ack().xml()
        ref = '<message ack="123" src="admin" dst="gateway" type="ACK" id="0">'
        self.assertEquals(res, ref)
        
    def testXMLExitMessage(self):
        """test exit message XML serialization"""
        res = gen_bye().xml()
        ref = '<message src="admin" dst="gateway" type="BYE" id="0">'
        self.assertEquals(res, ref)
        
    def testXMLErrorMessage(self):
        """test error message XML serialization"""
        res = gen_err().xml()
        ref = '<message reason="something wrong happened" src="admin" dst="gateway" type="ERR" id="0">'
        self.assertEquals(res, ref)
        
    def testConfigurationMessageDeserialize(self):
        """test XML deserialization of every message types"""
        generik_msg = {
            'cfg': gen_cfg,
            'ctl': gen_ctl,
            'ack': gen_ack,
            'bye': gen_bye,
            'err': gen_err
        }
        for name, ctor in generik_msg.iteritems():
            print 'trying %s message' % name
            i_str = StringIO(ctor().xml())
            o_str = StringIO()

            proc = MessagesProcessor(i_str, o_str)
            msg = proc.read_msg()

            self.assertNotEqual(msg, None)
        
            msg.id = 0 # this is mandatory as we want to compare this object with
                       # a generic one whose id is set to zero
            self.assertEquals(msg.xml(), i_str.getvalue())
            i_str.close()
            o_str.close()

    def testBuildingInvalidMessage(self):
        """test building invalid messages and ensure exceptions are raised"""
        factory = CSMessageFactory()
        self.assertRaises(MessageProcessingError, factory.new, {'foo': 'bar'})
        self.assertRaises(MessageProcessingError, factory.new, {'type': -1})

    def testReadTimeout(self):
        """test read timeout"""
        read_to = 1.0 # read timeout, in seconds
        margin = read_to * 0.01 # margin allowed for the test to succeed

        i_str = StringIO()
        o_str = StringIO()

        proc = MessagesProcessor(i_str, o_str)
        before = time.time()
        msg = proc.read_msg(timeout=read_to)
        end = time.time()

        self.assertEquals(msg, None)
        self.assertTrue(end - before > read_to - margin)
        self.assertTrue(end - before < read_to + margin)

    def testInvalidMsgStreams(self):
        """test detecting invalid messages"""
        patterns = [
            '<message src="a" dst="a" type="BLA" id="-1"></message>',
            '<message src="a" dst="b" type="ACK"><foo></foo></message>',
            '<message src="a" dst="b" type="CFG"><foo></bar></message>',
            '<message src="a" dst="b" type="CFG"><foo></message>',
            '<message src="a" dst="b" type="CTL"><param></param></message>',
            '<message src="a" dst="b" type="CTL"><param><action target="node123" type="foobar"></action></param></message>',
            '<param cmd=""></param></message>',
        ]
        for msg_xml in patterns:
            i_str = StringIO(msg_xml)
            o_str = StringIO()

            proc = MessagesProcessor(i_str, o_str)
            try:
                proc.read_msg()
            except MessageProcessingError, e:
                # actually this is Ok, we want this exception to be raised
                pass
            else:
                self.fail('Invalid message goes undetected: %s' % msg_xml)


def main():
    suite = unittest.TestLoader().loadTestsFromTestCase(CommunicationTest)
    unittest.TextTestRunner(verbosity=2).run(suite)

if __name__ == '__main__':
    #cProfile.run('main()')
    main()

