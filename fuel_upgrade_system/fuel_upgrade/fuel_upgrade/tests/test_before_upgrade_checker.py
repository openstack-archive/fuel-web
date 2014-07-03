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

from fuel_upgrade.before_upgrade_checker import CheckFreeSpace
from fuel_upgrade.before_upgrade_checker import CheckNoRunningTasks
from fuel_upgrade.before_upgrade_checker import CheckUpgradeVersions
from fuel_upgrade import errors
from fuel_upgrade.tests.base import BaseTestCase


class TestCheckNoRunningTasks(BaseTestCase):

    def setUp(self):
        config = mock.MagicMock()
        config.endpoints = {'nailgun': {'host': '127.0.0.1', 'port': 1234}}
        self.config = config

    @mock.patch('fuel_upgrade.before_upgrade_checker.NailgunClient.get_tasks',
                return_value=[{
                    'status': 'running', 'id': 'id',
                    'cluster': 123, 'name': 'task_name'}])
    def test_check_raises_error(self, get_tasks_mock):
        checker = CheckNoRunningTasks(self.config)

        self.assertRaisesRegexp(
            errors.CannotRunUpgrade,
            'Cannot run upgrade, tasks are running: '
            'id=id cluster=123 name=task_name',
            checker.check)

        self.called_once(get_tasks_mock)

    @mock.patch('fuel_upgrade.before_upgrade_checker.NailgunClient.get_tasks',
                return_value=[{
                    'status': 'ready', 'id': 'id',
                    'cluster': 123, 'name': 'task_name'}])
    def test_check_upgrade_opportunity_does_not_raise_error(
            self, get_tasks_mock):
        checker = CheckNoRunningTasks(self.config)
        checker.check()
        self.called_once(get_tasks_mock)


@mock.patch('fuel_upgrade.before_upgrade_checker.utils.find_mount_point',
            side_effect=['/var', '/var', '/etc'])
class TestCheckFreeSpace(BaseTestCase):

    def setUp(self):
        engine1 = mock.MagicMock(
            required_free_space={
                '/var/lib/docker': 10})

        engine2 = mock.MagicMock(
            required_free_space={
                '/etc/fuel': 10,
                '/vat/www': 10})

        engine3 = mock.MagicMock(required_free_space=None)

        self.engines = [engine1, engine2, engine3]

    @mock.patch('fuel_upgrade.before_upgrade_checker.utils.'
                'calculate_free_space')
    def test_check(self, calculate_free_space_mock, find_mount_point_mock):
        checker = CheckFreeSpace(self.engines)
        checker.check()

        self.called_times(find_mount_point_mock, 3)
        self.called_times(calculate_free_space_mock, 2)

    @mock.patch('fuel_upgrade.before_upgrade_checker.utils.'
                'calculate_free_space', return_value=9)
    def test_check_raises_errors(
            self, calculate_free_space_mock, find_mount_point_mock):

        checker = CheckFreeSpace(self.engines)
        err_msg = "Not enough free space on device: " +\
            "device /etc (required 10MB, available 9MB, not enough 1MB), " +\
            "device /var (required 20MB, available 9MB, not enough 11MB)"

        with self.assertRaises(errors.NotEnoughFreeSpaceOnDeviceError) as exc:
            checker.check()

        self.assertEqual(str(exc.exception), err_msg)
        self.called_times(find_mount_point_mock, 3)
        self.called_times(calculate_free_space_mock, 2)

    @mock.patch('fuel_upgrade.before_upgrade_checker.utils.'
                'calculate_free_space')
    def test_space_required_for_mount_points(
            self, calculate_free_space_mock, find_mount_point_mock):

        checker = CheckFreeSpace(self.engines)
        mount_points = checker.space_required_for_mount_points()

        self.assertEqual(mount_points, {'/etc': 10, '/var': 20})

    @mock.patch('fuel_upgrade.before_upgrade_checker.utils.'
                'calculate_free_space', return_value=9)
    def test_list_of_error_mount_points(
            self, calculate_free_space_mock, find_mount_point_mock):

        checker = CheckFreeSpace(self.engines)
        error_mount_points = checker.list_of_error_mount_points({
            '/etc': 100, '/var': 2})
        self.assertEqual(
            error_mount_points,
            [{'available': 9, 'path': '/etc', 'size': 100}])


class TestCheckUpgradeVersions(BaseTestCase):

    def setUp(self):
        self.checker = CheckUpgradeVersions(self.fake_config)

    @mock.patch(
        'fuel_upgrade.before_upgrade_checker.utils.compare_version',
        return_value=1)
    def test_check(self, compare_mock):
        self.checker.check()
        compare_mock.assert_called_once_with('0', '9999')

    @mock.patch(
        'fuel_upgrade.before_upgrade_checker.utils.compare_version',
        return_value=0)
    def test_check_same_version_error(self, compare_mock):
        err_msg = 'Cannot upgrade to the same version of fuel 0 -> 9999'
        self.assertRaisesRegexp(
            errors.WrongVersionError,
            err_msg,
            self.checker.check)
        compare_mock.assert_called_once_with('0', '9999')

    @mock.patch(
        'fuel_upgrade.before_upgrade_checker.utils.compare_version',
        return_value=-1)
    def test_check_higher_version_error(self, compare_mock):
        err_msg = 'Cannot upgrade from higher version of ' +\
                  'fuel to lower 0 -> 9999'
        self.assertRaisesRegexp(
            errors.WrongVersionError,
            err_msg,
            self.checker.check)
        compare_mock.assert_called_once_with('0', '9999')
