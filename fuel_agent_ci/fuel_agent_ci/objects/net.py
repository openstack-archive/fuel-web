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

from fuel_agent_ci.objects import Object

LOG = logging.getLogger(__name__)


class Net(Object):
    __typename__ = 'net'

    def __init__(self, env, name, bridge, ip, forward):
        self.env = env
        self.name = name
        self.bridge = bridge
        self.ip = ip
        self.forward = forward

    def start(self):
        if not self.status():
            LOG.debug('Starting network %s' % self.name)
            self.env.driver.net_start(self)

    def stop(self):
        if self.status():
            LOG.debug('Stopping network %s' % self.name)
            self.env.driver.net_stop(self)

    def status(self):
        status = self.env.driver.net_status(self)
        LOG.debug('Network %s status %s' % (self.name, status))
        return status
