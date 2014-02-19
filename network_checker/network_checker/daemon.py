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

import logging
import os

import daemonize

LOG = logging.getLogger(__name__)


def run_server(server, config):
    daemon = daemonize.Daemonize(
        app=config['app'],
        pid=config['pidfile'],
        action=server.serve_forever,
        # keep open stdin, stdout, stderr and socket file
        keep_fds=[0, 1, 2, server.fileno()])
    try:
        daemon.start()
    #this is required to do some stuff after server is daemonized
    except SystemExit as e:
        if e.code is 0:
            return True
        raise


def cleanup(config):
    if os.path.exists(config['unix']):
        os.unlink(config['unix'])
    if os.path.exists(config['pidfile']):
        with open(config['pidfile'], 'r') as f:
            pid = f.read().strip('\n')
            try:
                os.kill(int(pid), 9)
            except OSError:
                # it is ok if proc already stopped
                pass
        os.unlink(config['pidfile'])
    return True
