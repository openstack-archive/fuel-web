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

from StringIO import StringIO

import mock

from fuel_package_updates.tests import base


@mock.patch('fuel_package_updates.utils.exit_with_error',
            side_effect=SystemExit)
class TestCheckArgs(base.UnitTestCase):

    def test_list_supported_distors(self, mexit_with_error):
        command = "info -l"
        with self.assertRaises(SystemExit):
            self.execute(command)

        self.assertFalse(mexit_with_error.called)

    def test_incorrect_url(self, mexit_with_error):
        url = 'mirror.fuel-infra.org/repos/patching-test/ubuntu/'
        command = 'update -d ubuntu -r "2014.2-6.1" -u {url}'.format(url=url)

        with self.assertRaises(SystemExit):
            self.execute(command)

        self.assertTrue(mexit_with_error.called)
        self.assertIn(url, mexit_with_error.call_args[0][0])


class TestActions(base.UnitTestCase):

    def test_do_not_apply(self):
        command = (
            'update -d ubuntu -r "2014.2-6.1" -u '
            'http://mirror.fuel-infra.org/repos/patching-test/ubuntu/ '
            '-s "0.0.0.0"')

        mirror_remote_repository_patcher = mock.patch(
            'fuel_package_updates.main.RepoManager.mirror_remote_repository')

        stdout_patcher = mock.patch('sys.stdout', new=StringIO())

        with mirror_remote_repository_patcher as mmrr:
            with stdout_patcher as mstdout:
                self.execute(command)

        self.assertTrue(mmrr.called)
        self.assertIn(
            ('Your repositories are now ready for use. You will need to '
             'update your Fuel environment configuration to use these'
             ' repositories.'),
            mstdout.getvalue())
        self.assertIn(
            'uri: http://0.0.0.0:8000/2014.2-6.1/ubuntu/updates',
            mstdout.getvalue())

    @mock.patch('fuel_package_updates.clients.HTTPClient.token')
    @mock.patch(
        'fuel_package_updates.main.RepoManager.mirror_remote_repository')
    @mock.patch('fuel_package_updates.clients.requests.put')
    @mock.patch('fuel_package_updates.clients.requests.get')
    def test_apply(self, mget, mput, mmrr, mtoken):
        mput.return_value.status_code = 200
        mget.return_value.status_code = 200
        mget.return_value.json.return_value = {'editable': {}}

        cluster_id = 1
        ip = "0.0.0.0"
        port = 8000
        command = (
            'update -d ubuntu -r "2014.2-6.1" -u '
            'http://mirror.fuel-infra.org/repos/patching-test/ubuntu/ '
            '-s "{ip}" -a {cluster_id}'.format(ip=ip, cluster_id=cluster_id))

        nailgun_url = (
            'http://{ip}:{port}/api/clusters/{cluster_id}/attributes/').format(
                ip=ip,
                port=port,
                cluster_id=cluster_id)

        self.execute(command)

        self.assertEqual(mget.call_args[0][0], nailgun_url)
        self.assertEqual(mput.call_args[0][0], nailgun_url)

    @mock.patch('fuel_package_updates.repo.utils.exec_cmd', return_value=0)
    @mock.patch('os.path.exists', return_value=True)
    def test_mirror_remote_repository_http(self, mexists, mexec_cmd):
        http_url = "http://mirror.fuel-infra.org/repos/patching-test/ubuntu/"
        local_repo = "/var/www/nailgun/2014.2-6.1/ubuntu/updates"
        command = ('update -d ubuntu -s "10.0.0.20" -r "2014.2-6.1" -u '
                   '{url}'.format(url=http_url))

        self.execute(command)

        self.assertTrue(mexec_cmd.called)
        wget_args = ('wget', local_repo, http_url, '--recursive',
                     '--no-parent', '--no-verbose', '"*.gif" -R', '"*.key" -R',
                     '"*.gpg" -R', '"*.dsc" -R "', '"*.tar.gz"')

        for arg in wget_args:
            self.assertIn(arg, mexec_cmd.call_args[0][0])

    @mock.patch('fuel_package_updates.repo.utils.exec_cmd', return_value=0)
    @mock.patch('os.path.exists', return_value=True)
    def test_mirror_remote_repository_rsync(self, mexists, mexec_cmd):
        rsync_url = "rsync://mirror.fuel-infra.org/repos/patching-test/ubuntu/"
        local_repo = "/var/www/nailgun/2014.2-6.1/ubuntu/updates"
        command = ('update -d ubuntu -s "10.0.0.20" -r "2014.2-6.1" -u '
                   '{url}'.format(url=rsync_url))

        self.execute(command)

        self.assertTrue(mexec_cmd.called)
        wget_args = ('rsync', local_repo, rsync_url,
                     '--exclude="*.key","*.gpg",')
        for arg in wget_args:
            self.assertIn(arg, mexec_cmd.call_args[0][0])
