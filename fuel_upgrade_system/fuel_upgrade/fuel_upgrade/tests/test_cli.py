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
from fuel_upgrade import messages

from fuel_upgrade.cli import parse_args
from fuel_upgrade.cli import run_upgrade
from fuel_upgrade.tests.base import BaseTestCase


@mock.patch('fuel_upgrade.cli.CheckerManager', mock.Mock())
@mock.patch('fuel_upgrade.cli.PreUpgradeHookManager', mock.Mock())
@mock.patch('fuel_upgrade.cli.UpgradeManager', mock.Mock())
@mock.patch('fuel_upgrade.cli.build_config')
class TestAdminPassword(BaseTestCase):

    default_args = ['host-system', '--src', '/path']

    def get_args(self, args):
        return parse_args(args)

    def test_use_password_arg(self, mbuild_config):
        password = '12345678'
        args = self.get_args(self.default_args + ['--password', password])
        run_upgrade(args)

        mbuild_config.assert_called_once_with(
            mock.ANY, password
        )

    @mock.patch('fuel_upgrade.cli.getpass')
    def test_ask_for_password(self, mgetpass, mbuild_config):
        password = '987654321'
        mgetpass.getpass.return_value = password

        args = self.get_args(self.default_args)
        run_upgrade(args)

        mbuild_config.assert_called_once_with(
            mock.ANY, password
        )

    @mock.patch('fuel_upgrade.cli.getpass')
    def test_no_password_provided(self, mgetpass, mbuild_config):
        password = ''
        mgetpass.getpass.return_value = password

        with self.assertRaisesRegexp(errors.CommandError,
                                     messages.no_password_provided):
            args = self.get_args(self.default_args)
            run_upgrade(args)
