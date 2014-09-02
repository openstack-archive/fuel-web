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
import xmlrpclib

from fuel_upgrade.clients import SupervisorClient
from fuel_upgrade.tests.base import BaseTestCase


@mock.patch('fuel_upgrade.clients.supervisor_client.os')
class TestSupervisorClient(BaseTestCase):

    def setUp(self):
        self.utils_patcher = mock.patch(
            'fuel_upgrade.clients.supervisor_client.utils')
        self.utils_mock = self.utils_patcher.start()

        self.supervisor = SupervisorClient(self.fake_config, '0')
        type(self.supervisor).supervisor = mock.PropertyMock()

        self.new_version_supervisor_path = '/etc/supervisord.d/9999'
        self.previous_version_supervisor_path = '/etc/supervisord.d/0'

    def tearDown(self):
        self.utils_patcher.stop()

    def test_switch_to_new_configs(self, os_mock):
        self.supervisor.switch_to_new_configs()
        self.utils_mock.symlink.assert_called_once_with(
            self.new_version_supervisor_path,
            self.fake_config.supervisor['current_configs_prefix'])

    def test_switch_to_previous_configs(self, os_mock):
        self.supervisor.switch_to_previous_configs()
        self.utils_mock.symlink.assert_called_once_with(
            self.previous_version_supervisor_path,
            self.fake_config.supervisor['current_configs_prefix'])

    def test_stop_all_services(self, _):
        self.supervisor.stop_all_services()
        self.supervisor.supervisor.stopAllProcesses.assert_called_once_with()

    def test_restart_and_wait(self, _):
        self.supervisor.restart_and_wait()
        self.supervisor.supervisor.restart.assert_called_once_with()
        self.utils_mock.wait_for_true.assert_called_once_with(
            self.supervisor.get_all_processes_safely,
            timeout=600)

    def test_get_all_processes_safely(self, _):
        self.supervisor.get_all_processes_safely()
        self.supervisor.supervisor.getAllProcessInfo.assert_called_once_with()

    def test_get_all_processes_safely_does_not_raise_error(self, _):
        for exc in (IOError(), xmlrpclib.Fault('', '')):
            self.supervisor.supervisor.getAllProcessInfo.side_effect = exc
            self.assertIsNone(self.supervisor.get_all_processes_safely())

    def test_generate_configs(self, _):
        services = [
            {'config_name': 'config_name1',
             'service_name': 'service_name1',
             'command': 'cmd1',
             'autostart': True},
            {'config_name': 'config_name2',
             'service_name': 'service_name2',
             'command': 'cmd2',
             'autostart': False}]

        self.supervisor.generate_config = mock.MagicMock()
        self.supervisor.generate_configs(services)
        self.assertEqual(
            self.supervisor.generate_config.call_args_list,
            [mock.call('config_name1', 'service_name1',
                       'cmd1', autostart=True),
             mock.call('config_name2', 'service_name2',
                       'cmd2', autostart=False)])

    def test_generate_config(self, _):
        config_path = '/config/path'
        with mock.patch('fuel_upgrade.clients.supervisor_client.os.path.join',
                        return_value=config_path):
            self.supervisor.generate_config(
                'confing_name1', 'docker-service_name1', 'command1')

        self.utils_mock.render_template_to_file.assert_called_once_with(
            self.supervisor.supervisor_template_path,
            config_path,
            {'service_name': 'docker-service_name1',
             'command': 'command1',
             'log_path': '/var/log/docker-service_name1.log',
             'autostart': 'true'})

    def test_generate_cobbler_config(self, _):
        paths = ['script_path', '/path/cobbler_config', '']
        self.supervisor.generate_config = mock.MagicMock()
        with mock.patch(
                'fuel_upgrade.clients.supervisor_client.os.path.join',
                side_effect=paths):

            self.supervisor.generate_cobbler_config(
                'config_name1',
                'service_name1',
                'container_name1',
                autostart=False)

        self.utils_mock.render_template_to_file.assert_called_once_with(
            paths[0],
            paths[1],
            {'container_name': 'container_name1'})

        self.supervisor.generate_config.assert_called_once_with(
            'config_name1',
            'service_name1',
            'container_name1',
            autostart=False)
