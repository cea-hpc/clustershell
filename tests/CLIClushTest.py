#!/usr/bin/env python
# scripts/clush.py tool test suite
# Written by S. Thiell 2012-03-28


"""Unit test for CLI/Clush.py"""

import pwd
import subprocess
import sys
import unittest

from TLib import *
import ClusterShell.CLI.Clush
from ClusterShell.CLI.Clush import main
from ClusterShell.Task import task_cleanup


class CLIClushTest(unittest.TestCase):
    """Unit test class for testing CLI/Clush.py"""

    def tearDown(self):
        """cleanup all tasks"""
        task_cleanup()
        #subprocess.call(["ls", "-x", "/proc/self/fd"], stdout=sys.stdout)

    def _clush_t(self, args, input, expected_stdout, expected_rc=0,
                  expected_stderr=None):
        """This new version allows code coverage checking by calling clush's
        main entry point."""
        def raw_input_mock(prompt):
            time.sleep(3600)
        ClusterShell.CLI.Clush.raw_input = raw_input_mock
        clush_exit = ClusterShell.CLI.Clush.clush_exit
        try:
            ClusterShell.CLI.Clush.clush_exit = sys.exit # workaround (see #185)
            CLI_main(self, main, [ 'clush' ] + args, input, expected_stdout,
                     expected_rc, expected_stderr)
        finally:
            ClusterShell.CLI.Clush.clush_exit = clush_exit
            ClusterShell.CLI.Clush.raw_input = raw_input

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

    def test_001_display_tty(self):
        """test clush (display options) [tty]"""
        setattr(ClusterShell.CLI.Clush, '_f_user_interaction', True)
        try:
            self.test_000_display()
        finally:
            delattr(ClusterShell.CLI.Clush, '_f_user_interaction')

    def test_002_fanout(self):
        """test clush (fanout)"""
        self._clush_t(["-f", "10", "-w", "localhost", "true"], None, "")
        self._clush_t(["-f", "1", "-w", "localhost", "true"], None, "")
        self._clush_t(["-f", "1", "-w", "localhost", "echo", "ok"], None, \
            "localhost: ok\n")

    def test_003_fanout_tty(self):
        """test clush (fanout) [tty]"""
        setattr(ClusterShell.CLI.Clush, '_f_user_interaction', True)
        try:
            self.test_002_fanout()
        finally:
            delattr(ClusterShell.CLI.Clush, '_f_user_interaction')

    def test_004_ssh_options(self):
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

    def test_005_ssh_options_tty(self):
        """test clush (ssh options) [tty]"""
        setattr(ClusterShell.CLI.Clush, '_f_user_interaction', True)
        try:
            self.test_004_ssh_options()
        finally:
            delattr(ClusterShell.CLI.Clush, '_f_user_interaction')

    def test_006_output_gathering(self):
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
        self._clush_t(["-w", "localhost", "-vb", "echo", "ok"], None, \
            "localhost: ok\n---------------\nlocalhost\n---------------\nok\n")

    def test_007_output_gathering_tty(self):
        """test clush (output gathering) [tty]"""
        setattr(ClusterShell.CLI.Clush, '_f_user_interaction', True)
        try:
            self.test_006_output_gathering()
        finally:
            delattr(ClusterShell.CLI.Clush, '_f_user_interaction')

    def test_008_file_copy(self):
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

    def test_009_file_copy_tty(self):
        """test clush (file copy) [tty]"""
        setattr(ClusterShell.CLI.Clush, '_f_user_interaction', True)
        try:
            self.test_008_file_copy()
        finally:
            delattr(ClusterShell.CLI.Clush, '_f_user_interaction')

    def test_010_diff(self):
        """test clush (diff)"""
        self._clush_t(["-w", "localhost", "--diff", "echo", "ok"], None, "")
        self._clush_t(["-w", "localhost,127.0.0.1", "--diff", "echo", "ok"], None, "")

    def test_011_diff_tty(self):
        """test clush (diff) [tty]"""
        setattr(ClusterShell.CLI.Clush, '_f_user_interaction', True)
        try:
            self.test_010_diff()
        finally:
            delattr(ClusterShell.CLI.Clush, '_f_user_interaction')

    def test_012_stdin(self):
        """test clush (stdin)"""
        self._clush_t(["-w", "localhost", "sleep 1 && cat"], "ok", "localhost: ok\n")
        self._clush_t(["-w", "localhost", "cat"], "ok\nok", "localhost: ok\nlocalhost: ok\n")
        # write binary to stdin
        self._clush_t(["-w", "localhost", "gzip -d"], \
            "1f8b0800869a744f00034bcbcf57484a2ce2020027b4dd1308000000".decode("hex"), "localhost: foo bar\n")

    def test_014_stderr(self):
        """test clush (stderr)"""
        self._clush_t(["-w", "localhost", "echo err 1>&2"], None, "", 0, "localhost: err\n")
        self._clush_t(["-b", "-w", "localhost", "echo err 1>&2"], None, "", 0, "localhost: err\n")
        self._clush_t(["-B", "-w", "localhost", "echo err 1>&2"], None, "---------------\nlocalhost\n---------------\nerr\n")

    def test_015_stderr_tty(self):
        """test clush (stderr) [tty]"""
        setattr(ClusterShell.CLI.Clush, '_f_user_interaction', True)
        try:
            self.test_014_stderr()
        finally:
            delattr(ClusterShell.CLI.Clush, '_f_user_interaction')

    def test_016_retcodes(self):
        """test clush (retcodes)"""
        self._clush_t(["-w", "localhost", "/bin/false"], None, "", 0, "clush: localhost: exited with exit code 1\n")
        self._clush_t(["-w", "localhost", "-b", "/bin/false"], None, "", 0, "clush: localhost: exited with exit code 1\n")
        self._clush_t(["-S", "-w", "localhost", "/bin/false"], None, "", 1, "clush: localhost: exited with exit code 1\n")
        for i in (1, 2, 127, 128, 255):
            self._clush_t(["-S", "-w", "localhost", "exit %d" % i], None, "", i, \
                "clush: localhost: exited with exit code %d\n" % i)
        self._clush_t(["-v", "-w", "localhost", "/bin/false"], None, "", 0, "clush: localhost: exited with exit code 1\n")

    def test_017_retcodes_tty(self):
        """test clush (retcodes) [tty]"""
        setattr(ClusterShell.CLI.Clush, '_f_user_interaction', True)
        try:
            self.test_016_retcodes()
        finally:
            delattr(ClusterShell.CLI.Clush, '_f_user_interaction')

    def test_018_timeout(self):
        """test clush (timeout)"""
        self._clush_t(["-w", "localhost", "-u", "5", "sleep 7"], None, "", 0, "clush: localhost: command timeout\n")
        self._clush_t(["-w", "localhost", "-u", "5", "-b", "sleep 7"], None, "", 0, "clush: localhost: command timeout\n")

    def test_019_timeout_tty(self):
        """test clush (timeout) [tty]"""
        setattr(ClusterShell.CLI.Clush, '_f_user_interaction', True)
        try:
            self.test_018_timeout()
        finally:
            delattr(ClusterShell.CLI.Clush, '_f_user_interaction')


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(CLIClushTest)
    unittest.TextTestRunner(verbosity=2).run(suite)
