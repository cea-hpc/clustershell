#!/usr/bin/env python
# ClusterShell test command
# $Id$

"""
test_command.py [--help] [--test=test] [--rc=retcode]
"""

import getopt
import sys
import unittest


def testHuge():
    for i in range(0, 100000):
        print "huge! ",

if __name__ == '__main__':
    rc = 0
    test = None
    try:
        opts, args = getopt.getopt(sys.argv[1:], "ht:r:", ["help", "test=", "rc="])
    except getopt.error, msg:
        print msg
        print "Try `python %s -h' for more information." % sys.argv[0]
        sys.exit(2)

    for k, v in opts:
        if k in ("-t", "--test"):
            if v == "huge":
                test = testHuge
        elif k in ("-r", "--rc"):
            rc = int(v)
        elif k in ("-h", "--help"):
            print __doc__
            sys.exit(0)

    if test:
        test()

    sys.exit(rc)
