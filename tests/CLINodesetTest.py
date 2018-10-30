# ClusterShell.CLI.Nodeset test suite
# Written by S. Thiell

"""Unit test for CLI.Nodeset"""

import os
import random
from textwrap import dedent
import unittest

from TLib import *
from ClusterShell.CLI.Nodeset import main

from ClusterShell.NodeUtils import GroupResolverConfig
from ClusterShell.NodeSet import set_std_group_resolver, \
                                 set_std_group_resolver_config


class CLINodesetTestBase(unittest.TestCase):
    """Base unit test class for testing CLI/Nodeset.py"""

    def _nodeset_t(self, args, stdin, expected_stdout, expected_rc=0,
                   expected_stderr=None):
        CLI_main(self, main, ['nodeset'] + args, stdin, expected_stdout,
                 expected_rc, expected_stderr)


class CLINodesetTest(CLINodesetTestBase):
    """Unit test class for testing CLI/Nodeset.py"""

    def _battery_count(self, args):
        self._nodeset_t(args + ["--count", ""], None, b"0\n")
        self._nodeset_t(args + ["--count", "foo"], None, b"1\n")
        self._nodeset_t(args + ["--count", "foo", "bar"], None, b"2\n")
        self._nodeset_t(args + ["--count", "foo", "foo"], None, b"1\n")
        self._nodeset_t(args + ["--count", "foo", "foo", "bar"], None, b"2\n")
        self._nodeset_t(args + ["--count", "foo[0]"], None, b"1\n")
        self._nodeset_t(args + ["--count", "foo[2]"], None, b"1\n")
        self._nodeset_t(args + ["--count", "foo[1,2]"], None, b"2\n")
        self._nodeset_t(args + ["--count", "foo[1-2]"], None, b"2\n")
        self._nodeset_t(args + ["--count", "foo[1,2]", "foo[1-2]"], None, b"2\n")
        self._nodeset_t(args + ["--count", "foo[1-200,245-394]"], None, b"350\n")
        self._nodeset_t(args + ["--count", "foo[395-442]", "foo[1-200,245-394]"], None, b"398\n")
        self._nodeset_t(args + ["--count", "foo[395-442]", "foo", "foo[1-200,245-394]"], None, b"399\n")
        self._nodeset_t(args + ["--count", "foo[395-442]", "foo", "foo[0-200,245-394]"], None, b"400\n")
        self._nodeset_t(args + ["--count", "foo[395-442]", "bar3,bar24", "foo[1-200,245-394]"], None, b"400\n")
        # from stdin: use string not bytes as input because CLI/Nodeset.py works in text mode
        self._nodeset_t(args + ["--count"], "\n", b"0\n")
        self._nodeset_t(args + ["--count"], "foo\n", b"1\n")
        self._nodeset_t(args + ["--count"], "foo\nbar\n", b"2\n")
        self._nodeset_t(args + ["--count"], "foo\nfoo\n", b"1\n")
        self._nodeset_t(args + ["--count"], "foo\nfoo\nbar\n", b"2\n")
        self._nodeset_t(args + ["--count"], "foo[0]\n", b"1\n")
        self._nodeset_t(args + ["--count"], "foo[2]\n", b"1\n")
        self._nodeset_t(args + ["--count"], "foo[1,2]\n", b"2\n")
        self._nodeset_t(args + ["--count"], "foo[1-2]\n", b"2\n")
        self._nodeset_t(args + ["--count"], "foo[1,2]\nfoo[1-2]\n", b"2\n")
        self._nodeset_t(args + ["--count"], "foo[1-200,245-394]\n", b"350\n")
        self._nodeset_t(args + ["--count"], "foo[395-442]\nfoo[1-200,245-394]\n", b"398\n")
        self._nodeset_t(args + ["--count"], "foo[395-442]\nfoo\nfoo[1-200,245-394]\n", b"399\n")
        self._nodeset_t(args + ["--count"], "foo[395-442]\nfoo\nfoo[0-200,245-394]\n", b"400\n")
        self._nodeset_t(args + ["--count"], "foo[395-442]\nbar3,bar24\nfoo[1-200,245-394]\n", b"400\n")

    def test_001_count(self):
        """test nodeset --count"""
        self._battery_count([])
        self._battery_count(["--autostep=1"])
        self._battery_count(["--autostep=2"])
        self._battery_count(["--autostep=5"])
        self._battery_count(["--autostep=auto"])
        self._battery_count(["--autostep=0%"])
        self._battery_count(["--autostep=50%"])
        self._battery_count(["--autostep=100%"])

    def test_002_count_intersection(self):
        """test nodeset --count --intersection"""
        self._nodeset_t(["--count", "foo", "--intersection", "bar"], None, b"0\n")
        self._nodeset_t(["--count", "foo", "--intersection", "foo"], None, b"1\n")
        self._nodeset_t(["--count", "foo", "--intersection", "foo", "-i", "bar"], None, b"0\n")
        self._nodeset_t(["--count", "foo[0]", "--intersection", "foo0"], None, b"1\n")
        self._nodeset_t(["--count", "foo[2]", "--intersection", "foo"], None, b"0\n")
        self._nodeset_t(["--count", "foo[1,2]", "--intersection", "foo[1-2]"], None, b"2\n")
        self._nodeset_t(["--count", "foo[395-442]", "--intersection", "foo[1-200,245-394]"], None, b"0\n")
        self._nodeset_t(["--count", "foo[395-442]", "--intersection", "foo", "-i", "foo[1-200,245-394]"], None, b"0\n")
        self._nodeset_t(["--count", "foo[395-442]", "-i", "foo", "-i", "foo[0-200,245-394]"], None, b"0\n")
        self._nodeset_t(["--count", "foo[395-442]", "--intersection", "bar3,bar24", "-i", "foo[1-200,245-394]"], None, b"0\n")
        # multiline args (#394)
        self._nodeset_t(["--count", "foo[1,2]", "-i", "foo1\nfoo2"], None, b"2\n")
        self._nodeset_t(["--count", "foo[1,2]", "-i", "foo1\nfoo2", "foo3\nfoo4"], None, b"4\n")

    def test_003_count_intersection_stdin(self):
        """test nodeset --count --intersection (stdin)"""
        self._nodeset_t(["--count", "--intersection", "bar"], "foo\n", b"0\n")
        self._nodeset_t(["--count", "--intersection", "foo"], "foo\n", b"1\n")
        self._nodeset_t(["--count", "--intersection", "foo", "-i", "bar"], "foo\n", b"0\n")
        self._nodeset_t(["--count", "--intersection", "foo0"], "foo[0]\n", b"1\n")
        self._nodeset_t(["--count", "--intersection", "foo"], "foo[2]\n", b"0\n")
        self._nodeset_t(["--count", "--intersection", "foo[1-2]"], "foo[1,2]\n", b"2\n")
        self._nodeset_t(["--count", "--intersection", "foo[1-200,245-394]"], "foo[395-442]\n", b"0\n")
        self._nodeset_t(["--count", "--intersection", "foo", "-i", "foo[1-200,245-394]"], "foo[395-442]\n", b"0\n")
        self._nodeset_t(["--count", "-i", "foo", "-i", "foo[0-200,245-394]"], "foo[395-442]\n", b"0\n")
        self._nodeset_t(["--count", "--intersection", "bar3,bar24", "-i", "foo[1-200,245-394]"], "foo[395-442]\n", b"0\n")

    def _battery_fold(self, args):
        self._nodeset_t(args + ["--fold", ""], None, b"\n")
        self._nodeset_t(args + ["--fold", "foo"], None, b"foo\n")
        self._nodeset_t(args + ["--fold", "foo", "bar"], None, b"bar,foo\n")
        self._nodeset_t(args + ["--fold", "foo", "foo"], None, b"foo\n")
        self._nodeset_t(args + ["--fold", "foo", "foo", "bar"], None, b"bar,foo\n")
        self._nodeset_t(args + ["--fold", "foo[0]"], None, b"foo0\n")
        self._nodeset_t(args + ["--fold", "foo[2]"], None, b"foo2\n")
        self._nodeset_t(args + ["--fold", "foo[1,2]"], None, b"foo[1-2]\n")
        self._nodeset_t(args + ["--fold", "foo[1-2]"], None, b"foo[1-2]\n")
        self._nodeset_t(args + ["--fold", "foo[1,2]", "foo[1-2]"], None, b"foo[1-2]\n")
        self._nodeset_t(args + ["--fold", "foo[1-200,245-394]"], None, b"foo[1-200,245-394]\n")
        self._nodeset_t(args + ["--fold", "foo[395-442]", "foo[1-200,245-394]"], None, b"foo[1-200,245-442]\n")
        self._nodeset_t(args + ["--fold", "foo[395-442]", "foo", "foo[1-200,245-394]"], None, b"foo,foo[1-200,245-442]\n")
        self._nodeset_t(args + ["--fold", "foo[395-442]", "foo", "foo[0-200,245-394]"], None, b"foo,foo[0-200,245-442]\n")
        self._nodeset_t(args + ["--fold", "foo[395-442]", "bar3,bar24", "foo[1-200,245-394]"], None, b"bar[3,24],foo[1-200,245-442]\n")
        # multiline arg (#394)
        self._nodeset_t(args + ["--fold", "foo3\nfoo1\nfoo2\nbar"], None, b"bar,foo[1-3]\n")
        self._nodeset_t(args + ["--fold", "foo3\n\n\nfoo1\n\nfoo2\n\n"], None, b"foo[1-3]\n")
        # stdin
        self._nodeset_t(args + ["--fold"], "\n", b"\n")
        self._nodeset_t(args + ["--fold"], "foo\n", b"foo\n")
        self._nodeset_t(args + ["--fold"], "foo\nbar\n", b"bar,foo\n")
        self._nodeset_t(args + ["--fold"], "foo\nfoo\n", b"foo\n")
        self._nodeset_t(args + ["--fold"], "foo\nfoo\nbar\n", b"bar,foo\n")
        self._nodeset_t(args + ["--fold"], "foo[0]\n", b"foo0\n")
        self._nodeset_t(args + ["--fold"], "foo[2]\n", b"foo2\n")
        self._nodeset_t(args + ["--fold"], "foo[1,2]\n", b"foo[1-2]\n")
        self._nodeset_t(args + ["--fold"], "foo[1-2]\n", b"foo[1-2]\n")
        self._nodeset_t(args + ["--fold"], "foo[1,2]\nfoo[1-2]\n", b"foo[1-2]\n")
        self._nodeset_t(args + ["--fold"], "foo[1-200,245-394]\n", b"foo[1-200,245-394]\n")
        self._nodeset_t(args + ["--fold"], "foo[395-442]\nfoo[1-200,245-394]\n", b"foo[1-200,245-442]\n")
        self._nodeset_t(args + ["--fold"], "foo[395-442]\nfoo\nfoo[1-200,245-394]\n", b"foo,foo[1-200,245-442]\n")
        self._nodeset_t(args + ["--fold"], "foo[395-442]\nfoo\nfoo[0-200,245-394]\n", b"foo,foo[0-200,245-442]\n")
        self._nodeset_t(args + ["--fold"], "foo[395-442]\nbar3,bar24\nfoo[1-200,245-394]\n", b"bar[3,24],foo[1-200,245-442]\n")

    def test_004_fold(self):
        """test nodeset --fold"""
        self._battery_fold([])
        self._battery_fold(["--autostep=3"])
        # --autostep=auto (1.7)
        self._battery_fold(["--autostep=auto"])
        self._battery_count(["--autostep=0%"])
        self._battery_count(["--autostep=50%"])
        self._battery_count(["--autostep=100%"])

    def test_005_fold_autostep(self):
        """test nodeset --fold --autostep=X"""
        self._nodeset_t(["--autostep=2", "-f", "foo0", "foo2", "foo4", "foo6"], None, b"foo[0-6/2]\n")
        self._nodeset_t(["--autostep=2", "-f", "foo4", "foo2", "foo0", "foo6"], None, b"foo[0-6/2]\n")
        self._nodeset_t(["--autostep=3", "-f", "foo0", "foo2", "foo4", "foo6"], None, b"foo[0-6/2]\n")
        self._nodeset_t(["--autostep=4", "-f", "foo0", "foo2", "foo4", "foo6"], None, b"foo[0-6/2]\n")
        self._nodeset_t(["--autostep=5", "-f", "foo0", "foo2", "foo4", "foo6"], None, b"foo[0,2,4,6]\n")
        self._nodeset_t(["--autostep=auto", "-f", "foo0", "foo2", "foo4", "foo6"], None, b"foo[0-6/2]\n")
        self._nodeset_t(["--autostep=auto", "-f", "foo4", "foo2", "foo0", "foo6"], None, b"foo[0-6/2]\n")
        self._nodeset_t(["--autostep=auto", "-f", "foo4", "foo2", "foo0", "foo2", "foo6"], None, b"foo[0-6/2]\n")
        self._nodeset_t(["--autostep=auto", "-f", "foo4", "foo2", "foo0", "foo5", "foo6"], None, b"foo[0,2,4-6]\n")
        self._nodeset_t(["--autostep=auto", "-f", "foo4", "foo2", "foo0", "foo9", "foo6"], None, b"foo[0,2,4,6,9]\n")
        self._nodeset_t(["--autostep=75%", "-f", "foo0", "foo2", "foo4", "foo6"], None, b"foo[0-6/2]\n")
        self._nodeset_t(["--autostep=75%", "-f", "foo4", "foo2", "foo0", "foo6"], None, b"foo[0-6/2]\n")
        self._nodeset_t(["--autostep=80%", "-f", "foo4", "foo2", "foo0", "foo2", "foo6"], None, b"foo[0-6/2]\n")
        self._nodeset_t(["--autostep=80%", "-f", "foo4", "foo2", "foo0", "foo5", "foo6"], None, b"foo[0,2,4-6]\n")
        self._nodeset_t(["--autostep=80%", "-f", "foo4", "foo2", "foo0", "foo9", "foo6"], None, b"foo[0-6/2,9]\n")
        self._nodeset_t(["--autostep=81%", "-f", "foo4", "foo2", "foo0", "foo9", "foo6"], None, b"foo[0,2,4,6,9]\n")
        self._nodeset_t(["--autostep=100%", "-f", "foo4", "foo2", "foo0", "foo9", "foo6"], None, b"foo[0,2,4,6,9]\n")

    def test_006_expand(self):
        """test nodeset --expand"""
        self._nodeset_t(["--expand", ""], None, b"\n")
        self._nodeset_t(["--expand", "foo"], None, b"foo\n")
        self._nodeset_t(["--expand", "foo", "bar"], None, b"bar foo\n")
        self._nodeset_t(["--expand", "foo", "foo"], None, b"foo\n")
        self._nodeset_t(["--expand", "foo[0]"], None, b"foo0\n")
        self._nodeset_t(["--expand", "foo[2]"], None, b"foo2\n")
        self._nodeset_t(["--expand", "foo[1,2]"], None, b"foo1 foo2\n")
        self._nodeset_t(["--expand", "foo[1-2]"], None, b"foo1 foo2\n")
        self._nodeset_t(["--expand", "foo[1-2],bar"], None, b"bar foo1 foo2\n")

    def test_007_expand_stdin(self):
        """test nodeset --expand (stdin)"""
        self._nodeset_t(["--expand"], "\n", b"\n")
        self._nodeset_t(["--expand"], "foo\n", b"foo\n")
        self._nodeset_t(["--expand"], "foo\nbar\n", b"bar foo\n")
        self._nodeset_t(["--expand"], "foo\nfoo\n", b"foo\n")
        self._nodeset_t(["--expand"], "foo[0]\n", b"foo0\n")
        self._nodeset_t(["--expand"], "foo[2]\n", b"foo2\n")
        self._nodeset_t(["--expand"], "foo[1,2]\n", b"foo1 foo2\n")
        self._nodeset_t(["--expand"], "foo[1-2]\n", b"foo1 foo2\n")
        self._nodeset_t(["--expand"], "foo[1-2],bar\n", b"bar foo1 foo2\n")

    def test_008_expand_separator(self):
        """test nodeset --expand -S"""
        self._nodeset_t(["--expand", "-S", ":", "foo"], None, b"foo\n")
        self._nodeset_t(["--expand", "-S", ":", "foo", "bar"], None, b"bar:foo\n")
        self._nodeset_t(["--expand", "--separator", ":", "foo", "bar"], None, b"bar:foo\n")
        self._nodeset_t(["--expand", "--separator=:", "foo", "bar"], None, b"bar:foo\n")
        self._nodeset_t(["--expand", "-S", ":", "foo", "foo"], None, b"foo\n")
        self._nodeset_t(["--expand", "-S", ":", "foo[0]"], None, b"foo0\n")
        self._nodeset_t(["--expand", "-S", ":", "foo[2]"], None, b"foo2\n")
        self._nodeset_t(["--expand", "-S", ":", "foo[1,2]"], None, b"foo1:foo2\n")
        self._nodeset_t(["--expand", "-S", ":", "foo[1-2]"], None, b"foo1:foo2\n")
        self._nodeset_t(["--expand", "-S", " ", "foo[1-2]"], None, b"foo1 foo2\n")
        self._nodeset_t(["--expand", "-S", ",", "foo[1-2],bar"], None, b"bar,foo1,foo2\n")
        self._nodeset_t(["--expand", "-S", "uuu", "foo[1-2],bar"], None, b"baruuufoo1uuufoo2\n")
        self._nodeset_t(["--expand", "-S", "\\n", "foo[1-2]"], None, b"foo1\nfoo2\n")
        self._nodeset_t(["--expand", "-S", "\n", "foo[1-2]"], None, b"foo1\nfoo2\n")

    def test_009_fold_xor(self):
        """test nodeset --fold --xor"""
        self._nodeset_t(["--fold", "foo", "-X", "bar"], None, b"bar,foo\n")
        self._nodeset_t(["--fold", "foo", "-X", "foo"], None, b"\n")
        self._nodeset_t(["--fold", "foo[1,2]", "-X", "foo[1-2]"], None, b"\n")
        self._nodeset_t(["--fold", "foo[1-10]", "-X", "foo[5-15]"], None, b"foo[1-4,11-15]\n")
        self._nodeset_t(["--fold", "foo[395-442]", "-X", "foo[1-200,245-394]"], None, b"foo[1-200,245-442]\n")
        self._nodeset_t(["--fold", "foo[395-442]", "-X", "foo", "-X", "foo[1-200,245-394]"], None, b"foo,foo[1-200,245-442]\n")
        self._nodeset_t(["--fold", "foo[395-442]", "-X", "foo", "-X", "foo[0-200,245-394]"], None, b"foo,foo[0-200,245-442]\n")
        self._nodeset_t(["--fold", "foo[395-442]", "-X", "bar3,bar24", "-X", "foo[1-200,245-394]"], None, b"bar[3,24],foo[1-200,245-442]\n")
        # multiline args (#394)
        self._nodeset_t(["--fold", "foo[1-10]", "-X", "foo5\nfoo6\nfoo7"], None, b"foo[1-4,8-10]\n")
        self._nodeset_t(["--fold", "foo[1-10]", "-X", "foo5\nfoo6\nfoo7", "foo5\nfoo6"], None, b"foo[1-6,8-10]\n")

    def test_010_fold_xor_stdin(self):
        """test nodeset --fold --xor (stdin)"""
        self._nodeset_t(["--fold", "-X", "bar"], "foo\n", b"bar,foo\n")
        self._nodeset_t(["--fold", "-X", "foo"], "foo\n", b"\n")
        self._nodeset_t(["--fold", "-X", "foo[1-2]"], "foo[1,2]\n", b"\n")
        self._nodeset_t(["--fold", "-X", "foo[5-15]"], "foo[1-10]\n", b"foo[1-4,11-15]\n")
        self._nodeset_t(["--fold", "-X", "foo[1-200,245-394]"], "foo[395-442]\n", b"foo[1-200,245-442]\n")
        self._nodeset_t(["--fold", "-X", "foo", "-X", "foo[1-200,245-394]"], "foo[395-442]\n", b"foo,foo[1-200,245-442]\n")
        self._nodeset_t(["--fold", "-X", "foo", "-X", "foo[0-200,245-394]"], "foo[395-442]\n", b"foo,foo[0-200,245-442]\n")
        self._nodeset_t(["--fold", "-X", "bar3,bar24", "-X", "foo[1-200,245-394]"], "foo[395-442]\n", b"bar[3,24],foo[1-200,245-442]\n")
        # using stdin for -X
        self._nodeset_t(["-f", "foo[2-4]", "-X", "-"], "foo4 foo5 foo6\n", b"foo[2-3,5-6]\n")
        self._nodeset_t(["-f", "-X", "-", "foo[1-6]"], "foo4 foo5 foo6\n",
                        b"foo[1-6]\n", 0,
                        b"WARNING: empty left operand for set operation\n")

    def test_011_fold_exclude(self):
        """test nodeset --fold --exclude"""
        # Empty result
        self._nodeset_t(["--fold", "foo", "-x", "foo"], None, b"\n")
        # With no range
        self._nodeset_t(["--fold", "foo,bar", "-x", "foo"], None, b"bar\n")
        # Normal with range
        self._nodeset_t(["--fold", "foo[0-5]", "-x", "foo[0-10]"], None, b"\n")
        self._nodeset_t(["--fold", "foo[0-10]", "-x", "foo[0-5]"], None, b"foo[6-10]\n")
        # Do no change
        self._nodeset_t(["--fold", "foo[6-10]", "-x", "bar[0-5]"], None, b"foo[6-10]\n")
        self._nodeset_t(["--fold", "foo[0-10]", "foo[13-18]", "--exclude", "foo[5-10,15]"], None, b"foo[0-4,13-14,16-18]\n")
        # multiline args (#394)
        self._nodeset_t(["--fold", "foo[0-5]", "-x", "foo0\nfoo9\nfoo3\nfoo2\nfoo1"], None, b"foo[4-5]\n")
        self._nodeset_t(["--fold", "foo[0-5]", "-x", "foo0\nfoo9\nfoo3\nfoo2\nfoo1", "foo5\nfoo6"], None, b"foo[4-6]\n")

    def test_012_fold_exclude_stdin(self):
        """test nodeset --fold --exclude (stdin)"""
        # Empty result
        self._nodeset_t(["--fold", "-x", "foo"], "", b"\n", 0,
                        b"WARNING: empty left operand for set operation\n")
        self._nodeset_t(["--fold", "-x", "foo"], "\n", b"\n", 0,
                        b"WARNING: empty left operand for set operation\n")
        self._nodeset_t(["--fold", "-x", "foo"], "foo\n", b"\n")
        # With no range
        self._nodeset_t(["--fold", "-x", "foo"], "foo,bar\n", b"bar\n")
        # Normal with range
        self._nodeset_t(["--fold", "-x", "foo[0-10]"], "foo[0-5]\n", b"\n")
        self._nodeset_t(["--fold", "-x", "foo[0-5]"], "foo[0-10]\n", b"foo[6-10]\n")
        # Do no change
        self._nodeset_t(["--fold", "-x", "bar[0-5]"], "foo[6-10]\n", b"foo[6-10]\n")
        self._nodeset_t(["--fold", "--exclude", "foo[5-10,15]"], "foo[0-10]\nfoo[13-18]\n", b"foo[0-4,13-14,16-18]\n")
        # using stdin for -x
        self._nodeset_t(["-f", "foo[1-6]", "-x", "-"], "foo4 foo5 foo6\n", b"foo[1-3]\n")
        self._nodeset_t(["-f", "-x", "-", "foo[1-6]"], "foo4 foo5 foo6\n",
                        b"foo[1-6]\n", 0,
                        b"WARNING: empty left operand for set operation\n")

    def test_013_fold_intersection(self):
        """test nodeset --fold --intersection"""
        # Empty result
        self._nodeset_t(["--fold", "foo", "-i", "foo"], None, b"foo\n")
        # With no range
        self._nodeset_t(["--fold", "foo,bar", "--intersection", "foo"], None, b"foo\n")
        # Normal with range
        self._nodeset_t(["--fold", "foo[0-5]", "-i", "foo[0-10]"], None, b"foo[0-5]\n")
        self._nodeset_t(["--fold", "foo[0-10]", "-i", "foo[0-5]"], None, b"foo[0-5]\n")
        self._nodeset_t(["--fold", "foo[6-10]", "-i", "bar[0-5]"], None, b"\n")
        self._nodeset_t(["--fold", "foo[0-10]", "foo[13-18]", "-i", "foo[5-10,15]"], None, b"foo[5-10,15]\n")
        # numerical bracket folding (#228)
        self._nodeset_t(["--fold", "node123[1-2]", "-i", "node1232"], None, b"node1232\n")
        self._nodeset_t(["--fold", "node023[1-2]0", "-i", "node02320"], None, b"node02320\n")
        self._nodeset_t(["--fold", "node023[1-2]0-ipmi2", "-i", "node02320-ipmi2"], None, b"node02320-ipmi2\n")
        self._nodeset_t(["--fold", "-i", "foo", "foo"], None, b"foo\n", 0,
                        b"WARNING: empty left operand for set operation\n")

    def test_014_fold_intersection_stdin(self):
        """test nodeset --fold --intersection (stdin)"""
        # Empty result
        self._nodeset_t(["--fold", "--intersection", "foo"], "", b"\n", 0,
                        b"WARNING: empty left operand for set operation\n")
        self._nodeset_t(["--fold", "--intersection", "foo"], "\n", b"\n", 0,
                        b"WARNING: empty left operand for set operation\n")
        self._nodeset_t(["--fold", "-i", "foo"], "foo\n", b"foo\n")
        # With no range
        self._nodeset_t(["--fold", "-i", "foo"], "foo,bar\n", b"foo\n")
        # Normal with range
        self._nodeset_t(["--fold", "-i", "foo[0-10]"], "foo[0-5]\n", b"foo[0-5]\n")
        self._nodeset_t(["--fold", "-i", "foo[0-5]"], "foo[0-10]\n", b"foo[0-5]\n")
        # Do no change
        self._nodeset_t(["--fold", "-i", "bar[0-5]"], "foo[6-10]\n", b"\n")
        self._nodeset_t(["--fold", "-i", "foo[5-10,15]"], "foo[0-10]\nfoo[13-18]\n", b"foo[5-10,15]\n")
        # using stdin for -i
        self._nodeset_t(["-f", "foo[1-6]", "-i", "-"], "foo4 foo5 foo6\n", b"foo[4-6]\n")
        self._nodeset_t(["-f", "-i", "-", "foo[1-6]"], "foo4 foo5 foo6\n",
                        b"foo[1-6]\n", 0,
                        b"WARNING: empty left operand for set operation\n")
        # numerical bracket folding (#228)
        self._nodeset_t(["--fold", "-i", "node123[1-2]"], "node1232\n", b"node1232\n")
        self._nodeset_t(["--fold", "-i", "node023[1-2]0"], "node02320\n", b"node02320\n")
        self._nodeset_t(["--fold", "-i", "node023[1-2]0-ipmi2"], "node02320-ipmi2\n", b"node02320-ipmi2\n")

    def test_015_rangeset(self):
        """test nodeset --rangeset"""
        self._nodeset_t(["--fold", "--rangeset", "1,2"], None, b"1-2\n")
        self._nodeset_t(["--expand", "-R", "1-2"], None, b"1 2\n")
        self._nodeset_t(["--fold", "-R", "1-2", "-X", "2-3"], None, b"1,3\n")

    def test_016_rangeset_stdin(self):
        """test nodeset --rangeset (stdin)"""
        self._nodeset_t(["--fold", "--rangeset"], "1,2\n", b"1-2\n")
        self._nodeset_t(["--expand", "-R"], "1-2\n", b"1 2\n")
        self._nodeset_t(["--fold", "-R", "-X", "2-3"], "1-2\n", b"1,3\n")

    def test_017_stdin(self):
        """test nodeset - (stdin)"""
        self._nodeset_t(["-f", "-"], "foo\n", b"foo\n")
        self._nodeset_t(["-f", "-"], "foo1 foo2 foo3\n", b"foo[1-3]\n")
        self._nodeset_t(["--autostep=2", "-f"], "foo0 foo2 foo4 foo6\n", b"foo[0-6/2]\n")
        self._nodeset_t(["--autostep=auto", "-f"], "foo0 foo2 foo4 foo6\n", b"foo[0-6/2]\n")
        self._nodeset_t(["--autostep=100%", "-f"], "foo0 foo2 foo4 foo6\n", b"foo[0-6/2]\n")
        self._nodeset_t(["--autostep=0%", "-f"], "foo0 foo2 foo4 foo6\n", b"foo[0-6/2]\n")

    def test_018_split(self):
        """test nodeset --split"""
        self._nodeset_t(["--split=2", "-f", "bar"], None, b"bar\n")
        self._nodeset_t(["--split", "2", "-f", "foo,bar"], None, b"bar\nfoo\n")
        self._nodeset_t(["--split", "2", "-e", "foo", "bar", "bur", "oof", "gcc"], None, b"bar bur foo\ngcc oof\n")
        self._nodeset_t(["--split=2", "-f", "foo[2-9]"], None, b"foo[2-5]\nfoo[6-9]\n")
        self._nodeset_t(["--split=2", "-f", "foo[2-3,7]", "bar9"], None, b"bar9,foo2\nfoo[3,7]\n")
        self._nodeset_t(["--split=3", "-f", "foo[2-9]"], None, b"foo[2-4]\nfoo[5-7]\nfoo[8-9]\n")
        self._nodeset_t(["--split=1", "-f", "foo2", "foo3"], None, b"foo[2-3]\n")
        self._nodeset_t(["--split=4", "-f", "foo[2-3]"], None, b"foo2\nfoo3\n")
        self._nodeset_t(["--split=4", "-f", "foo3", "foo2"], None, b"foo2\nfoo3\n")
        self._nodeset_t(["--split=2", "-e", "foo[2-9]"], None, b"foo2 foo3 foo4 foo5\nfoo6 foo7 foo8 foo9\n")
        self._nodeset_t(["--split=3", "-e", "foo[2-9]"], None, b"foo2 foo3 foo4\nfoo5 foo6 foo7\nfoo8 foo9\n")
        self._nodeset_t(["--split=1", "-e", "foo3", "foo2"], None, b"foo2 foo3\n")
        self._nodeset_t(["--split=4", "-e", "foo[2-3]"], None, b"foo2\nfoo3\n")
        self._nodeset_t(["--split=4", "-e", "foo2", "foo3"], None, b"foo2\nfoo3\n")
        self._nodeset_t(["--split=2", "-c", "foo2", "foo3"], None, b"1\n1\n")

    def test_019_contiguous(self):
        """test nodeset --contiguous"""
        self._nodeset_t(["--contiguous", "-f", "bar"], None, b"bar\n")
        self._nodeset_t(["--contiguous", "-f", "foo,bar"], None, b"bar\nfoo\n")
        self._nodeset_t(["--contiguous", "-f", "foo", "bar", "bur", "oof", "gcc"], None, b"bar\nbur\nfoo\ngcc\noof\n")
        self._nodeset_t(["--contiguous", "-e", "foo", "bar", "bur", "oof", "gcc"], None, b"bar\nbur\nfoo\ngcc\noof\n")
        self._nodeset_t(["--contiguous", "-f", "foo2"], None, b"foo2\n")
        self._nodeset_t(["--contiguous", "-R", "-f", "2"], None, b"2\n")
        self._nodeset_t(["--contiguous", "-f", "foo[2-9]"], None, b"foo[2-9]\n")
        self._nodeset_t(["--contiguous", "-f", "foo[2-3,7]", "bar9"], None, b"bar9\nfoo[2-3]\nfoo7\n")
        self._nodeset_t(["--contiguous", "-R", "-f", "2-3,7", "9"], None, b"2-3\n7\n9\n")
        self._nodeset_t(["--contiguous", "-f", "foo2", "foo3"], None, b"foo[2-3]\n")
        self._nodeset_t(["--contiguous", "-f", "foo3", "foo2"], None, b"foo[2-3]\n")
        self._nodeset_t(["--contiguous", "-f", "foo3", "foo1"], None, b"foo1\nfoo3\n")
        self._nodeset_t(["--contiguous", "-f", "foo[1-5/2]", "foo7"], None, b"foo1\nfoo3\nfoo5\nfoo7\n")

    def test_020_slice(self):
        """test nodeset -I/--slice"""
        self._nodeset_t(["--slice=0", "-f", "bar"], None, b"bar\n")
        self._nodeset_t(["--slice=0", "-e", "bar"], None, b"bar\n")
        self._nodeset_t(["--slice=1", "-f", "bar"], None, b"\n")
        self._nodeset_t(["--slice=0-1", "-f", "bar"], None, b"bar\n")
        self._nodeset_t(["-I0", "-f", "bar[34-68,89-90]"], None, b"bar34\n")
        self._nodeset_t(["-R", "-I0", "-f", "34-68,89-90"], None, b"34\n")
        self._nodeset_t(["-I 0", "-f", "bar[34-68,89-90]"], None, b"bar34\n")
        self._nodeset_t(["-I 0", "-e", "bar[34-68,89-90]"], None, b"bar34\n")
        self._nodeset_t(["-I 0-3", "-f", "bar[34-68,89-90]"], None, b"bar[34-37]\n")
        self._nodeset_t(["-I 0-3", "-f", "bar[34-68,89-90]", "-x", "bar34"], None, b"bar[35-38]\n")
        self._nodeset_t(["-I 0-3", "-f", "bar[34-68,89-90]", "-x", "bar35"], None, b"bar[34,36-38]\n")
        self._nodeset_t(["-I 0-3", "-e", "bar[34-68,89-90]"], None, b"bar34 bar35 bar36 bar37\n")
        self._nodeset_t(["-I 3,1,0,2", "-f", "bar[34-68,89-90]"], None, b"bar[34-37]\n")
        self._nodeset_t(["-I 1,3,7,10,16,20,30,34-35,37", "-f", "bar[34-68,89-90]"], None, b"bar[35,37,41,44,50,54,64,68,89]\n")
        self._nodeset_t(["-I 8", "-f", "bar[34-68,89-90]"], None, b"bar42\n")
        self._nodeset_t(["-I 8-100", "-f", "bar[34-68,89-90]"], None, b"bar[42-68,89-90]\n")
        self._nodeset_t(["-I 0-100", "-f", "bar[34-68,89-90]"], None, b"bar[34-68,89-90]\n")
        self._nodeset_t(["-I 8-100/2", "-f", "bar[34-68,89-90]"], None, b"bar[42,44,46,48,50,52,54,56,58,60,62,64,66,68,90]\n")
        self._nodeset_t(["--autostep=2", "-I 8-100/2", "-f", "bar[34-68,89-90]"], None, b"bar[42-68/2,90]\n")
        self._nodeset_t(["--autostep=93%", "-I 8-100/2", "-f", "bar[34-68,89-90]"], None, b"bar[42-68/2,90]\n")
        self._nodeset_t(["--autostep=94%", "-I 8-100/2", "-f", "bar[34-68,89-90]"], None, b"bar[42,44,46,48,50,52,54,56,58,60,62,64,66,68,90]\n")
        self._nodeset_t(["--autostep=auto", "-I 8-100/2", "-f", "bar[34-68,89-90]"], None, b"bar[42,44,46,48,50,52,54,56,58,60,62,64,66,68,90]\n")
        self._nodeset_t(["--autostep=auto", "-I 8-100/2", "-f", "bar[34-68]"], None, b"bar[42-68/2]\n")
        self._nodeset_t(["--autostep=100%", "-I 8-100/2", "-f", "bar[34-68]"], None, b"bar[42-68/2]\n")

    def test_021_slice_stdin(self):
        """test nodeset -I/--slice (stdin)"""
        self._nodeset_t(["--slice=0", "-f"], "bar\n", b"bar\n")
        self._nodeset_t(["--slice=0", "-e"], "bar\n", b"bar\n")
        self._nodeset_t(["--slice=1", "-f"], "bar\n", b"\n")
        self._nodeset_t(["--slice=0-1", "-f"], "bar\n", b"bar\n")
        self._nodeset_t(["-I0", "-f"], "bar[34-68,89-90]\n", b"bar34\n")
        self._nodeset_t(["-R", "-I0", "-f"], "34-68,89-90\n", b"34\n")
        self._nodeset_t(["-I 0", "-f"], "bar[34-68,89-90]\n", b"bar34\n")
        self._nodeset_t(["-I 0", "-e"], "bar[34-68,89-90]\n", b"bar34\n")
        self._nodeset_t(["-I 0-3", "-f"], "bar[34-68,89-90]\n", b"bar[34-37]\n")
        self._nodeset_t(["-I 0-3", "-f", "-x", "bar34"], "bar[34-68,89-90]\n", b"bar[35-38]\n")
        self._nodeset_t(["-I 0-3", "-f", "-x", "bar35"], "bar[34-68,89-90]\n", b"bar[34,36-38]\n")
        self._nodeset_t(["-I 0-3", "-e"], "bar[34-68,89-90]\n", b"bar34 bar35 bar36 bar37\n")
        self._nodeset_t(["-I 3,1,0,2", "-f"], "bar[34-68,89-90]\n", b"bar[34-37]\n")
        self._nodeset_t(["-I 1,3,7,10,16,20,30,34-35,37", "-f"], "bar[34-68,89-90]\n", b"bar[35,37,41,44,50,54,64,68,89]\n")
        self._nodeset_t(["-I 8", "-f"], "bar[34-68,89-90]\n", b"bar42\n")
        self._nodeset_t(["-I 8-100", "-f"], "bar[34-68,89-90]\n", b"bar[42-68,89-90]\n")
        self._nodeset_t(["-I 0-100", "-f"], "bar[34-68,89-90]\n", b"bar[34-68,89-90]\n")
        self._nodeset_t(["-I 8-100/2", "-f"], "bar[34-68,89-90]\n", b"bar[42,44,46,48,50,52,54,56,58,60,62,64,66,68,90]\n")
        self._nodeset_t(["--autostep=2", "-I 8-100/2", "-f"], "bar[34-68,89-90]\n", b"bar[42-68/2,90]\n")
        self._nodeset_t(["--autostep=93%", "-I 8-100/2", "-f"], "bar[34-68,89-90]\n", b"bar[42-68/2,90]\n")
        self._nodeset_t(["--autostep=93.33%", "-I 8-100/2", "-f"], "bar[34-68,89-90]\n", b"bar[42-68/2,90]\n")
        self._nodeset_t(["--autostep=94%", "-I 8-100/2", "-f"], "bar[34-68,89-90]\n", b"bar[42,44,46,48,50,52,54,56,58,60,62,64,66,68,90]\n")
        self._nodeset_t(["--autostep=auto", "-I 8-100/2", "-f"], "bar[34-68,89-90]\n", b"bar[42,44,46,48,50,52,54,56,58,60,62,64,66,68,90]\n")
        self._nodeset_t(["--autostep=2", "-I 8-100/2", "-f"], "bar[34-68]\n", b"bar[42-68/2]\n")

    def test_022_output_format(self):
        """test nodeset -O"""
        self._nodeset_t(["--expand", "--output-format", "/path/%s/", "foo"], None, b"/path/foo/\n")
        self._nodeset_t(["--expand", "-O", "/path/%s/", "-S", ":", "foo"], None, b"/path/foo/\n")
        self._nodeset_t(["--expand", "-O", "/path/%s/", "foo[2]"], None, b"/path/foo2/\n")
        self._nodeset_t(["--expand", "-O", "%s-ib0", "foo[1-4]"], None, b"foo1-ib0 foo2-ib0 foo3-ib0 foo4-ib0\n")
        self._nodeset_t(["--expand", "-O", "%s-ib0", "-S", ":", "foo[1-4]"], None, b"foo1-ib0:foo2-ib0:foo3-ib0:foo4-ib0\n")
        self._nodeset_t(["--fold", "-O", "%s-ipmi", "foo", "bar"], None, b"bar-ipmi,foo-ipmi\n")
        self._nodeset_t(["--fold", "-O", "%s-ib0", "foo1", "foo2"], None, b"foo[1-2]-ib0\n")
        self._nodeset_t(["--fold", "-O", "%s-ib0", "foo1", "foo2", "bar1", "bar2"], None, b"bar[1-2]-ib0,foo[1-2]-ib0\n")
        self._nodeset_t(["--fold", "-O", "%s-ib0", "--autostep=auto", "foo[1-9/2]"], None, b"foo[1-9/2]-ib0\n")
        self._nodeset_t(["--fold", "-O", "%s-ib0", "--autostep=6", "foo[1-9/2]"], None, b"foo[1,3,5,7,9]-ib0\n")
        self._nodeset_t(["--fold", "-O", "%s-ib0", "--autostep=5", "foo[1-9/2]"], None, b"foo[1-9/2]-ib0\n")
        self._nodeset_t(["--count", "-O", "result-%s", "foo1", "foo2"], None, b"result-2\n")
        self._nodeset_t(["--contiguous", "-O", "%s-ipmi", "-f", "foo[2-3,7]", "bar9"], None, b"bar9-ipmi\nfoo[2-3]-ipmi\nfoo7-ipmi\n")
        self._nodeset_t(["--split=2", "-O", "%s-ib", "-e", "foo[2-9]"], None, b"foo2-ib foo3-ib foo4-ib foo5-ib\nfoo6-ib foo7-ib foo8-ib foo9-ib\n")
        self._nodeset_t(["--split=3", "-O", "hwm-%s", "-f", "foo[2-9]"], None, b"hwm-foo[2-4]\nhwm-foo[5-7]\nhwm-foo[8-9]\n")
        self._nodeset_t(["-I0", "-O", "{%s}", "-f", "bar[34-68,89-90]"], None, b"{bar34}\n")
        # RangeSet mode (-R)
        self._nodeset_t(["--fold", "-O", "{%s}", "--rangeset", "1,2"], None, b"{1-2}\n")
        self._nodeset_t(["--expand", "-O", "{%s}", "-R", "1-2"], None, b"{1} {2}\n")
        self._nodeset_t(["--fold", "-O", "{%s}", "-R", "1-2", "-X", "2-3"], None, b"{1,3}\n")
        self._nodeset_t(["--fold", "-O", "{%s}", "-S", ":", "--rangeset", "1,2"], None, b"{1-2}\n")
        self._nodeset_t(["--expand", "-O", "{%s}", "-S", ":", "-R", "1-2"], None, b"{1}:{2}\n")
        self._nodeset_t(["--fold", "-O", "{%s}", "-S", ":", "-R", "1-2", "-X", "2-3"], None, b"{1,3}\n")
        self._nodeset_t(["-R", "-I0", "-O", "{%s}", "-f", "34-68,89-90"], None, b"{34}\n")

    def test_023_axis(self):
        """test nodeset folding with --axis"""
        self._nodeset_t(["--axis=0", "-f", "bar"], None, b"bar\n")
        self._nodeset_t(["--axis=1", "-f", "bar"], None, b"bar\n")
        self._nodeset_t(["--axis=1", "-R", "-f", "1,2,3"], None, None, 2,
                        b"--axis option is only supported when folding nodeset\n")
        self._nodeset_t(["--axis=1", "-e", "bar"], None, None, 2,
                        b"--axis option is only supported when folding nodeset\n")

        # 1D and 2D nodeset: fold along axis 0 only
        self._nodeset_t(["--axis=1", "-f", "comp-[1-2]-[1-3],login-[1-2]"], None,
                        b'comp-[1-2]-1,comp-[1-2]-2,comp-[1-2]-3,login-[1-2]\n')
        # 1D and 2D nodeset: fold along axis 1 only
        self._nodeset_t(["--axis=2", "-f", "comp-[1-2]-[1-3],login-[1-2]"], None,
                        b'comp-1-[1-3],comp-2-[1-3],login-1,login-2\n')
        # 1D and 2D nodeset: fold along last axis only
        self._nodeset_t(["--axis=-1", "-f", "comp-[1-2]-[1-3],login-[1-2]"], None,
                        b'comp-1-[1-3],comp-2-[1-3],login-[1-2]\n')

        # test for a common case
        ndnodes = []
        for ib in range(2):
            for idx in range(500):
                ndnodes.append("node%d-ib%d" % (idx, ib))
        random.shuffle(ndnodes)

        self._nodeset_t(["--axis=1", "-f"] + ndnodes, None,
                        b"node[0-499]-ib0,node[0-499]-ib1\n")

        exp_result = []
        for idx in range(500):
            exp_result.append("node%d-ib[0-1]" % idx)

        exp_result_str = '%s\n' % ','.join(exp_result)

        self._nodeset_t(["--axis=2", "-f"] + ndnodes, None,
                        exp_result_str.encode())

        # 4D test
        ndnodes = ["c-1-2-3-4", "c-2-2-3-4", "c-3-2-3-4", "c-5-5-5-5",
                   "c-5-7-5-5", "c-5-9-5-5", "c-5-11-5-5", "c-9-8-8-08",
                   "c-9-8-8-09"]
        self._nodeset_t(["--axis=1", "-f"] + ndnodes, None,
                        b"c-5-5-5-5,c-5-7-5-5,c-5-9-5-5,c-5-11-5-5,c-[1-3]-2-3-4,c-9-8-8-08,c-9-8-8-09\n")
        self._nodeset_t(["--axis=2", "-f"] + ndnodes, None,
                        b"c-5-[5,7,9,11]-5-5,c-1-2-3-4,c-2-2-3-4,c-3-2-3-4,c-9-8-8-08,c-9-8-8-09\n")
        self._nodeset_t(["--axis=3", "-f"] + ndnodes, None,
                        b"c-5-5-5-5,c-5-7-5-5,c-5-9-5-5,c-5-11-5-5,c-1-2-3-4,c-2-2-3-4,c-3-2-3-4,c-9-8-8-08,c-9-8-8-09\n")
        self._nodeset_t(["--axis=4", "-f"] + ndnodes, None,
                        b"c-5-5-5-5,c-5-7-5-5,c-5-9-5-5,c-5-11-5-5,c-1-2-3-4,c-2-2-3-4,c-3-2-3-4,c-9-8-8-[08-09]\n")

        self._nodeset_t(["--axis=1-2", "-f"] + ndnodes, None,
                        b"c-5-[5,7,9,11]-5-5,c-[1-3]-2-3-4,c-9-8-8-08,c-9-8-8-09\n")
        self._nodeset_t(["--axis=2-3", "-f"] + ndnodes, None,
                        b"c-5-[5,7,9,11]-5-5,c-1-2-3-4,c-2-2-3-4,c-3-2-3-4,c-9-8-8-08,c-9-8-8-09\n")
        self._nodeset_t(["--axis=3-4", "-f"] + ndnodes, None,
                        b"c-5-5-5-5,c-5-7-5-5,c-5-9-5-5,c-5-11-5-5,c-1-2-3-4,c-2-2-3-4,c-3-2-3-4,c-9-8-8-[08-09]\n")
        self._nodeset_t(["--axis=1-3", "-f"] + ndnodes, None,
                        b"c-5-[5,7,9,11]-5-5,c-[1-3]-2-3-4,c-9-8-8-08,c-9-8-8-09\n")
        self._nodeset_t(["--axis=2-4", "-f"] + ndnodes, None,
                        b"c-5-[5,7,9,11]-5-5,c-1-2-3-4,c-2-2-3-4,c-3-2-3-4,c-9-8-8-[08-09]\n")

        self._nodeset_t(["--axis=1-4", "-f"] + ndnodes, None,
                        b"c-5-[5,7,9,11]-5-5,c-[1-3]-2-3-4,c-9-8-8-[08-09]\n")
        self._nodeset_t(["-f"] + ndnodes, None,
                        b"c-5-[5,7,9,11]-5-5,c-[1-3]-2-3-4,c-9-8-8-[08-09]\n")

        # a case where axis and autostep are working
        self._nodeset_t(["--autostep=4", "--axis=1-2", "-f"] + ndnodes, None,
                        b"c-5-[5-11/2]-5-5,c-[1-3]-2-3-4,c-9-8-8-08,c-9-8-8-09\n")

    def test_024_axis_stdin(self):
        """test nodeset folding with --axis (stdin)"""
        self._nodeset_t(["--axis=0", "-f"], "bar\n", b"bar\n")
        self._nodeset_t(["--axis=1", "-f"], "bar\n", b"bar\n")
        self._nodeset_t(["--axis=1", "-R", "-f"], "1,2,3", None, 2,
                        b"--axis option is only supported when folding nodeset\n")
        self._nodeset_t(["--axis=1", "-e"], "bar\n", None, 2,
                        b"--axis option is only supported when folding nodeset\n")

        # 1D and 2D nodeset: fold along axis 0 only
        self._nodeset_t(["--axis=1", "-f"], "comp-[1-2]-[1-3],login-[1-2]\n",
                        b'comp-[1-2]-1,comp-[1-2]-2,comp-[1-2]-3,login-[1-2]\n')
        # 1D and 2D nodeset: fold along axis 1 only
        self._nodeset_t(["--axis=2", "-f"], "comp-[1-2]-[1-3],login-[1-2]\n",
                        b'comp-1-[1-3],comp-2-[1-3],login-1,login-2\n')
        # 1D and 2D nodeset: fold along last axis only
        self._nodeset_t(["--axis=-1", "-f"], "comp-[1-2]-[1-3],login-[1-2]\n",
                        b'comp-1-[1-3],comp-2-[1-3],login-[1-2]\n')

        # test for a common case
        ndnodes = []
        for ib in range(2):
            for idx in range(500):
                ndnodes.append("node%d-ib%d" % (idx, ib))
        random.shuffle(ndnodes)

        self._nodeset_t(["--axis=1", "-f"], '\n'.join(ndnodes) + '\n',
                        b"node[0-499]-ib0,node[0-499]-ib1\n")

        exp_result = []
        for idx in range(500):
            exp_result.append("node%d-ib[0-1]" % idx)

        exp_result_str = '%s\n' % ','.join(exp_result)

        self._nodeset_t(["--axis=2", "-f"], '\n'.join(ndnodes) + '\n',
                        exp_result_str.encode())

    def test_025_pick(self):
        """test nodeset --pick"""
        for num in range(1, 100):
            self._nodeset_t(["--count", "--pick", str(num), "foo[1-100]"],
                            None, str(num).encode() + b'\n')
            self._nodeset_t(["--count", "--pick", str(num), "-R", "1-100"],
                            None, str(num).encode() + b'\n')


class CLINodesetGroupResolverTest1(CLINodesetTestBase):
    """Unit test class for testing CLI/Nodeset.py with custom Group Resolver"""

    def setUp(self):
        # Special tests that require a default group source set
        #
        # The temporary file needs to be persistent during the tests
        # because GroupResolverConfig does lazy init, this is why we
        # use an instance variable self.f
        #
        self.f = make_temp_file(dedent("""
            [Main]
            default: local

            [local]
            map: echo example[1-100]
            all: echo example[1-1000]
            list: echo foo bar moo
            """).encode())
        set_std_group_resolver(GroupResolverConfig(self.f.name))

    def tearDown(self):
        set_std_group_resolver(None)
        self.f = None  # used to release temp file

    def test_022_list(self):
        """test nodeset --list"""
        self._nodeset_t(["--list"], None, b"@bar\n@foo\n@moo\n")
        self._nodeset_t(["-ll"], None, b"@bar example[1-100]\n@foo example[1-100]\n@moo example[1-100]\n")
        self._nodeset_t(["-lll"], None, b"@bar example[1-100] 100\n@foo example[1-100] 100\n@moo example[1-100] 100\n")
        self._nodeset_t(["-l", "example[4,95]", "example5"], None, b"@bar\n@foo\n@moo\n")
        self._nodeset_t(["-ll", "example[4,95]", "example5"], None, b"@bar example[4-5,95]\n@foo example[4-5,95]\n@moo example[4-5,95]\n")
        self._nodeset_t(["-lll", "example[4,95]", "example5"], None, b"@bar example[4-5,95] 3/100\n@foo example[4-5,95] 3/100\n@moo example[4-5,95] 3/100\n")
        # test empty result
        self._nodeset_t(["-l", "foo[3-70]", "bar6"], None, b"")
        # more arg-mixed tests
        self._nodeset_t(["-a", "-l"], None, b"@bar\n@foo\n@moo\n")
        self._nodeset_t(["-a", "-l", "-x example[1-100]"], None, b"")
        self._nodeset_t(["-a", "-l", "-x example[1-40]"], None, b"@bar\n@foo\n@moo\n")
        self._nodeset_t(["-l", "-x example3"], None, b"") # no -a, remove from nothing
        self._nodeset_t(["-l", "-i example3"], None, b"") # no -a, intersect from nothing
        self._nodeset_t(["-l", "-X example3"], None, b"@bar\n@foo\n@moo\n") # no -a, xor from nothing
        self._nodeset_t(["-l", "-", "-i example3"], "example[3,500]\n", b"@bar\n@foo\n@moo\n")

    def test_023_list_all(self):
        """test nodeset --list-all"""
        self._nodeset_t(["--list-all"], None, b"@bar\n@foo\n@moo\n")
        self._nodeset_t(["-L"], None, b"@bar\n@foo\n@moo\n")
        self._nodeset_t(["-LL"], None, b"@bar example[1-100]\n@foo example[1-100]\n@moo example[1-100]\n")
        self._nodeset_t(["-LLL"], None, b"@bar example[1-100] 100\n@foo example[1-100] 100\n@moo example[1-100] 100\n")


class CLINodesetGroupResolverTest2(CLINodesetTestBase):
    """Unit test class for testing CLI/Nodeset.py with custom Group Resolver"""

    def setUp(self):
        # Special tests that require a default group source set
        self.f = make_temp_file(dedent("""
            [Main]
            default: test

            [test]
            map: echo example[1-100]
            all: echo @foo,@bar,@moo
            list: echo foo bar moo

            [other]
            map: echo nova[030-489]
            all: echo @baz,@qux,@norf
            list: echo baz qux norf
            """).encode())
        set_std_group_resolver(GroupResolverConfig(self.f.name))

    def tearDown(self):
        set_std_group_resolver(None)
        self.f = None  # used to release temp file

    def test_024_groups(self):
        self._nodeset_t(["--split=2", "-r", "unknown2", "unknown3"], None, b"unknown2\nunknown3\n")
        self._nodeset_t(["-f", "-a"], None, b"example[1-100]\n")
        self._nodeset_t(["-f", "@moo"], None, b"example[1-100]\n")
        self._nodeset_t(["-f", "@moo", "@bar"], None, b"example[1-100]\n")
        self._nodeset_t(["-e", "-a"], None, ' '.join(["example%d" % i for i in range(1, 101)]).encode() + b'\n')
        self._nodeset_t(["-c", "-a"], None, b"100\n")
        self._nodeset_t(["-r", "-a"], None, b"@bar\n")
        self._nodeset_t(["--split=2", "-r", "unknown2", "unknown3"], None, b"unknown2\nunknown3\n")

    # We need to split following unit tests in order to reset group
    # source in setUp/tearDown...

    def test_025_groups(self):
        self._nodeset_t(["-s", "test", "-c", "-a", "-d"], None, b"100\n")

    def test_026_groups(self):
        self._nodeset_t(["-s", "test", "-r", "-a"], None, b"@test:bar\n")

    def test_027_groups(self):
        self._nodeset_t(["-s", "test", "-G", "-r", "-a"], None, b"@bar\n")

    def test_028_groups(self):
        self._nodeset_t(["-s", "test", "--groupsources"], None, b"test (default)\nother\n")

    def test_029_groups(self):
        self._nodeset_t(["-s", "test", "-q", "--groupsources"], None, b"test\nother\n")

    def test_030_groups(self):
        self._nodeset_t(["-f", "-a", "-"], "example101\n", b"example[1-101]\n")
        self._nodeset_t(["-f", "-a", "-"], "example102 example101\n", b"example[1-102]\n")

    # Check default group source switching...

    def test_031_groups(self):
        self._nodeset_t(["-s", "other", "-c", "-a", "-d"], None, b"460\n")
        self._nodeset_t(["-s", "test", "-c", "-a", "-d"], None, b"100\n")

    def test_032_groups(self):
        self._nodeset_t(["-s", "other", "-r", "-a"], None, b"@other:baz\n")
        self._nodeset_t(["-s", "test", "-r", "-a"], None, b"@test:bar\n")

    def test_033_groups(self):
        self._nodeset_t(["-s", "other", "-G", "-r", "-a"], None, b"@baz\n")
        self._nodeset_t(["-s", "test", "-G", "-r", "-a"], None, b"@bar\n")

    def test_034_groups(self):
        self._nodeset_t(["--groupsources"], None, b"test (default)\nother\n")

    def test_035_groups(self):
        self._nodeset_t(["-s", "other", "--groupsources"], None, b"other (default)\ntest\n")

    def test_036_groups(self):
        self._nodeset_t(["--groupsources"], None, b"test (default)\nother\n")

    def test_037_groups_output_format(self):
        self._nodeset_t(["-r", "-O", "{%s}", "-a"], None, b"{@bar}\n")

    def test_038_groups_output_format(self):
        self._nodeset_t(["-O", "{%s}", "-s", "other", "-r", "-a"], None, b"{@other:baz}\n")

    def test_039_list_all(self):
        """test nodeset --list-all (multi sources)"""
        self._nodeset_t(["--list-all"], None,
                        b"@bar\n@foo\n@moo\n@other:baz\n@other:norf\n@other:qux\n")
        self._nodeset_t(["--list-all", "-G"], None,
                        b"@bar\n@foo\n@moo\n@baz\n@norf\n@qux\n")
        self._nodeset_t(["-GL"], None,
                        b"@bar\n@foo\n@moo\n@baz\n@norf\n@qux\n")
        self._nodeset_t(["--list-all", "-s", "other"], None,
                        b"@other:baz\n@other:norf\n@other:qux\n@test:bar\n@test:foo\n@test:moo\n")
        self._nodeset_t(["--list-all", "-G", "-s", "other"], None,
                        b"@baz\n@norf\n@qux\n@bar\n@foo\n@moo\n") # 'other' source first

    def test_040_wildcards(self):
        """test nodeset with wildcards"""
        self._nodeset_t(["-f", "*"], None, b"example[1-100]\n")
        self._nodeset_t(["-f", "x*"], None, b"\n")  # no match
        self._nodeset_t(["-s", "other", "-f", "*"], None, b"nova[030-489]\n")
        self._nodeset_t(["-G", "-s", "other", "-f", "*"], None,
                        b"nova[030-489]\n")
        self._nodeset_t(["-s", "other", "-f", "nova0??"], None,
                        b"nova[030-099]\n")
        self._nodeset_t(["-s", "other", "-f", "nova?[12-42]"], None,
                        b"nova[030-042,112-142,212-242,312-342,412-442]\n")
        self._nodeset_t(["-s", "other", "-f", "*!*[033]"], None,
                        b"nova[030-032,034-489]\n")
        self._nodeset_t(["-s", "other", "--autostep=3", "-f", "*!*[033-099/2]"],
                        None, b"nova[030-031,032-100/2,101-489]\n")


class CLINodesetGroupResolverTest3(CLINodesetTestBase):
    """Unit test class for testing CLI/Nodeset.py with custom Group Resolver

    A case we support: one of the source misses the list upcall.
    """

    def setUp(self):
        # Special tests that require a default group source set
        self.f = make_temp_file(dedent("""
            [Main]
            default: test

            [test]
            map: echo example[1-100]
            all: echo @foo,@bar,@moo
            list: echo foo bar moo

            [other]
            map: echo nova[030-489]
            all: echo @baz,@qux,@norf
            list: echo baz qux norf

            [pdu]
            map: echo pdu-[0-3]-[1-2]
            """).encode())
        set_std_group_resolver(GroupResolverConfig(self.f.name))

    def tearDown(self):
        set_std_group_resolver(None)
        self.f = None  # used to release temp file

    def test_list_all(self):
        """test nodeset --list-all (w/ missing list upcall)"""
        self._nodeset_t(["--list-all"], None,
                        b"@bar\n@foo\n@moo\n@other:baz\n@other:norf\n@other:qux\n", 0,
                        b"Warning: No list upcall defined for group source pdu\n")
        self._nodeset_t(["-LL"], None,
                        b"@bar example[1-100]\n@foo example[1-100]\n@moo example[1-100]\n"
                        b"@other:baz nova[030-489]\n@other:norf nova[030-489]\n@other:qux nova[030-489]\n", 0,
                        b"Warning: No list upcall defined for group source pdu\n")
        self._nodeset_t(["-LLL"], None,
                        b"@bar example[1-100] 100\n@foo example[1-100] 100\n@moo example[1-100] 100\n"
                        b"@other:baz nova[030-489] 460\n@other:norf nova[030-489] 460\n@other:qux nova[030-489] 460\n", 0,
                        b"Warning: No list upcall defined for group source pdu\n")

    def test_list_failure(self):
        """test nodeset --list -s source w/ missing list upcall"""
        self._nodeset_t(["--list", "-s", "pdu"], None, b"", 1,
                        b'No list upcall defined for group source "pdu"\n')


class CLINodesetGroupResolverConfigErrorTest(CLINodesetTestBase):
    """Unit test class for testing GroupResolverConfigError"""

    def setUp(self):
        self.dname = make_temp_dir()
        self.gconff = make_temp_file(dedent("""
            [Main]
            default: default
            autodir: %s
            """ % self.dname).encode('ascii'))
        self.yamlf = make_temp_file(dedent("""
            default:
                compute: 'foo'
            broken: i am not a dict
            """).encode('ascii'), suffix=".yaml", dir=self.dname)

        set_std_group_resolver(GroupResolverConfig(self.gconff.name))

    def tearDown(self):
        set_std_group_resolver(None)
        self.gconff = None
        self.yamlf = None
        os.rmdir(self.dname)

    def test_bad_yaml_config(self):
        """test nodeset with bad yaml config"""
        self._nodeset_t(["--list-all"], None, b"", 1,
                        b"invalid content (group source 'broken' is not a dict)\n")


class CLINodesetEmptyGroupsConf(CLINodesetTestBase):
    """Unit test class for testing empty groups.conf"""

    def setUp(self):
        self.gconff = make_temp_file(b"")
        set_std_group_resolver(GroupResolverConfig(self.gconff.name))

    def tearDown(self):
        set_std_group_resolver(None)
        self.gconff = None

    def test_empty_groups_conf(self):
        """test nodeset with empty groups.conf"""
        self._nodeset_t(["--list-all"], None, b"")


class CLINodesetMalformedGroupsConf(CLINodesetTestBase):
    """Unit test class for testing malformed groups.conf"""

    def setUp(self):
        self.gconff = make_temp_file(b"[Main")
        set_std_group_resolver(GroupResolverConfig(self.gconff.name))

    def tearDown(self):
        set_std_group_resolver(None)
        self.gconff = None

    def test_malformed_groups_conf(self):
        """test nodeset with malformed groups.conf"""
        self._nodeset_t(["--list-all"], None, b"", 1, b"'[Main'\n")


class CLINodesetGroupsConfOption(CLINodesetTestBase):
    """Unit test class for testing --groupsconf option"""

    def setUp(self):
        self.gconff = make_temp_file(dedent("""
            [Main]
            default: global_default

            [global_default]
            map: echo example[1-100]
            all: echo @foo,@bar,@moo
            list: echo foo bar moo
            """).encode())
        set_std_group_resolver_config(self.gconff.name)

        # passed to --groupsconf
        self.custf = make_temp_file(dedent("""
            [Main]
            default: custom

            [custom]
            map: echo custom[7-42]
            all: echo @selene,@artemis
            list: echo selene artemis
            """).encode())

    def tearDown(self):
        set_std_group_resolver(None)
        self.gconff = None
        self.custf = None

    def test_groupsconf_option(self):
        """test nodeset with --groupsconf"""
        self._nodeset_t(["--list-all"], None, b"@bar\n@foo\n@moo\n")
        self._nodeset_t(["-f", "@foo"], None, b"example[1-100]\n")
        self._nodeset_t(["--groupsconf", self.custf.name, "--list-all"], None, b"@artemis\n@selene\n")
        self._nodeset_t(["--groupsconf", self.custf.name, "-f", "@artemis"], None, b"custom[7-42]\n")
