#!/usr/bin/env python
#
# Copyright CEA/DAM/DIF (2010)
#  Contributor: Stephane THIELL <stephane.thiell@cea.fr>
#
# This file is part of the ClusterShell library.
#
# This software is governed by the CeCILL-C license under French law and
# abiding by the rules of distribution of free software.  You can  use,
# modify and/ or redistribute the software under the terms of the CeCILL-C
# license as circulated by CEA, CNRS and INRIA at the following URL
# "http://www.cecill.info".
#
# As a counterpart to the access to the source code and  rights to copy,
# modify and redistribute granted by the license, users are provided only
# with a limited warranty  and the software's author,  the holder of the
# economic rights,  and the successive licensors  have only  limited
# liability.
#
# In this respect, the user's attention is drawn to the risks associated
# with loading,  using,  modifying and/or developing or reproducing the
# software by the user in light of its specific status of free software,
# that may mean  that it is complicated to manipulate,  and  that  also
# therefore means  that it is reserved for developers  and  experienced
# professionals having in-depth computer knowledge. Users are therefore
# encouraged to load and test the software's suitability as regards their
# requirements in conditions enabling the security of their systems and/or
# data to be ensured and,  more generally, to use and operate it in the
# same conditions as regards security.
#
# The fact that you are presently reading this means that you have had
# knowledge of the CeCILL-C license and that you accept its terms.
#
# $Id$

"""
CLI configuration classes
"""

import ConfigParser
import os
import resource

from ClusterShell.CLI.Display import WHENCOLOR_CHOICES

VERB_QUIET = 0
VERB_STD = 1
VERB_VERB = 2
VERB_DEBUG = 3


class ClushConfigError(Exception):
    """Exception used by ClushConfig to report an error."""

    def __init__(self, section, option, msg):
        Exception.__init__(self)
        self.section = section
        self.option = option
        self.msg = msg

    def __str__(self):
        return "(Config %s.%s): %s" % (self.section, self.option, self.msg)

class ClushConfig(ConfigParser.ConfigParser):
    """Config class for clush (specialized ConfigParser)"""

    main_defaults = { "fanout" : "64",
                      "connect_timeout" : "30",
                      "command_timeout" : "0",
                      "history_size" : "100",
                      "color" : WHENCOLOR_CHOICES[0],
                      "verbosity" : "%d" % VERB_STD }

    def __init__(self, options, filename=None):
        ConfigParser.ConfigParser.__init__(self)
        # create Main section with default values
        self.add_section("Main")
        for key, value in ClushConfig.main_defaults.iteritems():
            self.set("Main", key, value)
        # config files override defaults values
        if filename:
            files = [filename]
        else:
            files = ['/etc/clustershell/clush.conf',
                     os.path.expanduser('~/.clush.conf')]
        self.read(files)

        # Apply command line overrides
        if options.quiet:
            self.set_main("verbosity", VERB_QUIET)
        if options.verbose:
            self.set_main("verbosity", VERB_VERB)
        if options.debug:
            self.set_main("verbosity", VERB_DEBUG)
        if options.fanout:
            self.set_main("fanout", options.fanout)
        if options.user:
            self.set_main("ssh_user", options.user)
        if options.options:
            self.set_main("ssh_options", options.options)
        if options.connect_timeout:
            self.set_main("connect_timeout", options.connect_timeout)
        if options.command_timeout:
            self.set_main("command_timeout", options.command_timeout)
        if options.whencolor:
            self.set_main("color", options.whencolor)

    def verbose_print(self, level, message):
        if self.get_verbosity() >= level:
            print message

    def max_fdlimit(self):
        """Make open file descriptors soft limit the max."""
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        if soft < hard:
            self.verbose_print(VERB_DEBUG, "Setting max soft limit "
                               "RLIMIT_NOFILE: %d -> %d" % (soft, hard))
            resource.setrlimit(resource.RLIMIT_NOFILE, (hard, hard))
        else:
            self.verbose_print(VERB_DEBUG, "Soft limit RLIMIT_NOFILE already "
                               "set to the max (%d)" % soft)

    def set_main(self, option, value):
        self.set("Main", option, str(value))

    def getint(self, section, option):
        try:
            return ConfigParser.ConfigParser.getint(self, section, option)
        except (ConfigParser.Error, TypeError, ValueError), e:
            raise ClushConfigError(section, option, e)

    def getfloat(self, section, option):
        try:
            return ConfigParser.ConfigParser.getfloat(self, section, option)
        except (ConfigParser.Error, TypeError, ValueError), e:
            raise ClushConfigError(section, option, e)

    def _get_optional(self, section, option):
        try:
            return self.get(section, option)
        except ConfigParser.Error:
            pass

    def get_color(self):
        whencolor = self._get_optional("Main", "color")
        if whencolor not in WHENCOLOR_CHOICES:
            raise ClushConfigError("Main", "color", "choose from %s" % \
                                   WHENCOLOR_CHOICES)
        return whencolor

    def get_verbosity(self):
        try:
            return self.getint("Main", "verbosity")
        except ClushConfigError:
            return 0

    def get_fanout(self):
        return self.getint("Main", "fanout")
    
    def get_connect_timeout(self):
        return self.getfloat("Main", "connect_timeout")

    def get_command_timeout(self):
        return self.getfloat("Main", "command_timeout")

    def get_ssh_user(self):
        return self._get_optional("Main", "ssh_user")

    def get_ssh_path(self):
        return self._get_optional("Main", "ssh_path")

    def get_ssh_options(self):
        return self._get_optional("Main", "ssh_options")

