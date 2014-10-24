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
from fuel_upgrade import errors
from fuel_upgrade.tests.base import BaseTestCase


class TestOpenStackUpgrader(BaseTestCase):
    releases_raw = '''
        [{
          "pk": 1,
          "fields": {
            "name": "releases name",
            "version": "2014.1",
            "operating_system": "CentOS",
          }
        }]
    '''

    metadata_raw = '''
    diff_releases:
       2012.2-6.0: 2014.1.1-5.1
    '''

    @mock.patch(
        'fuel_upgrade.engines.openstack.glob.glob', return_value=['path'])
    def setUp(self, _):
        """Create upgrader with mocked data.
        """
        with mock.patch('fuel_upgrade.engines.openstack.io.open',
                        self.mock_open(self.releases_raw)):
            self.upgrader = OpenStackUpgrader(self.fake_config)

    def test_constructor_load_releases(self):
        self.assertEqual(len(self.upgrader.releases), 1)

    def test_constructor_read_releases(self):
        orchestrator_data = self.upgrader.releases[0]['orchestrator_data']

        self.assertEqual(
            orchestrator_data['repo_metadata']['2014.1'],
            'http://{MASTER_IP}:8080/{OPENSTACK_VERSION}/centos/x86_64')

        self.assertEqual(
            orchestrator_data['puppet_manifests_source'],
            'rsync://{MASTER_IP}:/puppet/{OPENSTACK_VERSION}/manifests/')

        self.assertEqual(
            orchestrator_data['puppet_modules_source'],
            'rsync://{MASTER_IP}:/puppet/{OPENSTACK_VERSION}/modules/')

    @mock.patch(
        'fuel_upgrade.engines.openstack.OpenStackUpgrader.install_versions')
    @mock.patch(
        'fuel_upgrade.engines.openstack.OpenStackUpgrader.install_releases')
    @mock.patch(
        'fuel_upgrade.engines.openstack.OpenStackUpgrader.install_repos')
    @mock.patch(
        'fuel_upgrade.engines.openstack.OpenStackUpgrader.install_puppets')
    def test_upgrade(self, pup, rep, rel, ver):
        self.upgrader.upgrade()

        self.called_once(pup)
        self.called_once(rep)
        self.called_once(rel)
        self.called_once(ver)

    def test_on_success_does_not_raise_errors(self):
        self.upgrader.on_success()

    @mock.patch('fuel_upgrade.engines.openstack.glob.glob',
                return_value=['/upgrade/file1.yaml', '/upgrade/file2.yaml'])
    @mock.patch('fuel_upgrade.engines.openstack.utils')
    def test_install_versions(self, mock_utils, mock_glob):
        self.upgrader.install_versions()

        release_versions_path = '/etc/fuel/release_versions'
        mock_utils.create_dir_if_not_exists.assert_called_once_with(
            release_versions_path)
        self.assertEqual(
            mock_utils.copy.call_args_list,
            [mock.call(
                '/upgrade/file1.yaml',
                '{0}/file1.yaml'.format(release_versions_path)),
             mock.call(
                 '/upgrade/file2.yaml',
                 '{0}/file2.yaml'.format(release_versions_path))])

    @mock.patch('fuel_upgrade.engines.openstack.glob.glob',
                return_value=['/upgrade/file1.yaml'])
    @mock.patch('fuel_upgrade.engines.openstack.utils')
    def test_remove_versions(self, mock_utils, mock_glob):
        self.upgrader.remove_versions()
        self.assertEqual(
            mock_utils.remove.call_args_list,
            [mock.call('/etc/fuel/release_versions/file1.yaml')])

    @mock.patch(
        'fuel_upgrade.engines.openstack.OpenStackUpgrader.install_releases')
    @mock.patch(
        'fuel_upgrade.engines.openstack.OpenStackUpgrader.install_repos')
    @mock.patch(
        'fuel_upgrade.engines.openstack.OpenStackUpgrader.install_puppets')
    def test_upgrade_with_errors(self, pup, rep, rel):
        class MyException(Exception):
            pass

        rep.side_effect = MyException('Folder does no exist')
        self.assertRaises(MyException, self.upgrader.upgrade)

        self.called_once(pup)
        self.called_once(rep)
        self.method_was_not_called(rel)

    @mock.patch(
        'fuel_upgrade.engines.openstack.OpenStackUpgrader.remove_versions')
    @mock.patch(
        'fuel_upgrade.engines.openstack.OpenStackUpgrader.remove_puppets')
    @mock.patch(
        'fuel_upgrade.engines.openstack.OpenStackUpgrader.remove_repos')
    @mock.patch(
        'fuel_upgrade.engines.openstack.OpenStackUpgrader.remove_releases')
    def test_rollback(self, rel, rep, pup, ver):
        self.upgrader.rollback()

        self.called_once(rel)
        self.called_once(rep)
        self.called_once(pup)
        self.called_once(ver)

    @mock.patch('fuel_upgrade.engines.openstack.utils.copy')
    @mock.patch('fuel_upgrade.engines.openstack.glob.glob')
    def test_install_puppets(self, glob, copy):
        glob.return_value = ['one', 'two']
        self.upgrader.install_puppets()

        self.called_times(copy, 2)

        copy.assert_has_calls([
            mock.call('one', '/etc/puppet/one'),
            mock.call('two', '/etc/puppet/two')])

    @mock.patch('fuel_upgrade.engines.openstack.utils.remove')
    @mock.patch('fuel_upgrade.engines.openstack.glob.glob')
    def test_remove_puppets(self, glob, remove):
        glob.return_value = ['one', 'two']
        self.upgrader.remove_puppets()

        self.called_times(remove, 2)

        remove.assert_has_calls([
            mock.call('/etc/puppet/one'),
            mock.call('/etc/puppet/two')])

    @mock.patch('fuel_upgrade.engines.openstack.utils.copy')
    @mock.patch('fuel_upgrade.engines.openstack.glob.glob')
    def test_install_repos(self, glob, copy):
        glob.return_value = ['one', 'two']
        self.upgrader.install_repos()

        self.called_times(copy, 2)

        copy.assert_has_calls([
            mock.call('one', '/var/www/nailgun/one'),
            mock.call('two', '/var/www/nailgun/two')])

    @mock.patch('fuel_upgrade.engines.openstack.utils.remove')
    @mock.patch('fuel_upgrade.engines.openstack.glob.glob')
    def test_remove_repos(self, glob, remove):
        glob.return_value = ['one', 'two']
        self.upgrader.remove_repos()

        self.called_times(remove, 2)

        remove.assert_has_calls([
            mock.call('/var/www/nailgun/one'),
            mock.call('/var/www/nailgun/two')])

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

        self.called_once(mock_cr)
        self.called_once(mock_cn)

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
        self.called_once(mock_cr)
        self.called_once(mock_cn)

        self.assertEqual(len(self.upgrader._rollback_ids['release']), 1)
        self.assertEqual(len(self.upgrader._rollback_ids['notification']), 0)

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

    @mock.patch(
        'fuel_upgrade.engines.openstack.utils.os.path.isdir',
        return_value=True)
    @mock.patch(
        'fuel_upgrade.engines.openstack.utils.dir_size', return_value=42)
    @mock.patch(
        'fuel_upgrade.engines.openstack.glob.glob', return_value=['1', '2'])
    def test_required_free_space(self, glob, _, __):
        result = self.upgrader.required_free_space
        self.assertEqual(result, {
            '/etc/puppet': 84,
            '/var/www/nailgun': 84,
        })

    @mock.patch(
        'fuel_upgrade.engines.openstack.os.path.exists', return_value=True)
    def test_add_base_repos_to_releases(self, _):
        with mock.patch('fuel_upgrade.engines.openstack.io.open',
                        self.mock_open(self.metadata_raw)):

            releases = [
                {
                    'name': 'A',
                    'version': '2012.2-6.0',
                    'operating_system': 'centos',
                    'orchestrator_data': {
                        'repo_metadata': {
                            '2012.2-6.0': 'path/to/6.0',
                        }
                    },
                }
            ]

            existing_releases = [
                {
                    'name': 'A',
                    'version': '2012.2-5.0',
                    'operating_system': 'centos',
                    'orchestrator_data': {
                        'repo_metadata': {
                            'nailgun': 'path/to/5.0',
                        }
                    },
                },
                {
                    'name': 'A',
                    'version': '2012.2-5.1',
                    'operating_system': 'centos',
                    'orchestrator_data': {
                        'repo_metadata': {
                            'nailgun': 'path/to/5.1',
                        }
                    },
                },
            ]

            self.upgrader._add_base_repos_to_releases(
                releases, existing_releases)

            self.assertEqual(
                releases[0]['orchestrator_data']['repo_metadata'], {
                    '2012.2-6.0': 'path/to/6.0',
                    'nailgun': 'path/to/5.1'})

    @mock.patch(
        'fuel_upgrade.engines.openstack.os.path.exists', return_value=True)
    def test_add_base_repos_to_releases_not_found(self, _):
        with mock.patch('fuel_upgrade.engines.openstack.io.open',
                        self.mock_open(self.metadata_raw)):
            releases = [
                {
                    'name': 'A',
                    'version': '2012.2-6.0',
                    'operating_system': 'centos',
                    'orchestrator_data': {
                        'repo_metadata': {
                            '2012.2-6.0': 'path/to/6.0',
                        }
                    },
                }
            ]

            self.assertRaises(
                errors.BaseReleaseNotFound,
                self.upgrader._add_base_repos_to_releases,
                releases, [])
