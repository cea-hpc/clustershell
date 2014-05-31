#
# Copyright CEA/DAM/DIF (2009-2014)
#  Contributor: Stephane THIELL <stephane.thiell@cea.fr>
#
# This file is part of the ClusterShell library.
#
# This software is governed by the CeCILL-C license under French law and
# abiding by the rules of distribution of free software.  You can  use,
# modify and/ or redistribute the software under the terms of the CeCILL-C
# license as circulated by CEA, CNRS and INRIA at the following URL
# "http://www.cecill.info".
#
# As a counterpart to the access to the source code and  rights to copy,
# modify and redistribute granted by the license, users are provided only
# with a limited warranty  and the software's author,  the holder of the
# economic rights,  and the successive licensors  have only  limited
# liability.
#
# In this respect, the user's attention is drawn to the risks associated
# with loading,  using,  modifying and/or developing or reproducing the
# software by the user in light of its specific status of free software,
# that may mean  that it is complicated to manipulate,  and  that  also
# therefore means  that it is reserved for developers  and  experienced
# professionals having in-depth computer knowledge. Users are therefore
# encouraged to load and test the software's suitability as regards their
# requirements in conditions enabling the security of their systems and/or
# data to be ensured and,  more generally, to use and operate it in the
# same conditions as regards security.
#
# The fact that you are presently reading this means that you have had
# knowledge of the CeCILL-C license and that you accept its terms.

"""
EngineClient

ClusterShell engine's client interface.

An engine client is similar to a process, you can start/stop it, read data from
it and write data to it. Multiple data channels are supported (eg. stdin, stdout
and stderr, or even more...)
"""

import errno
import os
import Queue
import thread

from ClusterShell.Worker.fastsubprocess import Popen, PIPE, STDOUT, \
    set_nonblock_flag

from ClusterShell.Engine.Engine import EngineBaseTimer, E_READ, E_WRITE


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
        self.rbuf = ""
        self.wbuf = ""
        self.eof = False
        self.evmask = evmask
        self.events = 0
        self.new_events = 0
        self.set_file(sfile)

    def set_file(self, sfile, evmask=0):
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

    def __repr__(self):
        return "<%s at 0x%s (fd=%s rbuflen=%d wbuflen=%d eof=%d evmask=0x%x)>" \
            % (self.__class__.__name__, id(self), self.fd, len(self.rbuf), \
               len(self.wbuf), self.eof, self.evmask)

    def close(self):
        """Close stream."""
        os.close(self.fd)

    def readable(self):
        """Return whether the stream is setup as readable."""
        return self.evmask & E_READ

    def writable(self):
        """Return whether the stream is setup as writable."""
        return self.evmask & E_WRITE


class EngineClientStreamDict(dict):
    """EngineClient's named stream dictionary."""

    def add(self, fname, sfile=None, evmask=0):
        """Add file object or file descriptor to this pool."""
        engfile = dict.setdefault(self, fname, EngineClientStream(fname))
        engfile.set_file(sfile, evmask)
        return engfile

    def add_reader(self, fname, sfile=None):
        """Add readable file object or file descriptor to this pool."""
        self.add(fname, sfile, E_READ)

    def add_writer(self, fname, sfile=None):
        """Add writable file object or file descriptor to this pool."""
        self.add(fname, sfile, E_WRITE)

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

    def readers(self):
        """Convenience method to get an iterator on streams setup as
        readable."""
        return [s for s in self.values() if \
                (s.fd is not None) and s.evmask & E_READ]

    def writers(self):
        """Convenience method to get an iterator on streams setup as
        writable."""
        return [s for s in self.values() if \
                (s.fd is not None) and s.evmask & E_WRITE]

    def events(self):
        """Return all interest event bitmask for this stream dict."""
        result = 0
        for stream in self.values():
            result |= stream.events
        return result


class EngineClient(EngineBaseTimer):
    """
    Abstract class EngineClient.
    """

    def __init__(self, worker, stderr, timeout, autoclose):
        """
        Initializer. Should be called from derived classes.
        """
        EngineBaseTimer.__init__(self, timeout, -1, autoclose)

        self._reg_epoch = 0                 # registration generation number

        # read-only public
        self.registered = False             # registered on engine or not
        self.delayable = True               # subject to fanout limit

        self.worker = worker

        # boolean indicating whether stderr is on a separate fd
        self._stderr = stderr

        # streams associated with this client
        self.streams = EngineClientStreamDict()

    def _fire(self):
        """
        Fire timeout timer.
        """
        if self._engine:
            self._engine.remove(self, abort=True, did_timeout=True)

    def _start(self):
        """
        Starts client and returns client instance as a convenience.
        Derived classes (except EnginePort) must implement.
        """
        raise NotImplementedError("Derived classes must implement.")

    def _close(self, abort, timeout):
        """
        Close client. Called by the engine after client has been unregistered.
        This method should handle both termination types (normal or aborted)
        and should set timeout status accordingly.

        Derived classes must implement.
        """
        raise NotImplementedError("Derived classes must implement.")

    def _close_stream(self, fname):
        """
        Close specific stream by name (internal, called by engine). This method
        is the regular way to close a stream flushing read buffers accordingly.
        """
        self._flush_read(fname)
        del self.streams[fname]

    def _set_reading(self, fname):
        """
        Set reading state.
        """
        self._engine.set_reading(self, fname)

    def _set_writing(self, fname):
        """
        Set writing state.
        """
        self._engine.set_writing(self, fname)

    def _read(self, fname, size=65536):
        """
        Read data from process.
        """
        result = os.read(self.streams[fname].fd, size)
        if len(result) == 0:
            raise EngineClientEOF()
        self._set_reading(fname)
        return result

    def _flush_read(self, fname):
        """Called when stream is closing to flush read buffers."""
        pass # derived classes may implement

    def _handle_read(self, fname):
        """
        Handle a read notification. Called by the engine as the result of an
        event indicating that a read is available.
        """
        raise NotImplementedError("Derived classes must implement.")

    def _handle_write(self, fname):
        """
        Handle a write notification. Called by the engine as the result of an
        event indicating that a write can be performed now.
        """
        wfile = self.streams[fname]
        if not wfile.wbuf and wfile.eof:
            # remove stream from engine (not directly)
            self._engine.remove_stream(self, wfile)
        elif len(wfile.wbuf) > 0:
            try:
                wcnt = os.write(wfile.fd, wfile.wbuf)
            except OSError, exc:
                if (exc.errno == errno.EAGAIN):
                    self._set_writing(fname)
                    return
                raise
            if wcnt > 0:
                # dequeue written buffer
                wfile.wbuf = wfile.wbuf[wcnt:]
                # check for possible ending
                if wfile.eof and not wfile.wbuf:
                    # remove stream from engine (not directly)
                    self._engine.remove_stream(self, wfile)
                else:
                    self._set_writing(fname)

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
            self.streams.add('stderr', proc.stderr, E_READ)
        self.streams.add('stdout', proc.stdout, E_READ)
        self.streams.add('stdin', proc.stdin, E_WRITE)

        return proc

    def _readlines(self, fname):
        """Utility method to read client lines."""
        # read a chunk of data, may raise eof
        readbuf = self._read(fname)
        assert len(readbuf) > 0, "assertion failed: len(readbuf) > 0"

        # Current version implements line-buffered reads. If needed, we could
        # easily provide direct, non-buffered, data reads in the future.

        rfile = self.streams[fname]

        buf = rfile.rbuf + readbuf
        lines = buf.splitlines(True)
        rfile.rbuf = ""
        for line in lines:
            if line.endswith('\n'):
                if line.endswith('\r\n'):
                    yield line[:-2] # trim CRLF
                else:
                    # trim LF
                    yield line[:-1] # trim LF
            else:
                # keep partial line in buffer
                rfile.rbuf = line
                # breaking here

    def _write(self, fname, buf):
        """Add some data to be written to the client."""
        try:
            wfile = self.streams[fname]
        except KeyError:
            wfile = self.streams.add(fname)

        if wfile.fd:
            wfile.wbuf += buf
            # give it a try now (will set writing flag anyhow)
            self._handle_write(fname)
        else:
            # bufferize until pipe is ready
            wfile.wbuf += buf

    def _set_write_eof(self, fname):
        """Set EOF on specific writable stream"""
        try:
            wfile = self.streams[fname]
        except KeyError:
            wfile = self.streams.add(fname)
        wfile.eof = True
        if wfile.fd and not wfile.wbuf:
            # sendq empty, remove stream now
            self._engine.remove_stream(self, wfile)

    def abort(self):
        """Abort processing any action by this client."""
        if self._engine:
            self._engine.remove(self, abort=True)

class EnginePort(EngineClient):
    """
    An EnginePort is an abstraction object to deliver messages
    reliably between tasks.
    """

    class _Msg:
        """Private class representing a port message.
        
        A port message may be any Python object.
        """

        def __init__(self, user_msg, sync):
            self._user_msg = user_msg
            self._sync_msg = sync
            self.reply_lock = thread.allocate_lock()
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

    def __init__(self, task, handler=None, autoclose=False):
        """
        Initialize EnginePort object.
        """
        EngineClient.__init__(self, None, False, -1, autoclose)
        self.task = task
        self.eh = handler
        # ports are no subject to fanout
        self.delayable = False

        # Port messages queue
        self._msgq = Queue.Queue(self.task.default("port_qlimit"))

        # Request pipe
        (readfd, writefd) = os.pipe()
        # Set nonblocking flag
        set_nonblock_flag(readfd)
        set_nonblock_flag(writefd)
        self.streams.add('in', readfd, E_READ)
        self.streams.add('out', writefd, E_WRITE)

    def __repr__(self):
        try:
            fd_in = self.streams['in'].fd
        except KeyError:
            fd_in = None
        try:
            fd_out = self.streams['out'].fd
        except KeyError:
            fd_out = None
        return "<%s at 0x%s (streams=(%d, %d))>" % (self.__class__.__name__, \
                                                    id(self), fd_in, fd_out)

    def _start(self):
        return self

    def _close(self, abort, timeout):
        """
        Close port pipes.
        """
        if not self._msgq.empty():
            # purge msgq
            try:
                while not self._msgq.empty():
                    pmsg = self._msgq.get(block=False)
                    if self.task.info("debug", False):
                        self.task.info("print_debug")(self.task,
                            "EnginePort: dropped msg: %s" % str(pmsg.get()))
            except Queue.Empty:
                pass
        self._msgq = None
        del self.streams['out']
        del self.streams['in']

    def _handle_read(self, fname):
        """
        Handle a read notification. Called by the engine as the result of an
        event indicating that a read is available.
        """
        readbuf = self._read(fname, 4096)
        for dummy_char in readbuf:
            # raise Empty if empty (should never happen)
            pmsg = self._msgq.get(block=False)
            self.eh.ev_msg(self, pmsg.get())

    def msg(self, send_msg, send_once=False):
        """
        Port message send method that will wait for acknowledgement
        unless the send_once parameter if set.
        """
        pmsg = EnginePort._Msg(send_msg, not send_once)
        self._msgq.put(pmsg, block=True, timeout=None)
        try:
            ret = os.write(self.streams['out'].fd, "M")
        except OSError:
            raise
        pmsg.sync()
        return ret == 1

    def msg_send(self, send_msg):
        """
        Port message send-once method (no acknowledgement).
        """
        self.msg(send_msg, send_once=True)


