#
# Copyright CEA/DAM/DIF (2008-2015)
#  Contributor: Stephane THIELL <stephane.thiell@cea.fr>
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
ClusterShell Ssh/Scp support

This module implements OpenSSH engine client and task's worker.
"""

import os
# Older versions of shlex can not handle unicode correctly.
# Consider using ushlex instead.
import shlex

from ClusterShell.Worker.Exec import ExecClient, CopyClient, ExecWorker


class SshClient(ExecClient):
    """
    Ssh EngineClient.
    """

    def _build_cmd(self):
        """
        Build the shell command line to start the ssh commmand.
        Return an array of command and arguments.
        """

        task = self.worker.task
        path = task.info("ssh_path") or "ssh"
        user = task.info("ssh_user")
        options = task.info("ssh_options")

        # Build ssh command
        cmd_l = [os.path.expanduser(pathc) for pathc in shlex.split(path)]

        # Add custom ssh options first as the first obtained value is
        # used. Thus all options are overridable by custom options.
        if options:
            # use expanduser() for options like '-i ~/.ssh/my_id_rsa'
            cmd_l += [os.path.expanduser(opt) for opt in shlex.split(options)]

        # Hardwired options (overridable by ssh_options)
        cmd_l += [  "-a", "-x"  ]

        if user:
            cmd_l.append("-l")
            cmd_l.append(user)

        connect_timeout = task.info("connect_timeout", 0)
        if connect_timeout > 0:
            cmd_l.append("-oConnectTimeout=%d" % connect_timeout)

        # Disable passphrase/password querying
        # When used together with sshpass this must be overwritten
        # by a custom option to "-oBatchMode=no".
        cmd_l.append("-oBatchMode=yes")

        cmd_l.append("%s" % self.key)
        cmd_l.append("%s" % self.command)

        return (cmd_l, None)

class ScpClient(CopyClient):
    """
    Scp EngineClient.
    """

    def _build_cmd(self):
        """
        Build the shell command line to start the scp commmand.
        Return an array of command and arguments.
        """

        task = self.worker.task
        path = task.info("scp_path") or "scp"
        user = task.info("scp_user") or task.info("ssh_user")

        # If defined exclusively use scp_options. If no scp_options
        # given use ssh_options instead.
        options = task.info("scp_options") or task.info("ssh_options")

        # Build scp command
        cmd_l = [os.path.expanduser(pathc) for pathc in shlex.split(path)]

        # Add custom ssh options first as the first obtained value is
        # used. Thus all options are overridable by custom options.
        if options:
            # use expanduser() for options like '-i ~/.ssh/my_id_rsa'
            cmd_l += [os.path.expanduser(opt) for opt in shlex.split(options)]

        # Hardwired options (overridable by ssh_options)
        if self.isdir:
            cmd_l.append("-r")

        if self.preserve:
            cmd_l.append("-p")

        connect_timeout = task.info("connect_timeout", 0)
        if connect_timeout > 0:
            cmd_l.append("-oConnectTimeout=%d" % connect_timeout)

        # Disable passphrase/password querying
        # When used together with sshpass this must be overwritten
        # by a custom option to "-oBatchMode=no".
        cmd_l.append("-oBatchMode=yes")


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

class WorkerSsh(ExecWorker):
    """
    ClusterShell ssh-based worker Class.

    Remote Shell (ssh) usage example:
       >>> worker = WorkerSsh(nodeset, handler=MyEventHandler(),
       ...                    timeout=30, command="/bin/hostname")
       >>> task.schedule(worker)      # schedule worker for execution
       >>> task.resume()              # run

    Remote Copy (scp) usage example:
       >>> worker = WorkerSsh(nodeset, handler=MyEventHandler(),
       ...                    timeout=30, source="/etc/my.conf",
       ...                    dest="/etc/my.conf")
       >>> task.schedule(worker)      # schedule worker for execution
       >>> task.resume()              # run
    """

    SHELL_CLASS = SshClient
    COPY_CLASS = ScpClient

WORKER_CLASS=WorkerSsh
