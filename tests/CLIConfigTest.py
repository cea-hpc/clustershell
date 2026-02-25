# ClusterShell.CLI.Config test suite
# Written by S. Thiell

"""Unit test for CLI.Config"""

import resource
import os.path
import shutil
import tempfile
from textwrap import dedent
import unittest

from .TLib import *

from ClusterShell.CLI.Clush import set_fdlimit
from ClusterShell.CLI.Config import ClushConfig, ClushConfigError
from ClusterShell.CLI.Display import *
from ClusterShell.CLI.OptionParser import OptionParser


class CLIClushConfigTest(unittest.TestCase):
    """This test case performs a complete CLI.Config.ClushConfig
    verification.  Also CLI.OptionParser is used and some parts are
    verified btw.
    """
    def testClushConfigEmpty(self):
        """test CLI.Config.ClushConfig (empty)"""

        f = tempfile.NamedTemporaryFile(prefix='testclushconfig')
        f.write(b"\n")

        parser = OptionParser("dummy")
        parser.install_clush_config_options()
        parser.install_display_options(verbose_options=True)
        parser.install_connector_options()
        options, _ = parser.parse_args([])
        config = ClushConfig(options, filename=f.name)
        self.assertEqual(config.color, THREE_CHOICES[0])
        self.assertEqual(config.verbosity, VERB_STD)
        self.assertEqual(config.fanout, 64)
        self.assertEqual(config.maxrc, False)
        self.assertEqual(config.node_count, True)
        self.assertEqual(config.connect_timeout, 10)
        self.assertEqual(config.command_timeout, 0)
        self.assertEqual(config.ssh_user, None)
        self.assertEqual(config.ssh_path, None)
        self.assertEqual(config.ssh_options, None)
        f.close()

    def testClushConfigAlmostEmpty(self):
        """test CLI.Config.ClushConfig (almost empty)"""

        f = tempfile.NamedTemporaryFile(prefix='testclushconfig')
        f.write("[Main]\n".encode())

        parser = OptionParser("dummy")
        parser.install_clush_config_options()
        parser.install_display_options(verbose_options=True)
        parser.install_connector_options()
        options, _ = parser.parse_args([])
        config = ClushConfig(options, filename=f.name)
        self.assertEqual(config.color, THREE_CHOICES[0])
        self.assertEqual(config.verbosity, VERB_STD)
        self.assertEqual(config.maxrc, False)
        self.assertEqual(config.node_count, True)
        self.assertEqual(config.fanout, 64)
        self.assertEqual(config.connect_timeout, 10)
        self.assertEqual(config.command_timeout, 0)
        self.assertEqual(config.ssh_user, None)
        self.assertEqual(config.ssh_path, None)
        self.assertEqual(config.ssh_options, None)
        f.close()

    def testClushConfigDefault(self):
        """test CLI.Config.ClushConfig (default)"""

        f = tempfile.NamedTemporaryFile(prefix='testclushconfig')
        f.write(dedent("""
            [Main]
            fanout: 42
            connect_timeout: 14
            command_timeout: 0
            history_size: 100
            color: auto
            verbosity: 1
            #ssh_user: root
            #ssh_path: /usr/bin/ssh
            #ssh_options: -oStrictHostKeyChecking=no""").encode())
        f.flush()
        parser = OptionParser("dummy")
        parser.install_clush_config_options()
        parser.install_display_options(verbose_options=True)
        parser.install_connector_options()
        options, _ = parser.parse_args([])
        config = ClushConfig(options, filename=f.name)
        display = Display(options, config)
        display.vprint(VERB_STD, "test")
        display.vprint(VERB_DEBUG, "shouldn't see this")
        self.assertEqual(config.color, THREE_CHOICES[-1])
        self.assertEqual(config.verbosity, VERB_STD)
        self.assertEqual(config.maxrc, False)
        self.assertEqual(config.node_count, True)
        self.assertEqual(config.fanout, 42)
        self.assertEqual(config.connect_timeout, 14)
        self.assertEqual(config.command_timeout, 0)
        self.assertEqual(config.ssh_user, None)
        self.assertEqual(config.ssh_path, None)
        self.assertEqual(config.ssh_options, None)
        f.close()

    def testClushConfigFull(self):
        """test CLI.Config.ClushConfig (full)"""

        f = tempfile.NamedTemporaryFile(prefix='testclushconfig')
        f.write(dedent("""
            [Main]
            fanout: 42
            connect_timeout: 14
            command_timeout: 0
            history_size: 100
            color: auto
            maxrc: yes
            node_count: yes
            verbosity: 1
            ssh_user: root
            ssh_path: /usr/bin/ssh
            ssh_options: -oStrictHostKeyChecking=no
            """).encode())

        f.flush()
        parser = OptionParser("dummy")
        parser.install_clush_config_options()
        parser.install_display_options(verbose_options=True)
        parser.install_connector_options()
        options, _ = parser.parse_args([])
        config = ClushConfig(options, filename=f.name)
        self.assertEqual(config.color, THREE_CHOICES[-1])
        self.assertEqual(config.verbosity, VERB_STD)
        self.assertEqual(config.maxrc, True)
        self.assertEqual(config.node_count, True)
        self.assertEqual(config.fanout, 42)
        self.assertEqual(config.connect_timeout, 14)
        self.assertEqual(config.command_timeout, 0)
        self.assertEqual(config.ssh_user, "root")
        self.assertEqual(config.ssh_path, "/usr/bin/ssh")
        self.assertEqual(config.ssh_options, "-oStrictHostKeyChecking=no")
        f.close()

    def testClushConfigError(self):
        """test CLI.Config.ClushConfig (error)"""

        f = tempfile.NamedTemporaryFile(prefix='testclushconfig')
        f.write(dedent("""
            [Main]
            fanout: 3.2
            connect_timeout: foo
            command_timeout: bar
            history_size: 100
            color: maybe
            node_count: 3
            verbosity: bar
            ssh_user: root
            ssh_path: /usr/bin/ssh
            ssh_options: -oStrictHostKeyChecking=no
            """).encode())

        f.flush()
        parser = OptionParser("dummy")
        parser.install_clush_config_options()
        parser.install_display_options(verbose_options=True)
        parser.install_connector_options()
        options, _ = parser.parse_args([])
        config = ClushConfig(options, filename=f.name)
        try:
            c = config.color
            self.fail("Exception ClushConfigError not raised (color)")
        except ClushConfigError:
            pass
        self.assertEqual(config.verbosity, 0) # probably for compatibility
        try:
            f = config.fanout
            self.fail("Exception ClushConfigError not raised (fanout)")
        except ClushConfigError:
            pass
        try:
            f = config.node_count
            self.fail("Exception ClushConfigError not raised (node_count)")
        except ClushConfigError:
            pass
        try:
            f = config.fanout
        except ClushConfigError as e:
            self.assertEqual(str(e)[0:20], "(Config Main.fanout)")

        try:
            t = config.connect_timeout
            self.fail("Exception ClushConfigError not raised (connect_timeout)")
        except ClushConfigError:
            pass
        try:
            m = config.command_timeout
            self.fail("Exception ClushConfigError not raised (command_timeout)")
        except ClushConfigError:
            pass
        f.close()

    def testClushConfigSetRlimit(self):
        """test CLI.Config.ClushConfig (setrlimit)"""
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        hard2 = min(32768, hard)
        f = tempfile.NamedTemporaryFile(prefix='testclushconfig')
        f.write(dedent("""
            [Main]
            fanout: 42
            connect_timeout: 14
            command_timeout: 0
            history_size: 100
            color: auto
            fd_max: %d
            verbosity: 1
            """ % hard2).encode())
        f.flush()
        parser = OptionParser("dummy")
        parser.install_clush_config_options()
        parser.install_display_options(verbose_options=True)
        parser.install_connector_options()
        options, _ = parser.parse_args([])
        config = ClushConfig(options, filename=f.name)
        display = Display(options, config)

        # force a lower soft limit
        resource.setrlimit(resource.RLIMIT_NOFILE, (hard2//2, hard))
        # max_fdlimit should increase soft limit again
        set_fdlimit(config.fd_max, display)
        # verify
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        self.assertEqual(soft, hard2)
        f.close()

    def testClushConfigSetRlimitValueError(self):
        """test CLI.Config.ClushConfig (setrlimit ValueError)"""
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        f = tempfile.NamedTemporaryFile(prefix='testclushconfig')
        f.write(dedent("""
            [Main]
            fanout: 42
            connect_timeout: 14
            command_timeout: 0
            history_size: 100
            color: auto
            # Use wrong fd_max value to generate ValueError
            fd_max: -1
            verbosity: 1""").encode())
        f.flush()
        parser = OptionParser("dummy")
        parser.install_clush_config_options()
        parser.install_display_options(verbose_options=True)
        parser.install_connector_options()
        options, _ = parser.parse_args([])
        config = ClushConfig(options, filename=f.name)
        f.close()
        display = Display(options, config)

        class TestException(Exception): pass

        def mock_vprint_err(level, message):
            if message.startswith('Warning: Failed to set max open files'):
                raise TestException()

        display.vprint_err = mock_vprint_err
        self.assertRaises(TestException, set_fdlimit, config.fd_max, display)

        soft2, _ = resource.getrlimit(resource.RLIMIT_NOFILE)
        self.assertEqual(soft, soft2)

    def testClushConfigDefaultWithOptions(self):
        """test CLI.Config.ClushConfig (default with options)"""

        f = tempfile.NamedTemporaryFile(prefix='testclushconfig')
        f.write(dedent("""
            [Main]
            fanout: 42
            connect_timeout: 14
            command_timeout: 0
            history_size: 100
            color: auto
            verbosity: 1""").encode())
        f.flush()
        parser = OptionParser("dummy")
        parser.install_clush_config_options()
        parser.install_display_options(verbose_options=True)
        parser.install_connector_options()
        options, _ = parser.parse_args(["-f", "36", "-u", "3", "-t", "7",
                                        "--user", "foobar", "--color",
                                        "always", "-d", "-v", "-q", "-o",
                                        "-oSomething"])
        config = ClushConfig(options, filename=f.name)
        display = Display(options, config)
        display.vprint(VERB_STD, "test")
        display.vprint(VERB_DEBUG, "test")
        self.assertEqual(config.color, THREE_CHOICES[2])
        self.assertEqual(config.verbosity, VERB_DEBUG) # takes biggest
        self.assertEqual(config.fanout, 36)
        self.assertEqual(config.connect_timeout, 7)
        self.assertEqual(config.command_timeout, 3)
        self.assertEqual(config.ssh_user, "foobar")
        self.assertEqual(config.ssh_path, None)
        self.assertEqual(config.ssh_options, "-oSomething")
        f.close()

    def testClushConfigWithInstalledConfig(self):
        """test CLI.Config.ClushConfig (installed config required)"""
        # This test needs installed configuration files (needed for
        # maximum coverage).
        parser = OptionParser("dummy")
        parser.install_clush_config_options()
        parser.install_display_options(verbose_options=True)
        parser.install_connector_options()
        options, _ = parser.parse_args([])
        config = ClushConfig(options)

    def testClushConfigCustomGlobal(self):
        """test CLI.Config.ClushConfig (CLUSTERSHELL_CFGDIR global custom config)
        """

        # Save existing environment variable, if it's defined
        custom_config_save = os.environ.get('CLUSTERSHELL_CFGDIR')

        # Create fake CLUSTERSHELL_CFGDIR
        custom_cfg_dir = make_temp_dir()

        try:
            os.environ['CLUSTERSHELL_CFGDIR'] = custom_cfg_dir.name

            cfgfile = open(os.path.join(custom_cfg_dir.name, 'clush.conf'), 'w')
            cfgfile.write(dedent("""
                [Main]
                fanout: 42
                connect_timeout: 14
                command_timeout: 0
                history_size: 100
                color: never
                verbosity: 2
                ssh_user: joebar
                ssh_path: ~/bin/ssh
                ssh_options: -oSomeDummyUserOption=yes
                """))

            cfgfile.flush()
            parser = OptionParser("dummy")
            parser.install_clush_config_options()
            parser.install_display_options(verbose_options=True)
            parser.install_connector_options()
            options, _ = parser.parse_args([])
            config = ClushConfig(options) # filename=None to use defaults!
            self.assertEqual(config.color, THREE_CHOICES[1])
            self.assertEqual(config.verbosity, VERB_VERB) # takes biggest
            self.assertEqual(config.fanout, 42)
            self.assertEqual(config.connect_timeout, 14)
            self.assertEqual(config.command_timeout, 0)
            self.assertEqual(config.ssh_user, 'joebar')
            self.assertEqual(config.ssh_path, '~/bin/ssh')
            self.assertEqual(config.ssh_options, '-oSomeDummyUserOption=yes')
            cfgfile.close()

        finally:
            if custom_config_save:
                os.environ['CLUSTERSHELL_CFGDIR'] = custom_config_save
            else:
                del os.environ['CLUSTERSHELL_CFGDIR']
            custom_cfg_dir.cleanup()


    def testClushConfigUserOverride(self):
        """test CLI.Config.ClushConfig (XDG_CONFIG_HOME user config)"""

        xdg_config_home_save = os.environ.get('XDG_CONFIG_HOME')

        # Create fake XDG_CONFIG_HOME
        tdir = make_temp_dir()
        try:
            os.environ['XDG_CONFIG_HOME'] = tdir.name

            # create $XDG_CONFIG_HOME/clustershell/clush.conf
            usercfgdir = os.path.join(tdir.name, 'clustershell')
            os.mkdir(usercfgdir)
            cfgfile = open(os.path.join(usercfgdir, 'clush.conf'), 'w')
            cfgfile.write(dedent("""
                [Main]
                fanout: 42
                connect_timeout: 14
                command_timeout: 0
                history_size: 100
                color: never
                verbosity: 2
                ssh_user: trump
                ssh_path: ~/bin/ssh
                ssh_options: -oSomeDummyUserOption=yes
                """))

            cfgfile.flush()
            parser = OptionParser("dummy")
            parser.install_clush_config_options()
            parser.install_display_options(verbose_options=True)
            parser.install_connector_options()
            options, _ = parser.parse_args([])
            config = ClushConfig(options) # filename=None to use defaults!
            self.assertEqual(config.color, THREE_CHOICES[1])
            self.assertEqual(config.verbosity, VERB_VERB) # takes biggest
            self.assertEqual(config.fanout, 42)
            self.assertEqual(config.connect_timeout, 14)
            self.assertEqual(config.command_timeout, 0)
            self.assertEqual(config.ssh_user, 'trump')
            self.assertEqual(config.ssh_path, '~/bin/ssh')
            self.assertEqual(config.ssh_options, '-oSomeDummyUserOption=yes')
            cfgfile.close()

        finally:
            if xdg_config_home_save:
                os.environ['XDG_CONFIG_HOME'] = xdg_config_home_save
            else:
                del os.environ['XDG_CONFIG_HOME']
            tdir.cleanup()

    def testClushConfigConfDirModesEmpty(self):
        """test CLI.Config.ClushConfig (confdir with no modes)"""
        tdir1 = make_temp_dir()
        dname1 = tdir1.name
        tdir2 = make_temp_dir()
        dname2 = tdir2.name
        f = make_temp_file(dedent("""
            [Main]
            fanout: 42
            connect_timeout: 14
            command_timeout: 0
            history_size: 100
            color: auto
            maxrc: yes
            node_count: yes
            verbosity: 1
            confdir: %s "%s" %s
            """ % (dname1, dname2, dname1)).encode())

        try:
            parser = OptionParser("dummy")
            parser.install_clush_config_options()
            parser.install_display_options(verbose_options=True)
            parser.install_connector_options()
            options, _ = parser.parse_args([])
            config = ClushConfig(options, filename=f.name)
            self.assertEqual(config.color, THREE_CHOICES[-1])
            self.assertEqual(config.verbosity, VERB_STD)
            self.assertTrue(config.maxrc)
            self.assertTrue(config.node_count)
            self.assertEqual(config.fanout, 42)
            self.assertEqual(config.connect_timeout, 14)
            self.assertEqual(config.command_timeout, 0)
            self.assertEqual(config.ssh_user, None)
            self.assertEqual(config.ssh_path, None)
            self.assertEqual(config.ssh_options, None)
            self.assertEqual(config.command_prefix, "")
            self.assertFalse(config.command_prefix)
            self.assertFalse(config.password_prompt)

            self.assertEqual(len(set(config.modes())), 0)

            self.assertRaises(ClushConfigError, config.set_mode, "sshpass")
        finally:
            f.close()
            tdir2.cleanup()
            tdir1.cleanup()


    def testClushConfigConfDirModes(self):
        """test CLI.Config.ClushConfig (confdir and modes)"""
        tdir1 = make_temp_dir()
        dname1 = tdir1.name
        tdir2 = make_temp_dir()
        dname2 = tdir2.name
        # Notes:
        #   - use dname1 two times to check dup checking code
        #   - use quotes on one of the directory path
        #   - enable each run modes and test config options
        f = make_temp_file(dedent("""
            [Main]
            fanout: 42
            connect_timeout: 14
            command_timeout: 0
            history_size: 100
            color: auto
            maxrc: yes
            node_count: yes
            verbosity: 1
            ssh_user: root
            ssh_path: /usr/bin/ssh
            ssh_options: -oStrictHostKeyChecking=no
            confdir: %s "%s" %s
            """ % (dname1, dname2, dname1)).encode())

        f1 = make_temp_file(dedent("""
            [mode:sshpass]
            password_prompt: yes
            ssh_path: /usr/bin/sshpass /usr/bin/ssh
            scp_path: /usr/bin/sshpass /usr/bin/scp
            ssh_options: -oBatchMode=no
            """).encode(), suffix=".conf", dir=dname1)

        f2 = make_temp_file(dedent("""
            [mode:sudo]
            password_prompt: yes
            command_prefix: /usr/bin/sudo -S -p "''"
            """).encode(), suffix=".conf", dir=dname2)

        f3 = make_temp_file(dedent("""
            [mode:test]
            fanout: 100
            connect_timeout: 6
            command_timeout: 5
            history_size: 200
            color: always
            maxrc: no
            node_count: no
            verbosity: 0
            ssh_user: nobody
            ssh_path: /some/other/ssh
            ssh_options:
            """).encode(), suffix=".conf", dir=dname2)

        try:
            parser = OptionParser("dummy")
            parser.install_clush_config_options()
            parser.install_display_options(verbose_options=True)
            parser.install_connector_options()
            options, _ = parser.parse_args([])
            config = ClushConfig(options, filename=f.name)
            self.assertEqual(config.color, THREE_CHOICES[-1])
            self.assertEqual(config.verbosity, VERB_STD)
            self.assertTrue(config.maxrc)
            self.assertTrue(config.node_count)
            self.assertEqual(config.fanout, 42)
            self.assertEqual(config.connect_timeout, 14)
            self.assertEqual(config.command_timeout, 0)
            self.assertEqual(config.ssh_user, "root")
            self.assertEqual(config.ssh_path, "/usr/bin/ssh")
            self.assertEqual(config.ssh_options, "-oStrictHostKeyChecking=no")
            self.assertEqual(config.command_prefix, "")
            self.assertFalse(config.command_prefix)
            self.assertFalse(config.password_prompt)

            self.assertEqual(set(config.modes()), {'sshpass', 'sudo', 'test'})

            config.set_mode("sshpass")
            self.assertEqual(config.color, THREE_CHOICES[-1])
            self.assertEqual(config.verbosity, VERB_STD)
            self.assertTrue(config.maxrc)
            self.assertTrue(config.node_count)
            self.assertEqual(config.fanout, 42)
            self.assertEqual(config.connect_timeout, 14)
            self.assertEqual(config.command_timeout, 0)
            self.assertEqual(config.ssh_user, "root")
            self.assertEqual(config.ssh_path, "/usr/bin/sshpass /usr/bin/ssh")
            self.assertEqual(config.ssh_options, "-oBatchMode=no")
            self.assertEqual(config.command_prefix, "")
            self.assertFalse(config.command_prefix)
            self.assertTrue(config.password_prompt)

            config.set_mode("sudo")
            self.assertEqual(config.color, THREE_CHOICES[-1])
            self.assertEqual(config.verbosity, VERB_STD)
            self.assertTrue(config.maxrc)
            self.assertTrue(config.node_count)
            self.assertEqual(config.fanout, 42)
            self.assertEqual(config.connect_timeout, 14)
            self.assertEqual(config.command_timeout, 0)
            self.assertEqual(config.ssh_user, "root")
            self.assertEqual(config.ssh_path, "/usr/bin/ssh")
            self.assertEqual(config.ssh_options, "-oStrictHostKeyChecking=no")
            self.assertEqual(config.command_prefix, '/usr/bin/sudo -S -p "\'\'"')
            self.assertTrue(config.command_prefix)
            self.assertTrue(config.password_prompt)

            config.set_mode("test")
            self.assertEqual(config.color, THREE_CHOICES[2])
            self.assertEqual(config.verbosity, VERB_STD)
            self.assertFalse(config.maxrc)
            self.assertFalse(config.node_count)
            self.assertEqual(config.fanout, 100)
            self.assertEqual(config.connect_timeout, 6)
            self.assertEqual(config.command_timeout, 5)
            self.assertEqual(config.ssh_user, "nobody")
            self.assertEqual(config.ssh_path, "/some/other/ssh")
            self.assertEqual(config.ssh_options, "")
            self.assertEqual(config.command_prefix, "")
            self.assertFalse(config.command_prefix)
            self.assertFalse(config.password_prompt)
        finally:
            f3.close()
            f2.close()
            f1.close()
            f.close()
            tdir2.cleanup()
            tdir1.cleanup()
