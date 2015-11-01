#!/usr/bin/env python
#
# Copyright CEA/DAM/DIF (2010-2015)
#  Contributor: Stephane THIELL <sthiell@stanford.edu>
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
Common ClusterShell CLI OptionParser

With few exceptions, ClusterShell command-lines share most option
arguments. This module provides a common OptionParser class.
"""

from copy import copy
import optparse

from ClusterShell import __version__
from ClusterShell.Engine.Factory import PreferredEngine
from ClusterShell.CLI.Display import THREE_CHOICES


def check_autostep(option, opt, value):
    """type-checker function for autostep"""
    try:
        if '%' in value:
            return float(value[:-1]) / 100.0
        return int(value)
    except ValueError:
        if value == 'auto':
            return value
        error_fmt = "option %s: invalid value: %r, should be node count, " \
                    "node percentage or 'auto'"
        raise optparse.OptionValueError(error_fmt % (opt, value))

def check_safestring(option, opt, value):
    """type-checker function for safestring"""
    try:
        safestr = str(value)
        # check if the string is not empty and not an option
        if not safestr or safestr.startswith('-'):
            raise ValueError()
        return safestr
    except ValueError:
        raise optparse.OptionValueError(
            "option %s: invalid value: %r" % (opt, value))


class Option(optparse.Option):
    """This Option subclass adds a new safestring type."""
    TYPES = optparse.Option.TYPES + ("autostep", "safestring",)
    TYPE_CHECKER = copy(optparse.Option.TYPE_CHECKER)
    TYPE_CHECKER["autostep"] = check_autostep
    TYPE_CHECKER["safestring"] = check_safestring

class OptionParser(optparse.OptionParser):
    """Derived OptionParser for all CLIs"""

    def __init__(self, usage, **kwargs):
        """Initialize ClusterShell CLI OptionParser"""
        optparse.OptionParser.__init__(self, usage,
                                       version="%%prog %s" % __version__,
                                       option_class=Option,
                                       **kwargs)

        # Set parsing to stop on the first non-option
        self.disable_interspersed_args()

        # Always install groupsource support
        self.add_option("-s", "--groupsource", action="store",
                        type="safestring", dest="groupsource",
                        help="optional groups.conf(5) group source to use")

    def install_config_options(self, filename=''):
        """Install config options override"""
        self.add_option("-O", "--option", action="append", metavar="KEY=VALUE",
                        dest="option", default=[],
                        help="override any key=value %s options" % filename)

    def install_nodes_options(self):
        """Install nodes selection options"""
        optgrp = optparse.OptionGroup(self, "Selecting target nodes")
        optgrp.add_option("-w", action="append", type="safestring",
                          dest="nodes", help="nodes where to run the command")
        optgrp.add_option("-x", action="append", type="safestring",
                          dest="exclude", metavar="NODES",
                          help="exclude nodes from the node list")
        optgrp.add_option("-a", "--all", action="store_true", dest="nodes_all",
                          help="run command on all nodes")
        optgrp.add_option("-g", "--group", action="append", type="safestring",
                          dest="group", help="run command on a group of nodes")
        optgrp.add_option("-X", action="append", dest="exgroup",
                          metavar="GROUP", type="safestring",
                          help="exclude nodes from this group")
        optgrp.add_option("-E", "--engine", action="store", dest="engine",
                          choices=["auto"] + PreferredEngine.engines.keys(),
                          default="auto", help=optparse.SUPPRESS_HELP)
        optgrp.add_option("--hostfile", "--machinefile", action="append",
                          dest="hostfile", default=[], metavar='FILE',
                          help="path to file containing a list of target hosts")
        optgrp.add_option("--topology", action="store", dest="topofile",
                          default=None, metavar='FILE',
                          help="topology configuration file to use for tree "
                               "mode")
        self.add_option_group(optgrp)

    def install_display_options(self,
            debug_option=True,
            verbose_options=False,
            separator_option=False,
            dshbak_compat=False,
            msgtree_mode=False):
        """Install options needed by Display class"""
        optgrp = optparse.OptionGroup(self, "Output behaviour")
        if verbose_options:
            optgrp.add_option("-q", "--quiet", action="store_true",
                dest="quiet", help="be quiet, print essential output only")
            optgrp.add_option("-v", "--verbose", action="store_true",
                dest="verbose", help="be verbose, print informative messages")
        if debug_option:
            optgrp.add_option("-d", "--debug", action="store_true",
                dest="debug",
                help="output more messages for debugging purpose")
        optgrp.add_option("-G", "--groupbase", action="store_true",
            dest="groupbase", default=False,
            help="do not display group source prefix")
        optgrp.add_option("-L", action="store_true", dest="line_mode",
            help="disable header block and order output by nodes")
        optgrp.add_option("-N", action="store_false", dest="label",
            default=True, help="disable labeling of command line")
        if dshbak_compat:
            optgrp.add_option("-b", "-c", "--dshbak", action="store_true",
                dest="gather", help="gather nodes with same output")
        else:
            optgrp.add_option("-P", "--progress", action="store_true",
                dest="progress", help="show progress during command execution")
            optgrp.add_option("-b", "--dshbak", action="store_true",
                dest="gather", help="gather nodes with same output")
        optgrp.add_option("-B", action="store_true", dest="gatherall",
            default=False, help="like -b but including standard error")
        optgrp.add_option("-r", "--regroup", action="store_true",
                          dest="regroup", default=False,
                          help="fold nodeset using node groups")

        if separator_option:
            optgrp.add_option("-S", "--separator", action="store",
                              dest="separator", default=':',
                              help="node / line content separator string "
                                   "(default: ':')")
        else:
            optgrp.add_option("-S", action="store_true", dest="maxrc",
                              help="return the largest of command return codes")

        if msgtree_mode:
            # clubak specific
            optgrp.add_option("-F", "--fast", action="store_true",
                              dest="fast_mode",
                              help="faster but memory hungry mode")
            optgrp.add_option("-T", "--tree", action="store_true",
                              dest="trace_mode",
                              help="message tree trace mode")
            optgrp.add_option("--interpret-keys", action="store",
                              dest="interpret_keys", choices=THREE_CHOICES,
                              default=THREE_CHOICES[-1], help="whether to "
                              "interpret keys (never, always or auto)")

        optgrp.add_option("--color", action="store", dest="whencolor",
                          choices=THREE_CHOICES, help="whether to use ANSI "
                          "colors (never, always or auto)")
        optgrp.add_option("--diff", action="store_true", dest="diff",
                          help="show diff between gathered outputs")
        self.add_option_group(optgrp)

    def _copy_callback(self, option, opt_str, value, parser):
        """special callback method for copy and rcopy toggles"""
        # enable interspersed args again
        self.enable_interspersed_args()
        # set True to dest option attribute
        setattr(parser.values, option.dest, True)

    def install_filecopy_options(self):
        """Install file copying specific options"""
        optgrp = optparse.OptionGroup(self, "File copying")
        optgrp.add_option("-c", "--copy", action="callback", dest="copy",
                          callback=self._copy_callback,
                          help="copy local file or directory to remote nodes")
        optgrp.add_option("--rcopy", action="callback", dest="rcopy",
                          callback=self._copy_callback,
                          help="copy file or directory from remote nodes")
        optgrp.add_option("--dest", action="store", dest="dest_path",
                          help="destination file or directory on the nodes")
        optgrp.add_option("-p", action="store_true", dest="preserve_flag",
                          help="preserve modification times and modes")
        self.add_option_group(optgrp)


    def install_connector_options(self):
        """Install engine/connector (ssh, ...) options"""
        optgrp = optparse.OptionGroup(self, "Connection options")
        optgrp.add_option("-f", "--fanout", action="store", dest="fanout",
                          help="use a specified fanout", type="int")
        #help="queueing delay for traffic grooming"
        optgrp.add_option("--grooming", action="store", dest="grooming_delay",
                          help=optparse.SUPPRESS_HELP, type="float")
        optgrp.add_option("-l", "--user", action="store", type="safestring",
                          dest="user", help="execute remote command as user")
        optgrp.add_option("-o", "--options", action="store", dest="options",
                          help="can be used to give ssh options")
        optgrp.add_option("-t", "--connect_timeout", action="store",
                          dest="connect_timeout",
                          help="limit time to connect to a node", type="float")
        optgrp.add_option("-u", "--command_timeout", action="store",
                          dest="command_timeout",
                          help="limit time for command to run on the node",
                          type="float")
        optgrp.add_option("-R", "--worker", action="store", dest="worker",
                          help="worker name to use for command execution "
                               "('exec', 'rsh', 'ssh', etc. default is 'ssh')")
        optgrp.add_option("--remote", action="store", dest="remote",
                          choices=('yes', 'no'),
                          help="whether to enable remote execution: in tree "
                               "mode, 'yes' forces connections to the leaf "
                               "nodes for execution, 'no' establishes "
                               "connections up to the leaf parent nodes for "
                               "execution (default is 'yes')")
        self.add_option_group(optgrp)

    def install_nodeset_commands(self):
        """Install nodeset commands"""
        optgrp = optparse.OptionGroup(self, "Commands")
        optgrp.add_option("-c", "--count", action="store_true", dest="count",
                          default=False,
                          help="show number of nodes in nodeset(s)")
        optgrp.add_option("-e", "--expand", action="store_true", dest="expand",
                          default=False,
                          help="expand nodeset(s) to separate nodes")
        optgrp.add_option("-f", "--fold", action="store_true", dest="fold",
                          default=False, help="fold nodeset(s) (or separate "
                                              "nodes) into one nodeset")
        optgrp.add_option("-l", "--list", action="count", dest="list",
                          default=False, help="list node groups from one "
                                              "source (see -s GROUPSOURCE)")
        optgrp.add_option("-L", "--list-all", action="count", dest="listall",
                          default=False,
                          help="list node groups from all group sources")
        optgrp.add_option("-r", "--regroup", action="store_true",
                          dest="regroup", default=False,
                          help="fold nodes using node groups (see -s "
                               "GROUPSOURCE)")
        optgrp.add_option("--list-sources", "--groupsources",
                          action="store_true", dest="groupsources",
                          default=False,
                          help="list all active group sources (see "
                               "groups.conf(5))")
        self.add_option_group(optgrp)

    def install_nodeset_operations(self):
        """Install nodeset operations"""
        optgrp = optparse.OptionGroup(self, "Operations")
        optgrp.add_option("-x", "--exclude", action="append", dest="sub_nodes",
                          default=[], type="string",
                          help="exclude specified nodeset")
        optgrp.add_option("-i", "--intersection", action="append",
                          dest="and_nodes", default=[], type="string",
                          help="calculate nodesets intersection")
        optgrp.add_option("-X", "--xor", action="append", dest="xor_nodes",
                          default=[], type="string",
                          help="calculate symmetric difference between "
                               "nodesets")
        self.add_option_group(optgrp)

    def install_nodeset_options(self):
        """Install nodeset options"""
        optgrp = optparse.OptionGroup(self, "Options")
        optgrp.add_option("-a", "--all", action="store_true", dest="all",
                          help="call external node groups support to "
                               "display all nodes")
        optgrp.add_option("--autostep", action="store", dest="autostep",
                          help="enable a-b/step style syntax when folding, "
                               "value is min node count threshold (eg. '4', "
                               "'50%' or 'auto')",
                          type="autostep")
        optgrp.add_option("-d", "--debug", action="store_true", dest="debug",
                          help="output more messages for debugging purpose")
        optgrp.add_option("-q", "--quiet", action="store_true", dest="quiet",
                          help="be quiet, print essential output only")
        optgrp.add_option("-R", "--rangeset", action="store_true",
                          dest="rangeset", help="switch to RangeSet instead "
                          "of NodeSet. Useful when working on numerical "
                          "cluster ranges, eg. 1,5,18-31")
        optgrp.add_option("-G", "--groupbase", action="store_true",
                          dest="groupbase", help="hide group source prefix "
                          "(always \"@groupname\")")
        optgrp.add_option("-S", "--separator", action="store", dest="separator",
                          default=' ', help="separator string to use when "
                                            "expanding nodesets (default: ' ')")
        optgrp.add_option("-O", "--output-format", action="store",
                          dest="output_format", metavar='FORMAT', default='%s',
                          help="output format (default: '%s')")
        optgrp.add_option("-I", "--slice", action="store",
                          dest="slice_rangeset",
                          help="return sliced off result", type="string")
        optgrp.add_option("--split", action="store", dest="maxsplit",
                          help="split result into a number of subsets",
                          type="int")
        optgrp.add_option("--contiguous", action="store_true",
                          dest="contiguous", help="split result into "
                                                  "contiguous subsets")
        optgrp.add_option("--axis", action="store", dest="axis",
                          metavar="RANGESET", help="fold along these axis only "
                                                   "(axis 1..n for nD nodeset)")
        self.add_option_group(optgrp)
