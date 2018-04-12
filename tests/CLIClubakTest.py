# ClusterShell.CLI.Clubak test suite
# Written by S. Thiell

"""Unit test for CLI.Clubak"""

import re
from textwrap import dedent
import unittest

from TLib import *
from ClusterShell.CLI.Clubak import main

from ClusterShell.NodeSet import set_std_group_resolver, \
                                 set_std_group_resolver_config


def _outfmt(*args):
    outfmt = "---------------\n%s\n---------------\n bar\n"
    res = outfmt % args
    return res.encode()

def _outfmt_verb(*args):
    outfmt = "INPUT foo: bar\n---------------\n%s\n---------------\n bar\n"
    res = outfmt % args
    return res.encode()


class CLIClubakTest(unittest.TestCase):
    """Unit test class for testing CLI/Clubak.py"""

    def _clubak_t(self, args, stdin, expected_stdout, expected_rc=0,
                  expected_stderr=None):
        CLI_main(self, main, ['clubak'] + args, stdin, expected_stdout,
                 expected_rc, expected_stderr)

    def test_000_noargs(self):
        """test clubak (no argument)"""
        self._clubak_t([], b"foo: bar\n", _outfmt('foo'))
        self._clubak_t([], b"foo space: bar\n", _outfmt('foo space'))
        self._clubak_t([], b"foo space1: bar\n", _outfmt('foo space1'))
        self._clubak_t([], b"foo space1: bar\nfoo space2: bar",
                       _outfmt('foo space1') + _outfmt('foo space2'))
        self._clubak_t([], b": bar\n", b'', 1, b'clubak: no node found: ": bar"\n')
        self._clubak_t([], b"foo[: bar\n", _outfmt('foo['))
        self._clubak_t([], b"]o[o]: bar\n", _outfmt(']o[o]'))
        self._clubak_t([], b"foo:\n", b'---------------\nfoo\n---------------\n\n')
        self._clubak_t([], b"foo: \n", b'---------------\nfoo\n---------------\n \n')
        # nD
        self._clubak_t([], b"n1c1: bar\n", _outfmt('n1c1'))
        # Ticket #286
        self._clubak_t([], b"n1c01: bar\n", _outfmt('n1c01'))
        self._clubak_t([], b"n01c01: bar\n", _outfmt('n01c01'))
        self._clubak_t([], b"n001c01: bar\nn001c02: bar\n",
                       _outfmt('n001c01') + _outfmt('n001c02'))

    def test_001_verbosity(self):
        """test clubak (-q/-v/-d)"""
        self._clubak_t(["-d"], b"foo: bar\n", _outfmt_verb('foo'), 0,
                       b'line_mode=False gather=False tree_depth=1\n')
        self._clubak_t(["-d", "-b"], b"foo: bar\n", _outfmt_verb('foo'), 0,
                       b'line_mode=False gather=True tree_depth=1\n')
        self._clubak_t(["-d", "-L"], b"foo: bar\n", b'INPUT foo: bar\nfoo:  bar\n', 0,
                       b'line_mode=True gather=False tree_depth=1\n')
        self._clubak_t(["-v"], b"foo: bar\n", _outfmt_verb('foo'), 0)
        self._clubak_t(["-v", "-b"], b"foo: bar\n", _outfmt_verb('foo'), 0)
        # no node count with -q
        self._clubak_t(["-q", "-b"], b"foo[1-5]: bar\n", _outfmt('foo[1-5]'), 0)

    def test_002_b(self):
        """test clubak (gather -b)"""
        self._clubak_t(["-b"], b"foo: bar\n", _outfmt('foo'))
        self._clubak_t(["-b"], b"foo space: bar\n", _outfmt("foo space"))
        self._clubak_t(["-b"], b"foo space1: bar\n", _outfmt("foo space1"))
        self._clubak_t(["-b"], b"foo space1: bar\nfoo space2: bar",
                       _outfmt("foo space[1-2] (2)"))
        self._clubak_t(["-b"], b"foo space1: bar\nfoo space2: foo",
                       b"---------------\nfoo space1\n---------------\n bar\n---------------\nfoo space2\n---------------\n foo\n")
        self._clubak_t(["-b"], b": bar\n", b"", 1, b'clubak: no node found: ": bar"\n')
        self._clubak_t(["-b"], b"foo[: bar\n", _outfmt("foo["))
        self._clubak_t(["-b"], b"]o[o]: bar\n", _outfmt("]o[o]"))
        self._clubak_t(["-b"], b"foo:\n", b"---------------\nfoo\n---------------\n\n")
        self._clubak_t(["-b"], b"foo: \n", b"---------------\nfoo\n---------------\n \n")
        # nD
        self._clubak_t(["-b"], b"n1c1: bar\n", _outfmt("n1c1"))
        # Ticket #286
        self._clubak_t(["-b"], b"n1c01: bar\n", _outfmt("n1c01"))
        self._clubak_t(["-b"], b"n001c01: bar\n", _outfmt("n001c01"))
        self._clubak_t(["-b"], b"n001c01: bar\nn001c02: bar\n", _outfmt("n001c[01-02] (2)"))

    def test_003_L(self):
        """test clubak (line mode -L)"""
        self._clubak_t(["-L"], b"foo: bar\n", b"foo:  bar\n")
        self._clubak_t(["-L", "-S", ": "], b"foo: bar\n", b"foo: bar\n")
        self._clubak_t(["-bL"], b"foo: bar\n", b"foo:  bar\n")
        self._clubak_t(["-bL", "-S", ": "], b"foo: bar\n", b"foo: bar\n")
        # nD
        self._clubak_t(["-bL", "-S", ": "], b"n1c01: bar\n", b"n1c01: bar\n")

    def test_004_N(self):
        """test clubak (no header -N)"""
        self._clubak_t(["-N"], b"foo: bar\n", b" bar\n")
        self._clubak_t(["-NL"], b"foo: bar\n", b" bar\n")
        self._clubak_t(["-N", "-S", ": "], b"foo: bar\n", b"bar\n")
        self._clubak_t(["-bN"], b"foo: bar\n", b" bar\n")
        self._clubak_t(["-bN", "-S", ": "], b"foo: bar\n", b"bar\n")

    def test_005_fast(self):
        """test clubak (fast mode --fast)"""
        self._clubak_t(["--fast"], b"foo: bar\n", _outfmt("foo"))
        self._clubak_t(["-b", "--fast"], b"foo: bar\n", _outfmt("foo"))
        self._clubak_t(["-b", "--fast"], b"foo2: bar\nfoo1: bar\nfoo4: bar",
                       _outfmt("foo[1-2,4] (3)"))
        # check conflicting options
        self._clubak_t(["-L", "--fast"], b"foo2: bar\nfoo1: bar\nfoo4: bar",
                       b'', 2, b"error: incompatible tree options\n")

    def test_006_tree(self):
        """test clubak (tree mode --tree)"""
        self._clubak_t(["--tree"], b"foo: bar\n", _outfmt("foo"))
        self._clubak_t(["--tree", "-L"], b"foo: bar\n", b"foo:\n bar\n")
        stdin_buf = dedent("""foo1:bar
                              foo2:bar
                              foo1:moo
                              foo1:bla
                              foo2:m00
                              foo2:bla
                              foo1:abc
                              """).encode()
        self._clubak_t(["--tree", "-L"], stdin_buf,
                       re.compile(br"(foo\[1-2\]:\nbar\nfoo2:\n  m00\n  bla\nfoo1:\n  moo\n  bla\n  abc\n"
                                  br"|foo\[1-2\]:\nbar\nfoo1:\n  moo\n  bla\n  abc\nfoo2:\n  m00\n)"))
        # check conflicting options
        self._clubak_t(["--tree", "--fast"], stdin_buf, b'', 2,
                       b"error: incompatible tree options\n")

    def test_007_interpret_keys(self):
        """test clubak (--interpret-keys)"""
        self._clubak_t(["--interpret-keys=auto"], b"foo: bar\n", _outfmt("foo"))
        self._clubak_t(["-b", "--interpret-keys=auto"], b"foo: bar\n", _outfmt("foo"))
        self._clubak_t(["-b", "--interpret-keys=never"], b"foo: bar\n", _outfmt("foo"))
        self._clubak_t(["-b", "--interpret-keys=always"], b"foo: bar\n", _outfmt("foo"))
        self._clubak_t(["-b", "--interpret-keys=always"], b"foo[1-3]: bar\n",
                       _outfmt("foo[1-3] (3)"))
        self._clubak_t(["-b", "--interpret-keys=auto"], b"[]: bar\n", _outfmt("[]"))
        self._clubak_t(["-b", "--interpret-keys=never"], b"[]: bar\n", _outfmt("[]"))
        self._clubak_t(["-b", "--interpret-keys=always"], b"[]: bar\n",
                       b'', 1, b"Parse error: bad range: \"empty range\"\n")

    def test_008_color(self):
        """test clubak (--color)"""
        self._clubak_t(["-b"], b"foo: bar\n", _outfmt("foo"))
        self._clubak_t(["-b", "--color=never"], b"foo: bar\n", _outfmt("foo"))
        self._clubak_t(["-b", "--color=auto"], b"foo: bar\n", _outfmt("foo"))
        self._clubak_t(["-L", "--color=always"], b"foo: bar\n",
                       b"\x1b[94mfoo: \x1b[0m bar\n")
        self._clubak_t(["-b", "--color=always"], b"foo: bar\n",
                       b"\x1b[94m---------------\nfoo\n---------------\x1b[0m\n bar\n")

    def test_009_diff(self):
        """test clubak (--diff)"""
        self._clubak_t(["--diff"], b"foo1: bar\nfoo2: bar", b'')
        self._clubak_t(["--diff"], b"foo1: bar\nfoo2: BAR\nfoo2: end\nfoo1: end",
                       b"--- foo1\n+++ foo2\n@@ -1,2 +1,2 @@\n- bar\n+ BAR\n  end\n")
        self._clubak_t(["--diff"], b"foo1: bar\nfoo2: BAR\nfoo3: bar\nfoo2: end\nfoo1: end\nfoo3: end",
                       b"--- foo[1,3] (2)\n+++ foo2\n@@ -1,2 +1,2 @@\n- bar\n+ BAR\n  end\n")
        self._clubak_t(["--diff", "--color=always"], b"foo1: bar\nfoo2: BAR\nfoo3: bar\nfoo2: end\nfoo1: end\nfoo3: end",
                       b"\x1b[1m--- foo[1,3] (2)\x1b[0m\n\x1b[1m+++ foo2\x1b[0m\n\x1b[96m@@ -1,2 +1,2 @@\x1b[0m\n\x1b[91m- bar\x1b[0m\n\x1b[92m+ BAR\x1b[0m\n  end\n")
        self._clubak_t(["--diff", "-d"], b"foo: bar\n", b"INPUT foo: bar\n", 0,
                       b"line_mode=False gather=True tree_depth=1\n")
        self._clubak_t(["--diff", "-L"], b"foo1: bar\nfoo2: bar", b'', 2,
                       b"error: option mismatch (diff not supported in line_mode)\n")


class CLIClubakTestGroupsConf(CLIClubakTest):
    """Unit test class for testing --groupsconf option"""

    def setUp(self):
        self.gconff = make_temp_file(dedent("""
            [Main]
            default: global_default

            [global_default]
            map: echo foo[1-2]
            all: echo @foo
            list: echo foo
            """).encode())
        set_std_group_resolver_config(self.gconff.name)

        # passed to --groupsconf
        self.custf = make_temp_file(dedent("""
            [Main]
            default: custom

            [custom]
            map: echo foo[1-2]
            all: echo @bar
            list: echo bar
            """).encode())

    def tearDown(self):
        set_std_group_resolver(None)
        self.gconff = None
        self.custf = None

    def test_groupsconf_option(self):
        """test nodeset with --groupsconf"""
        # use -r (--regroup) to test group resolution
        self._clubak_t(["-r"], b"foo1: bar\nfoo2: bar", _outfmt("@foo (2)"))
        self._clubak_t(["--groupsconf", self.custf.name, "-r"],
                       b"foo1: bar\nfoo2: bar", _outfmt("@bar (2)"))
