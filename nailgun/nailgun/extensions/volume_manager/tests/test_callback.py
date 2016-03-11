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

from nailgun.db.sqlalchemy.models import Task
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
        self.node = self.env.nodes[0]
        self.cluster = self.env.clusters[0]
        self.task = Task(cluster_id=self.env.clusters[0].id)
        self.env.db.add(self.task)
        self.env.db.commit()

    def test_check_volumes_and_disks_do_not_run_if_node_ready(self):
        self.node.status = 'ready'
        self.env.db.commit()

        with mock.patch.object(
                VolumeManager,
                'check_disk_space_for_deployment') as check_mock:
            VolumeManagerExtension._check_disks(self.cluster)

        self.assertFalse(check_mock.called)

        with mock.patch.object(
                VolumeManager,
                'check_volume_sizes_for_deployment') as check_mock:
            VolumeManagerExtension._check_volumes(self.cluster)

        self.assertFalse(check_mock.called)

    def test_check_volumes_and_disks_run_if_node_not_ready(self):
        self.node.status = 'discover'
        self.env.db.commit()

        with mock.patch.object(
                VolumeManager,
                'check_disk_space_for_deployment') as check_mock:
            VolumeManagerExtension._check_disks(self.cluster)

        self.assertEqual(check_mock.call_count, 1)

        with mock.patch.object(
                VolumeManager,
                'check_volume_sizes_for_deployment') as check_mock:
            VolumeManagerExtension._check_volumes(self.cluster)

        self.assertEqual(check_mock.call_count, 1)
