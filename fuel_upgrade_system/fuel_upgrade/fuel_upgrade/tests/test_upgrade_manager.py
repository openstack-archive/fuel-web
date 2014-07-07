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
from fuel_upgrade.upgrade import UpgradeManager


class TestUpgradeManager(BaseTestCase):

    def default_args(self, **kwargs):
        fake_config = mock.Mock()
        fake_config.endpoints = {
            'nailgun':
            {'host': '127.0.0.1', 'port': 8000}}

        default = {
            'upgraders': [mock.Mock()],
            'checkers': [mock.Mock(), mock.Mock()],
            'no_rollback': False}

        default.update(kwargs)
        return default

    def test_run_rollback_in_case_of_errors(self):
        upgrader = UpgradeManager(**self.default_args())
        engine_mock = upgrader._upgraders[0]
        engine_mock.upgrade.side_effect = Exception('Upgrade failed')
        self.assertRaisesRegexp(
            Exception, 'Upgrade failed', upgrader.run)

        engine_mock.upgrade.assert_called_once_with()
        engine_mock.rollback.assert_called_once_with()

    def test_run_rollback_for_used_engines(self):
        upgrader = UpgradeManager(**self.default_args(
            upgraders=[mock.Mock(), mock.Mock(), mock.Mock()],
        ))
        upgrader._upgraders[1].upgrade.side_effect = Exception('Failed')

        self.assertRaisesRegexp(Exception, 'Failed', upgrader.run)

        self.called_once(upgrader._upgraders[0].upgrade)
        self.called_once(upgrader._upgraders[0].rollback)

        self.called_once(upgrader._upgraders[1].upgrade)
        self.called_once(upgrader._upgraders[1].rollback)

        self.method_was_not_called(upgrader._upgraders[2].upgrade)
        self.method_was_not_called(upgrader._upgraders[2].rollback)

    def test_run_upgrade_for_all_engines(self):
        upgrader = UpgradeManager(**self.default_args(
            upgraders=[mock.Mock(), mock.Mock()],
        ))
        upgrader.run()

        self.called_once(upgrader._upgraders[0].upgrade)
        self.method_was_not_called(upgrader._upgraders[0].rollback)

        self.called_once(upgrader._upgraders[1].upgrade)
        self.method_was_not_called(upgrader._upgraders[1].rollback)

    def test_does_not_run_rollback_if_disabled(self):
        upgrader = UpgradeManager(**self.default_args(no_rollback=True))
        engine_mock = upgrader._upgraders[0]
        engine_mock.upgrade.side_effect = Exception('Upgrade failed')
        self.assertRaisesRegexp(
            Exception, 'Upgrade failed', upgrader.run)

        engine_mock.upgrade.assert_called_once_with()
        self.method_was_not_called(engine_mock.rollback)

    def test_upgrade_succed(self):
        upgrader = UpgradeManager(**self.default_args())
        engine_mock = upgrader._upgraders[0]
        upgrader.run()

        engine_mock.upgrade.assert_called_once_with()
        self.method_was_not_called(engine_mock.rollback)

    def test_before_upgrade_is_called(self):
        upgrader = UpgradeManager(**self.default_args())
        upgrader.before_upgrade = mock.Mock()
        upgrader.run()

        self.called_once(upgrader.before_upgrade)

    def test_checkers_are_called(self):
        upgrader = UpgradeManager(**self.default_args())
        checkers_mock = upgrader._checkers
        upgrader.before_upgrade()

        for checker_mock in checkers_mock:
            self.called_once(checker_mock.check)
