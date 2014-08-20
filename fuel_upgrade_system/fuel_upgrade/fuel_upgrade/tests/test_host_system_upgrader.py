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
        self.upgrader = HostSystemUpgrader(self.fake_config)

    @mock.patch(
        'fuel_upgrade.engines.host_system.HostSystemUpgrader.update_repo')
    @mock.patch(
        'fuel_upgrade.engines.host_system.HostSystemUpgrader.run_puppet')
    @mock.patch(
        'fuel_upgrade.engines.host_system.utils')
    def test_upgrade(self, mock_utils, run_puppet_mock, update_repo_mock):
        self.upgrader.upgrade()

        mock_utils.copy.assert_called_once_with(
            '/tmp/upgrade_path/repos/2014.1.1-5.1/centos/x86_64',
            '/var/www/nailgun/2014.1.1-5.1/centos/x86_64')
        self.called_once(run_puppet_mock)
        self.called_once(update_repo_mock)

    @mock.patch('fuel_upgrade.engines.host_system.utils')
    def test_update_repo(self, utils_mock):
        self.upgrader.update_repo()
        templates_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '../templates'))
        utils_mock.render_template_to_file.assert_called_once_with(
            '{0}/nailgun.repo'.format(templates_path),
            '/etc/yum.repos.d/9999_nailgun.repo',
            {'version': '9999',
             'repo_path': '/var/www/nailgun/2014.1.1-5.1/centos/x86_64'})

    @mock.patch('fuel_upgrade.engines.host_system.utils')
    def test_run_puppet(self, utils_mock):
        self.upgrader.run_puppet()
        utils_mock.exec_cmd.assert_called_once_with(
            'puppet apply -d -v '
            '/tmp/upgrade_path/puppet/2014.1.1-5.1/modules/nailgun/examples'
            '/host-upgrade.pp '
            '--modulepath=/tmp/upgrade_path/puppet/2014.1.1-5.1/modules')

    @mock.patch(
        'fuel_upgrade.engines.host_system.'
        'HostSystemUpgrader.remove_repo_config')
    def test_rollback(self, remove_repo_config_mock):
        self.upgrader.rollback()
        self.called_once(remove_repo_config_mock)

    def test_on_success_does_not_raise_exceptions(self):
        self.upgrader.on_success()

    @mock.patch('fuel_upgrade.engines.host_system.utils')
    def test_remove_repo_config(self, utils_mock):
        self.upgrader.remove_repo_config()
        utils_mock.remove_if_exists.assert_called_once_with(
            '/etc/yum.repos.d/9999_nailgun.repo')

    def test_required_free_space(self):
        self.assertEqual(
            self.upgrader.required_free_space,
            {'/etc/yum.repos.d/9999_nailgun.repo': 10})
