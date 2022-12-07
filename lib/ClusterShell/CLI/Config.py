#
# Copyright (C) 2010-2016 CEA/DAM
# Copyright (C) 2017 Stephane Thiell <sthiell@stanford.edu>
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

try:
    from configparser import ConfigParser, NoOptionError, NoSectionError
except ImportError:
    # Python 2 compat
    from ConfigParser import ConfigParser, NoOptionError, NoSectionError

import glob
import os
import shlex
from string import Template

from ClusterShell.Defaults import config_paths, DEFAULTS
from ClusterShell.CLI.Display import VERB_QUIET, VERB_STD, \
    VERB_VERB, VERB_DEBUG, THREE_CHOICES


class ClushConfigError(Exception):
    """Exception used by ClushConfig to report an error."""
    def __init__(self, section=None, option=None, msg=None):
        Exception.__init__(self)
        self.section = section
        self.option = option
        self.msg = msg

    def __str__(self):
        serr = ""
        if self.section and self.option:
            serr += "(Config %s.%s): " % (self.section, self.option)
        if self.msg:
            serr += str(self.msg)
        return serr

class ClushConfig(ConfigParser, object):
    """Config class for clush (specialized ConfigParser)"""

    MAIN_SECTION = 'Main'
    MAIN_DEFAULTS = {"fanout": "%d" % DEFAULTS.fanout,
                     "connect_timeout": "%f" % DEFAULTS.connect_timeout,
                     "command_timeout": "%f" % DEFAULTS.command_timeout,
                     "history_size": "100",
                     "color": THREE_CHOICES[0], # ''
                     "verbosity": "%d" % VERB_STD,
                     "node_count": "yes",
                     "maxrc": "no",
                     "fd_max": "8192",
                     "command_prefix": "",
                     "password_prompt": "no"}

    def __init__(self, options, filename=None):
        """Initialize ClushConfig object from corresponding
        OptionParser options."""
        ConfigParser.__init__(self)
        self.mode = None
        # create Main section with default values
        self.add_section(self.MAIN_SECTION)
        for key, value in self.MAIN_DEFAULTS.items():
            self.set(self.MAIN_SECTION, key, value)
        # config files override defaults values
        if filename:
            files = [filename]
        else:
            files = config_paths('clush.conf')

        self.parsed = self.read(files)

        if self.parsed:
            # for proper $CFGDIR selection, take last parsed configfile only
            cfg_dirname = os.path.dirname(self.parsed[-1])

            # parse Main.confdir
            try:
                # keep track of loaded confdirs
                loaded_confdirs = set()

                confdirstr = self.get(self.MAIN_SECTION, "confdir")
                for confdir in shlex.split(confdirstr):
                    # substitute $CFGDIR, set to the highest priority
                    # configuration directory that has been found
                    confdir = Template(confdir).safe_substitute(
                                                    CFGDIR=cfg_dirname)
                    confdir = os.path.normpath(confdir)
                    if confdir in loaded_confdirs:
                        continue # load each confdir only once
                    loaded_confdirs.add(confdir)
                    if not os.path.isdir(confdir):
                        if not os.path.exists(confdir):
                            continue
                        msg = "Defined confdir %s is not a directory" % confdir
                        raise ClushConfigError(msg=msg)
                    # add config declared in clush.conf.d file parts
                    for cfgfn in sorted(glob.glob('%s/*.conf' % confdir)):
                        # ignore files that cannot be read
                        self.parsed += self.read(cfgfn)
            except (NoSectionError, NoOptionError):
                pass

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
        if options.maxrc:
            self._set_main("maxrc", options.maxrc)

        try:
            # -O/--option KEY=VALUE
            for cfgopt in options.option:
                optkey, optvalue = cfgopt.split('=', 1)
                self._set_main(optkey, optvalue)
        except ValueError as exc:
            raise ClushConfigError(self.MAIN_SECTION, cfgopt,
                                   "invalid -O/--option value")

    def _set_main(self, option, value):
        """Set given option/value pair in the Main section."""
        self.set(self.MAIN_SECTION, option, str(value))

    def _getx(self, xtype, section, option):
        """Return a value of specified type for the named option."""
        try:
            return getattr(ConfigParser, 'get%s' % xtype)(self, \
                section, option)
        except (NoOptionError, NoSectionError, TypeError, ValueError) as exc:
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
        except (NoOptionError, NoSectionError):
            pass

    def _getboolean_mode_optional(self, option):
        """Return a boolean value for the named option in the current
        mode (optionally defined)."""
        if self.mode:
            try:
                return getattr(ConfigParser,
                               'getboolean')(self, "mode:%s" % self.mode,
                                             option)
            except (NoOptionError, NoSectionError):
                pass
        return self.getboolean(self.MAIN_SECTION, option)

    def _getint_mode_optional(self, option):
        """Return an integer value for the named option in the current
        mode (optionally defined)."""
        if self.mode:
            try:
                return getattr(ConfigParser, 'getint')(self,
                                                       "mode:%s" % self.mode,
                                                       option)
            except (NoOptionError, NoSectionError):
                pass
        return self.getint(self.MAIN_SECTION, option)

    def _getfloat_mode_optional(self, option):
        """Return a float value for the named option in the current
        mode (optionally defined)."""
        if self.mode:
            try:
                return getattr(ConfigParser, 'getfloat')(self,
                                                         "mode:%s" % self.mode,
                                                         option)
            except (NoOptionError, NoSectionError):
                pass
        return self.getfloat(self.MAIN_SECTION, option)

    def _get_mode_optional(self, option):
        """Utility method to get a value for the named option in the
        current mode, but do not raise an exception if the option
        doesn't exist."""
        if self.mode:
            try:
                return self.get("mode:%s" % self.mode, option)
            except (NoOptionError, NoSectionError):
                pass
        return self._get_optional(self.MAIN_SECTION, option)

    @property
    def verbosity(self):
        """verbosity value as an integer"""
        try:
            return self.getint(self.MAIN_SECTION, "verbosity")
        except ClushConfigError:
            return 0

    @property
    def fanout(self):
        """fanout value as an integer"""
        return self._getint_mode_optional("fanout")

    @property
    def connect_timeout(self):
        """connect_timeout value as a float"""
        return self._getfloat_mode_optional("connect_timeout")

    @property
    def command_timeout(self):
        """command_timeout value as a float"""
        return self._getfloat_mode_optional("command_timeout")

    @property
    def ssh_user(self):
        """ssh_user value as a string (optional)"""
        return self._get_mode_optional("ssh_user")

    @property
    def ssh_path(self):
        """ssh_path value as a string (optional)"""
        return self._get_mode_optional("ssh_path")

    @property
    def ssh_options(self):
        """ssh_options value as a string (optional)"""
        return self._get_mode_optional("ssh_options")

    @property
    def scp_path(self):
        """scp_path value as a string (optional)"""
        return self._get_mode_optional("scp_path")

    @property
    def scp_options(self):
        """scp_options value as a string (optional)"""
        return self._get_mode_optional("scp_options")

    @property
    def rsh_path(self):
        """rsh_path value as a string (optional)"""
        return self._get_mode_optional("rsh_path")

    @property
    def rcp_path(self):
        """rcp_path value as a string (optional)"""
        return self._get_mode_optional("rcp_path")

    @property
    def rsh_options(self):
        """rsh_options value as a string (optional)"""
        return self._get_mode_optional("rsh_options")

    @property
    def color(self):
        """color value as a string in (never, always, auto)"""
        whencolor = self._get_mode_optional("color")
        if whencolor not in THREE_CHOICES:
            raise ClushConfigError(self.mode or self.MAIN_SECTION, "color",
                                   "choose from %s" % THREE_CHOICES)
        return whencolor

    @property
    def node_count(self):
        """node_count value as a boolean"""
        return self._getboolean_mode_optional("node_count")

    @property
    def maxrc(self):
        """maxrc value as a boolean"""
        return self._getboolean_mode_optional("maxrc")

    @property
    def fd_max(self):
        """max number of open files (soft rlimit)"""
        return self.getint(self.MAIN_SECTION, "fd_max")

    def modes(self):
        """return available run modes"""
        for section in self.sections():
            if section.startswith("mode:"):
                yield section[5:] # could use removeprefix() in py3.9+

    def set_mode(self, mode):
        """set run mode; properties will use it by default"""
        if mode not in self.modes():
            raise ClushConfigError(msg='invalid mode "%s" (available: %s)'
                                   % (mode, ' '.join(self.modes())))
        self.mode = mode

    @property
    def command_prefix(self):
        """command_prefix value as a string (optional)"""
        return self._get_mode_optional("command_prefix")

    @property
    def password_prompt(self):
        """password_prompt value as a boolean (optional)"""
        return self._getboolean_mode_optional("password_prompt")
