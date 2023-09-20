# ClusterShell.CLI.Display test suite
# Written by S. Thiell

"""Unit test for CLI.Display"""

import tempfile
import unittest
import os
from io import StringIO

from ClusterShell.CLI.Display import Display, THREE_CHOICES, VERB_STD
from ClusterShell.CLI.OptionParser import OptionParser

from ClusterShell.MsgTree import MsgTree
from ClusterShell.NodeSet import NodeSet, set_std_group_resolver

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

        ns = NodeSet("hostfoo")
        mtree = MsgTree()
        mtree.add("hostfoo", b"message0")
        mtree.add("hostfoo", b"message1")

        list_env_vars = []
        list_env_vars.append(dict())
        list_env_vars.append(dict(NO_COLOR='0'))
        list_env_vars.append(dict(CLICOLOR='0'))
        list_env_vars.append(dict(CLICOLOR='1'))
        list_env_vars.append(dict(CLICOLOR='0', CLICOLOR_FORCE='0'))
        list_env_vars.append(dict(CLICOLOR_FORCE='1'))

        for env_vars in list_env_vars:
            for var_name in env_vars:
                var_value = env_vars[var_name]
                os.environ[var_name] = var_value

            for whencolor in THREE_CHOICES: # test whencolor switch
                if whencolor == "":
                    options.whencolor = None
                else:
                    options.whencolor = whencolor
                for label in [True, False]: # test no-label switch
                    options.label = label
                    disp = Display(options)
                    # inhibit output
                    disp.out = StringIO()
                    disp.err = StringIO()
                    # test print_* methods...
                    disp.print_line(ns, b"foo bar")
                    disp.print_line_error(ns, b"foo bar")
                    disp.print_gather(ns, list(mtree.walk())[0][0])
                    # test also string nodeset as parameter
                    disp.print_gather("hostfoo", list(mtree.walk())[0][0])
                    # test line_mode property
                    self.assertEqual(disp.line_mode, False)
                    disp.line_mode = True
                    self.assertEqual(disp.line_mode, True)
                    disp.print_gather("hostfoo", list(mtree.walk())[0][0])
                    disp.line_mode = False
                    self.assertEqual(disp.line_mode, False)

            for var_name in env_vars:
                os.environ.pop(var_name)

    def testDisplayRegroup(self):
        """test CLI.Display (regroup)"""
        f = makeTestFile(b"""
# A comment

[Main]
default: local

[local]
map: echo hostfoo
#all:
list: echo all
#reverse:
        """)
        res = GroupResolverConfig(f.name)
        set_std_group_resolver(res)
        try:
            parser = OptionParser("dummy")
            parser.install_display_options(verbose_options=True)
            options, _ = parser.parse_args(["-r"])

            disp = Display(options, color=False)
            self.assertEqual(disp.regroup, True)
            disp.out = StringIO()
            disp.err = StringIO()
            self.assertEqual(disp.line_mode, False)

            ns = NodeSet("hostfoo")

            # nodeset.regroup() is performed by print_gather()
            disp.print_gather(ns, b"message0\nmessage1\n")
            self.assertEqual(disp.out.getvalue(),
                "---------------\n@all\n---------------\nmessage0\nmessage1\n\n")
        finally:
            set_std_group_resolver(None)

    def testDisplayClubak(self):
        """test CLI.Display for clubak"""
        parser = OptionParser("dummy")
        parser.install_display_options(separator_option=True, dshbak_compat=True)
        options, _ = parser.parse_args([])
        disp = Display(options)
        self.assertEqual(bool(disp.gather), False)
        self.assertEqual(disp.line_mode, False)
        self.assertEqual(disp.label, True)
        self.assertEqual(disp.regroup, False)
        self.assertEqual(bool(disp.groupsource), False)
        self.assertEqual(disp.noprefix, False)
        self.assertEqual(disp.maxrc, False)
        self.assertEqual(disp.node_count, True)
        self.assertEqual(disp.verbosity, VERB_STD)

    def testDisplayDecodingErrors(self):
        """test CLI.Display (decoding errors)"""
        parser = OptionParser("dummy")
        parser.install_display_options()
        options, _ = parser.parse_args([])
        disp = Display(options, color=False)
        disp.out = StringIO()
        disp.err = StringIO()
        self.assertEqual(bool(disp.gather), False)
        self.assertEqual(disp.line_mode, False)
        ns = NodeSet("node")
        disp.print_line(ns, b"message0\n\xf8message1\n")
        self.assertEqual(disp.out.getvalue(),
            "node: message0\n\ufffdmessage1\n\n")
        disp.print_line_error(ns, b"message0\n\xf8message1\n")
        self.assertEqual(disp.err.getvalue(),
            "node: message0\n\ufffdmessage1\n\n")

    def testDisplayDecodingErrorsGather(self):
        """test CLI.Display (decoding errors, gather)"""
        parser = OptionParser("dummy")
        parser.install_display_options(dshbak_compat=True)
        options, _ = parser.parse_args(["-b"])
        disp = Display(options, color=False)
        disp.out = StringIO()
        disp.err = StringIO()
        self.assertEqual(bool(disp.gather), True)
        self.assertEqual(disp.line_mode, False)
        ns = NodeSet("node")
        disp._print_buffer(ns, b"message0\n\xf8message1\n")
        self.assertEqual(disp.out.getvalue(),
            "---------------\nnode\n---------------\nmessage0\n\ufffdmessage1\n\n")

    def testDisplayDecodingErrorsLineMode(self):
        """test CLI.Display (decoding errors, line mode)"""
        parser = OptionParser("dummy")
        parser.install_display_options(dshbak_compat=True)
        options, _ = parser.parse_args(["-b", "-L"])
        disp = Display(options, color=False)
        disp.out = StringIO()
        disp.err = StringIO()
        self.assertEqual(bool(disp.gather), True)
        self.assertEqual(disp.label, True)
        self.assertEqual(disp.line_mode, True)
        ns = NodeSet("node")
        disp.print_gather(ns, [b"message0\n", b"\xf8message1\n"])
        self.assertEqual(disp.out.getvalue(),
            "node: message0\n\nnode: \ufffdmessage1\n\n")

    def testDisplayDecodingErrorsLineModeNoLabel(self):
        """test CLI.Display (decoding errors, line mode, no label)"""
        parser = OptionParser("dummy")
        parser.install_display_options(dshbak_compat=True)
        options, _ = parser.parse_args(["-b", "-L", "-N"])
        disp = Display(options, color=False)
        disp.out = StringIO()
        disp.err = StringIO()
        self.assertEqual(bool(disp.gather), True)
        self.assertEqual(disp.label, False)
        self.assertEqual(disp.line_mode, True)
        ns = NodeSet("node")
        disp.print_gather(ns, [b"message0\n", b"\xf8message1\n"])
        self.assertEqual(disp.out.getvalue(),
            "message0\n\n\ufffdmessage1\n\n")
