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


class Repo(Object):
    __typename__ = 'repo'

    def __init__(self, env, name, url, path, branch='master'):
        self.env = env
        self.name = name
        self.url = url
        self.path = path
        self.branch = branch

    def clone(self):
        if not self.status():
            LOG.debug('Cloning repo %s' % self.name)
            self.env.driver.repo_clone(self)

    def clean(self):
        if self.status():
            LOG.debug('Cleaning repo %s' % self.name)
            self.env.driver.repo_clean(self)

    def status(self):
        status = self.env.driver.repo_status(self)
        LOG.debug('Repo %s status %s' % (self.name, status))
        return status
