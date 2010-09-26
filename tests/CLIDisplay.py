#!/usr/bin/env python
# ClusterShell.CLI.Display test suite
# Written by S. Thiell 2010-09-25
# $Id$


"""Unit test for CLI.Display"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, '../lib')

from ClusterShell.CLI.Display import Display, WHENCOLOR_CHOICES
from ClusterShell.CLI.OptionParser import OptionParser

from ClusterShell.MsgTree import MsgTree
from ClusterShell.NodeSet import NodeSet

from ClusterShell.NodeUtils import GroupResolverConfig


def makeTestFile(text):
    """Create a temporary file with the provided text."""
    f = tempfile.NamedTemporaryFile()
    f.write(text)
    f.flush()
    return f

class CLIDisplayTest(unittest.TestCase):
    """This test case performs a complete CLI.Display verification.  Also
    CLI.OptionParser is used and some parts are verified btw.
    """
    def testDisplay(self):
        """test CLI.Display"""
        parser = OptionParser("dummy")
        parser.install_display_options(verbose_options=True)
        options, _ = parser.parse_args([])

        ns = NodeSet("localhost")
        mtree = MsgTree()
        mtree.add("localhost", "message0")
        mtree.add("localhost", "message1")

        for whencolor in WHENCOLOR_CHOICES: # test whencolor switch
            for label in [True, False]:     # test no-label switch
                options.label = label
                options.whencolor = whencolor
                disp = Display(options)
                # inhibit output
                disp.out = open("/dev/null", "w")
                disp.err = open("/dev/null", "w")
                self.assert_(disp != None)
                # test print_* methods...
                disp.print_line(ns, "foo bar")
                disp.print_line_error(ns, "foo bar")
                disp.print_gather(ns, list(mtree.walk())[0][0])
                # test also string nodeset as parameter
                disp.print_gather("localhost", list(mtree.walk())[0][0])
                # test line_mode property
                self.assertEqual(disp.line_mode, False)
                disp.line_mode = True
                self.assertEqual(disp.line_mode, True)
                disp.print_gather("localhost", list(mtree.walk())[0][0])
                disp.line_mode = False
                self.assertEqual(disp.line_mode, False)

    def testDisplayRegroup(self):
        """test CLI.Display (regroup)"""
        parser = OptionParser("dummy")
        parser.install_display_options(verbose_options=True)
        options, _ = parser.parse_args(["-r"])

        mtree = MsgTree()
        mtree.add("localhost", "message0")
        mtree.add("localhost", "message1")

        disp = Display(options)
        self.assertEqual(disp.regroup, True)
        disp.out = open("/dev/null", "w")
        disp.err = open("/dev/null", "w")
        self.assert_(disp != None)
        self.assertEqual(disp.line_mode, False)

        f = makeTestFile("""
# A comment

[Main]
default: local

[local]
map: echo localhost
#all:
list: echo all
#reverse:
        """)
        res = GroupResolverConfig(f.name)
        ns = NodeSet("localhost", resolver=res)

        # nodeset.regroup() is performed by print_gather()
        disp.print_gather(ns, list(mtree.walk())[0][0])


if __name__ == '__main__':
    suites = [unittest.TestLoader().loadTestsFromTestCase(CLIDisplayTest)]
    unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(suites))
