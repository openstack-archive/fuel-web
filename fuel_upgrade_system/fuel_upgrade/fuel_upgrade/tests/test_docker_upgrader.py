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

from fuel_upgrade import errors
from fuel_upgrade.tests.base import BaseTestCase
from fuel_upgrade.upgrade import DockerUpgrader


@mock.patch('fuel_upgrade.upgrade.exec_cmd')
class TestDockerUpgrader(BaseTestCase):

    def setUp(self):
        # NOTE (eli): it doesn't work correctly
        # when we try to patch docker client via
        # class decorator, it's the reason why
        # we have to do it explicitly
        self.client_patcher = mock.patch('fuel_upgrade.upgrade.Client')
        self.client_mock_class = self.client_patcher.start()
        self.client_mock = mock.MagicMock()
        self.client_mock_class.return_value = self.client_mock

        self.update_path = '/tmp/new_update'
        with mock.patch('os.makedirs'):
            self.upgrader = DockerUpgrader(self.update_path)

        self.pg_dump_path = os.path.join(
            self.upgrader.working_directory, 'pg_dump_all.sql')

    def tearDown(self):
        self.client_patcher.stop()

    def assert_pg_dump(self, mock):
        mock.assert_called_once_with(
            "su postgres -c 'pg_dumpall'"
            " > {0}".format(self.pg_dump_path))

    def test_backup_db_backup_does_not_exist(self, exec_cmd):
        with mock.patch(
                'fuel_upgrade.upgrade.os.path.exists', return_value=False):
            self.upgrader.backup_db()

        self.assert_pg_dump(exec_cmd)

    def test_backup_db_do_nothing_if_backup_exists(self, exec_cmd):
        with mock.patch(
                'fuel_upgrade.upgrade.os.path.exists', return_value=True):
            self.upgrader.backup_db()

        self.method_was_not_called(exec_cmd)

    @mock.patch(
        'fuel_upgrade.upgrade.os.path.exists',
        side_effect=[False, True])
    @mock.patch('fuel_upgrade.upgrade.os.remove')
    def test_backup_db_removes_file_in_case_of_error(
            self, remove, _, __):
        with mock.patch(
                'fuel_upgrade.upgrade.exec_cmd',
                side_effect=errors.ExecutedErrorNonZeroExitCode(
                    'error')) as cmd_mock:

            self.assertRaises(
                errors.ExecutedErrorNonZeroExitCode,
                self.upgrader.backup_db)

        self.assert_pg_dump(cmd_mock)
        remove.assert_called_once_with(self.pg_dump_path)

    @mock.patch('fuel_upgrade.upgrade.time.sleep')
    def test_run_with_retries(self, sleep, _):
        image_name = 'test_image'
        retries_count = 3

        with self.assertRaises(errors.DockerExecutedErrorNonZeroExitCode):
            self.upgrader.run(
                image_name,
                retry_interval=1,
                retries_count=retries_count)

        self.assertEquals(sleep.call_count, retries_count)
        self.called_once(self.client_mock.create_container)

    def test_run_without_errors(self, exec_cmd):
        image_name = 'test_image'
        self.client_mock.wait.return_value = 0

        self.upgrader.run(image_name)

        self.called_once(self.client_mock.create_container)
        self.called_once(self.client_mock.logs)
        self.called_once(self.client_mock.start)
        self.called_once(self.client_mock.wait)
