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

        self.assertEqual(
            len(self.upgrader._bootstraps),
            len(BootstrapUpgrader.bootstraps))

        for file_ in BootstrapUpgrader.bootstraps:
            self.assertTrue(file_ in self.upgrader._bootstraps)

        for file_ in self.upgrader._bootstraps:
            self.assertTrue(
                self.upgrader._bootstraps[file_]['src'].endswith(file_))
            self.assertTrue(
                self.upgrader._bootstraps[file_]['dst'].endswith(file_))
            self.assertTrue(
                self.upgrader._bootstraps[file_]['backup'].endswith(file_))

            self.assertTrue(
                '0' in self.upgrader._bootstraps[file_]['backup'])

    @mock.patch('fuel_upgrade.engines.bootstrap.utils.copy')
    def test_upgrade(self, utils_copy):
        self.upgrader.backup = mock.Mock()

        self.upgrader.upgrade()

        self.called_once(self.upgrader.backup)
        self.called_times(utils_copy, len(self.upgrader._bootstraps))

        for key in self.upgrader._bootstraps:
            utils_copy.assert_any_call(
                self.upgrader._bootstraps[key]['src'],
                self.upgrader._bootstraps[key]['dst'])

    @mock.patch('fuel_upgrade.engines.bootstrap.utils.remove_if_exists')
    @mock.patch('fuel_upgrade.engines.bootstrap.utils.copy')
    def test_rollback(self, utils_copy, utils_remove):
        self.upgrader.rollback()

        self.called_times(utils_remove, len(self.upgrader._bootstraps))
        self.called_times(utils_copy, len(self.upgrader._bootstraps))

        for key in self.upgrader._bootstraps:
            utils_remove.assert_any_call(
                self.upgrader._bootstraps[key]['dst'])

            utils_copy.assert_any_call(
                self.upgrader._bootstraps[key]['backup'],
                self.upgrader._bootstraps[key]['dst'])

    @mock.patch('fuel_upgrade.engines.bootstrap.utils.rename')
    def test_backup(self, utils_rename):
        self.upgrader.backup()

        self.called_times(utils_rename, len(self.upgrader._bootstraps))
