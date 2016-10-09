#
# Copyright (C) 2010-2016 CEA/DAM
# Copyright (C) 2010-2016 Aurelien Degremont <aurelien.degremont@cea.fr>
# Copyright (C) 2015-2016 Stephane Thiell <sthiell@stanford.edu>
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
Cluster nodes utility module

The NodeUtils module is a ClusterShell helper module that provides
supplementary services to manage nodes in a cluster. It is primarily
designed to enhance the NodeSet module providing some binding support
to external node groups sources in separate namespaces (example of
group sources are: files, jobs scheduler, custom scripts, etc.).
"""

import glob
import logging
import os
import shlex
import time

from ConfigParser import ConfigParser, NoOptionError, NoSectionError
from string import Template
from subprocess import Popen, PIPE


class GroupSourceError(Exception):
    """Base GroupSource error exception"""
    def __init__(self, message, group_source):
        Exception.__init__(self, message)
        self.group_source = group_source

class GroupSourceNoUpcall(GroupSourceError):
    """Raised when upcall or method is not available"""

class GroupSourceQueryFailed(GroupSourceError):
    """Raised when a query failed (eg. no group found)"""

class GroupResolverError(Exception):
    """Base GroupResolver error"""

class GroupResolverSourceError(GroupResolverError):
    """Raised when upcall is not available"""

class GroupResolverIllegalCharError(GroupResolverError):
    """Raised when an illegal group character is encountered"""

class GroupResolverConfigError(GroupResolverError):
    """Raised when a configuration error is encountered"""


_DEFAULT_CACHE_TIME = 3600


class GroupSource(object):
    """ClusterShell Group Source class.

    A Group Source object defines resolv_map, resolv_list, resolv_all and
    optional resolv_reverse methods for node group resolution. It is
    constituting a group resolution namespace.
    """

    def __init__(self, name, groups=None, allgroups=None):
        """Initialize GroupSource

        :param name: group source name
        :param groups: group to nodes dict
        :param allgroups: optional _all groups_ result (string)
        """
        self.name = name
        self.groups = groups or {} # we avoid the use of {} as default argument
        self.allgroups = allgroups
        self.has_reverse = False

    def resolv_map(self, group):
        """Get nodes from group `group`"""
        return self.groups.get(group, '')

    def resolv_list(self):
        """Return a list of all group names for this group source"""
        return self.groups.keys()

    def resolv_all(self):
        """Return the content of all groups as defined by this GroupSource"""
        if self.allgroups is None:
            raise GroupSourceNoUpcall("All groups info not available", self)
        return self.allgroups

    def resolv_reverse(self, node):
        """
        Return the group name matching the provided node.
        """
        raise GroupSourceNoUpcall("Not implemented", self)


class FileGroupSource(GroupSource):
    """File-based Group Source using loader for file format and cache expiry."""

    def __init__(self, name, loader):
        """
        Initialize FileGroupSource object.

        :param name: group source name (eg. key name of yaml root dict)
        :param loader: associated content loader (eg. YAMLGroupLoader object)
        """
        # do not call super.__init__ to allow the use of r/o properties
        self.name = name
        self.loader = loader
        self.has_reverse = False

    @property
    def groups(self):
        """groups property (dict)"""
        return self.loader.groups(self.name)

    @property
    def allgroups(self):
        """allgroups property (string)"""
        # FileGroupSource uses the 'all' group to implement resolv_all
        return self.groups.get('all')


class UpcallGroupSource(GroupSource):
    """
    GroupSource class managing external calls for nodegroup support.

    Upcall results are cached for a customizable amount of time. This is
    controlled by `cache_time` attribute. Default is 3600 seconds.
    """

    def __init__(self, name, map_upcall, all_upcall=None,
                 list_upcall=None, reverse_upcall=None, cfgdir=None,
                 cache_time=None):
        GroupSource.__init__(self, name)
        self.verbosity = 0 # deprecated
        self.cfgdir = cfgdir
        self.logger = logging.getLogger(__name__)

        # Supported external upcalls
        self.upcalls = {}
        self.upcalls['map'] = map_upcall
        if all_upcall:
            self.upcalls['all'] = all_upcall
        if list_upcall:
            self.upcalls['list'] = list_upcall
        if reverse_upcall:
            self.upcalls['reverse'] = reverse_upcall
            self.has_reverse = True

        # Cache upcall data
        if cache_time is None:
            self.cache_time = _DEFAULT_CACHE_TIME
        else:
            self.cache_time = cache_time
        self._cache = {}
        self.clear_cache()

    def clear_cache(self):
        """
        Remove all previously cached upcall results whatever their lifetime is.
        """
        self._cache = {
            'map': {},
            'reverse': {}
        }

    def _upcall_read(self, cmdtpl, args=dict()):
        """
        Invoke the specified upcall command, raise an Exception if
        something goes wrong and return the command output otherwise.
        """
        cmdline = Template(self.upcalls[cmdtpl]).safe_substitute(args)
        self.logger.debug("EXEC '%s'", cmdline)
        proc = Popen(cmdline, stdout=PIPE, shell=True, cwd=self.cfgdir)
        output = proc.communicate()[0].strip()
        self.logger.debug("READ '%s'", output)
        if proc.returncode != 0:
            self.logger.debug("ERROR '%s' returned %d", cmdline,
                              proc.returncode)
            raise GroupSourceQueryFailed(cmdline, self)
        return output

    def _upcall_cache(self, upcall, cache, key, **args):
        """
        Look for `key' in provided `cache'. If not found, call the
        corresponding `upcall'.

        If `key' is missing, it is added to provided `cache'. Each entry in a
        cache is kept only for a limited time equal to self.cache_time .
        """
        if not self.upcalls.get(upcall):
            raise GroupSourceNoUpcall(upcall, self)

        # Purge expired data from cache
        if key in cache and cache[key][1] < time.time():
            self.logger.debug("PURGE EXPIRED (%d)'%s'", cache[key][1], key)
            del cache[key]

        # Fetch the data if unknown of just purged
        if key not in cache:
            cache_expiry = time.time() + self.cache_time
            # $CFGDIR and $SOURCE always replaced
            args['CFGDIR'] = self.cfgdir
            args['SOURCE'] = self.name
            cache[key] = (self._upcall_read(upcall, args), cache_expiry)

        return cache[key][0]

    def resolv_map(self, group):
        """
        Get nodes from group 'group', using the cached value if
        available.
        """
        return self._upcall_cache('map', self._cache['map'], group, GROUP=group)

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


class YAMLGroupLoader(object):
    """
    YAML group file loader/reloader.

    Load or reload a YAML multi group sources file:

    - create GroupSource objects
    - gather groups dict content on load
    - reload the file once cache_time has expired
    """

    def __init__(self, filename, cache_time=None):
        """
        Initialize YAMLGroupLoader and load file.

        :param filename: YAML file path
        :param cache_time: cache time (seconds)
        """
        if cache_time is None:
            self.cache_time = _DEFAULT_CACHE_TIME
        else:
            self.cache_time = cache_time
        self.cache_expiry = 0
        self.filename = filename
        self.sources = {}
        self._groups = {}
        # must be loaded after initialization so self.sources is set
        self._load()

    def _load(self):
        """Load or reload YAML group file to create GroupSource objects."""
        yamlfile = open(self.filename) # later use: with open(filepath) as yfile
        try:
            try:
                import yaml
                sources = yaml.load(yamlfile)
            except ImportError, exc:
                msg = "Disable autodir or install PyYAML!"
                raise GroupResolverConfigError("%s (%s)" % (str(exc), msg))
            except yaml.YAMLError, exc:
                raise GroupResolverConfigError("%s: %s" % (self.filename, exc))
        finally:
            yamlfile.close()

        # NOTE: change to isinstance(sources, collections.Mapping) with py2.6+
        if not isinstance(sources, dict):
            fmt = "%s: invalid content (base is not a dict)"
            raise GroupResolverConfigError(fmt % self.filename)

        first = not self.sources

        for srcname, groups in sources.items():

            if not isinstance(groups, dict):
                fmt = "%s: invalid content (group source '%s' is not a dict)"
                raise GroupResolverConfigError(fmt % (self.filename, srcname))

            if first:
                self._groups[srcname] = groups
                self.sources[srcname] = FileGroupSource(srcname, self)
            elif srcname in self.sources:
                # update groups of existing source
                self._groups[srcname] = groups
            # else: cannot add new source on reload - just ignore it

        # groups are loaded, set cache expiry
        self.cache_expiry = time.time() + self.cache_time

    def __iter__(self):
        """Iterate over GroupSource objects."""
        # safe as long as self.sources is set at init (once)
        return self.sources.itervalues()

    def groups(self, sourcename):
        """
        Groups dict accessor for sourcename.

        This method is called by associated FileGroupSource objects and simply
        returns dict content, after reloading file if cache_time has expired.
        """
        if self.cache_expiry < time.time():
            # reload whole file if cache time expired
            self._load()

        return self._groups[sourcename]


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
        """Set debugging verbosity value (DEPRECATED: use logging.DEBUG)."""
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
        if self._default_source is None:
            return None
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

        try:
            grpiter = raw.splitlines()
        except AttributeError:
            grpiter = raw

        for line in grpiter:
            for grpstr in line.strip().split():
                if self.illegal_chars.intersection(grpstr):
                    errmsg = ' '.join(self.illegal_chars.intersection(grpstr))
                    raise GroupResolverIllegalCharError(errmsg)
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
            return self._source(namespace).has_reverse
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
    SECTION_MAIN = 'Main'

    def __init__(self, filenames, illegal_chars=None):
        """
        Initialize GroupResolverConfig from filenames. Only the first
        accessible config filename is loaded.
        """
        GroupResolver.__init__(self, illegal_chars=illegal_chars)

        # support single or multiple config filenames
        self.config = ConfigParser()
        parsed = self.config.read(filenames)

        # check if at least one parsable config file has been found, otherwise
        # continue with an empty self._sources
        if parsed:
            # for proper $CFGDIR selection, take last parsed configfile only
            self._parse_config(os.path.dirname(parsed[-1]))

    def _parse_config(self, cfg_dirname):
        """parse config using relative dir cfg_dirname"""
        # parse Main.confdir
        try:
            if self.config.has_option(self.SECTION_MAIN, 'groupsdir'):
                opt_confdir = 'groupsdir'
            else:
                opt_confdir = 'confdir'

            # keep track of loaded confdirs
            loaded_confdirs = set()

            confdirstr = self.config.get(self.SECTION_MAIN, opt_confdir)
            for confdir in shlex.split(confdirstr):
                # substitute $CFGDIR, set to the highest priority clustershell
                # configuration directory that has been found
                confdir = Template(confdir).safe_substitute(CFGDIR=cfg_dirname)
                confdir = os.path.normpath(confdir)
                if confdir in loaded_confdirs:
                    continue # load each confdir only once
                loaded_confdirs.add(confdir)
                if not os.path.isdir(confdir):
                    if not os.path.exists(confdir):
                        continue
                    raise GroupResolverConfigError("Defined confdir %s is not"
                                                   " a directory" % confdir)
                # add sources declared in groups.conf.d file parts
                for groupsfn in sorted(glob.glob('%s/*.conf' % confdir)):
                    grpcfg = ConfigParser()
                    grpcfg.read(groupsfn) # ignore files that cannot be read
                    self._sources_from_cfg(grpcfg, confdir)
        except (NoSectionError, NoOptionError):
            pass

        # parse Main.autodir
        try:
            # keep track of loaded autodirs
            loaded_autodirs = set()

            autodirstr = self.config.get(self.SECTION_MAIN, 'autodir')
            for autodir in shlex.split(autodirstr):
                # substitute $CFGDIR, set to the highest priority clustershell
                # configuration directory that has been found
                autodir = Template(autodir).safe_substitute(CFGDIR=cfg_dirname)
                autodir = os.path.normpath(autodir)
                if autodir in loaded_autodirs:
                    continue # load each autodir only once
                loaded_autodirs.add(autodir)
                if not os.path.isdir(autodir):
                    if not os.path.exists(autodir):
                        continue
                    raise GroupResolverConfigError("Defined autodir %s is not"
                                                   " a directory" % autodir)
                # add auto sources declared in groups.d YAML files
                for autosfn in sorted(glob.glob('%s/*.yaml' % autodir)):
                    self._sources_from_yaml(autosfn)
        except (NoSectionError, NoOptionError):
            pass

        # add sources declared directly in groups.conf
        self._sources_from_cfg(self.config, cfg_dirname)

        # parse Main.default
        try:
            def_sourcename = self.config.get('Main', 'default')
            # warning: default_source_name is a property
            self.default_source_name = def_sourcename
        except (NoSectionError, NoOptionError):
            pass
        except GroupResolverSourceError:
            if def_sourcename: # allow empty Main.default
                fmt = 'Default group source not found: "%s"'
                raise GroupResolverConfigError(fmt % self.config.get('Main',
                                                                     'default'))
        # pick random default source if not provided by config
        if not self.default_source_name and self._sources:
            self.default_source_name = self._sources.keys()[0]

    def _sources_from_cfg(self, cfg, cfgdir):
        """
        Instantiate as many UpcallGroupSources needed from cfg object,
        cfgdir (CWD for callbacks) and cfg filename.
        """
        try:
            for section in cfg.sections():
                # Support grouped sections: section1,section2,section3
                for srcname in section.split(','):
                    if srcname != self.SECTION_MAIN:
                        # only map is a mandatory upcall
                        map_upcall = cfg.get(section, 'map', True)
                        all_upcall = list_upcall = reverse_upcall = ctime = None
                        if cfg.has_option(section, 'all'):
                            all_upcall = cfg.get(section, 'all', True)
                        if cfg.has_option(section, 'list'):
                            list_upcall = cfg.get(section, 'list', True)
                        if cfg.has_option(section, 'reverse'):
                            reverse_upcall = cfg.get(section, 'reverse', True)
                        if cfg.has_option(section, 'cache_time'):
                            ctime = float(cfg.get(section, 'cache_time', True))
                        # add new group source
                        self.add_source(UpcallGroupSource(srcname, map_upcall,
                                                          all_upcall,
                                                          list_upcall,
                                                          reverse_upcall,
                                                          cfgdir, ctime))
        except (NoSectionError, NoOptionError, ValueError), exc:
            raise GroupResolverConfigError(str(exc))

    def _sources_from_yaml(self, filepath):
        """Load source(s) from YAML file."""
        for source in YAMLGroupLoader(filepath):
            self.add_source(source)
