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
will use it to create corresponding messages instances as a messages factory.

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

class XMLReader(ContentHandler):
    """SAX handler for XML -> Messages instances conversion"""
    def __init__(self):
        """
        """
        ContentHandler.__init__(self)
        self.msg_queue = deque()
        self.name = ''
        self.parent = ''
        # current packet under construction
        self._draft = None
        self._sections_map = None

    def startElement(self, name, attrs):
        """read a starting xml tag"""
        if name == 'channel':
            self.name = attrs['dst']
            self.parent = attrs['src']
        elif name == 'message':
            self._draft_new(attrs)
        elif self._draft is not None:
            self._draft_update(name, attrs)
        else:
            raise MessageProcessingError('Invalid starting tag %s' % name)

    def endElement(self, name):
        """read an ending xml tag"""
        # end of message
        if name == 'message':
            self.msg_queue.appendleft(self._draft)

    def characters(self, content):
        """read content characters"""
        content = content.encode('utf-8')
        content = strdel(content, [' ', '\t', '\r', '\n'])
        if content != '':
            self._draft.data_update(content)

    def msg_available(self):
        """return whether a message is available for delivery or not"""
        return len(self.msg_queue) > 0

    def pop_msg(self):
        """pop and return the oldest message queued"""
        if len(self.msg_queue) > 0:
            return self.msg_queue.pop()

    def _draft_new(self, attributes):
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
        # obtain expected sections map for this type of messages
        self._draft_update('message', attributes)

    def _draft_update(self, name, attributes):
        """update the current message draft with a new section"""
        assert(self._draft is not None)
        handle = self._draft.tag_demux(name)
        handle(attributes)

class Channel(EventHandler):
    """Use this event handler to establish a communication channel between to
    hosts whithin the propagation tree.

    Instances use a driver that describes their behavior, and send/recv messages
    over the channel.
    """
    def __init__(self, driver):
        """
        """
        EventHandler.__init__(self)
        self.driver = driver
        driver.channel = self
        self._handler = XMLReader()
        self._parser = xml.sax.make_parser(["IncrementalParser"])
        self._parser.setContentHandler(self._handler)

    def ev_start(self, worker):
        """connection established. Open higher level channel"""
        self.driver.worker = worker
        self.driver.run()

    def open(self, worker):
        """open a new communication channel from src to dst"""
        opener = u'<?xlm version="1.0" encoding="UTF-8"?>\n'
        out = StringIO()
        generator = XMLGenerator(out)
        channel_attr = {
            'src': self.driver.src,
            'dst': self.driver.dst
        }
        generator.startElement('channel', channel_attr)
        worker.write(opener + out.getvalue())

    def close(self, worker):
        """close an already opened channel"""
        out = StringIO()
        generator = XMLGenerator(out)
        generator.endElement('channel')
        worker.write(out.getvalue())

    def ev_read(self, worker):
        """channel has data to read"""
        _, raw = worker.last_read()
        self._parser.feed(raw)
        # pass next message to the driver if ready
        if self._handler.msg_available():
            msg = self._handler.pop_msg()
            assert msg is not None
            self.driver.recv(msg)

    def ev_hup(self, worker):
        """do some cleanup when the connection is over"""
        # TODO: call this statement on </channel>
        #self._parser.close()

class Driver:
    """describes the behavior of a communicating node"""
    def __init__(self, src, dst):
        """
        """
        self.exit = False
        self.src = src
        self.dst = dst
        self.channel = None # will be externally set by the channel
        self.worker = None

    def run(self):
        """main logic"""
        raise NotImplementedError('Abstract method: subclasses must implement')
    
    def recv(self, msg):
        """callback: process incoming message"""
        raise NotImplementedError('Abstract method: subclasses must implement')

    def send(self, msg):
        """return next outgoing message"""
        self.worker.write(msg.xml())

class Message:
    """base message class"""
    _inst_counter = 0
    ident = 'GEN'

    def __init__(self):
        """
        """
        self.attr = ['type', 'msgid']
        self.type = Message.ident
        self.msgid = Message._inst_counter
        self.data = ''
        Message._inst_counter += 1

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

    def tag_demux(self, tagname):
        """return the funcion to use to handle an specific tag or raises a
        MessageProcessingError on failure
        """
        construction_map = {
            'message': self.handle_message
        }
        try:
            return construction_map[tagname]
        except KeyError:
            raise MessageProcessingError('Invalid tag %s' % tagname)

    def handle_message(self, attributes):
        """handle a "message" section"""
        for k in self.attr:
            if attributes.has_key(k):
                self.__dict__[k] = attributes[k]
            else:
                raise MessageProcessingError(
                    'Invalid "message" attributes: missing key "%s"' % k)

    def xml(self):
        """generate XML version of a configuration message"""
        out = StringIO()
        generator = XMLGenerator(out)

        # "stringify" entries for XML conversion
        state = {}
        for k in self.attr:
            state[k] = str(self.__dict__[k])

        generator.startElement('message', state)
        content = strdel(self.data, [' ', '\t', '\r', '\n'])
        generator.characters(content)
        generator.endElement('message')
        xml_msg = out.getvalue()
        out.close()
        return xml_msg

class ConfigurationMessage(Message):
    """configuration propagation container"""
    ident = 'CFG'

    def __init__(self):
        """
        """
        Message.__init__(self)
        self.type = ConfigurationMessage.ident

class ControlMessage(Message):
    """action request"""
    ident = 'CTL'

    def __init__(self):
        """
        """
        Message.__init__(self)
        self.attr += ['action', 'targets']
        self.type = ControlMessage.ident

class ACKMessage(Message):
    """acknowledgement message"""
    ident = 'ACK'

    def __init__(self):
        """
        """
        Message.__init__(self)
        self.attr += ['ack']
        self.type = ACKMessage.ident

    def data_update(self, raw):
        """override method to ensure that incoming ACK messages don't contain
        unexpected payloads
        """
        raise MessageProcessingError('ACK messages have no payload')

class ErrorMessage(Message):
    """error message"""
    ident = 'ERR'

    def __init__(self):
        """
        """
        Message.__init__(self)
        self.attr += ['reason']
        self.type = ErrorMessage.ident

    def data_update(self, raw):
        """override method to ensure that incoming ACK messages don't contain
        unexpected payloads
        """
        raise MessageProcessingError('Error message have no payload')

class MessageProcessingError(Exception):
    """base exception raised when an error occurs while processing incoming or
    outgoing messages.
    """

