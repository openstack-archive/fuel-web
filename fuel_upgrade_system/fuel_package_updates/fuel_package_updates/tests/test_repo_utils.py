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

from fuel_package_updates import repo_utils


class TestRepoUtils(unittest2.TestCase):

    def test_repo_merge(self):
        repo_mos_updates = {
            "type": "deb",
            "name": "MOS-Updates",
            "uri": "some/uri",
        }
        repo_mos_security = {
            "type": "deb",
            "name": "mos6.1-security",
            "uri": "some/uri",
        }
        other_repos_moc_security = {
            "type": "rpm",
            "name": "mos6.1-security",
            "uri": "some/other_uri",
        }
        list_a = [repo_mos_updates, repo_mos_security]
        list_b = [other_repos_moc_security]
        check_merged = [repo_mos_updates, other_repos_moc_security]

        merged_repos = repo_utils.repo_merge(list_a, list_b)

        self.assertListEqual(merged_repos, check_merged)

    def test_get_repos_ubuntu(self):
        distro = "ubuntu"
        repopath = "/var/www/nailgun/2014.2-6.1/ubuntu/updates"
        ip = "10.0.0.20"
        port = 8000
        httproot = "/var/www/nailgun"

        uri = "http://10.0.0.20:8000/2014.2-6.1/ubuntu/updates"

        repos = repo_utils.get_repos(distro, repopath, ip, port, httproot)

        self.assertTrue(all(repo['uri'] == uri for repo in repos))

        self.assertTrue(
            all(repo['priority'] == 1100 for repo in repos
                if "holdback" in repo['name']))

    def test_get_repos_centos(self):
        distro = "centos"
        repopath = "/var/www/nailgun/2014.2-6.1/centos/updates"
        ip = "10.0.0.20"
        port = 8000
        httproot = "/var/www/nailgun"

        uri = "http://10.0.0.20:8000/2014.2-6.1/centos/updates"

        repos = repo_utils.get_repos(distro, repopath, ip, port, httproot)

        self.assertEqual(len(repos), 1)
        self.assertTrue(all(repo['uri'] == uri for repo in repos))
        self.assertTrue(
            all(repo['priority'] == 1100 for repo in repos
                if "holdback" in repo['name']))

    @mock.patch('fuel_package_updates.utils.exec_cmd', return_value=0)
    def test_mirror_remote_repository_http(self, mexec_cmd):
        distro = "ubuntu"
        http_url = "http://mirror.fuel-infra.org/repos/patching-test/ubuntu/"
        local_repo = "/var/www/nailgun/2014.2-6.1/centos/updates"
        repo_utils.mirror_remote_repository(distro, http_url, local_repo)

        self.assertTrue(mexec_cmd.called)

        wget_args = ('wget', local_repo, http_url, '--recursive',
                     '--no-parent', '--no-verbose', '"*.gif" -R', '"*.key" -R',
                     '"*.gpg" -R', '"*.dsc" -R "', '"*.tar.gz"')

        for arg in wget_args:
            self.assertIn(arg, str(mexec_cmd.call_args))

    @mock.patch('fuel_package_updates.utils.exec_cmd', return_value=0)
    def test_mirror_remote_repository_rsync(self, mexec_cmd):
        distro = "ubuntu"
        rsync_url = "rsync://mirror.fuel-infra.org/repos/patching-test/ubuntu/"
        local_repo = "/var/www/nailgun/2014.2-6.1/centos/updates"

        repo_utils.mirror_remote_repository(distro, rsync_url, local_repo)

        self.assertTrue(mexec_cmd.called)

        wget_args = ('rsync', local_repo, rsync_url,
                     '--exclude="*.key","*.gpg",')

        for arg in wget_args:
            self.assertIn(arg, str(mexec_cmd.call_args))
