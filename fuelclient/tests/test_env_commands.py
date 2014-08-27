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
import sys

from fuelclient.cli import error
from fuelclient import client
from fuelclient.commands import environment_commands

from tests import base


class TestEnvCreate(base.BaseTestCommand):
    request_to_mock = 'post_request'
    return_data = [{'id': 1, 'name': 'test', 'mode': 'ha',
                    'status': 'new', 'net_provider': 'nova',
                    'release_id': 1, 'changes': [{}],
                    'not_displayable': None}]

    command_class = environment_commands.EnvCreate

    def test_env_creation(self):
        cmd_args = ['test', '1', '--mode', 'ha']

        self.verify_show_command(
            cmd_args,
            self.command_class.columns_names,
            return_value=self.return_data[0]
        )

    def test_env_creation_nst_arguments_check(self):
        cmd_args = ['test', '1', '--net', 'neutron']
        self.assertRaises(error.ArgumentException, self._fake_execute_cmd,
                          self.cmd, cmd_args)

    def test_env_create_with_proper_data(self):
        url = 'clusters/'
        data_to_send = {
            'name': 'test',
            'release_id': 1,
            'mode': 'ha_compact',
            'net_provider': 'nova_network',
            'net_segment_type': None,
            'nodes': [],
            'tasks': []
        }
        cmd_args = ['test', '1', '--net', 'nova', '--mode', 'ha']

        self.check_request_mock_called_with_args(
            cmd_args, self.return_data[0], url, data_to_send
        )

    def test_env_create_name_decode(self):
        url = 'clusters/'

        byte_name = 'тест'
        # imitation of name passing with different shell locale
        byte_name = \
            byte_name\
            .decode(sys.getfilesystemencoding())\
            .encode('cp1251')

        cmd_args = [byte_name, '1', '--net', 'nova', '--mode', 'ha']

        data_to_send = {
            # name should be decoded into UTF using default shell encoding
            'name': byte_name.decode('cp1251'),

            'release_id': 1,
            'mode': 'ha_compact',
            'net_provider': 'nova_network',
            'net_segment_type': None,
            'nodes': [],
            'tasks': []
        }

        def getfilesystemencoding_mock(*args, **kwargs):
            return 'cp1251'

        with mock.patch('sys.getfilesystemencoding',
                        getfilesystemencoding_mock):
            self.check_request_mock_called_with_args(cmd_args,
                                                     self.return_data[0],
                                                     url,
                                                     data_to_send)


class TestEnvDelete(base.BaseTestCommand):
    cmd_args = ['1']
    request_to_mock = 'delete_request'

    command_class = environment_commands.EnvDelete

    def test_delete_command(self):
        expected_output = "Environment with id 1 was deleted\n"

        with mock.patch.object(client.APIClient, self.request_to_mock):
            self._fake_execute_cmd(self.cmd, self.cmd_args)

        self.assertEqual(self.fake_stdout.make_string(), expected_output)

    def test_delete_supply_proper_id(self):
        url = 'clusters/1/'
        self.check_request_mock_called_with_args(self.cmd_args, None, url)


class TestEnvShow(base.BaseTestCommand):
    cmd_args = ['1']
    request_to_mock = 'get_request'
    return_data = [{'id': 1, 'name': 'test', 'mode': 'ha',
                    'status': 'new', 'net_provider': 'nova',
                    'release_id': 1, 'changes': [{}],
                    'not_displayable': None}]

    command_class = environment_commands.EnvShow

    def test_show_env(self):
        self.verify_show_command(
            self.cmd_args,
            self.command_class.columns_names,
            return_value=self.return_data[0]
        )

    def test_get_http_request_with_proper_args(self):
        url = 'clusters/1/'
        self.check_request_mock_called_with_args(
            self.cmd_args,
            self.return_data[0],
            url)


class TestEnvList(base.BaseTestCommand):
    request_to_mock = 'get_request'
    return_data = [
        {'id': 1, 'name': 'test', 'mode': 'ha',
         'status': 'new', 'net_provider': 'nova',
         'release_id': 1, 'changes': [{}],
         'not_displayable': None},

        {'id': 2, 'name': 'test_two', 'mode': 'ha',
         'status': 'error', 'net_provider': 'neutron',
         'release_id': 2, 'changes': [{}],
         'not_displayable': None},

        {'id': 3, 'name': 'test', 'mode': 'multinode',
         'status': 'operational', 'net_provider': 'nova',
         'release_id': 1, 'changes': [{}],
         'not_displayable': None}
    ]

    command_class = environment_commands.EnvList

    def test_env_list(self):
        self.verify_show_command(
            [],
            self.command_class.columns_names,
            return_value=self.return_data
        )


class TestEnvUpdate(base.BaseTestCommand):
    request_to_mock = 'put_request'
    return_data = [{'id': 1, 'name': 'test', 'mode': 'multinode',
                    'status': 'new', 'net_provider': 'nova',
                    'release_id': 1, 'changes': [{}],
                    'not_displayable': None}]

    command_class = environment_commands.EnvUpdate

    def test_env_update_successfully(self):
        cmd_args = ['1', 'test', 'multinode']
        self.verify_show_command(
            cmd_args,
            self.command_class.columns_names,
            return_value=self.return_data[0]
        )

    def test_update_http_request_with_proper_args(self):
        cmd_args = ['1', 'test', 'ha']
        url = 'clusters/1/'
        data_to_send = {
            'mode': 'ha_compact',
            'name': 'test'
        }
        self.check_request_mock_called_with_args(
            cmd_args,
            self.return_data[0],
            url,
            data_to_send
        )


class TestEnvUpgrade(base.BaseTestCommand):
    cmd_args = ['1', '2']
    request_to_mock = 'put_request'
    return_value = {'id': 1}

    command_class = environment_commands.EnvUpgrade

    def test_environment_updagrade_successfully(self):
        expected_output = ("Update process for environment has been started. "
                           "Update task id is 1\n")
        with mock.patch.object(client.APIClient, self.request_to_mock,
                               return_value=self.return_value):
            self._fake_execute_cmd(self.cmd, self.cmd_args)

        self.assertEqual(self.fake_stdout.make_string(), expected_output)

    def test_put_http_request_with_proper_args(self):
        url = 'clusters/1/update/'
        data_to_send = {}
        self.check_request_mock_called_with_args(self.cmd_args,
                                                 self.return_value,
                                                 url,
                                                 data_to_send)
