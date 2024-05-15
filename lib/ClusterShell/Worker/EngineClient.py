#
# Copyright (C) 2009-2016 CEA/DAM
# Copyright (C) 2016-2017 Stephane Thiell <sthiell@stanford.edu>
#
# This file is part of ClusterShell.
#
# ClusterShell is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# ClusterShell is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with ClusterShell; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

"""
EngineClient

ClusterShell engine's client interface.

An engine client is similar to a process, you can start/stop it, read data from
it and write data to it. Multiple data channels are supported (eg. stdin, stdout
and stderr, or even more...)
"""

import errno
import logging
import os

try:
    import queue
except ImportError:
    # Python 2 compatibility
    import Queue as queue

import threading

from ClusterShell.Defaults import DEFAULTS
from ClusterShell.Worker.fastsubprocess import Popen, PIPE, STDOUT, \
    set_nonblock_flag
from ClusterShell.Engine.Engine import EngineBaseTimer, E_READ, E_WRITE


LOGGER = logging.getLogger(__name__)


class EngineClientException(Exception):
    """Generic EngineClient exception."""

class EngineClientEOF(EngineClientException):
    """EOF from client."""

class EngineClientError(EngineClientException):
    """Base EngineClient error exception."""

class EngineClientNotSupportedError(EngineClientError):
    """Operation not supported by EngineClient."""


class EngineClientStream(object):
    """EngineClient I/O stream object.

    Internal object used by EngineClient to manage its Engine-registered I/O
    streams. Each EngineClientStream is bound to a file object (file
    descriptor). It can be either an input, an output or a bidirectional
    stream (not used for now)."""

    def __init__(self, name, sfile=None, evmask=0):
        """Initialize an EngineClientStream object.

        @param name: Name of stream.
        @param sfile: File object or file descriptor.
        @param evmask: Config I/O event bitmask.
        """
        self.name = name
        self.fd = None
        self.rbuf = bytes()
        self.wbuf = bytes()
        self.eof = False
        self.evmask = evmask
        self.events = 0
        self.new_events = 0
        self.retain = False
        self.closefd = False
        self.set_file(sfile)

    def set_file(self, sfile, evmask=0, retain=True, closefd=True):
        """
        Set the stream file and event mask for this object.
        sfile should be a file object or a file descriptor.
        Event mask can be either E_READ, E_WRITE or both.
        Currently does NOT retain file object.
        """
        try:
            # file descriptor
            self.fd = sfile.fileno()
        except AttributeError:
            self.fd = sfile
        # Set I/O event mask
        self.evmask = evmask
        # Set retain flag
        self.retain = retain
        # Set closefd flag
        self.closefd = closefd

    def __repr__(self):
        return "<%s at 0x%s (name=%s fd=%s rbuflen=%d wbuflen=%d eof=%d " \
            "evmask=0x%x)>" % (self.__class__.__name__, id(self), self.name,
            self.fd, len(self.rbuf), len(self.wbuf), self.eof, self.evmask)

    def close(self):
        """Close stream."""
        if self.closefd and self.fd is not None:
            os.close(self.fd)

    def readable(self):
        """Return whether the stream is setup as readable."""
        return self.evmask & E_READ

    def writable(self):
        """Return whether the stream is setup as writable."""
        return self.evmask & E_WRITE


class EngineClientStreamDict(dict):
    """EngineClient's named stream dictionary."""

    def set_stream(self, sname, sfile=None, evmask=0, retain=True,
                   closefd=True):
        """Set stream based on file object or file descriptor.

        This method can be used to add a stream or update its
        parameters.
        """
        engfile = dict.setdefault(self, sname, EngineClientStream(sname))
        engfile.set_file(sfile, evmask, retain, closefd)
        return engfile

    def set_reader(self, sname, sfile=None, retain=True, closefd=True):
        """Set readable stream based on file object or file descriptor."""
        self.set_stream(sname, sfile, E_READ, retain, closefd)

    def set_writer(self, sname, sfile=None, retain=True, closefd=True):
        """Set writable stream based on file object or file descriptor."""
        self.set_stream(sname, sfile, E_WRITE, retain, closefd)

    def destroy(self, key):
        """Close file object and remove it from this pool."""
        self[key].close()
        dict.pop(self, key)

    def __delitem__(self, key):
        self.destroy(key)

    def clear(self):
        """Clear File Pool"""
        for stream in self.values():
            stream.close()
        dict.clear(self)

    def active_readers(self):
        """Get an iterator on readable streams (with fd set)."""
        return (s for s in self.readers() if s.fd is not None)

    def readers(self):
        """Get an iterator on all streams setup as readable."""
        return (s for s in list(self.values()) if s.evmask & E_READ)

    def active_writers(self):
        """Get an iterator on writable streams (with fd set)."""
        return (s for s in self.writers() if s.fd is not None)

    def writers(self):
        """Get an iterator on all streams setup as writable."""
        return (s for s in list(self.values()) if s.evmask & E_WRITE)

    def retained(self):
        """Check whether this set of streams is retained.

        Note on retain: an active stream with retain=True keeps the
        engine client alive. When only streams with retain=False
        remain, the engine client terminates.

        Return:
            True -- when at least one stream is retained
            False -- when no retainable stream remain
        """
        for stream in self.values():
            if stream.fd is not None and stream.retain:
                return True
        return False


class EngineClient(EngineBaseTimer):
    """
    Abstract class EngineClient.
    """

    def __init__(self, worker, key, stderr, timeout, autoclose):
        """EngineClient initializer.

        Should be called from derived classes.

        Arguments:
            worker -- parent worker instance
            key -- client key used by MsgTree (eg. node name)
            stderr -- boolean set if stderr is on a separate stream
            timeout -- client execution timeout value (float)
            autoclose -- boolean set to indicate whether this engine
                         client should be aborted as soon as all other
                         non-autoclosing clients have finished.
        """

        EngineBaseTimer.__init__(self, timeout, -1, autoclose)

        self._reg_epoch = 0                 # registration generation number

        # read-only public
        self.registered = False             # registered on engine or not
        self.delayable = True               # subject to fanout limit

        self.worker = worker
        if key is None:
            key = id(worker)
        self.key = key

        # boolean indicating whether stderr is on a separate fd
        self._stderr = stderr

        # streams associated with this client
        self.streams = EngineClientStreamDict()

    def __repr__(self):
        # added repr(self.key)
        return '<%s.%s instance at 0x%x key %r>' % (self.__module__,
                                                    self.__class__.__name__,
                                                    id(self), self.key)

    def _fire(self):
        """
        Fire timeout timer.
        """
        if self._engine:
            self._engine.remove(self, abort=True, did_timeout=True)

    def _start(self):
        """
        Starts client and returns client instance as a convenience.
        Derived classes must implement.
        """
        raise NotImplementedError("Derived classes must implement.")

    def _close(self, abort, timeout):
        """
        Close client. Called by the engine after client has been unregistered.
        This method should handle both termination types (normal or aborted)
        and should set timeout status accordingly.

        Derived classes should implement.
        """
        for sname in list(self.streams):
            self._close_stream(sname)

        self.invalidate()  # set self._engine to None

    def _close_stream(self, sname):
        """
        Close specific stream by name (internal, called by engine). This method
        is the regular way to close a stream flushing read buffers accordingly.
        """
        self._flush_read(sname)
        # flush_read() is useful but may generate user events (ev_read) that
        # could lead to worker abort and then ev_close. Be careful there.
        if sname in self.streams:
            del self.streams[sname]

    def _set_reading(self, sname):
        """
        Set reading state.
        """
        self._engine.set_reading(self, sname)

    def _set_writing(self, sname):
        """
        Set writing state.
        """
        self._engine.set_writing(self, sname)

    def _read(self, sname, size=65536):
        """
        Read data from process.
        """
        result = os.read(self.streams[sname].fd, size)
        if len(result) == 0:
            raise EngineClientEOF()
        self._set_reading(sname)
        return result

    def _flush_read(self, sname):
        """Called when stream is closing to flush read buffers."""
        pass # derived classes may implement

    def _handle_read(self, sname):
        """
        Handle a read notification. Called by the engine as the result of an
        event indicating that a read is available.
        """
        raise NotImplementedError("Derived classes must implement.")

    def _handle_write(self, sname):
        """
        Handle a write notification. Called by the engine as the result of an
        event indicating that a write can be performed now.
        """
        wfile = self.streams[sname]
        if not wfile.wbuf and wfile.eof:
            # remove stream from engine (not directly)
            if self._engine:
                self._engine.remove_stream(self, wfile)
        elif len(wfile.wbuf) > 0:
            try:
                wcnt = os.write(wfile.fd, wfile.wbuf)
            except OSError as exc:
                if exc.errno == errno.EAGAIN:
                    # _handle_write() is not only called by the engine but also
                    # by _write(), so this is legit: we just try again later
                    self._set_writing(sname)
                    return
                if exc.errno == errno.EPIPE:
                    # broken pipe: log warning message and do NOT retry
                    LOGGER.warning('%r: %s', self, exc)
                    return
                raise
            if wcnt > 0:
                # dequeue written buffer
                wfile.wbuf = wfile.wbuf[wcnt:]
                # check for possible ending
                if wfile.eof and not wfile.wbuf:
                    self.worker._on_written(self.key, wcnt, sname)
                    # remove stream from engine (not directly)
                    if self._engine:
                        self._engine.remove_stream(self, wfile)
                else:
                    self._set_writing(sname)
                    self.worker._on_written(self.key, wcnt, sname)

    def _exec_nonblock(self, commandlist, shell=False, env=None):
        """
        Utility method to launch a command with stdin/stdout file
        descriptors configured in non-blocking mode.
        """
        full_env = None
        if env:
            full_env = os.environ.copy()
            full_env.update(env)

        if self._stderr:
            stderr_setup = PIPE
        else:
            stderr_setup = STDOUT

        # Launch process in non-blocking mode
        proc = Popen(commandlist, bufsize=0, stdin=PIPE, stdout=PIPE,
                     stderr=stderr_setup, shell=shell, env=full_env)

        if self._stderr:
            self.streams.set_stream(self.worker.SNAME_STDERR, proc.stderr,
                                    E_READ)
        self.streams.set_stream(self.worker.SNAME_STDOUT, proc.stdout, E_READ)
        self.streams.set_stream(self.worker.SNAME_STDIN, proc.stdin, E_WRITE,
                                retain=False)

        return proc

    def _readlines(self, sname):
        """Utility method to read client lines."""
        # read a chunk of data, may raise eof
        readbuf = self._read(sname)
        assert len(readbuf) > 0, "assertion failed: len(readbuf) > 0"

        # Current version implements line-buffered reads. If needed, we could
        # easily provide direct, non-buffered, data reads in the future.

        rfile = self.streams[sname]

        buf = rfile.rbuf + readbuf
        lines = buf.splitlines(True)
        rfile.rbuf = bytes()
        for line in lines:
            if line.endswith(b'\n'):
                if line.endswith(b'\r\n'):
                    yield line[:-2] # trim CRLF
                else:
                    # trim LF
                    yield line[:-1] # trim LF
            else:
                # keep partial line in buffer
                rfile.rbuf = line
                # breaking here

    def _write(self, sname, buf):
        """Add some data to be written to the client."""
        wfile = self.streams[sname]
        if self._engine and wfile.fd:
            wfile.wbuf += buf
            # give it a try now (will set writing flag anyhow)
            self._handle_write(sname)
        else:
            # bufferize until pipe is ready
            wfile.wbuf += buf

    def _set_write_eof(self, sname):
        """Set EOF on specific writable stream."""
        if sname not in self.streams:
            LOGGER.debug("stream %s was already closed on client %s, skipping",
                         sname, self.key)
            return

        wfile = self.streams[sname]
        wfile.eof = True
        if self._engine and wfile.fd and not wfile.wbuf:
            # sendq empty, remove stream now
            self._engine.remove_stream(self, wfile)

    def abort(self):
        """Abort processing any action by this client.

        Safe to call on an already closing or aborting client.
        """
        engine = self._engine
        if engine:
            self.invalidate()  # set self._engine to None
            engine.remove(self, abort=True)


class EnginePort(EngineClient):
    """
    An EnginePort is an abstraction object to deliver messages
    reliably between tasks.
    """

    class _Msg(object):
        """Private class representing a port message.

        A port message may be any Python object.
        """

        def __init__(self, user_msg, sync):
            self._user_msg = user_msg
            self._sync_msg = sync
            self.reply_lock = threading.Lock()
            self.reply_lock.acquire()

        def get(self):
            """
            Get and acknowledge message.
            """
            self.reply_lock.release()
            return self._user_msg

        def sync(self):
            """
            Wait for message acknowledgment if needed.
            """
            if self._sync_msg:
                self.reply_lock.acquire()

    def __init__(self, handler=None, autoclose=False):
        """
        Initialize EnginePort object.
        """
        EngineClient.__init__(self, None, None, False, -1, autoclose)
        self.eh = handler
        # ports are no subject to fanout
        self.delayable = False

        # Port messages queue
        self._msgq = queue.Queue(DEFAULTS.port_qlimit)

        # Request pipe
        (readfd, writefd) = os.pipe()
        # Set nonblocking flag
        set_nonblock_flag(readfd)
        set_nonblock_flag(writefd)
        self.streams.set_stream('in', readfd, E_READ)
        self.streams.set_stream('out', writefd, E_WRITE)

    def __repr__(self):
        try:
            fd_in = self.streams['in'].fd
        except KeyError:
            fd_in = None
        try:
            fd_out = self.streams['out'].fd
        except KeyError:
            fd_out = None
        return "<%s at 0x%s (streams=(%s, %s))>" % (self.__class__.__name__,
                                                    id(self), fd_in, fd_out)

    def _start(self):
        """Start port."""
        if self.eh is not None:
            self.eh.ev_port_start(self)
        return self

    def _close(self, abort, timeout):
        """Close port."""
        if not self._msgq.empty():
            # purge msgq
            try:
                while not self._msgq.empty():
                    pmsg = self._msgq.get(block=False)
                    LOGGER.debug('%r: dropped msg: %s', self, pmsg.get())
            except queue.Empty:
                pass
        self._msgq = None
        del self.streams['out']
        del self.streams['in']
        self.invalidate()

    def _handle_read(self, sname):
        """
        Handle a read notification. Called by the engine as the result of an
        event indicating that a read is available.
        """
        readbuf = self._read(sname, 4096)
        for dummy_char in readbuf:
            # raise Empty if empty (should never happen)
            pmsg = self._msgq.get(block=False)
            self.eh.ev_msg(self, pmsg.get())

    def msg(self, send_msg, send_once=False):
        """
        Port message send method that will wait for acknowledgement
        unless the send_once parameter if set.

        May be called from another thread. Will generate ev_msg() on
        Port event handler (in Port task/thread).

        Return False if the message cannot be sent (eg. port closed).
        """
        if self._msgq is None: # called after port closed?
            return False

        pmsg = EnginePort._Msg(send_msg, not send_once)
        self._msgq.put(pmsg, block=True, timeout=None)
        try:
            ret = os.write(self.streams['out'].fd, b'M')
        except OSError:
            raise
        pmsg.sync()
        return ret == 1

    def msg_send(self, send_msg):
        """
        Port message send-once method (no acknowledgement). See msg().

        Return False if the message cannot be sent (eg. port closed).
        """
        return self.msg(send_msg, send_once=True)
