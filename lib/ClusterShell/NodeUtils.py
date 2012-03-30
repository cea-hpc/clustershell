# Copyright CEA/DAM/DIF (2010, 2012)
#  Contributors:
#   Stephane THIELL <stephane.thiell@cea.fr>
#   Aurelien DEGREMONT <aurelien.degremont@cea.fr>
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
Cluster nodes utility module

The NodeUtils module is a ClusterShell helper module that provides
supplementary services to manage nodes in a cluster. It is primarily
designed to enhance the NodeSet module providing some binding support
to external node groups sources in separate namespaces (example of
group sources are: files, jobs scheduler, custom scripts, etc.).
"""

import glob
import os
import sys

from ConfigParser import ConfigParser, NoOptionError, NoSectionError
from string import Template
from subprocess import Popen, PIPE


class GroupSourceException(Exception):
    """Base GroupSource exception"""
    def __init__(self, message, group_source):
        Exception.__init__(self, message)
        self.group_source = group_source

class GroupSourceNoUpcall(GroupSourceException):
    """Raised when upcall is not available"""

class GroupSourceQueryFailed(GroupSourceException):
    """Raised when a query failed (eg. no group found)"""

class GroupResolverError(Exception):
    """Base GroupResolver error"""

class GroupResolverSourceError(GroupResolverError):
    """Raised when upcall is not available"""

class GroupResolverConfigError(GroupResolverError):
    """Raised when a configuration error is encountered"""


class GroupSource(object):
    """
    GroupSource class managing external calls for nodegroup support.
    """
    def __init__(self, name, map_upcall, all_upcall=None,
                 list_upcall=None, reverse_upcall=None, cfgdir=None):
        self.name = name
        self.verbosity = 0
        self.cfgdir = cfgdir

        # Supported external upcalls
        self.map_upcall = map_upcall
        self.all_upcall = all_upcall
        self.list_upcall = list_upcall
        self.reverse_upcall = reverse_upcall

        # Cache upcall data
        self._cache_map = {}
        self._cache_list = []
        self._cache_all = None
        self._cache_reverse = {}

    def _verbose_print(self, msg):
        """Print msg depending on the verbosity level."""
        if self.verbosity > 0:
            print >> sys.stderr, "%s<%s> %s" % \
                (self.__class__.__name__, self.name, msg)

    def _upcall_read(self, cmdtpl, vars=dict()):
        """
        Invoke the specified upcall command, raise an Exception if
        something goes wrong and return the command output otherwise.
        """
        cmdline = Template(getattr(self, "%s_upcall" % \
                    cmdtpl)).safe_substitute(vars)
        self._verbose_print("EXEC '%s'" % cmdline)
        proc = Popen(cmdline, stdout=PIPE, shell=True, cwd=self.cfgdir)
        output = proc.communicate()[0].strip()
        self._verbose_print("READ '%s'" % output)
        if proc.returncode != 0:
            self._verbose_print("ERROR '%s' returned %d" % (cmdline, \
                proc.returncode))
            raise GroupSourceQueryFailed(cmdline, self)
        return output

    def resolv_map(self, group):
        """
        Get nodes from group 'group', using the cached value if
        available.
        """
        if group not in self._cache_map:
            self._cache_map[group] = self._upcall_read('map', dict(GROUP=group))

        return self._cache_map[group]

    def resolv_list(self):
        """
        Return a list of all group names for this group source, using
        the cached value if available.
        """
        if not self.list_upcall:
            raise GroupSourceNoUpcall("list", self)

        if not self._cache_list:
            self._cache_list = self._upcall_read('list')

        return self._cache_list
    
    def resolv_all(self):
        """
        Return the content of special group ALL, using the cached value
        if available.
        """
        if not self.all_upcall:
            raise GroupSourceNoUpcall("all", self)

        if not self._cache_all:
            self._cache_all = self._upcall_read('all')

        return self._cache_all

    def resolv_reverse(self, node):
        """
        Return the group name matching the provided node, using the
        cached value if available.
        """
        if not self.reverse_upcall:
            raise GroupSourceNoUpcall("reverse", self)

        if node not in self._cache_reverse:
            self._cache_reverse[node] = self._upcall_read('reverse', \
                                                          dict(NODE=node))
        return self._cache_reverse[node]


class GroupResolver(object):
    """
    Base class GroupResolver that aims to provide node/group resolution
    from multiple GroupSource's.
    """
    
    def __init__(self, default_source=None):
        """
        Initialize GroupResolver object.
        """
        self._sources = {}
        self._default_source = default_source
        if default_source:
            self._sources[default_source.name] = default_source
            
    def set_verbosity(self, value):
        """
        Set debugging verbosity value.
        """
        for source in self._sources.itervalues():
            source.verbosity = value

    def add_source(self, group_source):
        """
        Add a GroupSource to this resolver.
        """
        if group_source.name in self._sources:
            raise ValueError("GroupSource '%s': name collision" % \
                             group_source.name)
        self._sources[group_source.name] = group_source

    def sources(self):
        """
        Get the list of all resolver source names.
        """
        return self._sources.keys()

    def _list(self, source, what, *args):
        """Helper method that returns a list of result when the source
        is defined."""
        result = []
        assert source
        raw = getattr(source, 'resolv_%s' % what)(*args)
        for line in raw.splitlines():
            map(result.append, line.strip().split())
        return result

    def _source(self, namespace):
        """Helper method that returns the source by namespace name."""
        if not namespace:
            source = self._default_source
        else:
            source = self._sources.get(namespace)
        if not source:
            raise GroupResolverSourceError(namespace or "<default>")
        return source
        
    def group_nodes(self, group, namespace=None):
        """
        Find nodes for specified group name and optional namespace.
        """
        source = self._source(namespace)
        return self._list(source, 'map', group)

    def all_nodes(self, namespace=None):
        """
        Find all nodes. You may specify an optional namespace.
        """
        source = self._source(namespace)
        return self._list(source, 'all')

    def grouplist(self, namespace=None):
        """
        Get full group list. You may specify an optional
        namespace.
        """
        source = self._source(namespace)
        return self._list(source, 'list')

    def has_node_groups(self, namespace=None):
        """
        Return whether finding group list for a specified node is
        supported by the resolver (in optional namespace).
        """
        try:
            return bool(self._source(namespace).reverse_upcall)
        except GroupResolverSourceError:
            return False

    def node_groups(self, node, namespace=None):
        """
        Find group list for specified node and optional namespace.
        """
        source = self._source(namespace)
        return self._list(source, 'reverse', node)


class GroupResolverConfig(GroupResolver):
    """
    GroupResolver class that is able to automatically setup its
    GroupSource's from a configuration file. This is the default
    resolver for NodeSet.
    """

    def __init__(self, configfile):
        """
        """
        GroupResolver.__init__(self)

        self.default_sourcename = None

        self.config = ConfigParser()
        self.config.read(configfile)
        # Get config file sections
        groupscfgs = {}
        configfile_dirname = os.path.dirname(configfile)
        for section in self.config.sections():
            if section != 'Main':
                groupscfgs[section] = (self.config, configfile_dirname)
        try:
            self.groupsdir = self.config.get('Main', 'groupsdir')
            for groupsdir in self.groupsdir.split():
                # support relative-to-dirname(groups.conf) groupsdir
                groupsdir = os.path.normpath(os.path.join(configfile_dirname, \
                                                          groupsdir))
                if not os.path.isdir(groupsdir):
                    if not os.path.exists(groupsdir):
                        continue
                    raise GroupResolverConfigError("Defined groupsdir %s " \
                            "is not a directory" % groupsdir)
                for groupsfn in sorted(glob.glob('%s/*.conf' % groupsdir)):
                    grpcfg = ConfigParser()
                    grpcfg.read(groupsfn) # ignore files that cannot be read
                    for section in grpcfg.sections():
                        if section in groupscfgs:
                            raise GroupResolverConfigError("Group source " \
                                "\"%s\" re-defined in %s" % (section, groupsfn))
                        groupscfgs[section] = (grpcfg, groupsdir)
        except (NoSectionError, NoOptionError):
            pass

        try:
            self.default_sourcename = self.config.get('Main', 'default')
            if self.default_sourcename and self.default_sourcename \
                                            not in groupscfgs.keys():
                raise GroupResolverConfigError("Default group source not " \
                    "found: \"%s\"" % self.default_sourcename)
        except (NoSectionError, NoOptionError):
            pass

        if not groupscfgs:
            return

        # When not specified, select a random section.
        if not self.default_sourcename:
            self.default_sourcename = groupscfgs.keys()[0]

        try:
            for section, (cfg, cfgdir) in groupscfgs.iteritems():
                map_upcall = cfg.get(section, 'map', True)
                all_upcall = list_upcall = reverse_upcall = None
                if cfg.has_option(section, 'all'):
                    all_upcall = cfg.get(section, 'all', True)
                if cfg.has_option(section, 'list'):
                    list_upcall = cfg.get(section, 'list', True)
                if cfg.has_option(section, 'reverse'):
                    reverse_upcall = cfg.get(section, 'reverse', True)

                self.add_source(GroupSource(section, map_upcall, all_upcall, \
                                    list_upcall, reverse_upcall, cfgdir))
        except (NoSectionError, NoOptionError), exc:
            raise GroupResolverConfigError(str(exc))

    def _source(self, namespace):
        return GroupResolver._source(self, namespace or self.default_sourcename)

    def sources(self):
        """
        Get the list of all resolver source names (default source is always
        first).
        """
        srcs = GroupResolver.sources(self)
        if srcs:
            srcs.remove(self.default_sourcename)
            srcs.insert(0, self.default_sourcename)
        return srcs


