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


class Dhcp(Object):
    __typename__ = 'dhcp'

    def __init__(self, env, name, begin, end, network):
        self.name = name
        self.env = env
        self.begin = begin
        self.end = end
        self.network = network
        self.hosts = []
        self.bootp = None

    def add_host(self, mac, ip, name=None):
        host = {'mac': mac, 'ip': ip}
        if name is not None:
            host['name'] = name
        self.hosts.append(host)

    def set_bootp(self, file):
        self.bootp = {'file': file}

    def start(self):
        if not self.status():
            LOG.debug('Starting DHCP')
            self.env.driver.dhcp_start(self)

    def stop(self):
        if self.status():
            LOG.debug('Stopping DHCP')
            self.env.driver.dhcp_stop(self)

    def status(self):
        status = self.env.driver.dhcp_status(self)
        LOG.debug('DHCP status %s' % status)
        return status
