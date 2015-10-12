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

"""

from ConfigParser import ConfigParser, NoOptionError, NoSectionError
import os

from ClusterShell.Worker.Exec import ExecWorker
from ClusterShell.Worker.Ssh import WorkerSsh


__all__ = ['Defaults', 'DEFAULTS']

#
# defaults.conf sections
#
CFG_SECTION_TASK_DEFAULT = 'task.default'
CFG_SECTION_TASK_INFO = 'task.info'


def _task_print_debug(task, line):
    """Default task debug printing function."""
    print line


class Defaults(object):
    """Class used to manipulate ClusterShell defaults."""

    #
    # Default values for task "default" sync dict
    #
    TASK_DEFAULT = {"stderr"           : False,
                    "stdout_msgtree"   : True,
                    "stderr_msgtree"   : True,
                    "engine"           : 'auto',
                    "port_qlimit"      : 100,
                    "auto_tree"        : True,
                    "topology_file"    : '/etc/clustershell/topology.conf',
                    "local_worker"     : ExecWorker,
                    "distant_worker"   : WorkerSsh}

    #
    # Datatype converters for task_default
    #
    # FIXME: could implement ConfigParser converters for local_worker and
    #        distant_worker in Python 3
    #
    _TASK_DEFAULT_CONVERTERS = {"stderr"           : ConfigParser.getboolean,
                                "stdout_msgtree"   : ConfigParser.getboolean,
                                "stderr_msgtree"   : ConfigParser.getboolean,
                                "engine"           : ConfigParser.get,
                                "port_qlimit"      : ConfigParser.getint,
                                "auto_tree"        : ConfigParser.getboolean,
                                "topology_file"    : ConfigParser.get}

    #
    # Default values for task "info" async dict
    #
    TASK_INFO = {"debug"            : False,
                 "print_debug"      : _task_print_debug,
                 "fanout"           : 64,
                 "grooming_delay"   : 0.25,
                 "connect_timeout"  : 10,
                 "command_timeout"  : 0}

    #
    # Datatype converters for task_info
    #
    _TASK_INFO_CONVERTERS = {"debug"            : ConfigParser.getboolean,
                             "fanout"           : ConfigParser.getint,
                             "grooming_delay"   : ConfigParser.getfloat,
                             "connect_timeout"  : ConfigParser.getfloat,
                             "command_timeout"  : ConfigParser.getfloat}

    #
    # List of info keys whose values can safely be propagated in tree mode
    #
    TASK_INFO_PKEYS = ['debug',
                       'fanout',
                       'grooming_delay',
                       'connect_timeout',
                       'command_timeout']

    def __init__(self, filenames):
        """Initialize Defaults from config filenames"""

        self.task_default = self.TASK_DEFAULT.copy()
        self.task_info = self.TASK_INFO.copy()
        self.task_info_pkeys = list(self.TASK_INFO_PKEYS)

        config = ConfigParser()
        parsed = config.read(filenames)

        if parsed:
            self._parse_config(config)

    def _parse_config(self, config):
        """parse config"""

        # task_default overrides
        for key, conv in self._TASK_DEFAULT_CONVERTERS.items():
            try:
                self.task_default[key] = conv(config, CFG_SECTION_TASK_DEFAULT,
                                              key)
            except (NoSectionError, NoOptionError):
                pass

        # task_info overrides
        for key, conv in self._TASK_INFO_CONVERTERS.items():
            try:
                self.task_info[key] = conv(config, CFG_SECTION_TASK_INFO, key)
            except (NoSectionError, NoOptionError):
                pass


DEFAULTS_CONFIGS = [
    # system-wide config file
    '/etc/clustershell/defaults.conf',
    # default pip --user config file
    os.path.expanduser('~/.local/etc/clustershell/defaults.conf'),
    # per-user groups.conf config top override
    os.path.join(os.environ.get('XDG_CONFIG_HOME',
                                os.path.expanduser('~/.config')),
                 'clustershell', 'defaults.conf')]

#
# Globally accessible Defaults object
#
DEFAULTS = Defaults(DEFAULTS_CONFIGS)
