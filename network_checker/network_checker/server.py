#    Copyright 2014 Mirantis, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import json
import logging
import multiprocessing
import os
import socket
import sys

import daemonize

LOG = logging.getLogger(__name__)


class CommunicationServer(object):

    pid_form = '/tmp/{name}.pid'
    bind_form = '/tmp/{name}'

    def __init__(self, checker):
        self.checker = checker
        self.pid_file = self.pid_form.format(name=checker.name)
        self.bind_socket = self.bind_form.format(name=checker.name)

    def daemonize_serve(self):
        daemon = daemonize.Daemonize(
            app=self.checker.name,
            pid=self.pid_file,
            action=self.serve,
            # keep open stdin, stdout, stderr and socket file
            keep_fds=[0, 1, 2, self.server.fileno()])
        daemon.start()

    def cleanup(self):
        """Helper for cleaning up previous runs, in case of multiple starting
        agents
        """
        if os.path.exists(self.bind_socket):
            os.unlink(self.bind_socket)
        if os.path.exists(self.pid_file):
            with open(self.pid_file, 'r') as f:
                pid = f.read().strip('\n')
                try:
                    os.kill(int(pid), 9)
                except OSError:
                    # it is ok if proc already stopped
                    pass
            os.unlink(self.pid_file)

    def init_server(self):
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.bind(self.bind_socket)
        self.server.listen(1)
        proc = multiprocessing.Process(target=self.daemonize_serve)
        proc.start()

    def serve(self):
        finished = False
        try:
            while not finished:
                conn, addr = self.server.accept()
                msg = conn.recv(1024)
                if 'listen' in msg:
                    response = self.checker.listen()
                    conn.send(response)
                if 'get_info' in msg:
                    response = self.checker.get_info()
                    conn.send(json.dumps(response))
                    finished = True
        except Exception as e:
            LOG.error('Server erred with %s', e)
        finally:
            self.server.close()
            self.cleanup()
            sys.exit(0)
