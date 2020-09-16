#
# Copyright (C) 2013-2015 CEA/DAM
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
ClusterShell RSH support

It could also handles rsh forks, like krsh or mrsh.
This is also the base class for rsh evolutions, like Ssh worker.
"""

import os
import shlex
import re

from ClusterShell.Worker.Exec import ExecClient, CopyClient, ExecWorker


class RshClient(ExecClient):
    """
    Rsh EngineClient.
    """

    def _build_cmd(self):
        """
        Build the shell command line to start the rsh commmand.
        Return an array of command and arguments.
        """
        # Does not support 'connect_timeout'
        task = self.worker.task
        path = task.info("rsh_path") or "rsh"
        user = task.info("rsh_user")
        options = task.info("rsh_options")
        maxrc = task.info("maxrc", False)

        cmd_l = [os.path.expanduser(pathc) for pathc in shlex.split(path)]

        if user:
            cmd_l.append("-l")
            cmd_l.append(user)

        # Add custom options
        if options:
            cmd_l += shlex.split(options)

        cmd_l.append("%s" % self.key)  # key is the node
        cmd_l.append("%s" % self.command)

        # Save the return code from the command if required
        if maxrc:
            cmd_l.append("; echo XXRETCODE: $?")

        return (cmd_l, None)

    def _parse_line(self, line, sname):

        # Read the return code from the command if required
        task = self.worker.task
        maxrc = task.info("maxrc", False)
        if maxrc:
            match = re.search("^XXRETCODE: (\d+)$", line.decode("utf-8"))
            if match:
                self.worker.current_rc = int(match.group(1))
            else:
                self.worker._on_node_msgline(self.key, line, sname)
        else:
            self.worker._on_node_msgline(self.key, line, sname)

    def _handle_read(self, sname):
        """Engine is telling us a read is available."""
        for msg in self._readlines(sname):
            self._parse_line(msg, sname)


class RcpClient(CopyClient):
    """
    Rcp EngineClient.
    """

    def _build_cmd(self):
        """
        Build the shell command line to start the rcp commmand.
        Return an array of command and arguments.
        """

        # Does not support 'connect_timeout'
        task = self.worker.task
        path = task.info("rcp_path") or "rcp"
        user = task.info("rsh_user")
        options = task.info("rcp_options") or task.info("rsh_options")

        cmd_l = [os.path.expanduser(pathc) for pathc in shlex.split(path)]

        if self.isdir:
            cmd_l.append("-r")

        if self.preserve:
            cmd_l.append("-p")

        # Add custom rcp options
        if options:
            cmd_l += shlex.split(options)

        if self.reverse:
            if user:
                cmd_l.append("%s@%s:%s" % (user, self.key, self.source))
            else:
                cmd_l.append("%s:%s" % (self.key, self.source))

            cmd_l.append(os.path.join(self.dest, "%s.%s" % \
                         (os.path.basename(self.source), self.key)))
        else:
            cmd_l.append(self.source)
            if user:
                cmd_l.append("%s@%s:%s" % (user, self.key, self.dest))
            else:
                cmd_l.append("%s:%s" % (self.key, self.dest))

        return (cmd_l, None)


class WorkerRsh(ExecWorker):
    """
    ClusterShell rsh-based worker Class.

    Remote Shell (rsh) usage example:
       >>> worker = WorkerRsh(nodeset, handler=MyEventHandler(),
       ...                    timeout=30, command="/bin/hostname")
       >>> task.schedule(worker)      # schedule worker for execution
       >>> task.resume()              # run

    Remote Copy (rcp) usage example:
       >>> worker = WorkerRsh(nodeset, handler=MyEventHandler(),
       ...                     source="/etc/my.conf",
       ...                     dest="/etc/my.conf.bak")
       >>> task.schedule(worker)      # schedule worker for execution
       >>> task.resume()              # run

    connect_timeout option is ignored by this worker.
    """

    def _on_node_close(self, node, rc):
        if rc is None or self.current_rc > rc:
            rc = self.current_rc
        ExecWorker._on_close(self, node, rc)

    SHELL_CLASS = RshClient
    COPY_CLASS = RcpClient

WORKER_CLASS=WorkerRsh
