#
# Copyright CEA/DAM/DIF (2007, 2008, 2009, 2010, 2011)
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
import sys

from ClusterShell.NodeSet import NodeSet
from ClusterShell.Worker.EngineClient import EngineClient
from ClusterShell.Worker.EngineClient import EngineClientError
from ClusterShell.Worker.EngineClient import EngineClientNotSupportedError
from ClusterShell.Worker.Worker import DistantWorker
from ClusterShell.Worker.Worker import WorkerError


class WorkerPdsh(EngineClient, DistantWorker):
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

    def __init__(self, nodes, handler, timeout, **kwargs):
        """
        Initialize Pdsh worker instance.
        """
        DistantWorker.__init__(self, handler)

        self.nodes = NodeSet(nodes)
        self.closed_nodes = NodeSet()

        self.command = kwargs.get('command')
        self.source = kwargs.get('source')
        self.dest = kwargs.get('dest')

        autoclose = kwargs.get('autoclose', False)
        stderr = kwargs.get('stderr', False)

        EngineClient.__init__(self, self, stderr, timeout, autoclose)

        if self.command is not None:
            # PDSH
            self.source = None
            self.dest = None
            self.mode = 'pdsh'
        elif self.source:
            # PDCP
            self.command = None
            self.mode = 'pdcp'
            # Preserve modification times and modes?
            self.preserve = kwargs.get('preserve', False)
            # Reverse copy (rpdcp)?
            self.reverse = kwargs.get('reverse', False)
            if self.reverse:
                self.isdir = os.path.isdir(self.dest)
                if not self.isdir:
                    raise ValueError("reverse copy dest must be a directory")
            else:
                self.isdir = os.path.isdir(self.source)
        else:
            raise ValueError("missing command or source parameter in " \
			     "WorkerPdsh constructor")

        self.popen = None
        self._buf = ""

    def _engine_clients(self):
        return [self]

    def _start(self):
        """
        Start worker, initialize buffers, prepare command.
        """
        # Initialize worker read buffer
        self._buf = ""

        pdsh_env = {}

        if self.command is not None:
            # Build pdsh command
            executable = self.task.info("pdsh_path") or "pdsh"
            cmd_l = [ executable, "-b" ]

            fanout = self.task.info("fanout", 0)
            if fanout > 0:
                cmd_l.append("-f %d" % fanout)

            # Pdsh flag '-t' do not really works well. Better to use
            # PDSH_SSH_ARGS_APPEND variable to transmit ssh ConnectTimeout
            # flag.
            connect_timeout = self.task.info("connect_timeout", 0)
            if connect_timeout > 0:
                pdsh_env['PDSH_SSH_ARGS_APPEND'] = "-o ConnectTimeout=%d" % \
                        connect_timeout

            command_timeout = self.task.info("command_timeout", 0)
            if command_timeout > 0:
                cmd_l.append("-u %d" % command_timeout)

            cmd_l.append("-w %s" % self.nodes)
            cmd_l.append("%s" % self.command)

            if self.task.info("debug", False):
                self.task.info("print_debug")(self.task, "PDSH: %s" % \
                                                            ' '.join(cmd_l))
        else:
            # Build pdcp command
            if self.reverse:
                executable  = self.task.info('rpdcp_path') or "rpdcp"
            else:
                executable = self.task.info("pdcp_path") or "pdcp"
            cmd_l = [ executable, "-b" ]

            fanout = self.task.info("fanout", 0)
            if fanout > 0:
                cmd_l.append("-f %d" % fanout)

            connect_timeout = self.task.info("connect_timeout", 0)
            if connect_timeout > 0:
                cmd_l.append("-t %d" % connect_timeout)

            cmd_l.append("-w %s" % self.nodes)

            if self.isdir:
                cmd_l.append("-r")

            if self.preserve:
                cmd_l.append("-p")

            cmd_l.append(self.source)
            cmd_l.append(self.dest)

            if self.task.info("debug", False):
                self.task.info("print_debug")(self.task,"PDCP: %s" % \
                                                            ' '.join(cmd_l))

        self.popen = self._exec_nonblock(cmd_l, env=pdsh_env)
        self._on_start()

        return self

    def write(self, buf):
        """
        Write data to process. Not supported with Pdsh worker.
        """
        raise EngineClientNotSupportedError("writing is not " \
                                            "supported by pdsh worker")

    def _close(self, abort, flush, timeout):
        """
        Close client. See EngineClient._close().
        """
        if abort:
            prc = self.popen.poll()
            if prc is None:
                # process is still running, kill it
                self.popen.kill()
        prc = self.popen.wait()
        if prc >= 0:
            rc = prc
            if rc != 0:
                raise WorkerError("Cannot run pdsh (error %d)" % rc)
        if abort and timeout:
            if self.eh:
                self.eh.ev_timeout(self)

        os.close(self.fd_reader)
        self.fd_reader = None
        if self.fd_error:
            os.close(self.fd_error)
            self.fd_error = None
        if self.fd_writer:
            os.close(self.fd_writer)
            self.fd_writer = None

        if timeout:
            assert abort, "abort flag not set on timeout"
            for node in (self.nodes - self.closed_nodes):
                self._on_node_timeout(node)
        else:
            for node in (self.nodes - self.closed_nodes):
                self._on_node_rc(node, 0)

        if self.eh:
            self.eh.ev_close(self)

    def _parse_line(self, line, stderr):
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
                if self.mode == 'pdsh':
                    if len(words) == 4 and words[2] == "command" and \
                       words[3] == "timeout":
                        pass
                    elif len(words) == 8 and words[3] == "exited" and \
                         words[7].isdigit():
                        self._on_node_rc(words[1][:-1], int(words[7]))
                elif self.mode == 'pdcp':
                    self._on_node_rc(words[1][:-1], errno.ENOENT)

            except Exception, exc:
                print >> sys.stderr, exc
                raise EngineClientError()
        else:
            # split pdsh reply "nodename: msg"
            nodename, msg = line.split(': ', 1)
            if stderr:
                self._on_node_errline(nodename, msg)
            else:
                self._on_node_msgline(nodename, msg)

    def _handle_read(self):
        """
        Engine is telling us a read is available.
        """
        debug = self.task.info("debug", False)
        if debug:
            print_debug = self.task.info("print_debug")

        for msg in self._readlines():
            if debug:
                print_debug(self.task, "PDSH: %s" % msg)
            self._parse_line(msg, False)

    def _handle_error(self):
        """
        Engine is telling us an error read is available.
        """
        debug = self.worker.task.info("debug", False)
        if debug:
            print_debug = self.worker.task.info("print_debug")

        for msg in self._readerrlines():
            if debug:
                print_debug(self.task, "PDSH@STDERR: %s" % msg)
            self._parse_line(msg, True)

    def _on_node_rc(self, node, rc):
        """
        Return code received from a node, update last* stuffs.
        """
        DistantWorker._on_node_rc(self, node, rc)
        self.closed_nodes.add(node)

