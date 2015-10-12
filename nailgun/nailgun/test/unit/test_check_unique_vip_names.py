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

from nailgun.db.sqlalchemy.models import Task
from nailgun.errors import errors
from nailgun.task.manager import ApplyChangesTaskManager
from nailgun.test.base import BaseTestCase


class TestCheckVIPsNames(BaseTestCase):

    def setUp(self):
        super(TestCheckVIPsNames, self).setUp()

        self.env.create(
            release_kwargs={'version': '2015.1.0-7.0'},
            cluster_kwargs={
                'net_provider': 'neutron',
                'net_segment_type': 'gre'
            },
            nodes_kwargs=[{'roles': ['controller']}]
        )

        self.cluster = self.env.clusters[0]
        self.task = Task(cluster_id=self.cluster.id)
        self.db.add(self.task)
        self.db.flush()

    def test_check_vip_names(self):
        # in order VIPAssigningConflict error to be raised within
        # 'check_before_deployment' VIP names introduced by plugins
        # for the cluster must overlap with those in network configuration
        # of the cluster itself, so we make here such overlapping
        cluster_net_roles = self.cluster.release.network_roles_metadata

        err_msg = errors.DuplicatedVIPNames().message
        with mock.patch(
                'nailgun.objects.cluster.PluginManager.get_network_roles',
                new=mock.Mock(return_value=cluster_net_roles)
        ):

            with self.assertRaises(errors.CheckBeforeDeploymentError) as exc:
                ApplyChangesTaskManager(self.cluster.id)\
                    .check_before_deployment(self.task)

            self.assertEqual(exc.exception.message, err_msg)
