#
# Copyright CEA/DAM/DIF (2007-2014)
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
WorkerPdsh

ClusterShell worker for executing commands with LLNL pdsh.
"""

import errno
import os
import shlex
import sys

from ClusterShell.NodeSet import NodeSet
from ClusterShell.Worker.EngineClient import EngineClientError
from ClusterShell.Worker.EngineClient import EngineClientNotSupportedError
from ClusterShell.Worker.Worker import WorkerError
from ClusterShell.Worker.Exec import ExecWorker, ExecClient, CopyClient


class PdshClient(ExecClient):
    """EngineClient which run 'pdsh'"""

    MODE = 'pdsh'

    def __init__(self, node, command, worker, stderr, timeout, autoclose=False,
                 rank=None):
        ExecClient.__init__(self, node, command, worker, stderr, timeout,
                            autoclose, rank)
        self._closed_nodes = NodeSet()

    def _build_cmd(self):
        """
        Build the shell command line to start the commmand.
        Return an array of command and arguments.
        """
        task = self.worker.task
        pdsh_env = {}

        # Build pdsh command
        path = task.info("pdsh_path") or "pdsh"
        cmd_l = [os.path.expanduser(pathc) for pathc in shlex.split(path)]
        cmd_l.append("-b")

        fanout = task.info("fanout", 0)
        if fanout > 0:
            cmd_l.append("-f %d" % fanout)

        # Pdsh flag '-t' do not really works well. Better to use
        # PDSH_SSH_ARGS_APPEND variable to transmit ssh ConnectTimeout
        # flag.
        connect_timeout = task.info("connect_timeout", 0)
        if connect_timeout > 0:
            pdsh_env['PDSH_SSH_ARGS_APPEND'] = "-o ConnectTimeout=%d" % \
                    connect_timeout

        command_timeout = task.info("command_timeout", 0)
        if command_timeout > 0:
            cmd_l.append("-u %d" % command_timeout)

        cmd_l.append("-w %s" % self.key)
        cmd_l.append("%s" % self.command)

        return (cmd_l, pdsh_env)

    def _close(self, abort, timeout):
        """Close client. See EngineClient._close()."""
        if abort:
            # it's safer to call poll() first for long time completed processes
            prc = self.popen.poll()
            # if prc is None, process is still running
            if prc is None:
                try: # try to kill it
                    self.popen.kill()
                except OSError:
                    pass
        prc = self.popen.wait()

        if prc > 0:
            raise WorkerError("Cannot run pdsh (error %d)" % prc)

        self.streams.clear()

        if timeout:
            assert abort, "abort flag not set on timeout"
            for node in (self.key - self._closed_nodes):
                self.worker._on_node_timeout(node)
        else:
            for node in (self.key - self._closed_nodes):
                self.worker._on_node_rc(node, 0)

        self.worker._check_fini()

    def _parse_line(self, line, sname):
        """
        Parse Pdsh line syntax.
        """
        if line.startswith("pdsh@") or \
           line.startswith("pdcp@") or \
           line.startswith("sending "):
            try:
                # pdsh@cors113: cors115: ssh exited with exit code 1
                #       0          1      2     3     4    5    6  7
                # corsUNKN: ssh: corsUNKN: Name or service not known
                #     0      1       2       3  4     5     6    7
                # pdsh@fortoy0: fortoy101: command timeout
                #     0             1         2       3
                # sending SIGTERM to ssh fortoy112 pid 32014
                #     0      1     2  3      4      5    6
                # pdcp@cors113: corsUNKN: ssh exited with exit code 255
                #     0             1      2    3     4    5    6    7
                # pdcp@cors113: cors115: fatal: /var/cache/shine/...
                #     0             1      2                   3...

                words  = line.split()
                # Set return code for nodename of worker
                if self.MODE == 'pdsh':
                    if len(words) == 4 and words[2] == "command" and \
                       words[3] == "timeout":
                        pass
                    elif len(words) == 8 and words[3] == "exited" and \
                         words[7].isdigit():
                        self._closed_nodes.add(words[1][:-1])
                        self.worker._on_node_rc(words[1][:-1], int(words[7]))
                elif self.MODE == 'pdcp':
                    self._closed_nodes.add(words[1][:-1])
                    self.worker._on_node_rc(words[1][:-1], errno.ENOENT)

            except Exception, exc:
                print >> sys.stderr, exc
                raise EngineClientError()
        else:
            # split pdsh reply "nodename: msg"
            nodename, msg = line.split(': ', 1)
            self.worker._on_node_msgline(nodename, msg, sname)

    def _flush_read(self, sname):
        """Called at close time to flush stream read buffer."""
        pass

    def _handle_read(self, sname):
        """Engine is telling us a read is available."""
        debug = self.worker.task.info("debug", False)
        if debug:
            print_debug = self.worker.task.info("print_debug")

        suffix = ""
        if sname == 'stderr':
            suffix = "@STDERR"

        for msg in self._readlines(sname):
            if debug:
                print_debug(self.worker.task, "PDSH%s: %s" % (suffix, msg))
            self._parse_line(msg, sname)


class PdcpClient(CopyClient, PdshClient):
    """EngineClient when pdsh is run to copy file, using pdcp."""

    MODE = 'pdcp'

    def _build_cmd(self):

        cmd_l = []

        # Build pdcp command
        if self.reverse:
            path = self.worker.task.info("rpdcp_path") or "rpdcp"
        else:
            path = self.worker.task.info("pdcp_path") or "pdcp"
        cmd_l = [os.path.expanduser(pathc) for pathc in shlex.split(path)]
        cmd_l.append("-b")

        fanout = self.worker.task.info("fanout", 0)
        if fanout > 0:
            cmd_l.append("-f %d" % fanout)

        connect_timeout = self.worker.task.info("connect_timeout", 0)
        if connect_timeout > 0:
            cmd_l.append("-t %d" % connect_timeout)

        cmd_l.append("-w %s" % self.key)

        if self.isdir:
            cmd_l.append("-r")

        if self.preserve:
            cmd_l.append("-p")

        cmd_l.append(self.source)
        cmd_l.append(self.dest)

        return (cmd_l, None)


class WorkerPdsh(ExecWorker):
    """
    ClusterShell pdsh-based worker Class.

    Remote Shell (pdsh) usage example:
       >>> worker = WorkerPdsh(nodeset, handler=MyEventHandler(),
       ...                     timeout=30, command="/bin/hostname")
       >>> task.schedule(worker)      # schedule worker for execution
       >>> task.resume()              # run

    Remote Copy (pdcp) usage example:
       >>> worker = WorkerPdsh(nodeset, handler=MyEventHandler(),
       ...                     timeout=30, source="/etc/my.conf",
       ...                     dest="/etc/my.conf")
       >>> task.schedule(worker)      # schedule worker for execution
       >>> task.resume()              # run

    Known limitations:
      - write() is not supported by WorkerPdsh
      - return codes == 0 are not garanteed when a timeout is used (rc > 0
        are fine)
    """

    SHELL_CLASS = PdshClient
    COPY_CLASS = PdcpClient

    #
    # Spawn and control
    #

    def _create_clients(self, **kwargs):
        self._add_client(self.nodes, **kwargs)

    def write(self, buf):
        """
        Write data to process. Not supported with Pdsh worker.
        """
        raise EngineClientNotSupportedError("writing is not supported by pdsh "
                                            "worker")

    def set_write_eof(self):
        """
        Tell worker to close its writer file descriptor once flushed. Do not
        perform writes after this call.

        Not supported by PDSH Worker.
        """
        raise EngineClientNotSupportedError("writing is not supported by pdsh "
                                            "worker")

WORKER_CLASS = WorkerPdsh
