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
import six

from fuel_upgrade import errors
from fuel_upgrade import messages

from fuel_upgrade.cli import get_non_unique
from fuel_upgrade.cli import parse_args
from fuel_upgrade.cli import run_upgrade
from fuel_upgrade.tests.base import BaseTestCase


@mock.patch('fuel_upgrade.engines.host_system.SupervisorClient', mock.Mock())
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


class TestArgumentsParser(BaseTestCase):
    default_args = ['--src', '/path']

    def test_parse_list_of_systems(self):
        systems = ['host-system', 'docker']
        args = parse_args(systems + self.default_args)
        self.assertEqual(systems, args.systems)

    @mock.patch('argparse.ArgumentParser.error')
    def test_error_if_systems_have_duplicates(self, error_mock):
        parse_args(
            ['host-system', 'docker', 'openstack', 'openstack', 'docker'] +
            self.default_args
        )
        self.assertEqual(1, error_mock.call_count)
        self.assertEqual(1, len(error_mock.call_args[0]))
        self.assertIn('"docker, openstack"', error_mock.call_args[0][0])

    @mock.patch('argparse.ArgumentParser.error')
    def test_error_if_systems_are_incompatible(self, error_mock):
        parse_args(
            ['docker', 'docker-init'] + self.default_args
        )
        self.assertEqual(1, error_mock.call_count)
        self.assertEqual(1, len(error_mock.call_args[0]))
        self.assertIn('"docker-init, docker"', error_mock.call_args[0][0])


class TestGetNonUnique(BaseTestCase):
    def test_get_duplicates(self):
        self.assertEqual([2, 3], list(get_non_unique([2, 2, 2, 3, 3, 1])))

    def test_empty_if_no_duplicates(self):
        self.assertEqual([], list(get_non_unique(six.moves.range(3))))

    def test_empty_if_empty_input(self):
        self.assertEqual([], list(get_non_unique([])))
