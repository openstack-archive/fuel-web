# -*- coding: utf-8 -*-

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

from fuel_package_updates import fuel_package_updates as fpu
from fuel_package_updates.tests import base


@mock.patch.object(fpu.NailgunClient, 'get_releases')
class TestSpecifyRelease(base.BaseCliTestCase):

    def setUp(self):
        super(self.__class__, self).setUp()
        self.releases = [
            base.make_release(id=1, version='2015.1.0-7.0'),
            base.make_release(id=2, version='2014.2.2-6.1'),
            base.make_release(id=3, version='2014.2.2-5.1'),
        ]

    @mock.patch('fuel_package_updates.fuel_package_updates.os')
    def test_select_available_release(self, mock_os, mock_get_rels):
        mock_get_rels.return_value = self.releases
        with base.mock_stdout() as m_stdout:
            self.execute('--release', '2014.2.2-6.1',
                         '--distro', 'ubuntu', '--no-download')
        self.assertIn(
            "Your repositories are now ready for use.",
            m_stdout.getvalue())

    def test_release_not_avaiable(self, mock_get_rels):
        mock_get_rels.return_value = self.releases
        with self.assertRaises(fpu.UpdatePackagesException) as exc_ctx:
            self.execute('--release', 'strange-version', '--distro', 'ubuntu')
        self.assertIn(
            'Fuel release "strange-version" is not supported. '
            'Please specify one of the following: '
            '"2015.1.0-7.0, 2014.2.2-6.1"',
            str(exc_ctx.exception))

    def test_list_releases(self, mock_get_rels):
        mock_get_rels.return_value = self.releases

        with base.mock_stdout() as m_stdout:
            with self.assertRaises(SystemExit):
                self.execute('--list-releases')
        self.assertEqual(
            m_stdout.getvalue(),
            "Available releases:\n"
            "2015.1.0-7.0\n"
            "2014.2.2-6.1\n"
        )
