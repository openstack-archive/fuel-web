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

from mock import patch

from nailgun.test.base import BaseIntegrationTest
from nailgun.task.helpers import TaskHelper
from nailgun.task.task import ApplyChangesTaskManager


class TestDeploymentNodesFiltering(BaseIntegrationTest):

    def setUp(self):
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


    def test_related_nodes_are_present(self):

        cluster = self.env.clusters[0]
        controllers = [n for n in cluster.nodes if 'controller' in n.all_roles]
        nodes_to_deploy = TaskHelper.nodes_to_deploy(cluster)
        self.assertItemsEqual(controllers, nodes_to_deploy)

    @patch('nailgun.task.task.rpc.cast')
    def test_apply_changes(self, mcast):
