#!/usr/bin/env python
#
# Copyright (C) 2010-2016 CEA/DAM
#
# This file is part of ClusterShell.
#
# ClusterShell is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# ClusterShell is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with ClusterShell; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

"""
CLI configuration classes
"""

import ConfigParser
from os.path import expanduser

from ClusterShell.Defaults import config_paths, DEFAULTS
from ClusterShell.CLI.Display import VERB_QUIET, VERB_STD, \
    VERB_VERB, VERB_DEBUG, THREE_CHOICES


class ClushConfigError(Exception):
    """Exception used by ClushConfig to report an error."""
    def __init__(self, section, option, msg):
        Exception.__init__(self)
        self.section = section
        self.option = option
        self.msg = msg

    def __str__(self):
        return "(Config %s.%s): %s" % (self.section, self.option, self.msg)

class ClushConfig(ConfigParser.ConfigParser, object):
    """Config class for clush (specialized ConfigParser)"""

    main_defaults = {"fanout": "%d" % DEFAULTS.fanout,
                     "connect_timeout": "%f" % DEFAULTS.connect_timeout,
                     "command_timeout": "%f" % DEFAULTS.command_timeout,
                     "history_size": "100",
                     "color": THREE_CHOICES[-1], # auto
                     "verbosity": "%d" % VERB_STD,
                     "node_count": "yes",
                     "fd_max": "8192"}

    def __init__(self, options, filename=None):
        """Initialize ClushConfig object from corresponding
        OptionParser options."""
        ConfigParser.ConfigParser.__init__(self)
        # create Main section with default values
        self.add_section("Main")
        for key, value in ClushConfig.main_defaults.iteritems():
            self.set("Main", key, value)
        # config files override defaults values
        if filename:
            files = [filename]
        else:
            files = config_paths('clush.conf')
            # deprecated user config, kept in 1.x for 1.6 compat
            files.insert(1, expanduser('~/.clush.conf'))
        self.read(files)

        # Apply command line overrides
        if options.quiet:
            self._set_main("verbosity", VERB_QUIET)
        if options.verbose:
            self._set_main("verbosity", VERB_VERB)
        if options.debug:
            self._set_main("verbosity", VERB_DEBUG)
        if options.fanout:
            self._set_main("fanout", options.fanout)
        if options.user:
            self._set_main("ssh_user", options.user)
        if options.options:
            self._set_main("ssh_options", options.options)
        if options.connect_timeout:
            self._set_main("connect_timeout", options.connect_timeout)
        if options.command_timeout:
            self._set_main("command_timeout", options.command_timeout)
        if options.whencolor:
            self._set_main("color", options.whencolor)

        try:
            # -O/--option KEY=VALUE
            for cfgopt in options.option:
                optkey, optvalue = cfgopt.split('=', 1)
                self._set_main(optkey, optvalue)
        except ValueError, exc:
            raise ClushConfigError("Main", cfgopt, "invalid -O/--option value")

    def _set_main(self, option, value):
        """Set given option/value pair in the Main section."""
        self.set("Main", option, str(value))

    def _getx(self, xtype, section, option):
        """Return a value of specified type for the named option."""
        try:
            return getattr(ConfigParser.ConfigParser, 'get%s' % xtype)(self, \
                section, option)
        except (ConfigParser.Error, TypeError, ValueError), exc:
            raise ClushConfigError(section, option, exc)

    def getboolean(self, section, option):
        """Return a boolean value for the named option."""
        return self._getx('boolean', section, option)

    def getfloat(self, section, option):
        """Return a float value for the named option."""
        return self._getx('float', section, option)

    def getint(self, section, option):
        """Return an integer value for the named option."""
        return self._getx('int', section, option)

    def _get_optional(self, section, option):
        """Utility method to get a value for the named option, but do
        not raise an exception if the option doesn't exist."""
        try:
            return self.get(section, option)
        except ConfigParser.Error:
            pass

    @property
    def verbosity(self):
        """verbosity value as an integer"""
        try:
            return self.getint("Main", "verbosity")
        except ClushConfigError:
            return 0

    @property
    def fanout(self):
        """fanout value as an integer"""
        return self.getint("Main", "fanout")

    @property
    def connect_timeout(self):
        """connect_timeout value as a float"""
        return self.getfloat("Main", "connect_timeout")

    @property
    def command_timeout(self):
        """command_timeout value as a float"""
        return self.getfloat("Main", "command_timeout")

    @property
    def ssh_user(self):
        """ssh_user value as a string (optional)"""
        return self._get_optional("Main", "ssh_user")

    @property
    def ssh_path(self):
        """ssh_path value as a string (optional)"""
        return self._get_optional("Main", "ssh_path")

    @property
    def ssh_options(self):
        """ssh_options value as a string (optional)"""
        return self._get_optional("Main", "ssh_options")

    @property
    def scp_path(self):
        """scp_path value as a string (optional)"""
        return self._get_optional("Main", "scp_path")

    @property
    def scp_options(self):
        """scp_options value as a string (optional)"""
        return self._get_optional("Main", "scp_options")

    @property
    def rsh_path(self):
        """rsh_path value as a string (optional)"""
        return self._get_optional("Main", "rsh_path")

    @property
    def rcp_path(self):
        """rcp_path value as a string (optional)"""
        return self._get_optional("Main", "rcp_path")

    @property
    def rsh_options(self):
        """rsh_options value as a string (optional)"""
        return self._get_optional("Main", "rsh_options")

    @property
    def color(self):
        """color value as a string in (never, always, auto)"""
        whencolor = self._get_optional("Main", "color")
        if whencolor not in THREE_CHOICES:
            raise ClushConfigError("Main", "color", "choose from %s" % \
                                   THREE_CHOICES)
        return whencolor

    @property
    def node_count(self):
        """node_count value as a boolean"""
        return self.getboolean("Main", "node_count")

    @property
    def fd_max(self):
        """max number of open files (soft rlimit)"""
        return self.getint("Main", "fd_max")

