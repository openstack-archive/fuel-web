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

from nailgun import consts
from nailgun.task.manager import OpenstackConfigTaskManager
from nailgun.test import base
from nailgun.test.base import fake_tasks


class TestOpenstackConfigTaskManager(base.BaseIntegrationTest):

    def setUp(self):
        super(TestOpenstackConfigTaskManager, self).setUp()

        self.env.create(
            cluster_kwargs={'net_provider': 'neutron'},
            release_kwargs={'version': '1111-8.0'},
            nodes_kwargs=[
                {'roles': ['controller'], 'status': 'ready'},
                {'roles': ['compute'], 'status': 'ready'},
                {'roles': ['compute'], 'status': 'ready'},
                {'roles': ['compute'], 'pending_addition': True},
            ]
        )

        self.release = self.env.releases[0]
        self.cluster = self.env.clusters[0]

        self.env.create_openstack_config(
            cluster_id=self.cluster.id,
            configuration={
                'keystone_config': {'param_a': 'cluster'},
            })
        self.env.create_openstack_config(
            cluster_id=self.cluster.id,
            node_id=self.env.nodes[0].id,
            configuration={
                'keystone_config': {'param_a': 'node_1'},
                'nova_config': {'param_a': 'node_1'},
            })
        self.env.create_openstack_config(
            cluster_id=self.cluster.id,
            node_role='compute',
            configuration={
                'keystone_config': {},
            })

    @fake_tasks(fake_rpc=False, mock_rpc=False)
    @patch('nailgun.rpc.cast')
    def test_configuration_execute(self, mocked_rpc):
        task_manager = OpenstackConfigTaskManager(self.cluster.id)
        task = task_manager.execute({'cluster_id': self.cluster.id})

        self.assertEqual(task.status, consts.TASK_STATUSES.pending)

        node_ids = [n.id for n in self.env.nodes[:3]]
        self.assertEqual(sorted(task.cache['nodes']),
                         sorted(node_ids))

        tasks = mocked_rpc.call_args[0][1]['args']['tasks']
        # 3 tasks for all ready nodes with cluster config
        # 1 task for node[0] with node specific config
        # 2 tasks (1 per each compute conde)
        self.assertEqual(len(tasks), 6)
