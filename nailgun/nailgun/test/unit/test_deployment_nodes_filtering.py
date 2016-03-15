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

from nailgun.task.helpers import TaskHelper
from nailgun.test.base import BaseIntegrationTest


class TestDeploymentNodesFiltering(BaseIntegrationTest):

    def setUp(self):
        super(TestDeploymentNodesFiltering, self).setUp()
        self.env.create(
            release_kwargs={
                'version': "2014.2-6.0"
            },
            nodes_kwargs=[
                {'roles': ['controller'], 'status': 'ready'},
                {'pending_roles': ['controller'],
                 'pending_addition': True},
                {'roles': ['cinder'],
                 'pending_deletion': True,
                 'status': 'ready'}
            ]
        )

    def test_related_pending_deletion_nodes_not_present(self):
        cluster = self.env.clusters[0]
        controllers = [n for n in cluster.nodes if 'controller' in n.all_roles]
        nodes_to_deploy = TaskHelper.nodes_to_deploy(cluster)
        self.assertItemsEqual(controllers, nodes_to_deploy)

    def test_related_pending_deletion_nodes_not_present_with_force(self):
        cluster = self.env.clusters[0]
        controllers = [n for n in cluster.nodes if 'controller' in n.all_roles]
        nodes_to_deploy = TaskHelper.nodes_to_deploy(cluster, force=True)
        self.assertItemsEqual(controllers, nodes_to_deploy)
