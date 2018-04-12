# ClusterShell.CLI.Clush test suite
# Written by S. Thiell

"""Unit test for CLI.Clush"""

import codecs
import errno
import os
from os.path import basename
import pwd
import re
import resource
import signal
import sys
import tempfile
from textwrap import dedent
import threading
import time
import unittest

from subprocess import Popen, PIPE

from TLib import *
import ClusterShell.CLI.Clush
from ClusterShell.CLI.Clush import main
from ClusterShell.NodeSet import NodeSet
from ClusterShell.NodeSet import set_std_group_resolver, \
                                 set_std_group_resolver_config
from ClusterShell.Task import task_cleanup

from ClusterShell.Worker.EngineClient import EngineClientNotSupportedError


class CLIClushTest_A(unittest.TestCase):
    """Unit test class for testing CLI/Clush.py"""

    def setUp(self):
        """define constants used in tests"""
        s = "%s: ok\n" % HOSTNAME
        self.output_ok = s.encode()

        s = "\x1b[94m%s: \x1b[0mok\n" % HOSTNAME
        self.output_ok_color = s.encode()

        self.soft, self.hard = resource.getrlimit(resource.RLIMIT_NOFILE)

    def tearDown(self):
        """cleanup all tasks"""
        task_cleanup()

        # we played with fd_max: restore original nofile resource limits
        resource.setrlimit(resource.RLIMIT_NOFILE, (self.soft, self.hard))

    def _clush_t(self, args, stdin, expected_stdout, expected_rc=0,
                 expected_stderr=None):
        """This new version allows code coverage checking by calling clush's
        main entry point."""
        def raw_input_mock(prompt):
            # trusty sleep
            wait_time = 60
            start = time.time()
            while time.time() - start < wait_time:
                time.sleep(wait_time - (time.time() - start))
            return ""
        try:
            raw_input_save = ClusterShell.CLI.Clush.raw_input
        except:
            raw_input_save = raw_input
        ClusterShell.CLI.Clush.raw_input = raw_input_mock
        try:
            CLI_main(self, main, ['clush'] + args, stdin, expected_stdout,
                     expected_rc, expected_stderr)
        finally:
            ClusterShell.CLI.Clush.raw_input = raw_input_save

    def test_000_display(self):
        """test clush (display options)"""
        self._clush_t(["-w", HOSTNAME, "true"], None, b"")

        s = "%s: ok ok\n" % HOSTNAME
        exp_output2 = s.encode()

        self._clush_t(["-w", HOSTNAME, "echo", "ok"], None, self.output_ok)
        self._clush_t(["-w", HOSTNAME, "echo", "ok", "ok"], None, exp_output2)
        self._clush_t(["-N", "-w", HOSTNAME, "echo", "ok", "ok"], None,
                      b"ok ok\n")
        self._clush_t(["-w", "badhost,%s" % HOSTNAME, "-x", "badhost", "echo",
                       "ok"], None, self.output_ok)
        self._clush_t(["-qw", HOSTNAME, "echo", "ok"], None, self.output_ok)
        self._clush_t(["-vw", HOSTNAME, "echo", "ok"], None, self.output_ok)
        self._clush_t(["-qvw", HOSTNAME, "echo", "ok"], None, self.output_ok)
        self._clush_t(["-Sw", HOSTNAME, "echo", "ok"], None, self.output_ok)
        self._clush_t(["-Sqw", HOSTNAME, "echo", "ok"], None, self.output_ok)
        self._clush_t(["-Svw", HOSTNAME, "echo", "ok"], None, self.output_ok)
        self._clush_t(["--nostdin", "-w", HOSTNAME, "echo", "ok"], None,
                      self.output_ok)

        self._clush_t(["-w", HOSTNAME, "--color=always", "echo", "ok"], None,
                      self.output_ok_color)
        self._clush_t(["-w", HOSTNAME, "--color=never", "echo", "ok"], None,
                      self.output_ok)

        # issue #352
        self._clush_t(["-N", "-R", "exec", "-w", 'foo[1-2]', "-b",
                      "echo", "test"], None, b"test\n")

    def test_001_display_tty(self):
        """test clush (display options) [tty]"""
        setattr(ClusterShell.CLI.Clush, '_f_user_interaction', True)
        try:
            self.test_000_display()
        finally:
            delattr(ClusterShell.CLI.Clush, '_f_user_interaction')

    def test_002_fanout(self):
        """test clush (fanout)"""
        self._clush_t(["-f", "10", "-w", HOSTNAME, "true"], None, b"")
        self._clush_t(["-f", "1", "-w", HOSTNAME, "true"], None, b"")
        self._clush_t(["-f", "1", "-w", HOSTNAME, "echo", "ok"], None,
                      self.output_ok)

    def test_003_fanout_tty(self):
        """test clush (fanout) [tty]"""
        setattr(ClusterShell.CLI.Clush, '_f_user_interaction', True)
        try:
            self.test_002_fanout()
        finally:
            delattr(ClusterShell.CLI.Clush, '_f_user_interaction')

    def test_004_ssh_options(self):
        """test clush (ssh options)"""
        self._clush_t(["-o", "-oStrictHostKeyChecking=no", "-w", HOSTNAME,
                       "echo", "ok"], None, self.output_ok)
        self._clush_t(["-o", "-oStrictHostKeyChecking=no -oForwardX11=no",
                       "-w", HOSTNAME, "echo", "ok"], None, self.output_ok)
        self._clush_t(["-o", "-oStrictHostKeyChecking=no", "-o",
                       "-oForwardX11=no", "-w", HOSTNAME, "echo", "ok"], None,
                      self.output_ok)
        self._clush_t(["-o-oStrictHostKeyChecking=no", "-o-oForwardX11=no",
                       "-w", HOSTNAME, "echo", "ok"], None, self.output_ok)
        self._clush_t(["-u", "30", "-w", HOSTNAME, "echo", "ok"], None,
                      self.output_ok)
        self._clush_t(["-t", "30", "-u", "30", "-w", HOSTNAME, "echo", "ok"],
                      None, self.output_ok)

    def test_005_ssh_options_tty(self):
        """test clush (ssh options) [tty]"""
        setattr(ClusterShell.CLI.Clush, '_f_user_interaction', True)
        try:
            self.test_004_ssh_options()
        finally:
            delattr(ClusterShell.CLI.Clush, '_f_user_interaction')

    def test_006_output_gathering(self):
        """test clush (output gathering)"""
        self._clush_t(["-w", HOSTNAME, "-bL", "echo", "ok"], None,
                      self.output_ok)
        self._clush_t(["-w", HOSTNAME, "-qbL", "echo", "ok"], None,
                      self.output_ok)
        self._clush_t(["-w", HOSTNAME, "-BL", "echo", "ok"], None,
                      self.output_ok)
        self._clush_t(["-w", HOSTNAME, "-qBL", "echo", "ok"], None,
                      self.output_ok)
        self._clush_t(["-w", HOSTNAME, "-BLS", "echo", "ok"], None,
                      self.output_ok)
        self._clush_t(["-w", HOSTNAME, "-qBLS", "echo", "ok"], None,
                      self.output_ok)

        s = "%s: ok\n---------------\n%s\n---------------\nok\n" \
            % (HOSTNAME, HOSTNAME)
        self._clush_t(["-w", HOSTNAME, "-vb", "echo", "ok"], None,
                      s.encode())

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
        content = content.encode()
        f = make_temp_file(content)
        self._clush_t(["-w", HOSTNAME, "-c", f.name], None, b"")
        f.seek(0)
        self.assertEqual(f.read(), content)
        # test --dest option
        f2 = tempfile.NamedTemporaryFile()
        self._clush_t(["-w", HOSTNAME, "-c", f.name, "--dest", f2.name], None,
                      b"")
        f2.seek(0)
        self.assertEqual(f2.read(), content)
        # test --user option
        f2 = tempfile.NamedTemporaryFile()
        self._clush_t(["--user", pwd.getpwuid(os.getuid())[0], "-w", HOSTNAME,
                       "--copy", f.name, "--dest", f2.name], None, b"")
        f2.seek(0)
        self.assertEqual(f2.read(), content)
        # test --rcopy
        self._clush_t(["--user", pwd.getpwuid(os.getuid())[0], "-w", HOSTNAME,
                       "--rcopy", f.name, "--dest", os.path.dirname(f.name)],
                      None, b"")
        f2.seek(0)
        self.assertEqual(open("%s.%s" % (f.name, HOSTNAME), 'rb').read(),
                         content)

    def test_009_file_copy_tty(self):
        """test clush (file copy) [tty]"""
        setattr(ClusterShell.CLI.Clush, '_f_user_interaction', True)
        try:
            self.test_008_file_copy()
        finally:
            delattr(ClusterShell.CLI.Clush, '_f_user_interaction')

    def test_010_diff(self):
        """test clush (diff)"""
        self._clush_t(["-w", HOSTNAME, "--diff", "echo", "ok"], None, b"")
        self._clush_t(["-w", "%s,localhost" % HOSTNAME, "--diff", "echo",
                       "ok"], None, b"")

    def test_011_diff_tty(self):
        """test clush (diff) [tty]"""
        setattr(ClusterShell.CLI.Clush, '_f_user_interaction', True)
        try:
            self.test_010_diff()
        finally:
            delattr(ClusterShell.CLI.Clush, '_f_user_interaction')

    def test_012_diff_null(self):
        """test clush (diff w/o output)"""
        rxs = r"^--- %s\n\+\+\+ localhost\n@@ -1(,1)? \+[01],0 @@\n-ok\n$" % HOSTNAME
        self._clush_t(["-w", "%s,localhost" % HOSTNAME, "--diff",
                       'echo $SSH_CONNECTION | cut -d " " -f 3 |'
                       'egrep "^(127.0.0.1|::1)$" >/dev/null || echo ok'],
                      None, re.compile(rxs.encode()))

    def test_013_stdin(self):
        """test clush (stdin)"""
        self._clush_t(["-w", HOSTNAME, "sleep 1 && cat"], b"ok", self.output_ok)

        s = "%s: ok\n%s: ok\n" % (HOSTNAME, HOSTNAME)
        self._clush_t(["-w", HOSTNAME, "cat"], b"ok\nok", s.encode())
        # write binary to stdin
        s = "%s: foo bar\n" % HOSTNAME
        self._clush_t(["-w", HOSTNAME, "gzip -d"],
                      codecs.decode(b'1f8b0800869a744f00034bcbcf57484a2ce2020027b4dd1308000000',
                                    'hex'),
                      s.encode())

    def test_015_stderr(self):
        """test clush (stderr)"""
        s = "%s: err\n" % HOSTNAME
        self._clush_t(["-w", HOSTNAME, "echo err 1>&2"], None, b"", 0,
                      s.encode())
        self._clush_t(["-b", "-w", HOSTNAME, "-q", "echo err 1>&2"], None, b"",
                      0, s.encode())
        s = "---------------\n%s\n---------------\nerr\n" % HOSTNAME
        self._clush_t(["-B", "-w", HOSTNAME, "-q", "echo err 1>&2"], None,
                      s.encode())

    def test_016_stderr_tty(self):
        """test clush (stderr) [tty]"""
        setattr(ClusterShell.CLI.Clush, '_f_user_interaction', True)
        try:
            self.test_015_stderr()
        finally:
            delattr(ClusterShell.CLI.Clush, '_f_user_interaction')

    def test_017_retcodes(self):
        """test clush (retcodes)"""
        s = "clush: %s: exited with exit code 1\n" % HOSTNAME
        exp_err = s.encode()
        self._clush_t(["-w", HOSTNAME, "/bin/false"], None, b"", 0, exp_err)
        self._clush_t(["-w", HOSTNAME, "-b", "/bin/false"], None, b"", 0, exp_err)
        self._clush_t(["-S", "-w", HOSTNAME, "/bin/false"], None, b"", 1, exp_err)
        for i in (1, 2, 127, 128, 255):
            s = "clush: %s: exited with exit code %d\n" % (HOSTNAME, i)
            self._clush_t(["-S", "-w", HOSTNAME, "exit %d" % i], None, b"", i,
                          s.encode())
        self._clush_t(["-v", "-w", HOSTNAME, "/bin/false"], None, b"", 0,
                      exp_err)

        duo = str(NodeSet("%s,localhost" % HOSTNAME))
        s = "clush: %s (%d): exited with exit code 1\n" % (duo, 2)
        self._clush_t(["-w", duo, "-b", "/bin/false"], None, b"", 0, s.encode())
        s = "clush: %s: exited with exit code 1\n" % duo
        self._clush_t(["-w", duo, "-b", "-q", "/bin/false"], None, b"", 0,
                      s.encode())
        s = "clush: %s (%d): exited with exit code 1\n" % (duo, 2)
        self._clush_t(["-w", duo, "-S", "-b", "/bin/false"], None, b"", 1,
                      s.encode())
        self._clush_t(["-w", duo, "-S", "-b", "-q", "/bin/false"], None, b"", 1)

    def test_018_retcodes_tty(self):
        """test clush (retcodes) [tty]"""
        setattr(ClusterShell.CLI.Clush, '_f_user_interaction', True)
        try:
            self.test_017_retcodes()
        finally:
            delattr(ClusterShell.CLI.Clush, '_f_user_interaction')

    def test_019_timeout(self):
        """test clush (timeout)"""
        s = "clush: %s: command timeout\n" % HOSTNAME
        self._clush_t(["-w", HOSTNAME, "-u", "1", "sleep 3"], None, b"", 0,
                      s.encode())
        self._clush_t(["-w", HOSTNAME, "-u", "1", "-b", "sleep 3"], None, b"",
                      0, s.encode())

    def test_020_timeout_tty(self):
        """test clush (timeout) [tty]"""
        setattr(ClusterShell.CLI.Clush, '_f_user_interaction', True)
        try:
            self.test_019_timeout()
        finally:
            delattr(ClusterShell.CLI.Clush, '_f_user_interaction')

    def test_021_file_copy_timeout(self):
        """test clush file copy (timeout)"""
        content = "%f" % time.time()
        content = content.encode()
        f = make_temp_file(content)
        s = "clush: %s: command timeout\n" % HOSTNAME
        self._clush_t(["-w", HOSTNAME, "-u", "0.01", "-c", f.name], None,
                      b"", 0, s.encode())

    def test_022_file_copy_timeout_tty(self):
        """test clush file copy (timeout) [tty]"""
        setattr(ClusterShell.CLI.Clush, '_f_user_interaction', True)
        try:
            self.test_021_file_copy_timeout()
        finally:
            delattr(ClusterShell.CLI.Clush, '_f_user_interaction')

    def test_023_load_workerclass(self):
        """test _load_workerclass()"""
        for name in ('rsh', 'ssh', 'pdsh'):
            cls = ClusterShell.CLI.Clush._load_workerclass(name)
            self.assertTrue(cls)

    def test_024_load_workerclass_error(self):
        """test _load_workerclass() bad use cases"""
        func = ClusterShell.CLI.Clush._load_workerclass
        # Bad module
        self.assertRaises(ImportError, func, 'not_a_module')
        # Worker module but not supported
        self.assertRaises(AttributeError, func, 'worker')

    def test_025_worker(self):
        """test clush (worker)"""
        self._clush_t(["-w", HOSTNAME, "--worker=ssh", "echo ok"], None,
                      self.output_ok, 0)
        self._clush_t(["-w", HOSTNAME, "-R", "ssh", "echo ok"], None,
                      self.output_ok, 0)
        # also test in debug mode...
        # Warning: Python3 will display b'...' in debug mode
        rxs = r"EXECCLIENT: echo ok\n%s: [b\\']{0,2}ok[']{0,1}\n%s: ok\n" \
              % (HOSTNAME, HOSTNAME)
        self._clush_t(["-w", HOSTNAME, "--worker=exec", "-d", "echo ok"], None,
                      re.compile(rxs.encode()), 0)
        self._clush_t(["-w", HOSTNAME, "-R", "exec", "-d", "echo ok"], None,
                      re.compile(rxs.encode()), 0)

    def test_026_keyboard_interrupt(self):
        """test clush on keyboard interrupt"""
        # Note: the scope of this test is still limited as we cannot force user
        # interaction (as clush is launched by subprocess). For replicated
        # observation, we use --nostdin and only check if Keyboard interrupt
        # message is printed...

        class KillerThread(threading.Thread):
            def run(self):
                time.sleep(1)
                # replace later by process.send_signal() [py2.6+]
                os.kill(self.pidkill, signal.SIGINT)

        kth = KillerThread()
        args = ["-w", HOSTNAME, "--worker=exec", "-q", "--nostdin", "-b",
                "echo start; sleep 10"]
        python_exec = basename(sys.executable or 'python')
        process = Popen([python_exec, '-m', 'ClusterShell.CLI.Clush'] + args,
                        stderr=PIPE, stdout=PIPE, bufsize=0)
        kth.pidkill = process.pid
        kth.start()
        stderr = process.communicate()[1]
        self.assertEqual(stderr, b"Keyboard interrupt.\n")

    def test_027_warn_shell_globbing_nodes(self):
        """test clush warning on shell globbing (-w)"""
        tdir = make_temp_dir()
        tfile = open(os.path.join(tdir, HOSTNAME), "w")
        curdir = os.getcwd()
        try:
            os.chdir(tdir)
            s = "Warning: using '-w %s' and local path '%s' exists, was it " \
                "expanded by the shell?\n" % (HOSTNAME, HOSTNAME)
            self._clush_t(["-w", HOSTNAME, "echo", "ok"], None,
                          self.output_ok, 0, s.encode())
        finally:
            os.chdir(curdir)
            tfile.close()
            os.unlink(tfile.name)
            os.rmdir(tdir)

    def test_028_warn_shell_globbing_exclude(self):
        """test clush warning on shell globbing (-x)"""
        tdir = make_temp_dir()
        tfile = open(os.path.join(tdir, HOSTNAME), "wb")
        curdir = os.getcwd()
        try:
            os.chdir(tdir)
            rxs = r"^Warning: using '-x %s' and local path " \
                  r"'%s' exists, was it expanded by the shell\?\n" \
                  % (HOSTNAME, HOSTNAME)
            self._clush_t(["-S", "-w", "badhost,%s" % HOSTNAME, "-x", HOSTNAME,
                           "echo", "ok"], None, b"", 255,
                          re.compile(rxs.encode()))
        finally:
            os.chdir(curdir)
            tfile.close()
            os.unlink(tfile.name)
            os.rmdir(tdir)

    def test_029_hostfile(self):
        """test clush --hostfile"""
        f = make_temp_file(HOSTNAME.encode())
        self._clush_t(["--hostfile", f.name, "echo", "ok"], None,
                      self.output_ok)
        f2 = make_temp_file(HOSTNAME.encode())
        self._clush_t(["--hostfile", f.name, "--hostfile", f2.name,
                       "echo", "ok"], None, self.output_ok)
        self.assertRaises(OSError, self._clush_t,
                          ["--hostfile", "/I/do/NOT/exist", "echo", "ok"],
                          None, 1)

    def test_030_config_options(self):
        """test clush -O/--option"""
        self._clush_t(["--option", "color=never", "-w", HOSTNAME, "echo", "ok"],
                      None, self.output_ok)
        self._clush_t(["--option", "color=always", "-w", HOSTNAME, "echo",
                       "ok"], None, self.output_ok_color)
        self._clush_t(["--option=color=never", "-w", HOSTNAME, "echo", "ok"],
                      None, self.output_ok)
        self._clush_t(["--option=color=always", "-w", HOSTNAME, "echo", "ok"],
                      None, self.output_ok_color)
        self._clush_t(["-O", "fd_max=220", "--option", "color=never", "-w",
                       HOSTNAME, "echo", "ok"], None, self.output_ok)
        self._clush_t(["-O", "fd_max=220", "--option", "color=always", "-w",
                       HOSTNAME, "echo", "ok"], None, self.output_ok_color)
        self._clush_t(["--option", "color=never", "-O", "fd_max=220", "-w",
                       HOSTNAME, "echo", "ok"], None, self.output_ok)
        self._clush_t(["--option", "color=always", "-O", "fd_max=220", "-w",
                       HOSTNAME, "echo", "ok"], None, self.output_ok_color)
        self._clush_t(["--option", "color=never", "-O", "fd_max=220", "-O",
                       "color=always", "-w", HOSTNAME, "echo", "ok"], None,
                      self.output_ok_color)
        self._clush_t(["--option", "color=always", "-O", "fd_max=220", "-O",
                       "color=never", "-w", HOSTNAME, "echo", "ok"], None,
                      self.output_ok)

    def test_031_progress(self):
        """test clush -P/--progress"""
        self._clush_t(["-w", HOSTNAME, "--progress", "echo", "ok"], None,
                      self.output_ok)
        self._clush_t(["-w", HOSTNAME, "--progress", "sleep", "2"], None, b'', 0,
                      re.compile(r'clush: 0/1\r.*'.encode()))
        self._clush_t(["-w", HOSTNAME, "--progress", "sleep", "2"], b'AAAAAAAA',
                      b'', 0, re.compile(r'clush: 0/1 write: \d B/s\r.*'.encode()))
        self._clush_t(["-w", "%s,localhost" % HOSTNAME, "--progress", "sleep",
                       "2"], b'AAAAAAAAAAAAAA', b'', 0,
                      re.compile(r'clush: 0/2 write: \d+ B/s\r.*'.encode()))
        self._clush_t(["-w", HOSTNAME, "-b", "--progress", "sleep", "2"],
                      None, b'', 0, re.compile(r'clush: 0/1\r.*'.encode()))
        self._clush_t(["-w", HOSTNAME, "-b", "--progress", "sleep", "2"],
                      b'AAAAAAAAAAAAAAAA', b'', 0,
                      re.compile(r'clush: 0/1 write: \d+ B/s\r.*'.encode()))
        # -q and --progress: explicit -q wins
        self._clush_t(["-w", HOSTNAME, "--progress", "-q", "sleep", "2"], None,
                      b'', 0)
        self._clush_t(["-w", HOSTNAME, "-b", "--progress", "-q", "sleep", "2"],
                      None, b'', 0, b'')
        self._clush_t(["-w", HOSTNAME, "-b", "--progress", "-q", "sleep", "2"],
                      b'AAAAAAAAAAAAAAAA', b'', 0, b'')
        # cover stderr output and --progress
        s = "%s: bar\n" % HOSTNAME
        err_rxs = r'%s: foo\nclush: 0/1\r.*' % HOSTNAME
        self._clush_t(["-w", HOSTNAME, "--progress",
                       "echo foo >&2; echo bar; sleep 2"], None,
                      s.encode(), 0, re.compile(err_rxs.encode()))

    def test_032_worker_pdsh(self):
        """test clush (worker pdsh)"""
        # Warning: same as: echo -n | clush --worker=pdsh when launched from
        # jenkins (not a tty), so we need --nostdin as pdsh worker doesn't
        # support write
        self._clush_t(["-w", HOSTNAME, "--worker=pdsh", "--nostdin",
                       "echo ok"], None, self.output_ok, 0)
        # write not supported by pdsh worker
        self.assertRaises(EngineClientNotSupportedError, self._clush_t,
                          ["-w", HOSTNAME, "-R", "pdsh", "cat"], b"bar", None, 1)

    def test_033_worker_pdsh_tty(self):
        """test clush (worker pdsh) [tty]"""
        setattr(ClusterShell.CLI.Clush, '_f_user_interaction', True)
        try:
            self._clush_t(["-w", HOSTNAME, "--worker=pdsh", "echo ok"],
                          None, self.output_ok, 0)
        finally:
            delattr(ClusterShell.CLI.Clush, '_f_user_interaction')

    def test_034_pick(self):
        """test clush --pick"""
        rxs = r"^(localhost|%s): foo\n$" % HOSTNAME
        self._clush_t(["-w", "%s,localhost" % HOSTNAME, "--pick", "1",
                       "echo foo"], None, re.compile(rxs.encode()))
        rxs = r"^((localhost|%s): foo\n){2}$" % HOSTNAME
        self._clush_t(["-w", "%s,localhost" % HOSTNAME, "--pick", "2",
                       "echo foo"], None, re.compile(rxs.encode()))

    def test_035_sorted_line_mode(self):
        """test clush (sorted line mode -L)"""
        self._clush_t(["-w", HOSTNAME, "-L", "echo", "ok"], None,
                      self.output_ok)

        # Issue #326
        cmd = "bash -c 's=%h; n=${s//[!0-9]/}; if [[ $(expr $n %% 2) == 0 ]]; then " \
              "echo foo; else echo bar; fi'"

        self._clush_t(["-w", "cs[01-03]", "--worker=exec", "-L", cmd], None,
                      b'cs01: bar\ncs02: foo\ncs03: bar\n', 0)

    def test_036_sorted_gather(self):
        """test clush (CLI.Utils.bufnodeset_cmpkey)"""
        # test 1st sort criteria: largest nodeset first
        cmd = "bash -c 's=%h; n=${s//[!0-9]/}; if [[ $(expr $n %% 2) == 0 ]];" \
              "then echo foo; else echo bar; fi'"

        self._clush_t(["-w", "cs[01-03]", "--worker=exec", "-b", cmd], None,
                      b'---------------\ncs[01,03] (2)\n---------------\nbar\n'
                      b'---------------\ncs02\n---------------\nfoo\n', 0)

        # test 2nd sort criteria: smaller node index first
        cmd = "bash -c 's=%h; n=${s//[!0-9]/}; if [[ $(expr $n %% 2) == 0 ]];" \
              "then echo bar; else echo foo; fi'"

        self._clush_t(["-w", "cs[01-04]", "--worker=exec", "-b", cmd], None,
                      b'---------------\ncs[01,03] (2)\n---------------\nfoo\n'
                      b'---------------\ncs[02,04] (2)\n---------------\nbar\n',
                      0)

    def test_037_nostdin(self):
        """test clush (nostdin)"""
        self._clush_t(["-n", "-w", HOSTNAME, "cat"], b"dummy", b"")
        self._clush_t(["--nostdin", "-w", HOSTNAME, "cat"], b"dummy", b"")

    def test_038_rlimits(self):
        """test clush error with low fd_max"""
        # These tests also cover pipe() fd cleanup handling code in
        # fastsubprocess' Popen._gethandles(). All file descriptors should
        # be properly cleaned.
        #
        # Each fork creates 3 FDs remaining in the parent process. We have
        # two tests here with a different fd_max each time in order to raise
        # the exception during stdout and stderr pipe creation.
        # Depending on the current available FDs during the test, the two
        # tests below might be reversed.
        #
        # test for error when creating stdout pipes:
        #   99 used OK + 1 (stdin)
        self.assertRaises(OSError, self._clush_t,
                          ["-N", "-R", "exec", "-w", 'foo[1-1000]', "-b",
                           "-f", "1000", "-O", "fd_max=100", "echo ok"],
                          None, b"ok\n")
        #
        # test for error when creating stderr pipes:
        #   99 OK + 1 (stdin) + 1 (stdout)
        self.assertRaises(OSError, self._clush_t,
                          ["-N", "-R", "exec", "-w", 'foo[1-1000]', "-b",
                           "-f", "1000", "-O", "fd_max=101", "echo ok"],
                          None, b"ok\n")

    def test_039_conf_option(self):
        """test clush --conf option"""
        custf = make_temp_file(dedent("""
            [Main]
            node_count: no
            """).encode())

        # simple test that checks if "node_count:" no from custom conf file
        # is taken into account

        self._clush_t(["-b", "-R", "exec", "-w", "foo[1-10]", "echo ok"], b"",
                      b"---------------\nfoo[1-10] (10)\n---------------\nok\n")

        self._clush_t(["--conf", custf.name, "-b", "-R", "exec", "-w",
                       "foo[1-10]", "echo ok"], b"",
                      b"---------------\nfoo[1-10]\n---------------\nok\n")


class CLIClushTest_B_StdinFailure(unittest.TestCase):
    """Unit test class for testing CLI/Clush.py and stdin failure"""

    def setUp(self):
        class BrokenStdinMock(object):
            def isatty(self):
                return False
            def read(self, bufsize=1024):
                raise IOError(errno.EINVAL, "Invalid argument")

        sys.stdin = BrokenStdinMock()

    def tearDown(self):
        """cleanup all tasks"""
        task_cleanup()
        sys.stdin = sys.__stdin__

    def _clush_t(self, args, stdin, expected_stdout, expected_rc=0,
                 expected_stderr=None):
        CLI_main(self, main, ['clush'] + args, stdin, expected_stdout,
                 expected_rc, expected_stderr)

    def test_100_broken_stdin(self):
        """test clush with broken stdin"""
        self._clush_t(["-w", HOSTNAME, "-v", "sleep 1"], None,
                      b"stdin: [Errno 22] Invalid argument\n", 0, b"")


class CLIClushTest_C_GroupsConf(unittest.TestCase):
    """Unit test class for testing CLI/Clush.py with --groupsconf"""

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

    def _clush_t(self, args, stdin, expected_stdout, expected_rc=0,
                 expected_stderr=None):
        CLI_main(self, main, ['clush'] + args, stdin, expected_stdout,
                 expected_rc, expected_stderr)

    def test_200_groupsconf_option(self):
        """test clush --groupsconf"""
        self._clush_t(["-R", "exec", "-w", "@foo", "-bL", "echo ok"], None,
                      b"example[1-100]: ok\n", 0, b"")
        self._clush_t(["--groupsconf", self.custf.name, "-R", "exec", "-w",
                       "@foo", "-bL", "echo ok"], None,
                      b"custom[7-42]: ok\n", 0, b"")
