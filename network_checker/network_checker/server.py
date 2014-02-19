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

import sys
import json
import os
import socket
import logging


LOG = logging.getLogger(__name__)


class CommunicationServer(object):

    piddir_form = '/var/run/fuel_network_check/{name}'
    bind_form = '/tmp/{name}'

    def __init__(self, checker):
        self.mchecker = checker
        self.piddir = self.piddir_form.format(name=checker.name)
        self.bind_socket = self.bind_form.format(name=checker.name)
        self.init_server()

    def init_server(self):
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.bind(self.bind_socket)
        self.server.listen(1)

    def detach_serve(self):
        pid = os.fork()
        if pid > 0:
            return
        os.chdir("/")
        os.setsid()
        os.umask(0)
        self.serve()

    def addpid(self):
        pid = os.getpid()
        if not os.path.exists(self.piddir):
            os.mkdir(self.piddir)
        pidfile = os.path.join(self.piddir, str(pid))
        with open(pidfile, 'w') as fo:
            fo.write('')
        return pidfile

    def serve(self):
        try:
            while True:
                conn, addr = self.server.accept()
                msg = conn.recv(1024)
                if 'listen' in msg:
                    self.mchecker.listen()
                    conn.send('Listener started.')
                if 'get_info' in msg:
                    data = self.mchecker.get_info()
                    conn.send(json.dumps(data))
                    raise SystemExit
        except Exception as e:
            LOG.error('CommunicationServer erred with %s', e)
        finally:
            self.server.close()
            os.remove(self.bind_socket)
            sys.exit(0)
