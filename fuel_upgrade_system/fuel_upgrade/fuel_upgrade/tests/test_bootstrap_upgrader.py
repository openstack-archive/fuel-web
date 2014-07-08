# -*- coding: utf-8 -*-

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

import mock

from fuel_upgrade.engines.bootstrap import BootstrapUpgrader
from fuel_upgrade.tests.base import BaseTestCase


class TestBootstrapUpgrader(BaseTestCase):

    def setUp(self):
        self.upgrader = BootstrapUpgrader(self.fake_config)

    def test_constructor(self):
        self.assertEqual(len(self.upgrader._action_manager._actions), 4)

    def test_upgrade(self):
        self.upgrader._action_manager.do = mock.Mock()
        self.upgrader.upgrade()

        self.called_once(self.upgrader._action_manager.do)

    def test_rollback(self):
        self.upgrader._action_manager.undo = mock.Mock()
        self.upgrader.rollback()

        self.called_once(self.upgrader._action_manager.undo)

    @mock.patch('fuel_upgrade.utils.os.path.isdir', return_value=True)
    @mock.patch('fuel_upgrade.utils.dir_size', return_value=42)
    def test_required_free_space(self, _, __):
        result = self.upgrader.required_free_space
        self.assertEqual(result, {
            '/var/www/nailgun/9999_bootstrap': 42,
        })
