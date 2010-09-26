#!/usr/bin/env python
# ClusterShell.CLI.Config test suite
# Written by S. Thiell 2010-09-19
# $Id$


"""Unit test for CLI.Config"""

import os
import resource
import sys
import tempfile
import unittest

sys.path.insert(0, '../lib')

from ClusterShell.CLI.Config import ClushConfig, ClushConfigError
from ClusterShell.CLI.Config import VERB_QUIET, VERB_STD, VERB_DEBUG
from ClusterShell.CLI.Display import WHENCOLOR_CHOICES
from ClusterShell.CLI.OptionParser import OptionParser


class CLIClushConfigTest(unittest.TestCase):
    """This test case performs a complete CLI.Config.ClushConfig
    verification.  Also CLI.OptionParser is used and some parts are
    verified btw.
    """
    def testClushConfigEmpty(self):
        """test CLI.Config.ClushConfig (empty)"""

        f = tempfile.NamedTemporaryFile(prefix='testclushconfig', delete=False)
        f.write("""
""")

        f.close()
        parser = OptionParser("dummy")
        parser.install_display_options(verbose_options=True)
        parser.install_ssh_options()
        options, _ = parser.parse_args([])
        config = ClushConfig(options, filename=f.name)
        self.assert_(config != None)
        config.max_fdlimit()
        self.assertEqual(config.get_color(), WHENCOLOR_CHOICES[0])
        self.assertEqual(config.get_verbosity(), VERB_STD)
        self.assertEqual(config.get_fanout(), 64)
        self.assertEqual(config.get_connect_timeout(), 30)
        self.assertEqual(config.get_command_timeout(), 0)
        self.assertEqual(config.get_ssh_user(), None)
        self.assertEqual(config.get_ssh_path(), None)
        self.assertEqual(config.get_ssh_options(), None)
        os.remove(f.name)

    def testClushConfigAlmostEmpty(self):
        """test CLI.Config.ClushConfig (almost empty)"""

        f = tempfile.NamedTemporaryFile(prefix='testclushconfig', delete=False)
        f.write("""
[Main]
""")

        f.close()
        parser = OptionParser("dummy")
        parser.install_display_options(verbose_options=True)
        parser.install_ssh_options()
        options, _ = parser.parse_args([])
        config = ClushConfig(options, filename=f.name)
        self.assert_(config != None)
        config.max_fdlimit()
        self.assertEqual(config.get_color(), WHENCOLOR_CHOICES[0])
        self.assertEqual(config.get_verbosity(), VERB_STD)
        self.assertEqual(config.get_fanout(), 64)
        self.assertEqual(config.get_connect_timeout(), 30)
        self.assertEqual(config.get_command_timeout(), 0)
        self.assertEqual(config.get_ssh_user(), None)
        self.assertEqual(config.get_ssh_path(), None)
        self.assertEqual(config.get_ssh_options(), None)
        os.remove(f.name)
        
    def testClushConfigDefault(self):
        """test CLI.Config.ClushConfig (default)"""

        f = tempfile.NamedTemporaryFile(prefix='testclushconfig', delete=False)
        f.write("""
[Main]
fanout: 42
connect_timeout: 14
command_timeout: 0
history_size: 100
color: auto
verbosity: 1
#ssh_user: root
#ssh_path: /usr/bin/ssh
#ssh_options: -oStrictHostKeyChecking=no
""")

        f.close()
        parser = OptionParser("dummy")
        parser.install_display_options(verbose_options=True)
        parser.install_ssh_options()
        options, _ = parser.parse_args([])
        config = ClushConfig(options, filename=f.name)
        self.assert_(config != None)
        config.max_fdlimit()
        config.verbose_print(VERB_STD, "test")
        config.verbose_print(VERB_DEBUG, "shouldn't see this")
        self.assertEqual(config.get_color(), WHENCOLOR_CHOICES[2])
        self.assertEqual(config.get_verbosity(), VERB_STD)
        self.assertEqual(config.get_fanout(), 42)
        self.assertEqual(config.get_connect_timeout(), 14)
        self.assertEqual(config.get_command_timeout(), 0)
        self.assertEqual(config.get_ssh_user(), None)
        self.assertEqual(config.get_ssh_path(), None)
        self.assertEqual(config.get_ssh_options(), None)
        os.remove(f.name)
        
    def testClushConfigFull(self):
        """test CLI.Config.ClushConfig (full)"""

        f = tempfile.NamedTemporaryFile(prefix='testclushconfig', delete=False)
        f.write("""
[Main]
fanout: 42
connect_timeout: 14
command_timeout: 0
history_size: 100
color: auto
verbosity: 1
ssh_user: root
ssh_path: /usr/bin/ssh
ssh_options: -oStrictHostKeyChecking=no
""")

        f.close()
        parser = OptionParser("dummy")
        parser.install_display_options(verbose_options=True)
        parser.install_ssh_options()
        options, _ = parser.parse_args([])
        config = ClushConfig(options, filename=f.name)
        self.assert_(config != None)
        config.max_fdlimit()
        self.assertEqual(config.get_color(), WHENCOLOR_CHOICES[2])
        self.assertEqual(config.get_verbosity(), VERB_STD)
        self.assertEqual(config.get_fanout(), 42)
        self.assertEqual(config.get_connect_timeout(), 14)
        self.assertEqual(config.get_command_timeout(), 0)
        self.assertEqual(config.get_ssh_user(), "root")
        self.assertEqual(config.get_ssh_path(), "/usr/bin/ssh")
        self.assertEqual(config.get_ssh_options(), "-oStrictHostKeyChecking=no")
        os.remove(f.name)
        
    def testClushConfigError(self):
        """test CLI.Config.ClushConfig (error)"""

        f = tempfile.NamedTemporaryFile(prefix='testclushconfig', delete=False)
        f.write("""
[Main]
fanout: 3.2
connect_timeout: foo
command_timeout: bar
history_size: 100
color: maybe
verbosity: bar
ssh_user: root
ssh_path: /usr/bin/ssh
ssh_options: -oStrictHostKeyChecking=no
""")

        f.close()
        parser = OptionParser("dummy")
        parser.install_display_options(verbose_options=True)
        parser.install_ssh_options()
        options, _ = parser.parse_args([])
        config = ClushConfig(options, filename=f.name)
        self.assert_(config != None)
        config.max_fdlimit()
        self.assertRaises(ClushConfigError, config.get_color)
        self.assertEqual(config.get_verbosity(), 0) # probably for compatibility
        self.assertRaises(ClushConfigError, config.get_fanout)
        try:
            config.get_fanout()
        except ClushConfigError, e:
            self.assertEqual(str(e)[0:20], "(Config Main.fanout)")

        self.assertRaises(ClushConfigError, config.get_connect_timeout)
        self.assertRaises(ClushConfigError, config.get_command_timeout)

        os.remove(f.name)
        
    def testClushConfigSetRlimit(self):
        """test CLI.Config.ClushConfig (setrlimit)"""

        f = tempfile.NamedTemporaryFile(prefix='testclushconfig', delete=False)
        f.write("""
[Main]
fanout: 42
connect_timeout: 14
command_timeout: 0
history_size: 100
color: auto
verbosity: 1
""")

        f.close()
        parser = OptionParser("dummy")
        parser.install_display_options(verbose_options=True)
        parser.install_ssh_options()
        options, _ = parser.parse_args([])
        config = ClushConfig(options, filename=f.name)
        self.assert_(config != None)

        # force a lower soft limit
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        resource.setrlimit(resource.RLIMIT_NOFILE, (hard/2, hard))
        # max_fdlimit should increase soft limit again
        config.max_fdlimit()
        # verify
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        self.assertEqual(soft, hard)
        os.remove(f.name)
       
    def testClushConfigDefaultWithOptions(self):
        """test CLI.Config.ClushConfig (default with options)"""

        f = tempfile.NamedTemporaryFile(prefix='testclushconfig', delete=False)
        f.write("""
[Main]
fanout: 42
connect_timeout: 14
command_timeout: 0
history_size: 100
color: auto
verbosity: 1
#ssh_user: root
#ssh_path: /usr/bin/ssh
#ssh_options: -oStrictHostKeyChecking=no
""")

        f.close()
        parser = OptionParser("dummy")
        parser.install_display_options(verbose_options=True)
        parser.install_ssh_options()
        options, _ = parser.parse_args(["-f", "36", "-u", "3", "-t", "7",
                                        "--user", "foobar", "--color",
                                        "always", "-d", "-v", "-q", "-o",
                                        "-oSomething"])
        config = ClushConfig(options, filename=f.name)
        self.assert_(config != None)
        config.max_fdlimit()
        config.verbose_print(VERB_STD, "test")
        config.verbose_print(VERB_DEBUG, "test")
        self.assertEqual(config.get_color(), WHENCOLOR_CHOICES[1])
        self.assertEqual(config.get_verbosity(), VERB_DEBUG) # takes biggest
        self.assertEqual(config.get_fanout(), 36)
        self.assertEqual(config.get_connect_timeout(), 7)
        self.assertEqual(config.get_command_timeout(), 3)
        self.assertEqual(config.get_ssh_user(), "foobar")
        self.assertEqual(config.get_ssh_path(), None)
        self.assertEqual(config.get_ssh_options(), "-oSomething")
        os.remove(f.name)
        
    def testClushConfigWithInstalledConfig(self):
        """test CLI.Config.ClushConfig (installed config required)"""
        # This test needs installed configuration files (needed for
        # maximum coverage).
        parser = OptionParser("dummy")
        parser.install_display_options(verbose_options=True)
        parser.install_ssh_options()
        options, _ = parser.parse_args([])
        config = ClushConfig(options)
        self.assert_(config != None)


if __name__ == '__main__':
    suites = [unittest.TestLoader().loadTestsFromTestCase(CLIClushConfigTest)]
    unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(suites))
