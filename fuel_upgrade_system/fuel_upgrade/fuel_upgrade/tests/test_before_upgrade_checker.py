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

import requests
import six

from fuel_upgrade.before_upgrade_checker import CheckFreeSpace
from fuel_upgrade.before_upgrade_checker import CheckNoRunningOstf
from fuel_upgrade.before_upgrade_checker import CheckNoRunningTasks
from fuel_upgrade.before_upgrade_checker import CheckRequiredVersion
from fuel_upgrade.before_upgrade_checker import CheckUpgradeVersions
from fuel_upgrade import errors
from fuel_upgrade.tests.base import BaseTestCase


class TestCheckNoRunningTasks(BaseTestCase):

    def setUp(self):
        config = mock.MagicMock()
        config.endpoints = {
            'nginx_nailgun': {'host': '127.0.0.1', 'port': 1234}}
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

    @mock.patch('fuel_upgrade.before_upgrade_checker.NailgunClient.get_tasks',
                side_effect=requests.ConnectionError(''))
    def test_check_raises_error_if_nailgun_is_not_running(
            self, get_tasks_mock):
        checker = CheckNoRunningTasks(self.config)
        self.assertRaisesRegexp(
            errors.NailgunIsNotRunningError,
            'Cannot connect to rest api service',
            checker.check)
        self.called_once(get_tasks_mock)


class TestCheckNoRunningOstf(BaseTestCase):

    def setUp(self):
        config = mock.MagicMock()
        config.endpoints = {'ostf': {'host': '127.0.0.1', 'port': 1234}}

        self.checker = CheckNoRunningOstf(config)

    @mock.patch('fuel_upgrade.before_upgrade_checker.OSTFClient.get_tasks',
                return_value=[{'status': 'running'}])
    def test_check_raises_error(self, get_mock):
        self.assertRaisesRegexp(
            errors.CannotRunUpgrade,
            'Cannot run upgrade since there are OSTF running tasks.',
            self.checker.check)

        self.called_once(get_mock)

    @mock.patch('fuel_upgrade.before_upgrade_checker.OSTFClient.get_tasks',
                return_value=[{'status': 'finished'}])
    def test_check_upgrade_opportunity_does_not_raise_error(self, get_mock):
        self.checker.check()
        self.called_once(get_mock)

    @mock.patch('fuel_upgrade.before_upgrade_checker.OSTFClient.get_tasks',
                side_effect=requests.ConnectionError(''))
    def test_check_raises_error_if_ostf_is_not_running(self, get_mock):
        self.assertRaisesRegexp(
            errors.OstfIsNotRunningError,
            'Cannot connect to OSTF service.',
            self.checker.check)
        self.called_once(get_mock)


@mock.patch('fuel_upgrade.before_upgrade_checker.utils.find_mount_point',
            side_effect=['/var', '/var', '/etc'])
class TestCheckFreeSpace(BaseTestCase):

    def setUp(self):
        context = mock.MagicMock()
        context.required_free_spaces = [
            {'/var/lib/docker': 10},
            {'/etc/fuel': 10, '/vat/www': 10},
            None]

        self.context = context

    @mock.patch('fuel_upgrade.before_upgrade_checker.utils.'
                'calculate_free_space', return_value=100)
    def test_check(self, calculate_free_space_mock, find_mount_point_mock):
        checker = CheckFreeSpace(self.context)
        checker.check()

        self.called_times(find_mount_point_mock, 3)
        self.called_times(calculate_free_space_mock, 2)

    @mock.patch('fuel_upgrade.before_upgrade_checker.utils.'
                'calculate_free_space', return_value=9)
    def test_check_raises_errors(
            self, calculate_free_space_mock, find_mount_point_mock):

        checker = CheckFreeSpace(self.context)
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

        checker = CheckFreeSpace(self.context)
        mount_points = checker.space_required_for_mount_points()

        self.assertEqual(mount_points, {'/etc': 10, '/var': 20})

    @mock.patch('fuel_upgrade.before_upgrade_checker.utils.'
                'calculate_free_space', return_value=9)
    def test_list_of_error_mount_points(
            self, calculate_free_space_mock, find_mount_point_mock):

        checker = CheckFreeSpace(self.context)
        error_mount_points = checker.list_of_error_mount_points({
            '/etc': 100, '/var': 2})
        self.assertEqual(
            error_mount_points,
            [{'available': 9, 'path': '/etc', 'size': 100}])


class TestCheckUpgradeVersions(BaseTestCase):

    def setUp(self):
        context = mock.MagicMock(config=self.fake_config)
        self.checker = CheckUpgradeVersions(context)

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


class TestCheckRequiredVersions(BaseTestCase):

    def get_checker(self, user_conf={}):
        config = self.fake_config

        for key, value in six.iteritems(user_conf):
            setattr(config, key, value)

        return CheckRequiredVersion(mock.Mock(config=config))

    def test_check_support_version(self):
        checker = self.get_checker({
            'from_version': '5.1.1',
            'can_upgrade_from': ['5.1.1']})
        checker.check()

    def test_check_unsupport_version(self):
        checker = self.get_checker({
            'from_version': '5.1',
            'can_upgrade_from': ['5.1.1']})
        self.assertRaises(errors.WrongVersionError, checker.check)
