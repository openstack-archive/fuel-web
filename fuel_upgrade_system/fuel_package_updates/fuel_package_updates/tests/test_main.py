#!/usr/bin/env python
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

from functools import partial
import mock
import shlex
from StringIO import StringIO
import unittest2

from fuel_package_updates import main


@mock.patch('fuel_package_updates.utils.exit_with_error',
            side_effect=SystemExit)
class TestCheckArgs(unittest2.TestCase):

    def test_list_supported_distors(self, mexit_with_error):
        options = mock.Mock(list_distros=True)
        with self.assertRaises(SystemExit):
            main.check_info_args(options)

        self.assertFalse(mexit_with_error.called)

    def test_incorrect_url(self, mexit_with_error):
        url = 'mirror.fuel-infra.org/repos/patching-test/ubuntu/'
        options = mock.Mock(distro='ubuntu', release='2014.2-6.1', url=url)

        with self.assertRaises(SystemExit):
            main.check_update_args(options)

        self.assertTrue(mexit_with_error.called)
        self.assertIn(url, str(mexit_with_error.call_args))


class TestActions(unittest2.TestCase):

    def setUp(self):
        self.parser = main.get_parser()

    def parse_args_patcher(self, args):
        return mock.patch(
            'fuel_package_updates.main.parse_args',
            new=partial(main.parse_args, args=args))

    def test_parse_args(self):
        args = shlex.split(
            'update -d ubuntu -r "2014.2-6.1" -u '
            'http://mirror.fuel-infra.org/repos/patching-test/ubuntu/ '
            '-s "0.0.0.0"')
        options = self.parser.parse_args(args=args)

        self.assertEqual(options.distro, "ubuntu")
        self.assertEqual(options.release, "2014.2-6.1")
        self.assertEqual(options.ip, "0.0.0.0")
        self.assertEqual(
            options.url,
            "http://mirror.fuel-infra.org/repos/patching-test/ubuntu/")
        self.assertIsNone(options.apply)
        self.assertIsNone(options.baseurl)
        self.assertIsNone(options.admin_pass)
        self.assertFalse(options.verbose)

    def test_do_not_apply(self):
        args = shlex.split(
            'update -d ubuntu -r "2014.2-6.1" -u '
            'http://mirror.fuel-infra.org/repos/patching-test/ubuntu/ '
            '-s "0.0.0.0"')

        mirror_remote_repository_patcher = mock.patch(
            'fuel_package_updates.main.RepoManager.mirror_remote_repository')

        stdout_patcher = mock.patch('sys.stdout', new=StringIO())

        with self.parse_args_patcher(args):
            with mirror_remote_repository_patcher as mmrr:
                with stdout_patcher as mstdout:
                    main.main()

        self.assertTrue(mmrr.called)
        self.assertIn(
            ('Your repositories are now ready for use. You will need to '
             'update your Fuel environment configuration to use these'
             ' repositories.'),
            mstdout.getvalue())
        self.assertIn(
            'uri: http://0.0.0.0:8000/2014.2-6.1/ubuntu/updates',
            mstdout.getvalue())

    def test_apply(self):
        cluster_id = 1
        args = shlex.split(
            'update -d ubuntu -r "2014.2-6.1" -u '
            'http://mirror.fuel-infra.org/repos/patching-test/ubuntu/ '
            '-s "0.0.0.0" -a {cluster_id}'.format(cluster_id=cluster_id))

        mirror_remote_repository_patcher = mock.patch(
            'fuel_package_updates.main.RepoManager.mirror_remote_repository')

        fuel_web_client_patcher = mock.patch(
            'fuel_package_updates.repo.FuelWebClient')

        with self.parse_args_patcher(args):
            with mirror_remote_repository_patcher:
                with fuel_web_client_patcher as mfuel_web_client:
                    main.main()

        mfuel_web_client.assert_called_once_with(
            '0.0.0.0', 8000,
            {
                'username': 'admin',
                'tenant_name': 'admin',
                'password': 'admin'
            },
        )
