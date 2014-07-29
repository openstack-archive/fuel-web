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


class Http(Object):
    __typename__ = 'http'

    def __init__(self, env, name, http_root, port, network,
                 status_url='/status', shutdown_url='/shutdown'):
        self.name = name
        self.env = env
        self.http_root = http_root
        self.port = port
        self.network = network
        self.status_url = status_url
        self.shutdown_url = shutdown_url

    def start(self):
        if not self.status():
            LOG.debug('Starting HTTP server')
            self.env.driver.http_start(self)

    def stop(self):
        if self.status():
            LOG.debug('Stopping HTTP server')
            self.env.driver.http_stop(self)

    def status(self):
        status = self.env.driver.http_status(self)
        LOG.debug('HTTP status %s' % status)
        return status
