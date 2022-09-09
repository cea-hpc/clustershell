#
# Copyright (C) 2015-2019 Stephane Thiell <sthiell@stanford.edu>
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
ClusterShell Defaults module.

Manage library defaults.
"""

from __future__ import print_function

# Imported early
# Should not import any other ClusterShell modules when loaded
try:
    from configparser import ConfigParser, NoOptionError, NoSectionError
except ImportError:
    # Python 2 compat
    from ConfigParser import ConfigParser, NoOptionError, NoSectionError

import os
import sys


#
# defaults.conf sections
#
CFG_SECTION_TASK_DEFAULT = 'task.default'
CFG_SECTION_TASK_INFO = 'task.info'
CFG_SECTION_NODESET = 'nodeset'
CFG_SECTION_ENGINE = 'engine'

#
# Functions
#
def _task_print_debug(task, line):
    """Default task debug printing function."""
    print(line)

def _load_workerclass(workername):
    """
    Return the class pointer matching `workername`.

    This can be the 'short' name (such as `ssh`) or a fully-qualified
    module path (such as ClusterShell.Worker.Ssh).

    The module is loaded if not done yet.
    """

    # First try the worker name as a module under ClusterShell.Worker,
    # but if that fails, try the worker name directly
    try:
        modname = "ClusterShell.Worker.%s" % workername.capitalize()
        _import_module(modname)
    except ImportError:
        modname = workername
        _import_module(modname)

    # Get the class pointer
    return sys.modules[modname].WORKER_CLASS

def _import_module(modname):
    """Import a python module if not done yet."""
    # Iterate over a copy of sys.modules' keys to avoid RuntimeError
    if modname.lower() not in [mod.lower() for mod in list(sys.modules)]:
        # Import module if not yet loaded
        __import__(modname)

def _local_workerclass(defaults):
    """Return default local worker class."""
    return _load_workerclass(defaults.local_workername)

def _distant_workerclass(defaults):
    """Return default distant worker class."""
    return _load_workerclass(defaults.distant_workername)

def config_paths(config_name):
    """Return default path list for a ClusterShell config file name."""
    return [os.path.join(os.environ.get('CLUSTERSHELL_CFGDIR',
                                        '/etc/clustershell'),
			             config_name), # global config file
            # default pip --user config file
            os.path.expanduser('~/.local/etc/clustershell/%s' % config_name),
            # per-user config (top override)
            os.path.join(os.environ.get('XDG_CONFIG_HOME',
                                        os.path.expanduser('~/.config')),
                         'clustershell', config_name)]

def _converter_integer_tuple(value):
    """ConfigParser converter for tuple of integers"""
    # NOTE: compatible with ConfigParser 'converters' argument (Python 3.5+)
    return tuple(int(x) for x in value.split(',') if x.strip())

def _parser_get_integer_tuple(parser, section, option, **kwargs):
    """
    Compatible converter for parsing tuple of integers until we can use
    converters from new ConfigParser (Python 3.5+).
    """
    return _converter_integer_tuple(
        ConfigParser.get(parser, section, option, **kwargs))


#
# Classes
#
class Defaults(object):
    """
    Class used to manipulate ClusterShell defaults.

    The following attributes may be read at any time and also changed
    programmatically, for most of them **before** ClusterShell objects
    (Task or NodeSet) are initialized.

    NodeSet defaults:

    * fold_axis (tuple of axis integers; default is empty tuple ``()``)

    Task defaults:

    * stderr (boolean; default is ``False``)
    * stdin (boolean; default is ``True``)
    * stdout_msgtree (boolean; default is ``True``)
    * stderr_msgtree (boolean; default is ``True``)
    * engine (string; default is ``'auto'``)
    * local_workername (string; default is ``'exec'``)
    * distant_workername (string; default is ``'ssh'``)
    * debug (boolean; default is ``False``)
    * print_debug (function; default is internal)
    * fanout (integer; default is ``64``)
    * grooming_delay (float; default is ``0.25``)
    * connect_timeout (float; default is ``10``)
    * command_timeout (float; default is ``0``)

    Engine defaults:

    * port_qlimit (integer; default is ``100``)

    Example of use::

        >>> from ClusterShell.Defaults import DEFAULTS
        >>> from ClusterShell.Task import task_self
        >>> # Change default distant worker to rsh (WorkerRsh)
        ... DEFAULTS.distant_workername = 'rsh'
        >>> task = task_self()
        >>> task.run("uname -r", nodes="cs[01-03]")
        <ClusterShell.Worker.Rsh.WorkerRsh object at 0x1f4a410>
        >>> list((str(msg), nodes) for msg, nodes in task.iter_buffers())
        [('3.10.0-229.7.2.el7.x86_64', ['cs02', 'cs01', 'cs03'])]


    The library default values of all of the above attributes may be changed
    using the defaults.conf configuration file, except for *print_debug*
    (cf. :ref:`defaults-config`). An example defaults.conf file should be
    included with ClusterShell. Remember that this could affect all
    applications using ClusterShell.
    """

    #
    # Default values for task "default" sync dict
    #
    _TASK_DEFAULT = {"stderr"             : False,
                     "stdin"              : True,
                     "stdout_msgtree"     : True,
                     "stderr_msgtree"     : True,
                     "engine"             : 'auto',
                     "port_qlimit"        : 100, # 1.8 compat
                     "auto_tree"          : True,
                     "local_workername"   : 'exec',
                     "distant_workername" : 'ssh'}

    #
    # Datatype converters for task_default
    #
    _TASK_DEFAULT_CONVERTERS = {"stderr"             : ConfigParser.getboolean,
                                "stdin"              : ConfigParser.getboolean,
                                "stdout_msgtree"     : ConfigParser.getboolean,
                                "stderr_msgtree"     : ConfigParser.getboolean,
                                "engine"             : ConfigParser.get,
                                "port_qlimit"        : ConfigParser.getint, # 1.8 compat
                                "auto_tree"          : ConfigParser.getboolean,
                                "local_workername"   : ConfigParser.get,
                                "distant_workername" : ConfigParser.get}

    #
    # Default values for task "info" async dict
    #
    _TASK_INFO = {"debug"            : False,
                  "print_debug"      : _task_print_debug,
                  "fanout"           : 64,
                  "grooming_delay"   : 0.25,
                  "connect_timeout"  : 10,
                  "command_timeout"  : 0}

    #
    # Datatype converters for task_info
    #
    _TASK_INFO_CONVERTERS = {"debug"           : ConfigParser.getboolean,
                             "fanout"          : ConfigParser.getint,
                             "grooming_delay"  : ConfigParser.getfloat,
                             "connect_timeout" : ConfigParser.getfloat,
                             "command_timeout" : ConfigParser.getfloat}

    #
    # Black list of info keys whose values cannot safely be propagated
    # in tree mode
    #
    _TASK_INFO_PKEYS_BL = ['engine', 'print_debug']

    #
    # Default values for NodeSet
    #
    _NODESET = {"fold_axis" : ()}

    #
    # Datatype converters for NodeSet defaults
    #
    _NODESET_CONVERTERS = {"fold_axis" : _parser_get_integer_tuple}

    #
    # Default values for Engine objects
    #
    _ENGINE = {"port_qlimit" : 100}

    #
    # Datatype converters for Engine defaults
    #
    _ENGINE_CONVERTERS = {"port_qlimit" : ConfigParser.getint}

    def __init__(self, filenames):
        """Initialize Defaults from config filenames"""

        self._task_default = self._TASK_DEFAULT.copy()
        self._task_info = self._TASK_INFO.copy()
        self._task_info_pkeys_bl = list(self._TASK_INFO_PKEYS_BL)
        self._nodeset = self._NODESET.copy()
        self._engine = self._ENGINE.copy()

        config = ConfigParser()
        parsed = config.read(filenames)

        if parsed:
            self._parse_config(config)

    def _parse_config(self, config):
        """parse config"""

        # task_default overrides
        for key, conv in self._TASK_DEFAULT_CONVERTERS.items():
            try:
                self._task_default[key] = conv(config, CFG_SECTION_TASK_DEFAULT,
                                               key)
            except (NoSectionError, NoOptionError):
                pass

        # task_info overrides
        for key, conv in self._TASK_INFO_CONVERTERS.items():
            try:
                self._task_info[key] = conv(config, CFG_SECTION_TASK_INFO, key)
            except (NoSectionError, NoOptionError):
                pass

        # NodeSet
        for key, conv in self._NODESET_CONVERTERS.items():
            try:
                self._nodeset[key] = conv(config, CFG_SECTION_NODESET, key)
            except (NoSectionError, NoOptionError):
                pass

        # Engine
        for key, conv in self._ENGINE_CONVERTERS.items():
            try:
                self._engine[key] = conv(config, CFG_SECTION_ENGINE, key)
            except (NoSectionError, NoOptionError):
                pass

    def __getattr__(self, name):
        """Defaults attribute lookup"""
        # 1.8 compat: port_qlimit moved into engine section
        if name == 'port_qlimit':
            if self._engine[name] == self._ENGINE[name]:
                return self._task_default[name]
        if name in self._engine:
            return self._engine[name]
        elif name in self._task_default:
            return self._task_default[name]
        elif name in self._task_info:
            return self._task_info[name]
        elif name in self._nodeset:
            return self._nodeset[name]
        raise AttributeError(name)

    def __setattr__(self, name, value):
        """Defaults attribute assignment"""
        if name in ('_task_default', '_task_info', '_task_info_pkeys_bl',
                    '_nodeset', '_engine'):
            object.__setattr__(self, name, value)
        elif name in self._engine:
            self._engine[name] = value
        elif name in self._task_default:
            self._task_default[name] = value
        elif name in self._task_info:
            self._task_info[name] = value
        elif name in self._nodeset:
            self._nodeset[name] = value
        else:
            raise AttributeError(name)

#
# Globally accessible Defaults object
#
DEFAULTS = Defaults(config_paths('defaults.conf'))
