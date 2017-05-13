#!/usr/bin/env python
# ClusterShell test command

"""
test_command.py [--help] [--test=test] [--rc=retcode] [--timeout=timeout]
"""

from __future__ import print_function

import getopt
import sys
import time
import unittest


def testCmpOut():
    print("abcdefghijklmnopqrstuvwxyz")

def testTimeout(howlong):
    print("some buffer")
    print("here...")
    sys.stdout.flush()
    time.sleep(howlong)

if __name__ == '__main__':
    rc = 0
    test = None
    try:
        opts, args = getopt.getopt(sys.argv[1:], "ht:r:m:", ["help", "test=", "rc=", "timeout="])
    except getopt.error as msg:
        print(msg)
        print("Try `python %s -h' for more information." % sys.argv[0])
        sys.exit(2)

    for k, v in opts:
        if k in ("-t", "--test"):
            if v == "cmp_out":
                test = testCmpOut
        elif k in ("-r", "--rc"):
            rc = int(v)
        elif k in ("-m", "--timeout"):
            testTimeout(int(v))
        elif k in ("-h", "--help"):
            print(__doc__)
            sys.exit(0)

    if test:
        test()

    sys.exit(rc)
