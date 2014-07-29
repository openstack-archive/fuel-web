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

from fuel_agent_ci.objects.environment import Environment

LOG = logging.getLogger(__name__)


class Manager(object):
    def __init__(self, data):
        self.env = Environment.new(**data)

    def do_item(self, item_type, item_action, item_name=None, **kwargs):
        return getattr(
            self.env, '%s_%s' % (item_type, item_action))(item_name, **kwargs)

    def do_env(self, env_action, **kwargs):
        return getattr(self.env, env_action)(**kwargs)
