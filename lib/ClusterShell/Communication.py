#!/usr/bin/env python
#
# Copyright CEA/DAM/DIF (2010, 2011, 2012)
#  Contributor: Henri DOREAU <henri.doreau@gmail.com>
#  Contributor: Stephane THIELL <stephane.thiell@cea.fr>
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

"""
ClusterShell inter-nodes communication module

This module contains the required material for nodes to communicate between each
others within the propagation tree. At the highest level, messages are instances
of several classes. They can be converted into XML to be sent over SSH links
through a Channel instance.

In the other side, XML is parsed and new message objects are instanciated.

Communication channels have been implemented as ClusterShell events handlers.
Whenever a message chunk is read, the data is given to a SAX XML parser, that
will use it to create corresponding messages instances as a messages factory.

As soon as an instance is ready, it is then passed to a recv() method in the
channel. The recv() method of the Channel class is a stub, that requires to be
implemented in subclass to process incoming messages. So is the start() method
too.

Subclassing the Channel class allows implementing whatever logic you want on the
top of a communication channel.
"""

import cPickle
import base64
import logging
import xml.sax

from xml.sax.handler import ContentHandler
from xml.sax.saxutils import XMLGenerator
from xml.sax import SAXParseException

from collections import deque
from cStringIO import StringIO

from ClusterShell.Event import EventHandler


def strdel(s, badchars):
    """return s a copy of s with every badchar occurences removed"""
    stripped = s
    for ch in badchars:
        stripped = stripped.replace(ch, '')
    return stripped

class MessageProcessingError(Exception):
    """base exception raised when an error occurs while processing incoming or
    outgoing messages.
    """

class XMLReader(ContentHandler):
    """SAX handler for XML -> Messages instances conversion"""
    def __init__(self):
        """
        """
        ContentHandler.__init__(self)
        self.msg_queue = deque()
        # current packet under construction
        self._draft = None
        self._sections_map = None

    def startElement(self, name, attrs):
        """read a starting xml tag"""
        if name == 'channel':
            pass
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
            self._draft = None
        elif name == 'channel':
            self.msg_queue.append(EndMessage())

    def characters(self, content):
        """read content characters"""
        if self._draft is not None:
            content = content.decode('utf-8')
            #content = strdel(content, [' ', '\t', '\r', '\n'])
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
            ErrorMessage.ident: ErrorMessage,
            StdOutMessage.ident: StdOutMessage,
            StdErrMessage.ident: StdErrMessage,
            RetcodeMessage.ident: RetcodeMessage,
            TimeoutMessage.ident: TimeoutMessage,
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
        
        if name == 'message':
            self._draft.selfbuild(attributes)
        else:
            raise MessageProcessingError('Invalid tag %s' % name)

class Channel(EventHandler):
    """Use this event handler to establish a communication channel between to
    hosts whithin the propagation tree.

    The endpoint's logic has to be implemented by subclassing the Channel class
    and overriding the start() and recv() methods.
    
    There is no default behavior for these methods apart raising a
    NotImplementedError.
    
    Usage:
      >> chan = MyChannel() # inherits Channel
      >> task = task_self()
      >> task.shell("uname -a", node="host2", handler=chan)
      >> task.resume()
    """
    def __init__(self):
        """
        """
        EventHandler.__init__(self)
        
        self.exit = False
        self.worker = None

        self._xml_reader = XMLReader()
        self._parser = xml.sax.make_parser(["IncrementalParser"])
        self._parser.setContentHandler(self._xml_reader)

        self.logger = logging.getLogger(__name__)

    def _open(self):
        """open a new communication channel from src to dst"""
        generator = XMLGenerator(self.worker, encoding='UTF-8')
        generator.startDocument()
        generator.startElement('channel', {})

    def _close(self):
        """close an already opened channel"""
        generator = XMLGenerator(self.worker)
        generator.endElement('channel')
        # XXX
        self.worker.write('\n')
        self.exit = True

    def ev_start(self, worker):
        """connection established. Open higher level channel"""
        self.worker = worker
        self.start()

    def ev_written(self, worker):
        if self.exit:
            self.logger.debug("aborting worker after last write")
            self.worker.abort()

    def ev_read(self, worker):
        """channel has data to read"""
        raw = worker.current_msg
        #self.logger.debug("ev_read raw=\'%s\'" % raw)
        try:
            self._parser.feed(raw + '\n')
        except SAXParseException, ex:
            raise MessageProcessingError( \
                'Invalid communication (%s): "%s"' % (ex.getMessage(), raw))

        # pass next message to the driver if ready
        if self._xml_reader.msg_available():
            msg = self._xml_reader.pop_msg()
            assert msg is not None
            self.recv(msg)

    def send(self, msg):
        """write an outgoing message as its XML representation"""
        #print '[DBG] send: %s' % str(msg)
        #self.logger.debug("SENDING to %s: \"%s\"" % (self.worker, msg.xml()))
        self.worker.write(msg.xml() + '\n')

    def start(self):
        """initialization logic"""
        raise NotImplementedError('Abstract method: subclasses must implement')
    
    def recv(self, msg):
        """callback: process incoming message"""
        raise NotImplementedError('Abstract method: subclasses must implement')

class Message(object):
    """base message class"""
    _inst_counter = 0
    ident = 'GEN'

    def __init__(self):
        """
        """
        self.attr = {'type': str, 'msgid': int}
        self.type = self.__class__.ident
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
        #self.logger.debug("data_update raw=%s" % raw)
        self.data += raw

    def selfbuild(self, attributes):
        """self construction from a table of attributes"""
        for k, fmt in self.attr.iteritems():
            try:
                setattr(self, k, fmt(attributes[k]))
            except KeyError:
                raise MessageProcessingError(
                    'Invalid "message" attributes: missing key "%s"' % k)

    def __str__(self):
        """printable representation"""
        elts = ['%s: %s' % (k, str(self.__dict__[k])) for k in self.attr.keys()]
        attributes = ', '.join(elts)
        return "Message %s (%s)" % (self.type, attributes)

    def xml(self):
        """generate XML version of a configuration message"""
        out = StringIO()
        generator = XMLGenerator(out)

        # "stringify" entries for XML conversion
        state = {}
        for k in self.attr:
            state[k] = str(getattr(self, k))

        generator.startElement('message', state)
        generator.characters(self.data)
        generator.endElement('message')
        xml_msg = out.getvalue()
        out.close()
        return xml_msg

class ConfigurationMessage(Message):
    """configuration propagation container"""
    ident = 'CFG'

class RoutedMessageBase(Message):
    """abstract class for routed message (with worker source id)"""
    def __init__(self, srcid):
        Message.__init__(self)
        self.attr.update({'srcid': int})
        self.srcid = srcid

class ControlMessage(RoutedMessageBase):
    """action request"""
    ident = 'CTL'

    def __init__(self, srcid=0):
        """
        """
        RoutedMessageBase.__init__(self, srcid)
        self.attr.update({'action': str, 'target': str})
        self.action = ''
        self.target = ''

class ACKMessage(Message):
    """acknowledgement message"""
    ident = 'ACK'

    def __init__(self, ackid=0):
        """
        """
        Message.__init__(self)
        self.attr.update({'ack': int})
        self.ack = ackid

    def data_update(self, raw):
        """override method to ensure that incoming ACK messages don't contain
        unexpected payloads
        """
        raise MessageProcessingError('ACK messages have no payload')

class ErrorMessage(Message):
    """error message"""
    ident = 'ERR'

    def __init__(self, err=''):
        """
        """
        Message.__init__(self)
        self.attr.update({'reason': str})
        self.reason = err

    def data_update(self, raw):
        """override method to ensure that incoming ACK messages don't contain
        unexpected payloads
        """
        raise MessageProcessingError('Error message have no payload')

class StdOutMessage(RoutedMessageBase):
    """container message for standard output"""
    ident = 'OUT'

    def __init__(self, nodes='', output='', srcid=0):
        """
        """
        RoutedMessageBase.__init__(self, srcid)
        self.attr.update({'nodes': str})
        self.nodes = nodes
        self.data = output

class StdErrMessage(StdOutMessage):
    ident = 'SER'

class RetcodeMessage(RoutedMessageBase):
    """container message for return code"""
    ident = 'RET'

    def __init__(self, nodes='', retcode=0, srcid=0):
        """
        """
        RoutedMessageBase.__init__(self, srcid)
        self.attr.update({'retcode': int, 'nodes': str})
        self.retcode = retcode
        self.nodes = nodes

    def data_update(self, raw):
        """override method to ensure that incoming ACK messages don't contain
        unexpected payloads
        """
        raise MessageProcessingError('Retcode message has no payload')

class TimeoutMessage(RoutedMessageBase):
    """container message for timeout notification"""
    ident = 'TIM'

    def __init__(self, nodes='', srcid=0):
        """
        """
        RoutedMessageBase.__init__(self, srcid)
        self.attr.update({'nodes': str})
        self.nodes = nodes

class EndMessage(Message):
    """end of channel message"""
    ident = 'END'

