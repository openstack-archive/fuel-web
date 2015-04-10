#    Copyright 2015 Mirantis, Inc.
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
import unittest2

from fuel_package_updates import repo


class TestRepo(unittest2.TestCase):

    def setUp(self):
        self._settings_patcher = mock.patch(
            'fuel_package_updates.repo.SETTINGS',
            port=8000,
            keystone_creds={
                'username': 'admin',
                'password': 'admin',
                'tenant_name': 'admin'
            },
            updates_destinations={
                'centos': '{0}/centos/updates',
                'ubuntu': '{0}/ubuntu/updates',
            },
            httproot='/var/www/nailgun',
        )
        self.settings = self._settings_patcher.start()

    def tearDown(self):
        self._settings_patcher.stop()

    def test_supported_distros_implemented(self):
        for distro in repo.RepoManager.supported_distros:
            self.assertTrue(
                hasattr(repo.RepoManager, "_get_{}_repos".format(distro)))

    @mock.patch('os.path.exists', return_value=True)
    def test_get_repos_ubuntu(self, mexists):
        options = mock.Mock(
            distro="ubuntu",
            ip="10.0.0.20",
            release="2014.2-6.1",
            url="http://mirror.fuel-infra.org/repos/patching-test/ubuntu/"
        )
        repo_manager = repo.RepoManager(options)

        uri = "http://10.0.0.20:8000/2014.2-6.1/ubuntu/updates"

        self.assertTrue(all(repo['uri'] == uri for repo in repo_manager.repos))

        self.assertTrue(
            all(repo['priority'] == 1100 for repo in repo_manager.repos
                if "holdback" in repo['name']))

    @mock.patch('os.path.exists', return_value=True)
    def test_get_repos_centos(self, mexists):
        options = mock.Mock(
            distro="centos",
            ip="10.0.0.20",
            release="2014.2-6.1",
            url="http://mirror.fuel-infra.org/repos/patching-test/centos/"
        )
        repo_manager = repo.RepoManager(options)

        uri = "http://10.0.0.20:8000/2014.2-6.1/centos/updates"

        self.assertTrue(all(repo['uri'] == uri for repo in repo_manager.repos))
        self.assertTrue(
            all(repo['priority'] == 1100 for repo in repo_manager.repos
                if "holdback" in repo['name']))

    def test_distro_not_in_supported_distros(self):
        not_implemented_distro = 'ForSureNotImplemented_distro'
        options = mock.Mock(distro=not_implemented_distro)

        with self.assertRaises(NotImplementedError):
            repo.RepoManager(options)

    @mock.patch(
        'fuel_package_updates.repo.RepoManager.supported_distros',
        new_callable=mock.PropertyMock)
    @mock.patch('os.path.exists', return_value=True)
    def test_distro_not_implemented(self, mexists, msupported_distros):
        not_implemented_distro = 'ForSureNotImplemented_distro'
        msupported_distros.return_value = (not_implemented_distro,)

        options = mock.Mock(
            distro=not_implemented_distro,
            ip="10.0.0.20",
            release="2014.2-6.1",
            url="http://mirror.fuel-infra.org/repos/patching-test/ubuntu/"
        )

        self.settings.updates_destinations = {
            not_implemented_distro: '{0}/%s/updates' % not_implemented_distro,
        }

        repo_manager = repo.RepoManager(options)
        with self.assertRaises(AttributeError):
            repo_manager.repos
