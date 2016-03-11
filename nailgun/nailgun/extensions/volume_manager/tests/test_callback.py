# -*- coding: utf-8 -*-
#    Copyright 2013 Mirantis, Inc.
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

from nailgun.extensions import fire_callback_on_before_deployment_check
from nailgun.extensions.volume_manager.extension import VolumeManagerExtension
from nailgun.extensions.volume_manager.manager import VolumeManager
from nailgun.test.base import BaseTestCase


class TestCheckBeforeDeploymentCallback(BaseTestCase):

    def setUp(self):
        super(TestCheckBeforeDeploymentCallback, self).setUp()
        self.env.create(
            release_kwargs={'version': '1111-8.0'},
            cluster_kwargs={
                'net_provider': 'neutron',
                'net_segment_type': 'gre'
            },
            nodes_kwargs=[{'roles': ['controller']}])

        self.env.create_node()
        self.cluster = self.env.clusters[0]
        self.node = self.cluster.nodes[0]

    def is_checking_required(self):
        return VolumeManagerExtension._is_disk_checking_required(self.node)

    def test_is_disk_checking_required(self):
        self.node.status = 'ready'
        self.assertFalse(self.is_checking_required())

        self.node.status = 'deploying'
        self.assertFalse(self.is_checking_required())

        self.node.status = 'discover'
        self.assertTrue(self.is_checking_required())

        self.node.status = 'provisioned'
        self.assertFalse(self.is_checking_required())

    def test_is_disk_checking_required_in_case_of_error(self):
        self.node.status = 'error'
        self.node.error_type = 'provision'
        self.assertTrue(self.is_checking_required())

        self.node.error_type = 'deploy'
        self.assertFalse(self.is_checking_required())

    def test_check_volumes_and_disks_do_not_run_if_node_ready(self):
        self.node.status = 'ready'

        with mock.patch.object(
                VolumeManager,
                'check_disk_space_for_deployment') as check_mock:
            fire_callback_on_before_deployment_check(self.cluster)

        self.assertFalse(check_mock.called)

        with mock.patch.object(
                VolumeManager,
                'check_volume_sizes_for_deployment') as check_mock:
            fire_callback_on_before_deployment_check(self.cluster)

        self.assertFalse(check_mock.called)

    def test_check_volumes_and_disks_run_if_node_not_ready(self):
        self.node.status = 'discover'

        with mock.patch.object(
                VolumeManager,
                'check_disk_space_for_deployment') as check_mock:
            fire_callback_on_before_deployment_check(self.cluster)

        self.assertEqual(check_mock.call_count, 1)

        with mock.patch.object(
                VolumeManager,
                'check_volume_sizes_for_deployment') as check_mock:
            fire_callback_on_before_deployment_check(self.cluster)

        self.assertEqual(check_mock.call_count, 1)
