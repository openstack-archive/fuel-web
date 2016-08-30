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

from nailgun.plugins.adapters import PluginAdapterBase
from nailgun.plugins import loaders


class PluginAdapterV1(PluginAdapterBase):
    """Plugins attributes class for package version 1.0.0."""

    loader_class = loaders.PluginLoaderV1

    @property
    def attributes_processors(self):
        ap = super(PluginAdapterV1, self).attributes_processors
        ap.update({
            'tasks': self._process_legacy_tasks
        })
        return ap

    @staticmethod
    def _process_legacy_tasks(tasks):
        tasks = tasks or []
        for task in tasks:
            role = task['role']
            if isinstance(role, list) and 'controller' in role:
                role.append('primary-controller')
        return tasks

    def get_tasks(self):
        tasks = self.plugin.tasks
        slave_path = self.slaves_scripts_path
        for task in tasks:
            task['roles'] = task.get('role')

            role = task['role']
            if isinstance(role, list) \
                    and ('controller' in role) \
                    and ('primary-controller' not in role):
                role.append('primary-controller')

            parameters = task.get('parameters')
            if parameters is not None:
                parameters.setdefault('cwd', slave_path)
        return tasks

    @property
    def path_name(self):
        """Returns a name and full version

        e.g. if there is a plugin with name "plugin_name" and version
        is "1.0.0", the method returns "plugin_name-1.0.0"
        """
        return self.full_name
