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

from fuel_upgrade import errors
from fuel_upgrade.tests.base import BaseTestCase
from fuel_upgrade.upgrade import UpgradeManager


@mock.patch('fuel_upgrade.upgrade.get_request', return_value=[])
class TestUpgradeManager(BaseTestCase):

    def default_args(self, **kwargs):
        default = {
            'source_path': '/tmp/src_file',
            'upgraders': [mock.Mock()],
            'auto_rollback': True}

        default.update(kwargs)
        return default

    def test_run_rollback_in_case_of_errors(self, _):
        upgrader = UpgradeManager(**self.default_args())
        engine_mock = upgrader._upgraders[0]
        engine_mock.upgrade.side_effect = Exception('Upgrade failed')
        upgrader.run()

        engine_mock.backup.assert_called_once_with()
        engine_mock.upgrade.assert_called_once_with()
        engine_mock.rollback.assert_called_once_with()

    def test_does_not_run_rollback_if_disabled(self, _):
        upgrader = UpgradeManager(**self.default_args(auto_rollback=False))
        engine_mock = upgrader._upgraders[0]
        engine_mock.upgrade.side_effect = Exception('Upgrade failed')
        upgrader.run()

        engine_mock.backup.assert_called_once_with()
        engine_mock.upgrade.assert_called_once_with()
        self.method_was_not_called(engine_mock.rollback)

    def test_upgrade_succed(self, _):
        upgrader = UpgradeManager(**self.default_args())
        engine_mock = upgrader._upgraders[0]
        upgrader.run()

        engine_mock.backup.assert_called_once_with()
        engine_mock.upgrade.assert_called_once_with()
        self.method_was_not_called(engine_mock.rollback)

    def test_check_upgrade_opportunity_raises_error(self, _):
        engine_mock = mock.Mock()

        tasks = [{
            'status': 'running',
            'id': 'id',
            'cluster': 123,
            'name': 'task_name'}]

        with mock.patch(
                'fuel_upgrade.upgrade.get_request',
                return_value=tasks) as get_method_mock:

            upgrader = UpgradeManager(**self.default_args(upgraders=[engine_mock]))

            self.assertRaisesRegexp(
                errors.CannotRunUpgrade,
                'Cannot run upgrade, tasks are running: '
                'id=id cluster=123 name=task_name',
                upgrader.check_upgrade_opportunity)

        get_method_mock.assert_called_once_with(
            'http://127.0.0.1:8000/api/v1/tasks')

    def test_check_upgrade_opportunity_does_not_raise_error(self, _):
        engine_mock = mock.Mock()

        tasks = [{
            'status': 'error',
            'id': 'id',
            'cluster': 123,
            'name': 'task_name'}]

        with mock.patch(
                'fuel_upgrade.upgrade.get_request',
                return_value=tasks) as get_method_mock:
            upgrader = UpgradeManager(**self.default_args(upgraders=[engine_mock]))
            upgrader.check_upgrade_opportunity()

        get_method_mock.assert_called_once_with(
            'http://127.0.0.1:8000/api/v1/tasks')
