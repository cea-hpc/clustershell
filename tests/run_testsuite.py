#!/usr/bin/env python
# ClusterShell test suite
# Written by S. Thiell
# $Id$

"""
run_testsuite.py [-hv]

Run ClusterShell tests written using the unittest module.

-v
    Verbose output.  With one -v, unittest prints a dot (".") for each
    test run.  With -vv, unittest prints the name of each test (for
    some definition of "name" ...).  With no -v, unittest is silent
    until the end of the run, except when errors occur.
"""

import getopt
import sys
import unittest

if __name__ == '__main__':
    verb = 0

    try:
        opts, args = getopt.getopt(sys.argv[1:], "hv", ["help"])
    except getopt.error, msg:
        print msg
        print "Try `python %s -h' for more information." % sys.argv[0]
        sys.exit(2)

    for k, v in opts:
        if k == "-v":
            verb += 1
        elif k in ("-h", "--help"):
            print __doc__
            sys.exit(0)

    loader = unittest.TestLoader()
    suite = loader.loadTestsFromNames([ "RangeSetTest",
                                        "RangeSetErrorTest",
                                        "NodeSetTest",
                                        "NodeSetErrorTest",
                                        "NodeSetScriptTest",
                                        "MisusageTest",
                                        "MsgTreeTest",
                                        "TaskAdvancedTest",
                                        "TaskEventTest",
                                        "TaskLocalTest",
                                        "TaskDistantTest",
                                        "TaskMsgTreeTest",
                                        "TaskPortTest",
                                        "TaskTimeoutTest",
                                        "TaskTimerTest",
                                        "TaskThreadJoinTest",
                                        "TaskThreadSuspendTest",
                                        ])

    unittest.TextTestRunner(verbosity=verb).run(suite)
