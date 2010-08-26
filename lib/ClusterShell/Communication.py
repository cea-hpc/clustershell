#!/usr/bin/env python
#
# Copyright CEA/DAM/DIF (2008, 2009, 2010)
# Contributor: Henri DOREAU <henri.doreau@gmail.com>
#
# This file is part of the ClusterShell library.
#
# This software is governed by the CeCILL-C license under French law and abiding
# by the rules of distribution of free software. You can use, modify and/ or
# redistribute the software under the terms of the CeCILL-C license as
# circulated by CEA, CNRS and INRIA at the following URL
# "http://www.cecill.info".
#
# As a counterpart to the access to the source code and rights to copy, modify
# and redistribute granted by the license, users are provided only with a
# limited warranty and the software's author, the holder of the economic rights,
# and the successive licensors have only limited liability.
#
# In this respect, the user's attention is drawn to the risks associated with
# loading, using, modifying and/or developing or reproducing the software by the
# user in light of its specific status of free software, that may mean that it
# is complicated to manipulate, and that also therefore means that it is
# reserved for developers and experienced professionals having in-depth computer
# knowledge. Users are therefore encouraged to load and test the software's
# suitability as regards their requirements in conditions enabling the security
# of their systems and/or data to be ensured and, more generally, to use and
# operate it in the same conditions as regards security.
#
# The fact that you are presently reading this means that you have had knowledge
# of the CeCILL-C license and that you accept its terms.
#
# $Id$

"""
ClusterShell inter-nodes communication module

This module contains the required material for nodes to communicate between each
others whithin the propagation tree. At the highest level, messages are
instances of several classes. Then they're converted into XML to be sent over
SSH links through a CommunicationChannel instance.

In the other side, XML is parsed and new message objects are instanciated.

Communication channels have been implemented as ClusterShell events handlers.
Whenever a message chunk is read, the data is given to a SAX XML parser, that
will use it to create corresponding messages instances through a messages
factory.

As soon as an instance is ready, it is then passed to a CommunicationDriver. The
driver is an interface able to get and emit messages instances. Subclassing this
interface offers the ability to connect whatever logic you want over a
communication channel.
"""

import cPickle
import base64
import xml.sax

from xml.sax.handler import ContentHandler
from xml.sax.saxutils import XMLGenerator

from collections import deque
from cStringIO import StringIO

from ClusterShell.Event import EventHandler


def strdel(s, badchars):
    """return s a copy of s with every badchar occurences removed"""
    stripped = s
    for ch in badchars:
        stripped = stripped.replace(ch, '')
    return stripped

class XMLMsgHandler(ContentHandler):
    """SAX handler for XML -> CSMessages instances conversion"""
    def __init__(self):
        """
        """
        ContentHandler.__init__(self)
        self.msg_queue = deque()
        self._msg_factory = CSMessageFactory()

    def startElement(self, name, attrs):
        """read a starting xml tag"""
        if name == 'channel':
            self._msg_factory.name = attrs['dst']
            self._msg_factory.parent = attrs['src']
        elif name == 'message':
            self._msg_factory.new(attrs)
        else:
            self._msg_factory.update(name, attrs)

    def endElement(self, name):
        """read an ending xml tag"""
        # end of message
        if name == 'message':
            # if the message is available (ie. complete)...
            if self._msg_factory.msg_available():
                # ... then take it and queue it
                self.msg_queue.appendleft(self._msg_factory.deliver())
            else:
                # ... otherwise raise an exception
                raise MessageProcessingError('Incomplete message received')

    def characters(self, content):
        """read content characters"""
        content = content.encode('utf-8')
        content = strdel(content, [' ', '\t', '\r', '\n'])
        if content != '':
            self._msg_factory.data_update(content)

    def msg_available(self):
        """return whether a message is available for delivery or not"""
        return len(self.msg_queue) > 0

    def pop_msg(self):
        """pop and return the oldest message queued"""
        if len(self.msg_queue) > 0:
            return self.msg_queue.pop()

class CSMessageFactory:
    """XML -> instance deserialization class"""
    def __init__(self):
        """
        """
        self.name = ''
        self.parent = ''
        # current packet under construction
        self._draft = None
        self._sections_map = None

    def new(self, attributes):
        """start a new packet construction"""
        # associative array to select to correct constructor according to the
        # message type field contained in the serialized representation
        ctors_map = {
            ConfigurationMessage.ident: ConfigurationMessage,
            ControlMessage.ident: ControlMessage,
            ACKMessage.ident: ACKMessage,
            ErrorMessage.ident: ErrorMessage
        }
        try:
            msg_type = attributes['type']
            # select the good constructor
            ctor = ctors_map[msg_type]
        except KeyError:
            raise MessageProcessingError('Unknown message type')
        self._draft = ctor()
        self._draft.src = self.parent
        self._draft.dst = self.name
        # obtain expected sections map for this type of messages
        self._sections_map = self._draft.expected_sections()
        self.update('message', attributes)

    def update(self, name, attributes):
        """update the current message draft with a new section"""
        try:
            handle = self._sections_map[name]
        except KeyError:
            # this type of message do not have such elements
            raise MessageProcessingError('Invalid element: %s' % name)
        except TypeError:
            # no message being crafted, we shouldn't be there!
            raise MessageProcessingError('Syntax error/orphan element detected')
        else:
            handle(attributes)

    def data_update(self, raw):
        """update the current message draft with characters"""
        self._draft.data_update(raw)

    def msg_available(self):
        """return whether a message is available for delivery or not"""
        return self._draft is not None and self._draft.is_complete()

    def deliver(self):
        """release the current packet"""
        msg = self._draft
        self._draft = None
        self._sections_map = None
        return msg

class CommunicationChannel(EventHandler):
    """Use this event handler to establish a communication channel between to
    hosts whithin the propagation tree.

    Instances use a driver that describes their behavior, and send/recv messages
    over the channel.
    """
    def __init__(self, driver):
        """
        """
        EventHandler.__init__(self)
        self._driver = driver
        self._handler = XMLMsgHandler()
        self._parser = xml.sax.make_parser(["IncrementalParser"])
        self._parser.setContentHandler(self._handler)

    def ev_start(self, worker):
        """connection established. Open higher level channel"""
        worker.write(self._channel_open())
        msg = self._driver.next_msg()
        if msg is not None:
            worker.write(msg.xml())

    def _channel_open(self):
        """open a new communication channel from src to dst"""
        opener = u'<?xlm version="1.0" encoding="UTF-8"?>\n'
        out = StringIO()
        generator = XMLGenerator(out)
        channel_attr = {
            'src': self._driver.src,
            'dst': self._driver.dst
        }
        generator.startElement('channel', channel_attr)
        return opener + out.getvalue()

    def _channel_close(self):
        """close an already opened channel"""
        out = StringIO()
        generator = XMLGenerator(out)
        generator.endElement('channel')
        return out.getvalue()

    def ev_read(self, worker):
        """channel has data to read"""
        # feed the message factory with received data
        _, raw = worker.last_read()
        self._parser.feed(raw)
        # pass next message to the driver if ready
        if self._handler.msg_available():
            msg = self._handler.pop_msg()
            assert msg is not None
            self._driver.read_msg(msg)
        # eventually reply
        while True:
            msg = self._driver.next_msg()
            if msg is None:
                break
            worker.write(msg.xml())
        # close the connection if asked to do so by the driver
        if self._driver.exit:
            worker.write(self._channel_close())

    def ev_hup(self, worker):
        """do some cleanup when the connection is over"""
        # TODO: call this statement on </channel>
        #self._parser.close()

class CommunicationDriver:
    """describes the behavior of a communicating node"""
    def __init__(self, src, dst):
        """
        """
        self.exit = False
        self.src = src
        self.dst = dst

    def read_msg(self, msg):
        """process incoming message"""
        NotImplementedError('Abstract method: subclasses must implement')

    def next_msg(self):
        """return next outgoing message"""
        NotImplementedError('Abstract method: subclasses must implement')

class CSMessage:
    """base message class"""

    _inst_counter = 0
    ident = 'GEN'

    def __init__(self):
        """
        """
        self.type = CSMessage.ident
        self.src = ''
        self.dst = ''
        self.id = CSMessage._inst_counter
        CSMessage._inst_counter += 1

    def data_update(self, data):
        """
        Process raw data contained in messages between tags. Not every message
        types need this, so subclasses must implement if necessary.
        """
        raise MessageProcessingError('This type of message have no data field')

    def expected_sections(self):
        """return an associative array made of sections name (keys) and methods
        to handle these sections (values)
        """
        sections_map = {
            'message': self.handle_message
        }
        return sections_map

    def handle_message(self, attributes):
        """handle a "message" section"""
        try:
            self.type = attributes['type']
            self.id = attributes['msgid']
        except KeyError, k:
            raise MessageProcessingError(
                'Invalid "message" attributes: missing key "%s"' % k)

    def is_complete(self):
        """return whether every fields are set or not"""
        return self.src != '' and self.dst != '' and self.type != ''

    def xml(self):
        """return the XML representation of the current instance"""
        raise NotImplementedError('Abstract method: subclasses must implement')

class ConfigurationMessage(CSMessage):
    """configuration propagation container"""
    
    ident = 'CFG'
    
    def __init__(self):
        """
        """
        CSMessage.__init__(self)
        self.type = ConfigurationMessage.ident
        self.data = ''

    def data_encode(self, inst):
        """serialize an instance and store the result"""
        self.data = base64.encodestring(cPickle.dumps(inst))

    def data_decode(self):
        """deserialize a previously encoded instance and return it"""
        return cPickle.loads(base64.decodestring(self.data))

    def data_update(self, raw):
        """append data to the instance (used for deserialization)"""
        # TODO : bufferize and use ''.join() for performance
        self.data += raw

    def is_complete(self):
        """return whether every fields are set or not"""
        base = CSMessage.is_complete(self)
        return base and self.data != ''

    def xml(self):
        """generate XML version of a configuration message"""
        out = StringIO()
        generator = XMLGenerator(out)
        msg_attr = {
            'type': self.type,
            'msgid': str(self.id)
        }
        generator.startElement('message', msg_attr)
        generator.characters(self.data)
        generator.endElement('message')
        xml_msg = out.getvalue()
        out.close()
        return xml_msg

class ControlMessage(CSMessage):
    """action request"""

    ident = 'CTL'

    # TODO : remove hardcoded values (action type, parameters...)
    def __init__(self):
        """
        """
        CSMessage.__init__(self)
        self.type = ControlMessage.ident
        self.action_type = ''
        self.action_target = ''
        self.params = {}

    def expected_sections(self):
        """return an associative array made of sections name (keys) and methods
        to handle these sections (values)
        """
        sections_map = CSMessage.expected_sections(self)
        sections_map['action'] = self.handle_action
        sections_map['param'] = self.handle_param
        return sections_map

    def handle_action(self, attributes):
        """handle attributes associated to an "action" section"""
        try:
            self.action_type = attributes['type']
            self.action_target = attributes['target']
        except KeyError, k:
            raise MessageProcessingError(
                'Invalid "action" attributes: missing key "%s"' % k)

    def handle_param(self, attributes):
        """handle attributes associated to a "param" section"""
        try:
            self.params['cmd'] = attributes['cmd']
        except KeyError, k:
            raise MessageProcessingError(
                'Invalid "param" attributes: missing key "%s"' % k)

    def is_complete(self):
        """return whether every fields are set or not"""
        return  CSMessage.is_complete(self) \
            and self.action_type != '' \
            and self.action_target != '' \
            and self._param_got_all()

    def _param_got_all(self):
        """ensure that for the given action type, we've received at least every
        mandatory parameters
        """
        if self.action_type == 'shell':
            expected_params = ['cmd']
        else:
            # unknown action type
            raise MessageProcessingError('Unknown action type %s' % \
                self.action_type)
        # ---
        # '<=' stands for "is subset of" here
        return expected_params <= self.params.keys()

    def xml(self):
        """generate XML version of a control message"""
        out = StringIO()
        generator = XMLGenerator(out)
        msg_attr = {
            'type': self.type,
            'msgid': str(self.id)
        }
        generator.startElement('message', msg_attr)
        action_attr = {
            'type': self.action_type,
            'target': str(self.action_target)
        }
        generator.startElement('action', action_attr)
        for k, v in self.params.iteritems():
            generator.startElement('param', {str(k): str(v)})
            generator.endElement('param')
        generator.endElement('action')
        generator.endElement('message')
        xml_msg = out.getvalue()
        out.close()
        return xml_msg

class ACKMessage(CSMessage):
    """acknowledgement message"""

    ident = 'ACK'

    def __init__(self):
        """
        """
        CSMessage.__init__(self)
        self.type = ACKMessage.ident
        self.ack_id = -1

    def handle_message(self, attributes):
        """handle attributes associated to a "message" section"""
        CSMessage.handle_message(self, attributes)
        try:
            self.ack_id = attributes['ack']
        except KeyError, k:
            raise MessageProcessingError(
                'Invalid "message" attributes: missing key "%s"' % k)

    def is_complete(self):
        """return whether every fields are set or not"""
        base = CSMessage.is_complete(self)
        return base and self.ack_id > 0

    def xml(self):
        """generate XML version of an acknowledgement message"""
        out = StringIO()
        generator = XMLGenerator(out)
        msg_attr = {
            'type': self.type,
            'msgid': str(self.id),
            'ack': str(self.ack_id)
        }
        generator.startElement('message', msg_attr)
        generator.endElement('message')
        xml_msg = out.getvalue()
        out.close()
        return xml_msg

class ErrorMessage(CSMessage):
    """error message"""

    ident = 'ERR'

    def __init__(self):
        """
        """
        CSMessage.__init__(self)
        self.type = ErrorMessage.ident
        self.reason = ''

    def handle_message(self, attributes):
        """handle attributes associated to a "message" section"""
        CSMessage.handle_message(self, attributes)
        try:
            self.reason = attributes['reason']
        except KeyError, k:
            raise MessageProcessingError(
                'Invalid "message" attributes: missing key "%s"' % k)

    def is_complete(self):
        """return whether every fields are set or not"""
        base = CSMessage.is_complete(self)
        return base and self.reason != ''

    def xml(self):
        """generate XML version of an error message"""
        out = StringIO()
        generator = XMLGenerator(out)
        msg_attr = {
            'type': self.type,
            'msgid': str(self.id),
            'reason': self.reason,
        }
        generator.startElement('message', msg_attr)
        generator.endElement('message')
        xml_msg = out.getvalue()
        out.close()
        return xml_msg

class MessageProcessingError(Exception):
    """base exception raised when an error occurs while processing incoming or
    outgoing messages.
    """

