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

import os

import mock

from fuel_upgrade.engines.host_system import HostSystemUpgrader
from fuel_upgrade.tests.base import BaseTestCase
from fuel_upgrade.upgrade import UpgradeManager


class TestUpgradeManager(BaseTestCase):

    def setUp(self):
        super(TestUpgradeManager, self).setUp()

        self.version_mock = mock.MagicMock()
        self.version_patcher = mock.patch(
            'fuel_upgrade.upgrade.VersionFile', return_value=self.version_mock)
        self.version_patcher.start()

    def tearDown(self):
        self.version_patcher.stop()
        super(TestUpgradeManager, self).tearDown()

    def default_args(self, **kwargs):
        default = {
            'upgraders': [mock.Mock()],
            'config': self.fake_config,
            'no_rollback': False}

        default.update(kwargs)
        return default

    def test_run_rollback_in_case_of_errors(self):
        upgrader = UpgradeManager(**self.default_args())
        engine_mock = upgrader._upgraders[0]
        engine_mock.upgrade.side_effect = Exception('Upgrade failed')
        self.assertRaisesRegexp(
            Exception, 'Upgrade failed', upgrader.run)

        self.called_once(self.version_mock.save_current)
        self.called_once(self.version_mock.switch_to_new)

        engine_mock.upgrade.assert_called_once_with()
        engine_mock.rollback.assert_called_once_with()

        self.called_once(self.version_mock.switch_to_previous)

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

    def test_run_backup_for_all_engines(self):
        upgrader = UpgradeManager(**self.default_args(
            upgraders=[mock.Mock(), mock.Mock()],
        ))
        upgrader.run()

        self.called_once(upgrader._upgraders[0].backup)
        self.called_once(upgrader._upgraders[1].backup)

    def test_run_backup_fails(self):
        upgrader = UpgradeManager(**self.default_args(
            upgraders=[mock.Mock(), mock.Mock()],
        ))
        upgrader._upgraders[1].backup.side_effect = Exception('Backup fails')
        self.assertRaisesRegexp(
            Exception, 'Backup fails', upgrader.run)

        self.called_once(upgrader._upgraders[0].backup)
        self.called_once(upgrader._upgraders[1].backup)

        self.method_was_not_called(upgrader._upgraders[0].rollback)
        self.method_was_not_called(upgrader._upgraders[1].rollback)

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

        self.called_once(self.version_mock.save_current)
        self.called_once(self.version_mock.switch_to_new)
        self.method_was_not_called(self.version_mock.switch_to_previous)

    def test_upgrade_run_on_success_methods(self):
        upgrader = UpgradeManager(**self.default_args())
        upgrader._on_success = mock.Mock()
        upgrader.run()

        self.called_once(upgrader._on_success)

    def test_upgrade_does_not_fail_if_on_success_method_raise_error(self):
        upgrader = UpgradeManager(**self.default_args())
        upgrader._on_success = mock.Mock()
        upgrader._on_success.side_effect = Exception('error')
        upgrader.run()

    @mock.patch('fuel_upgrade.engines.host_system.SupervisorClient')
    def test_hostsystem_rollback_is_first(self, _):
        args = self.default_args()

        hostsystem = HostSystemUpgrader(args['config'])
        hostsystem.upgrade = mock.Mock()
        hostsystem.rollback = mock.Mock()

        def check_call():
            hostsystem.rollback.assert_called_once_with()

        # there's no way to check call order of different mocks, so
        # let's use this trick - check that all mock calls were
        # after hostsystem rollback call.
        args['upgraders'] = [
            hostsystem,
            mock.Mock(rollback=mock.Mock(side_effect=check_call)),
            mock.Mock(rollback=mock.Mock(side_effect=check_call))]

        upgrader = UpgradeManager(**args)
        upgrader._used_upgraders = args['upgraders']
        upgrader.rollback()

    @mock.patch('fuel_upgrade.upgrade.utils')
    @mock.patch('fuel_upgrade.upgrade.glob.glob',
                return_value=['file1', 'file2'])
    def test_on_success(self, glob_mock, utils_mock):
        upgrader = UpgradeManager(**self.default_args())
        upgrader._on_success()

        glob_mock.assert_called_once_with(self.fake_config.version_files_mask)
        self.assertEqual(
            utils_mock.remove.call_args_list,
            [mock.call('file1'), mock.call('file2')])

        templates_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '../templates'))
        utils_mock.render_template_to_file.assert_has_calls([
            mock.call(
                '{0}/nailgun.repo'.format(templates_path),
                '/etc/yum.repos.d/mos9999-updates.repo',
                {
                    'name': 'mos9999-updates',
                    'baseurl': 'http://mirror.fuel-infra.org/mos/centos-6/'
                               'mos9999/updates/',
                    'gpgcheck': 0,
                    'skip_if_unavailable': 1,
                }),
            mock.call(
                '{0}/nailgun.repo'.format(templates_path),
                '/etc/yum.repos.d/mos9999-security.repo',
                {
                    'name': 'mos9999-security',
                    'baseurl': 'http://mirror.fuel-infra.org/mos/centos-6/'
                               'mos9999/security/',
                    'gpgcheck': 0,
                    'skip_if_unavailable': 1,
                }),
        ])
