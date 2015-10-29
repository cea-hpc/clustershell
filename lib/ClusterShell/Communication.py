#!/usr/bin/env python
#
# Copyright CEA/DAM/DIF (2010-2015)
#  Contributor: Henri DOREAU <henri.doreau@cea.fr>
#  Contributor: Stephane THIELL <sthiell@stanford.edu>
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

from ClusterShell import __version__
from ClusterShell.Event import EventHandler


ENCODING = 'utf-8'


class MessageProcessingError(Exception):
    """base exception raised when an error occurs while processing incoming or
    outgoing messages.
    """


class XMLReader(ContentHandler):
    """SAX handler for XML -> Messages instances conversion"""
    def __init__(self):
        """XMLReader initializer"""
        ContentHandler.__init__(self)
        self.msg_queue = deque()
        self.version = None
        # current packet under construction
        self._draft = None
        self._sections_map = None

    def startElement(self, name, attrs):
        """read a starting xml tag"""
        if name == 'channel':
            self.version = attrs.get('version')
            self.msg_queue.appendleft(StartMessage())
        elif name == 'message':
            self._draft_new(attrs)
        else:
            raise MessageProcessingError('Invalid starting tag %s' % name)

    def endElement(self, name):
        """read an ending xml tag"""
        # end of message
        if name == 'message':
            self.msg_queue.appendleft(self._draft)
            self._draft = None
        elif name == 'channel':
            self.msg_queue.appendleft(EndMessage())

    def characters(self, content):
        """read content characters"""
        if self._draft is not None:
            content = content.decode(ENCODING)
            self._draft.data_update(content)

    def msg_available(self):
        """return whether a message is available for delivery or not"""
        return len(self.msg_queue) > 0

    def pop_msg(self):
        """pop and return the oldest message queued"""
        if self.msg_available():
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
        # build message with its attributes
        self._draft = ctor()
        self._draft.selfbuild(attributes)


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

    # Common channel stream names
    SNAME_WRITER = 'ch-writer'
    SNAME_READER = 'ch-reader'
    SNAME_ERROR = 'ch-error'

    def __init__(self, error_response=False):
        """
        """
        EventHandler.__init__(self)

        self.worker = None

        # channel state flags
        self.opened = False
        self.setup = False
        # will this channel send communication error responses?
        self.error_response = error_response

        self._xml_reader = XMLReader()
        self._parser = xml.sax.make_parser(["IncrementalParser"])
        self._parser.setContentHandler(self._xml_reader)

        self.logger = logging.getLogger(__name__)

    def _init(self):
        """start xml document for communication"""
        XMLGenerator(self.worker, encoding=ENCODING).startDocument()

    def _open(self):
        """open a new communication channel from src to dst"""
        xmlgen = XMLGenerator(self.worker, encoding=ENCODING)
        xmlgen.startElement('channel', {'version': __version__})

    def _close(self):
        """close an already opened channel"""
        send_endtag = self.opened
        # set to False before sending tag for state test purposes
        self.opened = self.setup = False
        if send_endtag:
            XMLGenerator(self.worker, encoding=ENCODING).endElement('channel')
        self.worker.abort()

    def ev_start(self, worker):
        """connection established. Open higher level channel"""
        self.worker = worker
        self.start()

    def ev_read(self, worker):
        """channel has data to read"""
        raw = worker.current_msg
        try:
            self._parser.feed(raw + '\n')
        except SAXParseException, ex:
            self.logger.error("SAXParseException: %s: %s", ex.getMessage(), raw)
            # Warning: do not send malformed raw message back
            if self.error_response:
                self.send(ErrorMessage('Parse error: %s' % ex.getMessage()))
            self._close()
            return
        except MessageProcessingError, ex:
            if self.error_response:
                self.send(ErrorMessage(str(ex)))
            self._close()
            return

        # pass messages to the driver if ready
        while self._xml_reader.msg_available():
            msg = self._xml_reader.pop_msg()
            assert msg is not None
            self.recv(msg)

    def send(self, msg):
        """write an outgoing message as its XML representation"""
        #self.logger.debug('SENDING to worker %s: "%s"', id(self.worker),
        #                  msg.xml())
        self.worker.write(msg.xml() + '\n', sname=self.SNAME_WRITER)

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
    has_payload = False

    def __init__(self):
        """
        """
        self.attr = {'type': str, 'msgid': int}
        self.type = self.__class__.ident
        self.msgid = Message._inst_counter
        self.data = None
        Message._inst_counter += 1

    def data_encode(self, inst):
        """serialize an instance and store the result"""
        self.data = base64.encodestring(cPickle.dumps(inst))

    def data_decode(self):
        """deserialize a previously encoded instance and return it"""
        # if self.data is None then an exception is raised here
        try:
            return cPickle.loads(base64.decodestring(self.data))
        except (EOFError, TypeError):
            # raised by cPickle.loads() if self.data is not valid
            raise MessageProcessingError('Message %s has an invalid payload'
                                         % self.ident)

    def data_update(self, raw):
        """append data to the instance (used for deserialization)"""
        if self.has_payload:
            if self.data is None:
                self.data = raw # first encoded packet
            else:
                self.data += raw
        else:
            # ensure that incoming messages don't contain unexpected payloads
            raise MessageProcessingError('Got unexpected payload for Message %s'
                                         % self.ident)

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
        generator = XMLGenerator(out, encoding=ENCODING)

        # "stringify" entries for XML conversion
        state = {}
        for k in self.attr:
            state[k] = str(getattr(self, k))

        generator.startElement('message', state)
        if self.data:
            generator.characters(self.data)
        generator.endElement('message')
        xml_msg = out.getvalue()
        out.close()
        return xml_msg

class ConfigurationMessage(Message):
    """configuration propagation container"""
    ident = 'CFG'
    has_payload = True

    def __init__(self, gateway=''):
        """initialize with gateway node name"""
        Message.__init__(self)
        self.attr.update({'gateway': str})
        self.gateway = gateway

class RoutedMessageBase(Message):
    """abstract class for routed message (with worker source id)"""
    def __init__(self, srcid):
        Message.__init__(self)
        self.attr.update({'srcid': int})
        self.srcid = srcid

class ControlMessage(RoutedMessageBase):
    """action request"""
    ident = 'CTL'
    has_payload = True

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

class ErrorMessage(Message):
    """error message"""
    ident = 'ERR'

    def __init__(self, err=''):
        """
        """
        Message.__init__(self)
        self.attr.update({'reason': str})
        self.reason = err

class StdOutMessage(RoutedMessageBase):
    """container message for standard output"""
    ident = 'OUT'
    has_payload = True

    def __init__(self, nodes='', output=None, srcid=0):
        """
        Initialized either with empty payload (to be loaded, already encoded),
        or with payload provided (via output to encode here).
        """
        RoutedMessageBase.__init__(self, srcid)
        self.attr.update({'nodes': str})
        self.nodes = nodes
        self.data = None # something encoded or None
        if output is not None:
            self.data_encode(output)

class StdErrMessage(StdOutMessage):
    """container message for stderr output"""
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

class TimeoutMessage(RoutedMessageBase):
    """container message for timeout notification"""
    ident = 'TIM'

    def __init__(self, nodes='', srcid=0):
        """
        """
        RoutedMessageBase.__init__(self, srcid)
        self.attr.update({'nodes': str})
        self.nodes = nodes

class StartMessage(Message):
    """message indicating the start of a channel communication"""
    ident = 'CHA'

class EndMessage(Message):
    """end of channel message"""
    ident = 'END'
