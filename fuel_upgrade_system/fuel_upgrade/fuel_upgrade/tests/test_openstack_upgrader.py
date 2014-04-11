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

from fuel_upgrade import config
from fuel_upgrade import errors
from fuel_upgrade.tests.base import BaseTestCase
from fuel_upgrade.upgrade import OpenStackUpgrader


class TestOpenStackUpgrader(BaseTestCase):
    def setUp(self):
        """Create upgrader with mocked data.
        """
        with mock.patch('fuel_upgrade.upgrade.io.open') as io_open:
            io_open.return_value.__enter__.return_value.read.return_value = \
                '{ "name": "release name", "version": "2014" }'

            self.upgrader = OpenStackUpgrader(
                '/tmp/update_src', self.get_conf()
            )

    def get_conf(self):
        conf = config.Config()
        setattr(conf, 'openstack', {
            'releases': 'releases.json'
        })
        return conf

    @mock.patch('fuel_upgrade.upgrade.pynailgun.PyNailgun.create_notification')
    @mock.patch('fuel_upgrade.upgrade.pynailgun.PyNailgun.create_release')
    def prepare_successful_state(self, mock_cr, mock_cn, releases_count=2):
        self.upgrader.releases = [
            self.upgrader.releases[0] for i in range(releases_count)
        ]
        self.upgrader.upgrade()

        self.assertTrue(mock_cr.called)
        self.assertTrue(mock_cn.called)

        for type_ in ('release', 'notification'):
            self.assertEqual(
                len(self.upgrader._rollback_ids[type_]), releases_count)

    def prepare_unsuccessful_state(self, releases_count=2):
        self.upgrader.releases = [
            self.upgrader.releases[0] for i in range(releases_count)
        ]

        for i in range(releases_count / 2):
            self.upgrader._rollback_ids['release'].append(i)

        for i in range(releases_count / 4):
            self.upgrader._rollback_ids['notification'].append(i)

    @mock.patch('fuel_upgrade.upgrade.io.open')
    def test_load_releases(self, mock_open):
        # load one-release file
        mock_open.return_value.__enter__.return_value.read.return_value = \
            '{ "name": "release name" }'

        upgrader = OpenStackUpgrader('/tmp/update_src', self.get_conf())
        self.assertEqual(len(upgrader.releases), 1)

        # load multiple-release file
        mock_open.return_value.__enter__.return_value.read.return_value = \
            '[{ "name": "release name" }, { "name": "another release"}]'

        upgrader = OpenStackUpgrader('/tmp/update_src', self.get_conf())
        self.assertEqual(len(upgrader.releases), 2)

    @mock.patch('fuel_upgrade.upgrade.pynailgun.PyNailgun.create_notification')
    @mock.patch('fuel_upgrade.upgrade.pynailgun.PyNailgun.create_release')
    def test_successful_upgrade(self, mock_cr, mock_cn):
        # test one release
        mock_cr.return_value = {'id': '1'}
        mock_cn.return_value = {'id': '100'}

        self.upgrader.upgrade()

        self.assertTrue(mock_cr.called)
        self.assertTrue(mock_cn.called)

        for type_ in ('release', 'notification'):
            self.assertEqual(len(self.upgrader._rollback_ids[type_]), 1)

        # test multiple releases
        self.upgrader.releases.append(self.upgrader.releases[0])
        self.upgrader.upgrade()

        self.assertTrue(mock_cr.called)
        self.assertTrue(mock_cn.called)

        for type_ in ('release', 'notification'):
            self.assertEqual(len(self.upgrader._rollback_ids[type_]), 2)

    @mock.patch('fuel_upgrade.upgrade.pynailgun.PyNailgun.create_notification')
    @mock.patch('fuel_upgrade.upgrade.pynailgun.PyNailgun.create_release')
    def test_unsuccessful_upgrade(self, mock_cr, mock_cn):
        mock_cr.return_value = {'id': '1'}
        mock_cn.side_effect = errors.FailedApiCall('Something wrong')

        self.assertRaises(errors.FailedApiCall, self.upgrader.upgrade)
        self.assertTrue(mock_cr.called)
        self.assertTrue(mock_cn.called)

        self.assertEqual(len(self.upgrader._rollback_ids['release']), 1)
        self.assertEqual(len(self.upgrader._rollback_ids['notification']), 0)

    @mock.patch('fuel_upgrade.upgrade.pynailgun.PyNailgun.remove_notification')
    @mock.patch('fuel_upgrade.upgrade.pynailgun.PyNailgun.remove_release')
    def test_partial_rollback(self, mock_rr, mock_rn):
        self.prepare_unsuccessful_state()

        self.upgrader.rollback()

        self.assertTrue(mock_rr.called)
        self.assertFalse(mock_rn.called)

    @mock.patch('fuel_upgrade.upgrade.pynailgun.PyNailgun.remove_notification')
    @mock.patch('fuel_upgrade.upgrade.pynailgun.PyNailgun.remove_release')
    def test_full_rollback(self, mock_rr, mock_rn):
        self.prepare_successful_state()

        self.upgrader.rollback()

        self.assertTrue(mock_rr.called)
        self.assertTrue(mock_rn.called)

    @mock.patch('fuel_upgrade.upgrade.pynailgun.PyNailgun.remove_notification')
    @mock.patch('fuel_upgrade.upgrade.pynailgun.PyNailgun.remove_release')
    def test_rollback_with_errors(self, mock_rr, mock_rn):
        self.prepare_successful_state(releases_count=2)

        mock_rr.side_effect = Exception('something wrong')
        mock_rn.side_effect = Exception('something wrong')

        self.upgrader.rollback()

        self.assertEqual(mock_rr.call_count, 2)
        self.assertEqual(mock_rn.call_count, 2)
