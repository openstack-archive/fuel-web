#    Copyright 2014 Mirantis, Inc.
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

from nailgun.task import manager
from nailgun.task.verify_registry import registry
from nailgun.test import base


class TestTaskManagerRegistry(base.BaseTestCase):

    def setUp(self):
        self.collected_managers = registry._registry

    def test_verify_task_managers_collected(self):

        self.assertTrue(self.collected_managers)

        for name, mngr in self.collected_managers.iteritems():
            self.assertTrue(issubclass(mngr, manager.TaskManager))

    def test_get_task_manager(self):

        verify_manager = registry.get_task_manager(
            manager.VerifyNetworksTaskManager.task_name)

        self.assertEqual(verify_manager, manager.VerifyNetworksTaskManager)
