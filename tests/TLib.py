"""
Unit test library
"""

import os
import socket
import sys
import tempfile
import time

try:
    import configparser
except ImportError:
    import ConfigParser as configparser

from io import BytesIO, StringIO


__all__ = ['HOSTNAME', 'load_cfg', 'make_temp_filename', 'make_temp_file',
           'make_temp_dir', 'CLI_main']

# Get machine short hostname
HOSTNAME = socket.gethostname().split('.', 1)[0]

class TBytesIO(BytesIO):
    """Standard stream of in memory bytes for testing purpose."""

    def __init__(self, initial_bytes=None):
        if initial_bytes and type(initial_bytes) is not bytes:
            initial_bytes = initial_bytes.encode('ascii')
        BytesIO.__init__(self, initial_bytes)

    def write(self, b):
        if type(b) is bytes:
            BytesIO.write(self, b)
        else:
            BytesIO.write(self, b.encode('ascii'))

    def isatty(self):
        return False

def load_cfg(name):
    """Load test configuration file as a new ConfigParser"""
    cfgparser = configparser.ConfigParser()
    cfgparser.read([ \
        os.path.expanduser('~/.clustershell/tests/%s' % name),
        '/etc/clustershell/tests/%s' % name])
    return cfgparser

#
# Temp files and directories
#
def make_temp_filename(suffix=''):
    """Return a temporary name for a file."""
    if len(suffix) > 0 and suffix[0] != '-':
        suffix = '-' + suffix
    fd, name = tempfile.mkstemp(suffix, prefix='cs-test-')
    os.close(fd)  # don't leak open fd
    return name

def make_temp_file(text, suffix='', dir=None):
    """Create a temporary file with the provided text."""
    assert type(text) is bytes
    tmp = tempfile.NamedTemporaryFile(prefix='cs-test-',
                                      suffix=suffix, dir=dir)
    tmp.write(text)
    tmp.flush()
    return tmp

def make_temp_dir(suffix=''):
    """Create a temporary directory."""
    if len(suffix) > 0 and suffix[0] != '-':
        suffix = '-' + suffix
    return tempfile.mkdtemp(suffix, prefix='cs-test-')

#
# CLI tests
#
def CLI_main(test, main, args, stdin, expected_stdout, expected_rc=0,
             expected_stderr=None):
    """Generic CLI main() direct calling function that allows code coverage
    checks."""
    rc = -1

    saved_stdin = sys.stdin
    saved_stdout = sys.stdout
    saved_stderr = sys.stderr

    # Capture standard streams

    # Input: if defined, stdin may either be a buffer or a string (with an
    # encoding).
    if stdin is not None:
        if type(stdin) is bytes:  # also works for str in Python 2
            sys.stdin = TBytesIO(stdin)
        else:
            # If stdin is a string in Python 3, use StringIO as sys.stdin
            # should be read in text mode for some tests.
            sys.stdin = StringIO(stdin)

    # Output: ClusterShell sends bytes to sys_stdout()/sys_stderr() and when
    # print() is used, TBytesIO does a conversion to ascii.
    sys.stdout = out = TBytesIO()
    sys.stderr = err = TBytesIO()
    sys.argv = args
    try:
        main()
    except SystemExit as exc:
        rc = int(str(exc))
    finally:
        sys.stdout = saved_stdout
        sys.stderr = saved_stderr
        sys.stdin = saved_stdin

    try:
        if expected_stdout is not None:
            # expected_stdout might be a compiled regexp or a string
            try:
                if not expected_stdout.search(out.getvalue()):
                    # search failed; use assertEqual() to display
                    # expected/output
                    test.assertEqual(out.getvalue(), expected_stdout.pattern)
            except AttributeError:
                # not a regexp
                test.assertEqual(out.getvalue(), expected_stdout)

        if expected_stderr is not None:
            # expected_stderr might be a compiled regexp or a string
            try:
                if not expected_stderr.match(err.getvalue()):
                    # match failed; use assertEqual() to display expected/output
                    test.assertEqual(err.getvalue(), expected_stderr.pattern)
            except AttributeError:
                # check the end as stderr messages are often prefixed with
                # argv[0]
                test.assertTrue(err.getvalue().endswith(expected_stderr),
                                err.getvalue() + b' != ' + expected_stderr)

        if expected_rc is not None:
            test.assertEqual(rc, expected_rc,
                             "rc=%d err=%s" % (rc, err.getvalue()))
    finally:
        out.close()
        err.close()
