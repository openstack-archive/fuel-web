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


class TestHostSystemUpgrader(BaseTestCase):

    def setUp(self):
        with mock.patch('fuel_upgrade.engines.host_system.SupervisorClient'):
            self.upgrader = HostSystemUpgrader(self.fake_config)
        self.upgrader.supervisor = mock.Mock()

    @mock.patch(
        'fuel_upgrade.engines.host_system.HostSystemUpgrader.install_repos')
    @mock.patch(
        'fuel_upgrade.engines.host_system.HostSystemUpgrader.update_repo')
    @mock.patch(
        'fuel_upgrade.engines.host_system.HostSystemUpgrader.run_puppet')
    @mock.patch(
        'fuel_upgrade.engines.host_system.utils')
    def test_upgrade(self, mock_utils, run_puppet_mock, update_repo_mock,
                     install_repos_mock):
        self.upgrader.upgrade()

        self.called_once(install_repos_mock)
        self.called_once(run_puppet_mock)
        self.called_once(update_repo_mock)
        self.called_once(self.upgrader.supervisor.stop_all_services)
        mock_utils.exec_cmd.assert_called_with(
            'yum install -v -y fuel-9999.0.0')

    @mock.patch('fuel_upgrade.engines.host_system.utils')
    def test_update_repo(self, utils_mock):
        self.upgrader.update_repo()
        templates_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '../templates'))
        utils_mock.render_template_to_file.assert_called_once_with(
            '{0}/nailgun.repo'.format(templates_path),
            '/etc/yum.repos.d/9999_nailgun.repo',
            {
                'name': '9999_nailgun',
                'baseurl': 'file:/var/www/nailgun/2014.1.1-5.1/centos/x86_64',
                'gpgcheck': 0,
                'skip_if_unavailable': 0,
            })

    @mock.patch('fuel_upgrade.engines.host_system.utils')
    def test_run_puppet(self, utils_mock):
        self.upgrader.run_puppet()
        utils_mock.exec_cmd.assert_called_once_with(
            'puppet apply -d -v '
            '/etc/puppet/2014.1.1-5.1/modules/nailgun/examples'
            '/host-upgrade.pp '
            '--modulepath=/etc/puppet/2014.1.1-5.1/modules')

    @mock.patch(
        'fuel_upgrade.engines.host_system.HostSystemUpgrader.remove_repos')
    @mock.patch(
        'fuel_upgrade.engines.host_system.'
        'HostSystemUpgrader.remove_repo_config')
    def test_rollback(self, remove_repo_config_mock, remove_repos_mock):
        self.upgrader.rollback()
        self.called_once(remove_repo_config_mock)
        self.called_once(remove_repos_mock)
        self.called_once(self.upgrader.supervisor.start_all_services)

    @mock.patch('fuel_upgrade.engines.host_system.utils.remove_if_exists')
    def test_remove_repo_config(self, remove_mock):
        self.upgrader.config.from_version = '6.0'
        self.upgrader.remove_repo_config()
        self.assertEqual(remove_mock.call_args_list, [
            mock.call('/etc/yum.repos.d/9999_nailgun.repo'),
            mock.call('/etc/yum.repos.d/auxiliary.repo'),
        ])

    @mock.patch('fuel_upgrade.engines.host_system.utils.remove_if_exists')
    def test_remove_repo_config_for_fuel_ge_61(self, remove_mock):
        self.upgrader.config.from_version = '6.1'
        self.upgrader.config.new_version = '7.0'
        self.upgrader.remove_repo_config()
        self.assertEqual(remove_mock.call_args_list, [
            mock.call('/etc/yum.repos.d/9999_nailgun.repo'),
            mock.call('/etc/yum.repos.d/7.0_auxiliary.repo'),
        ])

    @mock.patch('fuel_upgrade.engines.host_system.utils.copy')
    @mock.patch('fuel_upgrade.engines.host_system.glob.glob')
    def test_install_repos(self, glob, copy):
        glob.return_value = ['one', 'two']
        self.upgrader.install_repos()

        self.called_times(copy, 2)

        copy.assert_has_calls([
            mock.call('one', '/var/www/nailgun/one'),
            mock.call('two', '/var/www/nailgun/two')])
        glob.assert_called_with('/tmp/upgrade_path/repos/[0-9.-]*')

    @mock.patch('fuel_upgrade.engines.host_system.utils.remove')
    @mock.patch('fuel_upgrade.engines.host_system.glob.glob')
    def test_remove_repos(self, glob, remove):
        glob.return_value = ['one', 'two']
        self.upgrader.remove_repos()

        self.called_times(remove, 2)

        remove.assert_has_calls([
            mock.call('/var/www/nailgun/one'),
            mock.call('/var/www/nailgun/two')])
        glob.assert_called_with('/tmp/upgrade_path/repos/[0-9.-]*')

    @mock.patch(
        'fuel_upgrade.engines.openstack.utils.os.path.isdir',
        return_value=True)
    @mock.patch(
        'fuel_upgrade.engines.openstack.utils.dir_size', return_value=42)
    @mock.patch(
        'fuel_upgrade.engines.openstack.glob.glob', return_value=['1', '2'])
    def test_required_free_space(self, glob, __, ___):
        self.assertEqual(
            self.upgrader.required_free_space,
            {'/etc/yum.repos.d/9999_nailgun.repo': 10,
             '/var/www/nailgun': 84})
        glob.assert_called_with('/tmp/upgrade_path/repos/[0-9.-]*')
