
"""Unit test small library"""

import os
import socket
import tempfile
import time

from ConfigParser import ConfigParser


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

