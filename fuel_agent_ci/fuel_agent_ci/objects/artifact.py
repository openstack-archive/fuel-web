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


class Artifact(Object):
    __typename__ = 'artifact'

    def __init__(self, env, name, url, path, unpack=None, clean=None):
        self.env = env
        self.name = name
        self.url = url
        self.path = path
        self.unpack = unpack
        self.clean = clean

    def get(self):
        if not self.status():
            LOG.debug('Getting artifact %s' % self.name)
            self.env.driver.artifact_get(self)

    def clean(self):
        if self.status():
            LOG.debug('Cleaning artifact %s' % self.name)
            self.env.driver.artifact_clean(self)

    def status(self):
        status = self.env.driver.artifact_status(self)
        LOG.debug('Artifact %s status %s' % (self.name, status))
        return status
