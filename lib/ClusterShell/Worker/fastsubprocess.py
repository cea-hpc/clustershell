# fastsubprocess - POSIX relaxed revision of subprocess.py
# Based on Python 2.6.4 subprocess.py
# This is a performance oriented version of subprocess module.
# Modified by Stephane Thiell
# Changes:
#   * removed Windows specific code parts
#   * removed pipe for transferring possible exec failure from child to
#     parent, to avoid os.read() blocking call after each fork.
#   * child returns status code 255 on execv failure, which can be
#     handled with Popen.wait().
#   * removed file objects creation using costly fdopen(): this version
#     returns non-blocking file descriptors bound to child
#   * added module method set_nonblock_flag() and used it in Popen().
##
# Original Disclaimer:
#
# For more information about this module, see PEP 324.
#
# This module should remain compatible with Python 2.2, see PEP 291.
#
# Copyright (c) 2003-2005 by Peter Astrand <astrand@lysator.liu.se>
#
# Licensed to PSF under a Contributor Agreement.
# See http://www.python.org/2.4/license for licensing details.

"""_subprocess - Subprocesses with accessible I/O non-blocking file
descriptors

Faster revision of subprocess-like module.
"""

import gc
import os
import signal
import sys
import types

# Python 3 compatibility
try:
    basestring
except NameError:
    basestring = str

# Exception classes used by this module.
class CalledProcessError(Exception):
    """This exception is raised when a process run by check_call() returns
    a non-zero exit status.  The exit status will be stored in the
    returncode attribute."""
    def __init__(self, returncode, cmd):
        self.returncode = returncode
        self.cmd = cmd
    def __str__(self):
        return "Command '%s' returned non-zero exit status %d" % (self.cmd,
            self.returncode)

import select
import errno
import fcntl

__all__ = ["Popen", "PIPE", "STDOUT", "call", "check_call", \
           "CalledProcessError"]

try:
    MAXFD = os.sysconf("SC_OPEN_MAX")
except:
    MAXFD = 256

_active = []

def _cleanup():
    for inst in _active[:]:
        if inst._internal_poll(_deadstate=sys.maxsize) >= 0:
            try:
                _active.remove(inst)
            except ValueError:
                # This can happen if two threads create a new Popen instance.
                # It's harmless that it was already removed, so ignore.
                pass

PIPE = -1
STDOUT = -2


def call(*popenargs, **kwargs):
    """Run command with arguments.  Wait for command to complete, then
    return the returncode attribute.

    The arguments are the same as for the Popen constructor.  Example:

    retcode = call(["ls", "-l"])
    """
    return Popen(*popenargs, **kwargs).wait()


def check_call(*popenargs, **kwargs):
    """Run command with arguments.  Wait for command to complete.  If
    the exit code was zero then return, otherwise raise
    CalledProcessError.  The CalledProcessError object will have the
    return code in the returncode attribute.

    The arguments are the same as for the Popen constructor.  Example:

    check_call(["ls", "-l"])
    """
    retcode = call(*popenargs, **kwargs)
    cmd = kwargs.get("args")
    if cmd is None:
        cmd = popenargs[0]
    if retcode:
        raise CalledProcessError(retcode, cmd)
    return retcode


def set_nonblock_flag(fd):
    """Set non blocking flag to file descriptor fd"""
    old = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, old | os.O_NDELAY)


class Popen(object):
    """A faster Popen"""
    def __init__(self, args, bufsize=0, executable=None,
                 stdin=None, stdout=None, stderr=None,
                 preexec_fn=None, shell=False,
                 cwd=None, env=None, universal_newlines=False):
        """Create new Popen instance."""
        _cleanup()

        self._child_created = False
        if not isinstance(bufsize, int):
            raise TypeError("bufsize must be an integer")

        self.pid = None
        self.returncode = None
        self.universal_newlines = universal_newlines

        # Input and output objects. The general principle is like
        # this:
        #
        # Parent                   Child
        # ------                   -----
        # p2cwrite   ---stdin--->  p2cread
        # c2pread    <--stdout---  c2pwrite
        # errread    <--stderr---  errwrite
        #
        # On POSIX, the child objects are file descriptors.  On
        # Windows, these are Windows file handles.  The parent objects
        # are file descriptors on both platforms.  The parent objects
        # are None when not using PIPEs. The child objects are None
        # when not redirecting.

        (p2cread, p2cwrite,
         c2pread, c2pwrite,
         errread, errwrite) = self._get_handles(stdin, stdout, stderr)

        self._execute_child(args, executable, preexec_fn,
                            cwd, env, universal_newlines, shell,
                            p2cread, p2cwrite,
                            c2pread, c2pwrite,
                            errread, errwrite)

        if p2cwrite is not None:
            set_nonblock_flag(p2cwrite)
        self.stdin = p2cwrite
        if c2pread is not None:
            set_nonblock_flag(c2pread)
        self.stdout = c2pread
        if errread is not None:
            set_nonblock_flag(errread)
        self.stderr = errread


    def _translate_newlines(self, data):
        data = data.replace("\r\n", "\n")
        data = data.replace("\r", "\n")
        return data


    def __del__(self, sys=sys):
        if not self._child_created:
            # We didn't get to successfully create a child process.
            return
        # In case the child hasn't been waited on, check if it's done.
        self._internal_poll(_deadstate=sys.maxsize)
        if self.returncode is None and _active is not None:
            # Child is still running, keep us alive until we can wait on it.
            _active.append(self)


    def communicate(self, input=None):
        """Interact with process: Send data to stdin.  Read data from
        stdout and stderr, until end-of-file is reached.  Wait for
        process to terminate.  The optional input argument should be a
        string to be sent to the child process, or None, if no data
        should be sent to the child.

        communicate() returns a tuple (stdout, stderr)."""

        # Optimization: If we are only using one pipe, or no pipe at
        # all, using select() or threads is unnecessary.
        if [self.stdin, self.stdout, self.stderr].count(None) >= 2:
            stdout = None
            stderr = None
            if self.stdin:
                if input:
                    self.stdin.write(input)
                self.stdin.close()
            elif self.stdout:
                stdout = self.stdout.read()
                self.stdout.close()
            elif self.stderr:
                stderr = self.stderr.read()
                self.stderr.close()
            self.wait()
            return (stdout, stderr)

        return self._communicate(input)


    def poll(self):
        return self._internal_poll()


    def _get_handles(self, stdin, stdout, stderr):
        """Construct and return tuple with IO objects:
        p2cread, p2cwrite, c2pread, c2pwrite, errread, errwrite
        """
        p2cread, p2cwrite = None, None
        c2pread, c2pwrite = None, None
        errread, errwrite = None, None

        if stdin is None:
            pass
        elif stdin == PIPE:
            p2cread, p2cwrite = os.pipe()
        elif isinstance(stdin, int):
            p2cread = stdin
        else:
            # Assuming file-like object
            p2cread = stdin.fileno()

        if stdout is None:
            pass
        elif stdout == PIPE:
            try:
                c2pread, c2pwrite = os.pipe()
            except:
                # Cleanup of previous pipe() descriptors
                if stdin == PIPE:
                    os.close(p2cread)
                    os.close(p2cwrite)
                raise
        elif isinstance(stdout, int):
            c2pwrite = stdout
        else:
            # Assuming file-like object
            c2pwrite = stdout.fileno()

        if stderr is None:
            pass
        elif stderr == PIPE:
            try:
                errread, errwrite = os.pipe()
            except:
                # Cleanup of previous pipe() descriptors
                if stdin == PIPE:
                    os.close(p2cread)
                    os.close(p2cwrite)
                if stdout == PIPE:
                    os.close(c2pread)
                    os.close(c2pwrite)
                raise
        elif stderr == STDOUT:
            errwrite = c2pwrite
        elif isinstance(stderr, int):
            errwrite = stderr
        else:
            # Assuming file-like object
            errwrite = stderr.fileno()

        return (p2cread, p2cwrite,
                c2pread, c2pwrite,
                errread, errwrite)


    def _execute_child(self, args, executable, preexec_fn,
                       cwd, env, universal_newlines, shell,
                       p2cread, p2cwrite,
                       c2pread, c2pwrite,
                       errread, errwrite):
        """Execute program (POSIX version)"""

        if isinstance(args, basestring):
            args = [args]
        else:
            args = list(args)

        if shell:
            args = ["/bin/sh", "-c"] + args

        if executable is None:
            executable = args[0]

        gc_was_enabled = gc.isenabled()
        # Disable gc to avoid bug where gc -> file_dealloc ->
        # write to stderr -> hang.  http://bugs.python.org/issue1336
        gc.disable()
        try:
            self.pid = os.fork()
        except:
            if gc_was_enabled:
                gc.enable()
            raise
        self._child_created = True
        if self.pid == 0:
            # Child
            try:
                # Close parent's pipe ends
                if p2cwrite is not None:
                    os.close(p2cwrite)
                if c2pread is not None:
                    os.close(c2pread)
                if errread is not None:
                    os.close(errread)

                # Dup fds for child
                if p2cread is not None:
                    os.dup2(p2cread, 0)
                if c2pwrite is not None:
                    os.dup2(c2pwrite, 1)
                if errwrite is not None:
                    os.dup2(errwrite, 2)

                # Close pipe fds.  Make sure we don't close the same
                # fd more than once, or standard fds.
                if p2cread is not None and p2cread not in (0,):
                    os.close(p2cread)
                if c2pwrite is not None and c2pwrite not in (p2cread, 1):
                    os.close(c2pwrite)
                if errwrite is not None and errwrite not in \
                        (p2cread, c2pwrite, 2):
                    os.close(errwrite)

                if cwd is not None:
                    os.chdir(cwd)

                if preexec_fn:
                    preexec_fn()

                if env is None:
                    os.execvp(executable, args)
                else:
                    os.execvpe(executable, args, env)
            except:
                # Child execution failure
                os._exit(255)

        # Parent
        if gc_was_enabled:
            gc.enable()

        if p2cread is not None and p2cwrite is not None:
            os.close(p2cread)
        if c2pwrite is not None and c2pread is not None:
            os.close(c2pwrite)
        if errwrite is not None and errread is not None:
            os.close(errwrite)


    def _handle_exitstatus(self, sts):
        if os.WIFSIGNALED(sts):
            self.returncode = -os.WTERMSIG(sts)
        elif os.WIFEXITED(sts):
            self.returncode = os.WEXITSTATUS(sts)
        else:
            # Should never happen
            raise RuntimeError("Unknown child exit status!")


    def _internal_poll(self, _deadstate=None):
        """Check if child process has terminated.  Returns returncode
        attribute."""
        if self.returncode is None:
            try:
                pid, sts = os.waitpid(self.pid, os.WNOHANG)
                if pid == self.pid:
                    self._handle_exitstatus(sts)
            except os.error:
                if _deadstate is not None:
                    self.returncode = _deadstate
        return self.returncode


    def wait(self):
        """Wait for child process to terminate.  Returns returncode
        attribute."""
        if self.returncode is None:
            pid, sts = os.waitpid(self.pid, 0)
            self._handle_exitstatus(sts)
        return self.returncode


    def _communicate(self, input):
        read_set = []
        write_set = []
        stdout = None # Return
        stderr = None # Return

        if self.stdin:
            # Flush stdio buffer.  This might block, if the user has
            # been writing to .stdin in an uncontrolled fashion.
            self.stdin.flush()
            if input:
                write_set.append(self.stdin)
            else:
                self.stdin.close()
        if self.stdout:
            read_set.append(self.stdout)
            stdout = []
        if self.stderr:
            read_set.append(self.stderr)
            stderr = []

        input_offset = 0
        while read_set or write_set:
            try:
                rlist, wlist, xlist = select.select(read_set, write_set, [])
            except select.error as ex:
                if ex.args[0] == errno.EINTR:
                    continue
                raise

            if self.stdin in wlist:
                # When select has indicated that the file is writable,
                # we can write up to PIPE_BUF bytes without risk
                # blocking.  POSIX defines PIPE_BUF >= 512
                chunk = input[input_offset : input_offset + 512]
                bytes_written = os.write(self.stdin.fileno(), chunk)
                input_offset += bytes_written
                if input_offset >= len(input):
                    self.stdin.close()
                    write_set.remove(self.stdin)

            if self.stdout in rlist:
                data = os.read(self.stdout.fileno(), 1024)
                if data == "":
                    self.stdout.close()
                    read_set.remove(self.stdout)
                stdout.append(data)

            if self.stderr in rlist:
                data = os.read(self.stderr.fileno(), 1024)
                if data == "":
                    self.stderr.close()
                    read_set.remove(self.stderr)
                stderr.append(data)

        # All data exchanged.  Translate lists into strings.
        if stdout is not None:
            stdout = ''.join(stdout)
        if stderr is not None:
            stderr = ''.join(stderr)

        # Translate newlines, if requested.  We cannot let the file
        # object do the translation: It is based on stdio, which is
        # impossible to combine with select (unless forcing no
        # buffering).
        if self.universal_newlines and hasattr(file, 'newlines'):
            if stdout:
                stdout = self._translate_newlines(stdout)
            if stderr:
                stderr = self._translate_newlines(stderr)

        self.wait()
        return (stdout, stderr)

    def send_signal(self, sig):
        """Send a signal to the process
        """
        os.kill(self.pid, sig)

    def terminate(self):
        """Terminate the process with SIGTERM
        """
        self.send_signal(signal.SIGTERM)

    def kill(self):
        """Kill the process with SIGKILL
        """
        self.send_signal(signal.SIGKILL)

