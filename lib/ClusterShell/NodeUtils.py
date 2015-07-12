# Copyright CEA/DAM/DIF (2010, 2012, 2013, 2014)
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
import time

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

class GroupResolverIllegalCharError(GroupResolverError):
    """Raised when an illegal group character is encountered"""

class GroupResolverConfigError(GroupResolverError):
    """Raised when a configuration error is encountered"""


_DEFAULT_CACHE_DELAY = 3600

class GroupSource(object):
    """
    GroupSource class managing external calls for nodegroup support.

    Upcall results are cached for a customizable amount of time. This is
    controled by `cache_delay' attribute. Default is 3600 seconds.
    """

    def __init__(self, name, map_upcall, all_upcall=None,
                 list_upcall=None, reverse_upcall=None, cfgdir=None,
                 cache_delay=None):
        self.name = name
        self.verbosity = 0
        self.cfgdir = cfgdir

        # Supported external upcalls
        self.upcalls = {}
        self.upcalls['map'] = map_upcall
        if all_upcall:
            self.upcalls['all'] = all_upcall
        if list_upcall:
            self.upcalls['list'] = list_upcall
        if reverse_upcall:
            self.upcalls['reverse'] = reverse_upcall

        # Cache upcall data
        self.cache_delay = cache_delay or _DEFAULT_CACHE_DELAY
        self._cache = {}
        self.clear_cache()

    def clear_cache(self):
        """
        Remove all previously cached upcall results whatever their lifetime is.
        """
        self._cache = {
                'map':     {},
                'reverse': {}
            }

    def _verbose_print(self, msg):
        """Print msg depending on the verbosity level."""
        if self.verbosity > 0:
            print >> sys.stderr, "%s<%s> %s" % \
                (self.__class__.__name__, self.name, msg)

    def _upcall_read(self, cmdtpl, args=dict()):
        """
        Invoke the specified upcall command, raise an Exception if
        something goes wrong and return the command output otherwise.
        """
        cmdline = Template(self.upcalls[cmdtpl]).safe_substitute(args)
        self._verbose_print("EXEC '%s'" % cmdline)
        proc = Popen(cmdline, stdout=PIPE, shell=True, cwd=self.cfgdir)
        output = proc.communicate()[0].strip()
        self._verbose_print("READ '%s'" % output)
        if proc.returncode != 0:
            self._verbose_print("ERROR '%s' returned %d" % (cmdline, \
                proc.returncode))
            raise GroupSourceQueryFailed(cmdline, self)
        return output

    def _upcall_cache(self, upcall, cache, key, **args):
        """
        Look for `key' in provided `cache'. If not found, call the
        corresponding `upcall'.

        If `key' is missing, it is added to provided `cache'. Each entry in a
        cache is kept only for a limited time equal to self.cache_delay .
        """
        if not self.upcalls.get(upcall):
            raise GroupSourceNoUpcall(upcall, self)

        # Purge expired data from cache
        if key in cache and cache[key][1] < time.time():
            self._verbose_print("PURGE EXPIRED (%d)'%s'" % (cache[key][1], key))
            del cache[key]

        # Fetch the data if unknown of just purged
        if key not in cache:
            timestamp = time.time() + self.cache_delay
            cache[key] = (self._upcall_read(upcall, args), timestamp)

        return cache[key][0]

    def resolv_map(self, group):
        """
        Get nodes from group 'group', using the cached value if
        available.
        """
        return self._upcall_cache('map', self._cache['map'], group,
                                  GROUP=group)

    def resolv_list(self):
        """
        Return a list of all group names for this group source, using
        the cached value if available.
        """
        return self._upcall_cache('list', self._cache, 'list')
    
    def resolv_all(self):
        """
        Return the content of special group ALL, using the cached value
        if available.
        """
        return self._upcall_cache('all', self._cache, 'all')

    def resolv_reverse(self, node):
        """
        Return the group name matching the provided node, using the
        cached value if available.
        """
        return self._upcall_cache('reverse', self._cache['reverse'], node,
                                  NODE=node)



class GroupResolver(object):
    """
    Base class GroupResolver that aims to provide node/group resolution
    from multiple GroupSources.

    A GroupResolver object might be initialized with a default
    GroupSource object, that is later used when group resolution is
    requested with no source information. As of version 1.7, a set of
    illegal group characters may also be provided for sanity check
    (raising GroupResolverIllegalCharError when found).
    """
    
    def __init__(self, default_source=None, illegal_chars=None):
        """Initialize GroupResolver object."""
        self._sources = {}
        self._default_source = default_source
        self.illegal_chars = illegal_chars or set()
        if default_source:
            self._sources[default_source.name] = default_source
            
    def set_verbosity(self, value):
        """Set debugging verbosity value. """
        for source in self._sources.itervalues():
            source.verbosity = value

    def add_source(self, group_source):
        """Add a GroupSource to this resolver."""
        if group_source.name in self._sources:
            raise ValueError("GroupSource '%s': name collision" % \
                             group_source.name)
        self._sources[group_source.name] = group_source

    def sources(self):
        """Get the list of all resolver source names. """
        srcs = list(self._sources.keys())
        if srcs and srcs[0] is not self._default_source:
            srcs.remove(self._default_source.name)
            srcs.insert(0, self._default_source.name)
        return srcs

    def _get_default_source_name(self):
        """Get default source name of resolver."""
        return self._default_source.name

    def _set_default_source_name(self, sourcename):
        """Set default source of resolver (by name)."""
        try:
            self._default_source = self._sources[sourcename]
        except KeyError:
            raise GroupResolverSourceError(sourcename)

    default_source_name = property(_get_default_source_name,
                                   _set_default_source_name)

    def _list_nodes(self, source, what, *args):
        """Helper method that returns a list of results (nodes) when
        the source is defined."""
        result = []
        assert source
        raw = getattr(source, 'resolv_%s' % what)(*args)
        for line in raw.splitlines():
            [result.append(x) for x in line.strip().split()]
        return result

    def _list_groups(self, source, what, *args):
        """Helper method that returns a list of results (groups) when
        the source is defined."""
        result = []
        assert source
        raw = getattr(source, 'resolv_%s' % what)(*args)
        for line in raw.splitlines():
            for grpstr in line.strip().split():
                if self.illegal_chars.intersection(grpstr):
                    raise GroupResolverIllegalCharError( \
                        ' '.join(self.illegal_chars.intersection(grpstr)))
                result.append(grpstr)
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
        return self._list_nodes(source, 'map', group)

    def all_nodes(self, namespace=None):
        """
        Find all nodes. You may specify an optional namespace.
        """
        source = self._source(namespace)
        return self._list_nodes(source, 'all')

    def grouplist(self, namespace=None):
        """
        Get full group list. You may specify an optional
        namespace.
        """
        source = self._source(namespace)
        return self._list_groups(source, 'list')

    def has_node_groups(self, namespace=None):
        """
        Return whether finding group list for a specified node is
        supported by the resolver (in optional namespace).
        """
        try:
            return 'reverse' in self._source(namespace).upcalls
        except GroupResolverSourceError:
            return False

    def node_groups(self, node, namespace=None):
        """
        Find group list for specified node and optional namespace.
        """
        source = self._source(namespace)
        return self._list_groups(source, 'reverse', node)


class GroupResolverConfig(GroupResolver):
    """
    GroupResolver class that is able to automatically setup its
    GroupSource's from a configuration file. This is the default
    resolver for NodeSet.
    """

    def __init__(self, configfile, illegal_chars=None):
        """
        """
        GroupResolver.__init__(self, illegal_chars=illegal_chars)

        default_sourcename = None

        self.config = ConfigParser()
        self.config.read(configfile)
        # Get config file sections
        groupscfgs = {}
        configfile_dirname = os.path.dirname(configfile)
        for section in self.config.sections():
            if section != 'Main':
                # Support grouped sections: section1,section2,section3
                for srcname in section.split(','):
                    groupscfgs[srcname] = (self.config,
                                           configfile_dirname,
                                           section) # keep full section name
        try:
            self.groupsdir = self.config.get('Main', 'groupsdir')
            for groupsdir in self.groupsdir.split():
                # support relative-to-dirname(groups.conf) groupsdir
                groupsdir = os.path.normpath(os.path.join(configfile_dirname,
                                                          groupsdir))
                if not os.path.isdir(groupsdir):
                    if not os.path.exists(groupsdir):
                        continue
                    raise GroupResolverConfigError("Defined groupsdir %s is not"
                                                   " a directory" % groupsdir)
                for groupsfn in sorted(glob.glob('%s/*.conf' % groupsdir)):
                    grpcfg = ConfigParser()
                    grpcfg.read(groupsfn) # ignore files that cannot be read
                    for section in grpcfg.sections():
                        # Support grouped sections also in groupsdir confs
                        for srcname in section.split(','):
                            if srcname in groupscfgs:
                                fmt = "Group source \"%s\" re-defined in %s"
                                raise GroupResolverConfigError(fmt % (srcname,
                                                                      groupsfn))
                            groupscfgs[srcname] = (grpcfg, groupsdir, section)
        except (NoSectionError, NoOptionError):
            pass

        try:
            default_sourcename = self.config.get('Main', 'default')
            if default_sourcename and default_sourcename \
                                            not in groupscfgs.keys():
                raise GroupResolverConfigError("Default group source not " \
                    "found: \"%s\"" % default_sourcename)
        except (NoSectionError, NoOptionError):
            pass

        if not groupscfgs:
            return

        # When default is not specified, select a random section.
        if not default_sourcename:
            default_sourcename = groupscfgs.keys()[0]

        try:
            for srcname, (cfg, cfgdir, section) in groupscfgs.iteritems():
                # only map is a mandatory upcall
                raw_cmd = cfg.get(section, 'map', True)
                # substitute $SOURCE in every command
                srcmap = { 'SOURCE': srcname }
                map_upcall = Template(raw_cmd).safe_substitute(srcmap)
                all_upcall = list_upcall = reverse_upcall = delay = None
                if cfg.has_option(section, 'all'):
                    raw_cmd = cfg.get(section, 'all', True)
                    all_upcall = Template(raw_cmd).safe_substitute(srcmap)
                if cfg.has_option(section, 'list'):
                    raw_cmd = cfg.get(section, 'list', True)
                    list_upcall = Template(raw_cmd).safe_substitute(srcmap)
                if cfg.has_option(section, 'reverse'):
                    raw_cmd = cfg.get(section, 'reverse', True)
                    reverse_upcall = Template(raw_cmd).safe_substitute(srcmap)
                if cfg.has_option(section, 'cache_delay'):
                    delay = float(cfg.get(section, 'cache_delay', True))
                # add new group source
                self.add_source(GroupSource(srcname, map_upcall, all_upcall,
                                            list_upcall, reverse_upcall,
                                            cfgdir, delay))
        except (NoSectionError, NoOptionError), exc:
            raise GroupResolverConfigError(str(exc))

        self.default_source_name = default_sourcename

