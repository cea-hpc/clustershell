
"""Unit test small library"""

import os
import socket
import sys
import tempfile
import time

from ConfigParser import ConfigParser
from StringIO import StringIO


def my_node():
    """Helper to get local short hostname."""
    return socket.gethostname().split('.')[0]

def load_cfg(name):
    """Load test configuration file as a new ConfigParser"""
    cfgparser = ConfigParser()
    cfgparser.read([ \
        os.path.expanduser('~/.clustershell/tests/%s' % name),
        '/etc/clustershell/tests/%s' % name])
    return cfgparser

def chrono(func):
    """chrono decorator"""
    def timing(*args):
        start = time.time()
        res = func(*args)
        print "execution time: %f s" % (time.time() - start)
        return res
    return timing

def make_temp_file(text, suffix='', dir=None):
    """Create a temporary file with the provided text."""
    f = tempfile.NamedTemporaryFile(suffix=suffix, dir=dir)
    f.write(text)
    f.flush()
    return f

def make_temp_dir():
    """Create a temporary directory."""
    dname = tempfile.mkdtemp()
    return dname

def CLI_main(test, main, args, stdin, expected_stdout, expected_rc=0,
             expected_stderr=None):
    """Generic CLI main() direct calling function that allows code coverage
    checks."""
    rc = -1
    saved_stdin = sys.stdin
    saved_stdout = sys.stdout
    saved_stderr = sys.stderr
    if stdin is not None:
        sys.stdin = StringIO(stdin)
    sys.stdout = out = StringIO()
    sys.stderr = err = StringIO()
    sys.argv = args
    try:
        try:
            main()
        except SystemExit, exc:
            rc = int(str(exc))
    finally:
        sys.stdout = saved_stdout
        sys.stderr = saved_stderr
        sys.stdin = saved_stdin
    if expected_stdout is not None:
        test.assertEqual(out.getvalue(), expected_stdout)
    out.close()
    if expected_stderr is not None:
        # check the end as stderr messages are often prefixed with argv[0]
        test.assertTrue(err.getvalue().endswith(expected_stderr), err.getvalue())
    if expected_rc is not None:
        test.assertEqual(rc, expected_rc, "rc=%d err=%s" % (rc, err.getvalue()))
    err.close()

