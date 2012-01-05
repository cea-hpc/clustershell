#!/usr/bin/env python
# ClusterShell.CLI.Config test suite
# Written by S. Thiell 2010-09-19
# $Id$


"""Unit test for CLI.Config"""

import resource
import sys
import tempfile
import unittest

sys.path.insert(0, '../lib')


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
        f.write("""
""")

        parser = OptionParser("dummy")
        parser.install_display_options(verbose_options=True)
        parser.install_ssh_options()
        options, _ = parser.parse_args([])
        config = ClushConfig(options, filename=f.name)
        self.assert_(config != None)
        self.assertEqual(config.color, WHENCOLOR_CHOICES[-1])
        self.assertEqual(config.verbosity, VERB_STD)
        self.assertEqual(config.fanout, 64)
        self.assertEqual(config.node_count, True)
        self.assertEqual(config.connect_timeout, 30)
        self.assertEqual(config.command_timeout, 0)
        self.assertEqual(config.ssh_user, None)
        self.assertEqual(config.ssh_path, None)
        self.assertEqual(config.ssh_options, None)
        f.close()

    def testClushConfigAlmostEmpty(self):
        """test CLI.Config.ClushConfig (almost empty)"""

        f = tempfile.NamedTemporaryFile(prefix='testclushconfig')
        f.write("""
[Main]
""")

        parser = OptionParser("dummy")
        parser.install_display_options(verbose_options=True)
        parser.install_ssh_options()
        options, _ = parser.parse_args([])
        config = ClushConfig(options, filename=f.name)
        self.assert_(config != None)
        self.assertEqual(config.color, WHENCOLOR_CHOICES[-1])
        self.assertEqual(config.verbosity, VERB_STD)
        self.assertEqual(config.node_count, True)
        self.assertEqual(config.fanout, 64)
        self.assertEqual(config.connect_timeout, 30)
        self.assertEqual(config.command_timeout, 0)
        self.assertEqual(config.ssh_user, None)
        self.assertEqual(config.ssh_path, None)
        self.assertEqual(config.ssh_options, None)
        f.close()
        
    def testClushConfigDefault(self):
        """test CLI.Config.ClushConfig (default)"""

        f = tempfile.NamedTemporaryFile(prefix='testclushconfig')
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

        f.flush()
        parser = OptionParser("dummy")
        parser.install_display_options(verbose_options=True)
        parser.install_ssh_options()
        options, _ = parser.parse_args([])
        config = ClushConfig(options, filename=f.name)
        self.assert_(config != None)
        display = Display(options, config)
        self.assert_(display != None)
        display.vprint(VERB_STD, "test")
        display.vprint(VERB_DEBUG, "shouldn't see this")
        self.assertEqual(config.color, WHENCOLOR_CHOICES[2])
        self.assertEqual(config.verbosity, VERB_STD)
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
        f.write("""
[Main]
fanout: 42
connect_timeout: 14
command_timeout: 0
history_size: 100
color: auto
node_count: yes
verbosity: 1
ssh_user: root
ssh_path: /usr/bin/ssh
ssh_options: -oStrictHostKeyChecking=no
""")

        f.flush()
        parser = OptionParser("dummy")
        parser.install_display_options(verbose_options=True)
        parser.install_ssh_options()
        options, _ = parser.parse_args([])
        config = ClushConfig(options, filename=f.name)
        self.assert_(config != None)
        self.assertEqual(config.color, WHENCOLOR_CHOICES[2])
        self.assertEqual(config.verbosity, VERB_STD)
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
        f.write("""
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
""")

        f.flush()
        parser = OptionParser("dummy")
        parser.install_display_options(verbose_options=True)
        parser.install_ssh_options()
        options, _ = parser.parse_args([])
        config = ClushConfig(options, filename=f.name)
        self.assert_(config != None)
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
        except ClushConfigError, e:
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
        f.write("""
[Main]
fanout: 42
connect_timeout: 14
command_timeout: 0
history_size: 100
color: auto
fd_max: %d
verbosity: 1
""" % hard2)

        f.flush()
        parser = OptionParser("dummy")
        parser.install_display_options(verbose_options=True)
        parser.install_ssh_options()
        options, _ = parser.parse_args([])
        config = ClushConfig(options, filename=f.name)
        self.assert_(config != None)
        display = Display(options, config)
        self.assert_(display != None)

        # force a lower soft limit
        resource.setrlimit(resource.RLIMIT_NOFILE, (hard2/2, hard))
        # max_fdlimit should increase soft limit again
        set_fdlimit(config.fd_max, display)
        # verify
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        self.assertEqual(soft, hard2)
        f.close()
       
    def testClushConfigDefaultWithOptions(self):
        """test CLI.Config.ClushConfig (default with options)"""

        f = tempfile.NamedTemporaryFile(prefix='testclushconfig')
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

        f.flush()
        parser = OptionParser("dummy")
        parser.install_display_options(verbose_options=True)
        parser.install_ssh_options()
        options, _ = parser.parse_args(["-f", "36", "-u", "3", "-t", "7",
                                        "--user", "foobar", "--color",
                                        "always", "-d", "-v", "-q", "-o",
                                        "-oSomething"])
        config = ClushConfig(options, filename=f.name)
        self.assert_(config != None)
        display = Display(options, config)
        self.assert_(display != None)
        display.vprint(VERB_STD, "test")
        display.vprint(VERB_DEBUG, "test")
        self.assertEqual(config.color, WHENCOLOR_CHOICES[1])
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
        parser.install_display_options(verbose_options=True)
        parser.install_ssh_options()
        options, _ = parser.parse_args([])
        config = ClushConfig(options)
        self.assert_(config != None)


if __name__ == '__main__':
    suites = [unittest.TestLoader().loadTestsFromTestCase(CLIClushConfigTest)]
    unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(suites))
