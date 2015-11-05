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

from oslo_serialization import jsonutils

from nailgun.test import base
from nailgun.test.base import fake_tasks
from nailgun.utils import reverse


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

        self.env.create_configuration(
            cluster_id=self.cluster.id,
            configuration={
                'keystone_config': {'param_a': 'cluster'},
            })
        self.env.create_configuration(
            cluster_id=self.cluster.id,
            node_id=self.env.nodes[0].id,
            configuration={
                'keystone_config': {'param_a': 'node_1'},
                'nova_config': {'param_a': 'node_1'},
            })
        self.env.create_configuration(
            cluster_id=self.cluster.id,
            node_role='compute',
            configuration={
                'keystone_config': {},
            })

    @fake_tasks(fake_rpc=False, mock_rpc=False)
    @patch('nailgun.rpc.cast')
    def test_configuration_execute(self, mocked_rpc):
        params = {
            'cluster_id': self.cluster.id
        }

        resp = self.app.put(
            reverse('OpenstackConfigExecuteHandler'),
            params=jsonutils.dumps(params),
            headers=self.default_headers
        )

        self.assertEqual(resp.status_code, 202)
        tasks = mocked_rpc.call_args[0][1]['args']['tasks']
        # 3 tasks for all ready nodes with cluster config
        # 1 task for node[0] with node specific config
        # 2 tasks (1 per each compute conde)
        self.assertEqual(len(tasks), 6)
