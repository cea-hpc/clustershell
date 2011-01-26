# $Id$

"""Unit test small library"""

import os
import time

from ConfigParser import ConfigParser


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

