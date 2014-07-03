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

from fuel_upgrade.engines.openstack import OpenStackUpgrader
from fuel_upgrade.tests.base import BaseTestCase


class TestOpenStackUpgrader(BaseTestCase):
    releases_sample = '''
        [{
          "pk": 1,
          "fields": {
            "name": "releases name",
            "version": "2014.1",
            "operating_system": "CentOS",

            "orchestrator_data": {
              "repo_metadata": {
                "nailgun": "http://{master_ip}:8080/path/to/repo",
              },
              "puppet_manifests_source": "rsync://{master_ip}:/some/path",
              "puppet_modules_source": "rsync://{master_ip}:/some/path"
            }
          }
        }]
    '''

    def setUp(self):
        """Create upgrader with mocked data.
        """
        with mock.patch(
                'fuel_upgrade.engines.openstack.io.open',
                self.mock_open(self.releases_sample)):
            self.upgrader = OpenStackUpgrader(self.fake_config)

    def test_constructor_load_releases(self):
        self.assertEqual(len(self.upgrader.releases), 1)

    def test_constructor_update_conf(self):
        orchestrator_data = self.upgrader.releases[0]['orchestrator_data']

        self.assertEqual(
            orchestrator_data['repo_metadata']['nailgun'],
            'http://0.0.0.0:8080/path/to/repo')

        self.assertEqual(
            orchestrator_data['puppet_manifests_source'],
            'rsync://0.0.0.0:/some/path')

        self.assertEqual(
            orchestrator_data['puppet_modules_source'],
            'rsync://0.0.0.0:/some/path')

    def test_constructor_without_orchestration_data_in_releases(self):
        releases_sample = '''
            [{ "pk": 1,
               "fields": { "name": "releases name",
                           "version": "2014.1",
                           "operating_system": "CentOS"
                         }
             },
             { "pk": 2,
               "fields": { "name": "Ubuntu",
                           "version": "2014.1",
                           "operating_system": "Ubuntu"
                         }
            }]
        '''
        with mock.patch(
            'fuel_upgrade.engines.openstack.io.open',
            self.mock_open(releases_sample)
        ):
            self.upgrader = OpenStackUpgrader(self.fake_config)

        orchestrator_data = self.upgrader.releases[0]['orchestrator_data']
        self.assertEqual(
            orchestrator_data['repo_metadata']['nailgun'],
            'http://0.0.0.0:8080/9999/centos/x86_64')
        self.assertEqual(
            orchestrator_data['puppet_manifests_source'],
            'rsync://0.0.0.0:/puppet/9999/manifests/')
        self.assertEqual(
            orchestrator_data['puppet_modules_source'],
            'rsync://0.0.0.0:/puppet/9999/modules/')

        orchestrator_data = self.upgrader.releases[1]['orchestrator_data']
        self.assertEqual(
            orchestrator_data['repo_metadata']['nailgun'],
            'http://0.0.0.0:8080/9999/ubuntu/x86_64 precise main')

    @mock.patch(
        'fuel_upgrade.engines.openstack.OpenStackUpgrader.install_repos')
    @mock.patch(
        'fuel_upgrade.engines.openstack.OpenStackUpgrader.install_puppets')
    @mock.patch(
        'fuel_upgrade.engines.openstack.OpenStackUpgrader.install_releases')
    def test_upgrade(self, i_releases, i_puppets, i_repos):
        self.upgrader.upgrade()

        self.assertTrue(i_repos.called)
        self.assertTrue(i_puppets.called)
        self.assertTrue(i_releases.called)

    @mock.patch(
        'fuel_upgrade.engines.openstack.OpenStackUpgrader.install_repos')
    @mock.patch(
        'fuel_upgrade.engines.openstack.OpenStackUpgrader.install_puppets')
    @mock.patch(
        'fuel_upgrade.engines.openstack.OpenStackUpgrader.install_releases')
    def test_upgrade_with_errors(self, i_releases, i_puppets, i_repos):
        class MyException(Exception):
            pass

        i_puppets.side_effect = MyException('Folder does no exist')

        self.assertRaises(MyException, self.upgrader.upgrade)

        self.assertTrue(i_repos.called)
        self.assertTrue(i_puppets.called)
        self.assertFalse(i_releases.called)

    @mock.patch(
        'fuel_upgrade.engines.openstack.OpenStackUpgrader.remove_repos')
    @mock.patch(
        'fuel_upgrade.engines.openstack.OpenStackUpgrader.remove_puppets')
    @mock.patch(
        'fuel_upgrade.engines.openstack.OpenStackUpgrader.remove_releases')
    def test_rollback(self, r_releases, r_puppets, r_repos):
        self.upgrader.rollback()

        self.assertTrue(r_repos.called)
        self.assertTrue(r_puppets.called)
        self.assertTrue(r_releases.called)

    @mock.patch('fuel_upgrade.engines.openstack.utils.copytree')
    def test_install_repos(self, copytree):
        self.upgrader.install_repos()

        copytree.assert_any_call(
            self.upgrader.config.openstack['repos']['centos']['src'],
            self.upgrader.config.openstack['repos']['centos']['dst'])
        copytree.assert_any_call(
            self.upgrader.config.openstack['repos']['ubuntu']['src'],
            self.upgrader.config.openstack['repos']['ubuntu']['dst'])

    @mock.patch('fuel_upgrade.engines.openstack.utils.copytree')
    def test_install_puppets(self, copytree):
        self.upgrader.install_puppets()

        copytree.assert_any_call(
            self.upgrader.config.openstack['puppets']['modules']['src'],
            self.upgrader.config.openstack['puppets']['modules']['dst'])
        copytree.assert_any_call(
            self.upgrader.config.openstack['puppets']['manifests']['src'],
            self.upgrader.config.openstack['puppets']['manifests']['dst'])

    @mock.patch(
        'fuel_upgrade.engines.openstack.NailgunClient.create_notification')
    @mock.patch(
        'fuel_upgrade.engines.openstack.NailgunClient.create_release')
    @mock.patch(
        'fuel_upgrade.engines.openstack.NailgunClient.get_releases',
        return_value=[])
    def test_install_releases(self, _, mock_cr, mock_cn):
        # test one release
        mock_cr.return_value = {'id': '1'}
        mock_cn.return_value = {'id': '100'}

        self.upgrader.install_releases()

        self.assertTrue(mock_cr.called)
        self.assertTrue(mock_cn.called)

        for type_ in ('release', 'notification'):
            self.assertEqual(len(self.upgrader._rollback_ids[type_]), 1)

    @mock.patch(
        'fuel_upgrade.engines.openstack.NailgunClient.create_notification')
    @mock.patch(
        'fuel_upgrade.engines.openstack.NailgunClient.create_release')
    @mock.patch(
        'fuel_upgrade.engines.openstack.NailgunClient.get_releases',
        return_value=[])
    def test_install_releases_with_errors(self, _, mock_cr, mock_cn):
        mock_cr.return_value = {'id': '1'}
        mock_cn.side_effect = requests.exceptions.HTTPError('Something wrong')

        self.assertRaises(
            requests.exceptions.HTTPError, self.upgrader.install_releases)
        self.assertTrue(mock_cr.called)
        self.assertTrue(mock_cn.called)

        self.assertEqual(len(self.upgrader._rollback_ids['release']), 1)
        self.assertEqual(len(self.upgrader._rollback_ids['notification']), 0)

    @mock.patch('fuel_upgrade.engines.openstack.utils.rmtree')
    def test_remove_repos(self, rmtree):
        self.upgrader.remove_repos()

        rmtree.assert_any_call(
            self.upgrader.config.openstack['repos']['centos']['dst'])
        rmtree.assert_any_call(
            self.upgrader.config.openstack['repos']['ubuntu']['dst'])

    @mock.patch('fuel_upgrade.engines.openstack.utils.rmtree')
    def test_remove_puppets(self, rmtree):
        self.upgrader.remove_puppets()

        rmtree.assert_any_call(
            self.upgrader.config.openstack['puppets']['modules']['dst'])
        rmtree.assert_any_call(
            self.upgrader.config.openstack['puppets']['manifests']['dst'])

    @mock.patch(
        'fuel_upgrade.engines.openstack.NailgunClient.remove_notification')
    @mock.patch(
        'fuel_upgrade.engines.openstack.NailgunClient.remove_release')
    def test_remove_releases(self, r_release, r_notification):
        self.upgrader._rollback_ids['release'] = [1, 3]
        self.upgrader._rollback_ids['notification'] = [2, 4]

        self.upgrader.remove_releases()

        r_release.assert_has_calls([
            mock.call(3),
            mock.call(1)])
        r_notification.assert_has_calls([
            mock.call(4),
            mock.call(2)])

    def test_get_unique_releases(self):
        releases = [
            {
                'name': 'Ubuntu',
                'version': 'A',
            },
            {
                'name': 'Centos',
                'version': 'A',
            },
        ]

        existing_releases = [
            {
                'name': 'Ubuntu',
                'version': 'A',
            },
            {
                'name': 'Centos',
                'version': 'B',
            },
        ]

        expected_releases = [
            {
                'name': 'Centos',
                'version': 'A',
            },
        ]

        self.assertEqual(
            self.upgrader._get_unique_releases(releases, existing_releases),
            expected_releases)

    @mock.patch('fuel_upgrade.engines.docker_engine.utils.dir_size',
                return_value=5)
    def test_required_free_space(self, _):
        self.assertEqual(
            self.upgrader.required_free_space,
            {'/etc/puppet/9999/manifests': 5,
             '/etc/puppet/9999/modules': 5,
             '/var/www/nailgun/9999/centos': 5,
             '/var/www/nailgun/9999/ubuntu': 5})
