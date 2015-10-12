#
# Copyright 2015 Stephane Thiell <sthiell@stanford.edu>
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

"""
ClusterShell Defaults module.

Manage library defaults.
"""

# Imported early
# Should not import any other ClusterShell modules when loaded
from ConfigParser import ConfigParser, NoOptionError, NoSectionError
import os
import sys


#
# defaults.conf sections
#
CFG_SECTION_TASK_DEFAULT = 'task.default'
CFG_SECTION_TASK_INFO = 'task.info'

#
# Functions
#
def _task_print_debug(task, line):
    """Default task debug printing function."""
    print line

def _load_workerclass(workername):
    """
    Return the class pointer matching `workername`.

    The module is loaded if not done yet.
    """
    modname = "ClusterShell.Worker.%s" % workername.capitalize()

    # Import module if not yet loaded
    if modname.lower() not in [mod.lower() for mod in sys.modules]:
        __import__(modname)

    # Get the class pointer
    return sys.modules[modname].WORKER_CLASS

def _local_workerclass(defaults):
    """Return default local worker class."""
    return _load_workerclass(defaults.local_workername)

def _distant_workerclass(defaults):
    """Return default distant worker class."""
    return _load_workerclass(defaults.distant_workername)

def config_paths(config_name):
    """Return default path list for a ClusterShell config file name."""
    return [# system-wide config file
            '/etc/clustershell/%s' % config_name,
            # default pip --user config file
            os.path.expanduser('~/.local/etc/clustershell/%s' % config_name),
            # per-user config (top override)
            os.path.join(os.environ.get('XDG_CONFIG_HOME',
                                        os.path.expanduser('~/.config')),
                         'clustershell', config_name)]

#
# Classes
#
class Defaults(object):
    """
    Class used to manipulate ClusterShell defaults.

    The following attributes may be read at any time and also changed
    programmatically, for most of them **before** ClusterShell objects
    are initialized (like Task):

    * stderr (boolean; default is ``False``)
    * stdout_msgtree (boolean; default is ``True``)
    * stderr_msgtree (boolean; default is ``True``)
    * engine (string; default is ``'auto'``)
    * port_qlimit (integer; default is ``100``)
    * local_workername (string; default is ``'exec'``)
    * distant_workername (string; default is ``'ssh'``)
    * debug (boolean; default is ``False``)
    * print_debug (function; default is internal)
    * fanout (integer; default is ``64``)
    * grooming_delay (float; default is ``0.25``)
    * connect_timeout (float; default is ``10``)
    * command_timeout (float; default is ``0``)

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
                     "stdout_msgtree"     : True,
                     "stderr_msgtree"     : True,
                     "engine"             : 'auto',
                     "port_qlimit"        : 100,
                     "auto_tree"          : True,
                     "local_workername"   : 'exec',
                     "distant_workername" : 'ssh'}

    #
    # Datatype converters for task_default
    #
    _TASK_DEFAULT_CONVERTERS = {"stderr"             : ConfigParser.getboolean,
                                "stdout_msgtree"     : ConfigParser.getboolean,
                                "stderr_msgtree"     : ConfigParser.getboolean,
                                "engine"             : ConfigParser.get,
                                "port_qlimit"        : ConfigParser.getint,
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
    # List of info keys whose values can safely be propagated in tree mode
    #
    _TASK_INFO_PKEYS = ['debug',
                        'fanout',
                        'grooming_delay',
                        'connect_timeout',
                        'command_timeout']

    def __init__(self, filenames):
        """Initialize Defaults from config filenames"""

        self._task_default = self._TASK_DEFAULT.copy()
        self._task_info = self._TASK_INFO.copy()
        self._task_info_pkeys = list(self._TASK_INFO_PKEYS)

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

    def __getattr__(self, name):
        """Defaults attribute lookup"""
        if name in self._task_default:
            return self._task_default[name]
        elif name in self._task_info:
            return self._task_info[name]
        raise AttributeError(name)

    def __setattr__(self, name, value):
        """Defaults attribute assignment"""
        if name in ('_task_default', '_task_info', '_task_info_pkeys'):
            object.__setattr__(self, name, value)
        elif name in self._task_default:
            self._task_default[name] = value
        elif name in self._task_info:
            self._task_info[name] = value
        else:
            raise AttributeError(name)

#
# Globally accessible Defaults object
#
DEFAULTS = Defaults(config_paths('defaults.conf'))
