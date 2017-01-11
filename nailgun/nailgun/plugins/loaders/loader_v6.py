#
#    Copyright 2016 Mirantis, Inc.
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

from loader_v5 import PluginLoaderV5


class PluginLoaderV6(PluginLoaderV5):
    @property
    def paths_to_fields(self):
        path_to_fields = dict(super(PluginLoaderV6, self).paths_to_fields)
        path_to_fields['tags_metadata'] = 'node_tags.yaml'
        return path_to_fields
