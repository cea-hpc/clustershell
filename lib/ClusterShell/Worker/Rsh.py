#
# Copyright CEA/DAM/DIF (2013-2015)
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
ClusterShell RSH support

It could also handles rsh forks, like krsh or mrsh.
This is also the base class for rsh evolutions, like Ssh worker.
"""

import os
import shlex

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

        cmd_l = [os.path.expanduser(pathc) for pathc in shlex.split(path)]

        if user:
            cmd_l.append("-l")
            cmd_l.append(user)

        # Add custom options
        if options:
            cmd_l += shlex.split(options)

        cmd_l.append("%s" % self.key)  # key is the node
        cmd_l.append("%s" % self.command)

        return (cmd_l, None)


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
       ...                     dest="/etc/my.conf")
       >>> task.schedule(worker)      # schedule worker for execution
       >>> task.resume()              # run

    connect_timeout option is ignored by this worker.
    """

    SHELL_CLASS = RshClient
    COPY_CLASS = RcpClient

WORKER_CLASS=WorkerRsh
