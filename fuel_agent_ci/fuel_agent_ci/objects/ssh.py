# Copyright 2014 Mirantis, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import time

from fuel_agent_ci.objects import Object

LOG = logging.getLogger(__name__)


class Ssh(Object):
    __typename__ = 'ssh'

    def __init__(self, env, name, host, key_filename, user='root',
                 connection_timeout=5, command_timeout=10):
        self.env = env
        self.name = name
        self.host = host
        self.user = user
        self.key_filename = key_filename
        self.connection_timeout = int(connection_timeout)
        self.command_timeout = int(command_timeout)

    def status(self):
        status = self.env.driver.ssh_status(self)
        LOG.debug('SSH %s status %s' % (self.name, status))
        return status

    def put_content(self, content, remote_filename):
        if self.status():
            LOG.debug('Putting content %s' % self.name)
            self.env.driver.ssh_put_content(self, content, remote_filename)
        else:
            raise Exception('Wrong ssh status: %s' % self.name)

    def get_file(self, remote_filename, filename):
        if self.status():
            LOG.debug('Getting file %s' % self.name)
            self.env.driver.ssh_get_file(self, remote_filename, filename)
        else:
            raise Exception('Wrong ssh status: %s' % self.name)

    def put_file(self, filename, remote_filename):
        if self.status():
            LOG.debug('Putting file %s' % self.name)
            self.env.driver.ssh_put_file(self, filename, remote_filename)
        else:
            raise Exception('Wrong ssh status: %s' % self.name)

    def run(self, command, command_timeout=None):
        if self.status():
            LOG.debug('Running command %s' % self.name)
            return self.env.driver.ssh_run(
                self, command, command_timeout or self.command_timeout)
        raise Exception('Wrong ssh status: %s' % self.name)

    def wait(self, timeout=200):
        begin_time = time.time()
        # this loop does not have sleep statement
        # because it relies on self.connection_timeout
        # which is by default 5 seconds
        while time.time() - begin_time < timeout:
            if self.status():
                return True
            LOG.debug('Waiting for ssh connection to be '
                      'available: %s' % self.name)
        return False
