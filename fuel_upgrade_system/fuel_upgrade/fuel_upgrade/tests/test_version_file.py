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

from fuel_upgrade.tests.base import BaseTestCase
from fuel_upgrade.version_file import VersionFile


class TestVersionFile(BaseTestCase):

    def setUp(self):
        self.version_file = VersionFile(self.fake_config)

    @mock.patch('fuel_upgrade.version_file.utils')
    def test_save_current(self, mock_utils):
        self.version_file.save_current()
        mock_utils.copy_if_does_not_exist.assert_called_once_with(
            '/etc/fuel/version.yaml',
            '/var/lib/fuel_upgrade/9999/version.yaml')

    @mock.patch('fuel_upgrade.version_file.utils')
    def test_switch_to_new(self, mock_utils):
        self.version_file.switch_to_new()

        mock_utils.create_dir_if_not_exists.assert_called_once_with(
            '/etc/fuel/9999')
        mock_utils.copy.assert_called_once_with(
            '/tmp/upgrade_path/config/version.yaml',
            '/etc/fuel/9999/version.yaml')
        mock_utils.symlink.assert_called_once_with(
            '/etc/fuel/9999/version.yaml',
            '/etc/fuel/version.yaml')

    @mock.patch('fuel_upgrade.version_file.utils.symlink')
    def test_switch_to_previous(self, symlink_mock):
        self.version_file.switch_to_previous()

        symlink_mock.assert_called_once_with(
            '/etc/fuel/0/version.yaml',
            '/etc/fuel/version.yaml')
