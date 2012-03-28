#!/usr/bin/env python
# scripts/clush.py tool test suite
# Written by S. Thiell 2012-03-28


"""Unit test for CLI/Clush.py"""

import pwd
import sys
import unittest

from TLib import *
import ClusterShell.CLI.Clush
from ClusterShell.CLI.Clush import main


class CLIClushTest(unittest.TestCase):
    """Unit test class for testing CLI/Clush.py"""

    def _clush_t(self, args, input, expected_stdout, expected_rc=0,
                  expected_stderr=None):
        """This new version allows code coverage checking by calling clush's
        main entry point."""
        clush_exit = ClusterShell.CLI.Clush.clush_exit
        try:
            ClusterShell.CLI.Clush.clush_exit = sys.exit # workaround (see #185)
            CLI_main(self, main, [ 'clush' ] + args, input, expected_stdout,
                     expected_rc, expected_stderr)
        finally:
            ClusterShell.CLI.Clush.clush_exit = clush_exit

    def test_000_display(self):
        """test clush (display options)"""
        self._clush_t(["-w", "localhost", "true"], None, "")
        self._clush_t(["-w", "localhost", "echo", "ok"], None, \
            "localhost: ok\n")
        self._clush_t(["-w", "localhost", "echo", "ok", "ok"], None, \
            "localhost: ok ok\n")
        self._clush_t(["-N", "-w", "localhost", "echo", "ok", "ok"], None, \
            "ok ok\n")
        self._clush_t(["-qw", "localhost", "echo", "ok"], None, \
            "localhost: ok\n")
        self._clush_t(["-vw", "localhost", "echo", "ok"], None, \
            "localhost: ok\n")
        self._clush_t(["-qvw", "localhost", "echo", "ok"], None, \
            "localhost: ok\n")
        self._clush_t(["-Sw", "localhost", "echo", "ok"], None, \
            "localhost: ok\n")
        self._clush_t(["-Sqw", "localhost", "echo", "ok"], None, \
            "localhost: ok\n")
        self._clush_t(["-Svw", "localhost", "echo", "ok"], None, \
            "localhost: ok\n")
        self._clush_t(["--nostdin", "-w", "localhost", "echo", "ok"], None, \
            "localhost: ok\n")

    def test_001_fanout(self):
        """test clush (fanout)"""
        self._clush_t(["-f", "10", "-w", "localhost", "true"], None, "")
        self._clush_t(["-f", "1", "-w", "localhost", "true"], None, "")
        self._clush_t(["-f", "1", "-w", "localhost", "echo", "ok"], None, \
            "localhost: ok\n")

    def test_002_ssh_options(self):
        """test clush (ssh options)"""
        self._clush_t(["-o", "-oStrictHostKeyChecking=no", "-w", "localhost", \
            "echo", "ok"], None, "localhost: ok\n")
        self._clush_t(["-o", "-oStrictHostKeyChecking=no -oForwardX11=no", \
            "-w", "localhost", "echo", "ok"], None, "localhost: ok\n")
        self._clush_t(["-o", "-oStrictHostKeyChecking=no", "-o", \
            "-oForwardX11=no", "-w", "localhost", "echo", "ok"], None, \
                "localhost: ok\n")
        self._clush_t(["-o-oStrictHostKeyChecking=no", "-o-oForwardX11=no", \
            "-w", "localhost", "echo", "ok"], None, "localhost: ok\n")
        self._clush_t(["-u", "4", "-w", "localhost", "echo", "ok"], None, \
            "localhost: ok\n")
        self._clush_t(["-t", "4", "-u", "4", "-w", "localhost", "echo", \
            "ok"], None, "localhost: ok\n")

    def test_003_output_gathering(self):
        """test clush (output gathering)"""
        self._clush_t(["-w", "localhost", "-L", "echo", "ok"], None, \
            "localhost: ok\n")
        self._clush_t(["-w", "localhost", "-bL", "echo", "ok"], None, \
            "localhost: ok\n")
        self._clush_t(["-w", "localhost", "-qbL", "echo", "ok"], None, \
            "localhost: ok\n")
        self._clush_t(["-w", "localhost", "-BL", "echo", "ok"], None, \
            "localhost: ok\n")
        self._clush_t(["-w", "localhost", "-qBL", "echo", "ok"], None, \
            "localhost: ok\n")
        self._clush_t(["-w", "localhost", "-BLS", "echo", "ok"], None, \
            "localhost: ok\n")
        self._clush_t(["-w", "localhost", "-qBLS", "echo", "ok"], None, \
            "localhost: ok\n")

    def test_004_file_copy(self):
        """test clush (file copy)"""
        content = "%f" % time.time()
        f = make_temp_file(content)
        self._clush_t(["-w", "localhost", "-c", f.name], None, "")
        f.seek(0)
        self.assertEqual(f.read(), content)
        # test --dest option
        f2 = tempfile.NamedTemporaryFile()
        self._clush_t(["-w", "localhost", "-c", f.name, "--dest", f2.name], \
            None, "")
        f2.seek(0)
        self.assertEqual(f2.read(), content)
        # test --user option
        f2 = tempfile.NamedTemporaryFile()
        self._clush_t(["--user", pwd.getpwuid(os.getuid())[0], "-w", \
            "localhost", "--copy", f.name, "--dest", f2.name], None, "")
        f2.seek(0)
        self.assertEqual(f2.read(), content)
        # test --rcopy
        self._clush_t(["--user", pwd.getpwuid(os.getuid())[0], "-w", \
            "localhost", "--rcopy", f.name, "--dest", \
                os.path.dirname(f.name)], None, "")
        f2.seek(0)
        self.assertEqual(open("%s.localhost" % f.name).read(), content)

    def test_005_diff(self):
        """test clush (diff)"""
        self._clush_t(["-w", "localhost", "--diff", "echo", "ok"], None, "")
        self._clush_t(["-w", "localhost,127.0.0.1", "--diff", "echo", "ok"], None, "")


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(CLIClushTest)
    unittest.TextTestRunner(verbosity=2).run(suite)
