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

import copy
import mock
import os

from nailgun import errors
from nailgun.plugins.manager import PluginManager
from nailgun.test import base


class TestSync(base.BaseTestCase):

    def test_removes_tasks_from_db_if_removed_from_new_plugin(self):
        plugin = self.env.create_plugin(
            tasks=self.env.get_default_plugin_tasks())
        mocked_metadata = {
            'metadata.yaml': {},
            'environment_config.yaml': {},
        }
        self.assertNotEqual(plugin.tasks, [])

        with mock.patch(
            'nailgun.plugins.loaders.files_manager.FilesManager.load'
        ) as load:

            def se(key):
                # Simulate that tasks.yaml was removed
                if key.endswith('tasks.yaml'):
                    raise errors.NoPluginFileFound()
                return copy.deepcopy(
                    mocked_metadata.get(os.path.basename(key)))

            load.side_effect = se
            PluginManager.sync_plugins_metadata(plugin_ids=[plugin.id])

        self.assertEqual(plugin.tasks, [])
