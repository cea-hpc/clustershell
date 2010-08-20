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

sys.path.insert(0, '../lib')

from ClusterShell.Communication import *


class CommunicationTest(unittest.TestCase):
    def _gen_cfg(self):
        msg = ConfigurationMessage()
        msg.id = 0
        msg.src = 'admin'
        msg.dst = 'gateway'
        msg.data = 'azerty'
        msg.pickle_proto = 2
        return msg

    def _gen_ctl(self):
        msg = ControlMessage()
        msg.id = 0
        msg.src = 'admin'
        msg.dst = 'gateway'
        msg.action_type = 'shell'
        msg.action_target = 'node[0-10]'
        msg.params['cmd'] = 'uname -a'
        return msg

    def _gen_ack(self):
        msg = ACKMessage()
        msg.id = 0
        msg.src = 'admin'
        msg.dst = 'gateway'
        msg.ack_id = 123
        return msg
    
    def _gen_bye(self):
        msg = ExitMessage()
        msg.id = 0
        msg.src = 'admin'
        msg.dst = 'gateway'
        return msg

    def _gen_err(self):
        msg = ErrorMessage()
        msg.id = 0
        msg.src = 'admin'
        msg.dst = 'gateway'
        msg.reason = 'something wrong happened'
        msg.id_ref = 123
        return msg

    def testXMLConfigurationMessage(self):
        """test configuration message XML serialization"""
        res = self._gen_cfg().xml()
        ref = '<message src="admin" dst="gateway" type="CFG" id="0">azerty</message>'
        self.assertEquals(res, ref)
        
    def testXMLControlMessage(self):
        """test message XML serialization"""
        res = self._gen_ctl().xml()
        ref = '<message src="admin" dst="gateway" type="CTL" id="0"><action' \
              ' type="shell" target="node[0-10]"><param cmd="uname -a"></param>' \
              '</action></message>'
        self.assertEquals(res, ref)
        
    def testXMLACKMessage(self):
        """test message XML serialization"""
        res = self._gen_ack().xml()
        ref = '<message ack="123" src="admin" dst="gateway" type="ACK" id="0">'
        self.assertEquals(res, ref)
        
    def testXMLExitMessage(self):
        """test message XML serialization"""
        res = self._gen_bye().xml()
        ref = '<message src="admin" dst="gateway" type="BYE" id="0">'
        self.assertEquals(res, ref)
        
    def testXMLErrorMessage(self):
        """test error message XML serialization"""
        res = self._gen_err().xml()
        ref = '<message src="admin" dst="gateway" id_ref="123" reason=' \
              '"something wrong happened" type="ERR" id="0">'
        self.assertEquals(res, ref)
        
    def testConfigurationMessageDeserialize(self):
        """test XML deserialization"""
        generik_msg = {
            'cfg': self._gen_cfg,
            'ctl': self._gen_ctl,
            'ack': self._gen_ack,
            'bye': self._gen_bye,
            'err': self._gen_err
        }
        for name, ctor in generik_msg.iteritems():
            i_str = StringIO(ctor().xml())
            o_str = StringIO()

            proc = MessagesProcessor(i_str, o_str)
            msg = proc.read_msg()

            self.assertNotEqual(msg, None)
        
            msg.id = 0 # this is mandatory as we want to compare this object with
                       # the generic one
            self.assertEquals(msg.xml(), i_str.getvalue())
            i_str.close()
            o_str.close()


def main():
    suite = unittest.TestLoader().loadTestsFromTestCase(CommunicationTest)
    unittest.TextTestRunner(verbosity=2).run(suite)

if __name__ == '__main__':
    #cProfile.run('main()')
    main()

