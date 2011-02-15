#!/usr/bin/env python
# scripts/nodeset.py tool test suite 
# Written by S. Thiell 2009-07-29
# $Id$


"""Unit test for scripts/nodeset.py"""

import copy
import sys
import unittest

from subprocess import *


class NodeSetScriptTest(unittest.TestCase):
    """Unit test class for testing nodeset.py"""

    def _launchAndCompare(self, args, expected_output, stdin=None):
        output = Popen(["../scripts/nodeset.py"] + args, stdout=PIPE, stdin=PIPE).communicate(input=stdin)[0].strip()
        if type(expected_output) is list:
            ok = False
            for o in expected_output:
                if output == o:
                    ok = True
            self.assert_(ok, "Output %s != one of %s" % (output, expected_output))
        else:
            self.assertEqual(expected_output, output)

    def _launchBatteryOfCountTests(self, args):
        self._launchAndCompare(args + ["--count", "foo"], "1")
        self._launchAndCompare(args + ["--count", "foo", "bar"], "2")
        self._launchAndCompare(args + ["--count", "foo", "foo"], "1")
        self._launchAndCompare(args + ["--count", "foo", "foo", "bar"], "2")
        self._launchAndCompare(args + ["--count", "foo[0]"], "1")
        self._launchAndCompare(args + ["--count", "foo[2]"], "1")
        self._launchAndCompare(args + ["--count", "foo[1,2]"], "2")
        self._launchAndCompare(args + ["--count", "foo[1-2]"], "2")
        self._launchAndCompare(args + ["--count", "foo[1,2]", "foo[1-2]"], "2")
        self._launchAndCompare(args + ["--count", "foo[1-200,245-394]"], "350")
        self._launchAndCompare(args + ["--count", "foo[395-442]", "foo[1-200,245-394]"], "398")
        self._launchAndCompare(args + ["--count", "foo[395-442]", "foo", "foo[1-200,245-394]"], "399")
        self._launchAndCompare(args + ["--count", "foo[395-442]", "foo", "foo[0-200,245-394]"], "400")
        self._launchAndCompare(args + ["--count", "foo[395-442]", "bar3,bar24", "foo[1-200,245-394]"], "400")

    def testCount(self):
        """test nodeset.py --count"""
        self._launchBatteryOfCountTests([])
        self._launchBatteryOfCountTests(["--autostep=1"])
        self._launchBatteryOfCountTests(["--autostep=2"])
        self._launchBatteryOfCountTests(["--autostep=5"])

    def testCountIntersection(self):
        """test nodeset.py --count --intersection"""
        self._launchAndCompare(["--count", "foo", "--intersection", "bar"], "0")
        self._launchAndCompare(["--count", "foo", "--intersection", "foo"], "1")
        self._launchAndCompare(["--count", "foo", "--intersection", "foo", "-i", "bar"], "0")
        self._launchAndCompare(["--count", "foo[0]", "--intersection", "foo0"], "1")
        self._launchAndCompare(["--count", "foo[2]", "--intersection", "foo"], "0")
        self._launchAndCompare(["--count", "foo[1,2]", "--intersection", "foo[1-2]"], "2")
        self._launchAndCompare(["--count", "foo[395-442]", "--intersection", "foo[1-200,245-394]"], "0")
        self._launchAndCompare(["--count", "foo[395-442]", "--intersection", "foo", "-i", "foo[1-200,245-394]"], "0")
        self._launchAndCompare(["--count", "foo[395-442]", "-i", "foo", "-i", "foo[0-200,245-394]"], "0")
        self._launchAndCompare(["--count", "foo[395-442]", "--intersection", "bar3,bar24", "-i", "foo[1-200,245-394]"], "0")

    def _launchBatteryOfFoldTests(self, args):
        self._launchAndCompare(args + ["--fold", "foo"], "foo")
        self._launchAndCompare(args + ["--fold", "foo", "bar"], ["bar,foo", "foo,bar"])
        self._launchAndCompare(args + ["--fold", "foo", "foo"], "foo")
        self._launchAndCompare(args + ["--fold", "foo", "foo", "bar"], ["bar,foo", "foo,bar"])
        self._launchAndCompare(args + ["--fold", "foo[0]"], "foo0")
        self._launchAndCompare(args + ["--fold", "foo[2]"], "foo2")
        self._launchAndCompare(args + ["--fold", "foo[1,2]"], "foo[1-2]")
        self._launchAndCompare(args + ["--fold", "foo[1-2]"], "foo[1-2]")
        self._launchAndCompare(args + ["--fold", "foo[1,2]", "foo[1-2]"], "foo[1-2]")
        self._launchAndCompare(args + ["--fold", "foo[1-200,245-394]"], "foo[1-200,245-394]")
        self._launchAndCompare(args + ["--fold", "foo[395-442]", "foo[1-200,245-394]"], "foo[1-200,245-442]")
        self._launchAndCompare(args + ["--fold", "foo[395-442]", "foo", "foo[1-200,245-394]"], ["foo[1-200,245-442],foo", "foo,foo[1-200,245-442]"])
        self._launchAndCompare(args + ["--fold", "foo[395-442]", "foo", "foo[0-200,245-394]"], ["foo[0-200,245-442],foo", "foo,foo[0-200,245-442]"])
        self._launchAndCompare(args + ["--fold", "foo[395-442]", "bar3,bar24", "foo[1-200,245-394]"], ["foo[1-200,245-442],bar[3,24]", "bar[3,24],foo[1-200,245-442]"])

    def testFold(self):
        """test nodeset.py --fold"""
        self._launchBatteryOfFoldTests([])
        self._launchBatteryOfFoldTests(["--autostep=3"])

    def testExpand(self):
        """test nodeset.py --expand"""
        self._launchAndCompare(["--expand", "foo"], "foo")
        self._launchAndCompare(["--expand", "foo", "bar"], ["bar foo", "foo bar"])
        self._launchAndCompare(["--expand", "foo", "foo"], "foo")
        self._launchAndCompare(["--expand", "foo[0]"], "foo0")
        self._launchAndCompare(["--expand", "foo[2]"], "foo2")
        self._launchAndCompare(["--expand", "foo[1,2]"], "foo1 foo2")
        self._launchAndCompare(["--expand", "foo[1-2]"], "foo1 foo2")
        self._launchAndCompare(["--expand", "foo[1-2],bar"], ["bar foo1 foo2", "foo1 foo2 bar"])

    def testExpandWithSeparator(self):
        """test nodeset.py --expand -S"""
        self._launchAndCompare(["--expand", "-S", ":", "foo"], "foo")
        self._launchAndCompare(["--expand", "-S", ":", "foo", "bar"], ["bar:foo", "foo:bar"])
        self._launchAndCompare(["--expand", "--separator", ":", "foo", "bar"], ["bar:foo", "foo:bar"])
        self._launchAndCompare(["--expand", "--separator=:", "foo", "bar"], ["bar:foo", "foo:bar"])
        self._launchAndCompare(["--expand", "-S", ":", "foo", "foo"], "foo")
        self._launchAndCompare(["--expand", "-S", ":", "foo[0]"], "foo0")
        self._launchAndCompare(["--expand", "-S", ":", "foo[2]"], "foo2")
        self._launchAndCompare(["--expand", "-S", ":", "foo[1,2]"], "foo1:foo2")
        self._launchAndCompare(["--expand", "-S", ":", "foo[1-2]"], "foo1:foo2")
        self._launchAndCompare(["--expand", "-S", " ", "foo[1-2]"], "foo1 foo2")
        self._launchAndCompare(["--expand", "-S", ",", "foo[1-2],bar"], ["bar,foo1,foo2", "foo1,foo2,bar"])
        self._launchAndCompare(["--expand", "-S", "uuu", "foo[1-2],bar"], ["baruuufoo1uuufoo2", "foo1uuufoo2uuubar"])
        self._launchAndCompare(["--expand", "-S", "\\n", "foo[1-2]"], "foo1\nfoo2")

    def testFoldXOR(self):
        """test nodeset.py --fold --xor"""
        self._launchAndCompare(["--fold", "foo", "-X", "bar"], ["bar,foo", "foo,bar"])
        self._launchAndCompare(["--fold", "foo", "-X", "foo"], "")
        self._launchAndCompare(["--fold", "foo[1,2]", "-X", "foo[1-2]"], "")
        self._launchAndCompare(["--fold", "foo[1-10]", "-X", "foo[5-15]"], "foo[1-4,11-15]")
        self._launchAndCompare(["--fold", "foo[395-442]", "-X", "foo[1-200,245-394]"], "foo[1-200,245-442]")
        self._launchAndCompare(["--fold", "foo[395-442]", "-X", "foo", "-X", "foo[1-200,245-394]"], ["foo[1-200,245-442],foo", "foo,foo[1-200,245-442]"])
        self._launchAndCompare(["--fold", "foo[395-442]", "-X", "foo", "-X", "foo[0-200,245-394]"], ["foo[0-200,245-442],foo", "foo,foo[0-200,245-442]"])
        self._launchAndCompare(["--fold", "foo[395-442]", "-X", "bar3,bar24", "-X", "foo[1-200,245-394]"], "bar[3,24],foo[1-200,245-442]")

    def testExclude(self):
        """test nodeset.py --fold --exclude"""
        # Empty result
        self._launchAndCompare(["--fold", "foo", "-x", "foo"], "")
        # With no range
        self._launchAndCompare(["--fold", "foo,bar", "-x", "foo"], "bar")
        # Normal with range
        self._launchAndCompare(["--fold", "foo[0-5]", "-x", "foo[0-10]"], "")
        self._launchAndCompare(["--fold", "foo[0-10]", "-x", "foo[0-5]"], "foo[6-10]")
        # Do no change
        self._launchAndCompare(["--fold", "foo[6-10]", "-x", "bar[0-5]"], "foo[6-10]")
        self._launchAndCompare(["--fold", "foo[0-10]", "foo[13-18]", "--exclude", "foo[5-10,15]"], "foo[0-4,13-14,16-18]")

    def testRangeSet(self):
        """test nodeset.py --rangeset"""
        self._launchAndCompare(["--fold","--rangeset","1,2"], "1-2")
        self._launchAndCompare(["--expand","-R","1-2"], "1 2")
        self._launchAndCompare(["--fold","-R","1-2","-X","2-3"], "1,3")

    def testStdin(self):
        """test nodeset.py - (stdin)"""
        self._launchAndCompare(["-f","-"], "foo", stdin="foo\n")
        self._launchAndCompare(["-f","-"], "foo[1-3]", stdin="foo1 foo2 foo3\n")
        
    def testSplit(self):
        """test nodeset.py --split"""
        self._launchAndCompare(["--split=2","-f", "bar"], "bar")
        self._launchAndCompare(["--split", "2","-f", "foo,bar"], "bar\nfoo")
        self._launchAndCompare(["--split", "2","-e", "foo", "bar", "bur", "oof", "gcc"], "bar bur foo\ngcc oof")
        self._launchAndCompare(["--split=2","-f", "foo[2-9]"], "foo[2-5]\nfoo[6-9]")
        self._launchAndCompare(["--split=2","-f", "foo[2-3,7]", "bar9"], "bar9,foo2\nfoo[3,7]")
        self._launchAndCompare(["--split=3","-f", "foo[2-9]"], "foo[2-4]\nfoo[5-7]\nfoo[8-9]")
        self._launchAndCompare(["--split=1","-f", "foo2", "foo3"], "foo[2-3]")
        self._launchAndCompare(["--split=4","-f", "foo[2-3]"], "foo2\nfoo3")
        self._launchAndCompare(["--split=4","-f", "foo3", "foo2"], "foo2\nfoo3")
        self._launchAndCompare(["--split=2","-e", "foo[2-9]"], "foo2 foo3 foo4 foo5\nfoo6 foo7 foo8 foo9")
        self._launchAndCompare(["--split=3","-e", "foo[2-9]"], "foo2 foo3 foo4\nfoo5 foo6 foo7\nfoo8 foo9")
        self._launchAndCompare(["--split=1","-e", "foo3", "foo2"], "foo2 foo3")
        self._launchAndCompare(["--split=4","-e", "foo[2-3]"], "foo2\nfoo3")
        self._launchAndCompare(["--split=4","-e", "foo2", "foo3"], "foo2\nfoo3")
        self._launchAndCompare(["--split=2","-c", "foo2", "foo3"], "1\n1")
        # following test requires a default group source set
        self._launchAndCompare(["--split=2","-r", "foo2", "foo3"], "foo2\nfoo3")


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(NodeSetScriptTest)
    unittest.TextTestRunner(verbosity=2).run(suite)
