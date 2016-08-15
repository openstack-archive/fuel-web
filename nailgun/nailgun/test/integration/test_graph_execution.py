# -*- coding: utf-8 -*-

#    Copyright 2016 Mirantis, Inc.
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

from oslo_serialization import jsonutils

from nailgun import consts
from nailgun import objects

from nailgun.test import base
from nailgun.utils import reverse


class TestGraphExecutorHandler(base.BaseIntegrationTest):

    def setUp(self):
        super(TestGraphExecutorHandler, self).setUp()
        self.cluster = self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"status": consts.NODE_STATUSES.discover},
            ],
            release_kwargs={
                'version': 'mitaka-9.0',
                'operating_system': consts.RELEASE_OS.ubuntu
            }
        )
        objects.DeploymentGraph.create_for_model(
            {
                'tasks': [
                    {
                        'id': 'test_task',
                        'type': consts.ORCHESTRATOR_TASK_TYPES.puppet,
                        'roles': ['/.*/']
                    },
                ],
                'name': 'test_graph',
            },
            instance=self.cluster,
            graph_type='test_graph'
        )

    @mock.patch('nailgun.transactions.manager.rpc')
    def test_execute(self, rpc_mock):
        resp = self.app.post(
            reverse('GraphsExecutorHandler'),
            params=jsonutils.dumps(
                {
                    "cluster": self.cluster.id,
                    "graphs": [{"type": "test_graph"}],
                }
            ),
            headers=self.default_headers
        )
        self.assertEqual(202, resp.status_code)
        task = objects.Task.get_by_uid(resp.json_body['id'])
        sub_task = task.subtasks[0]
        rpc_mock.cast.assert_called_once_with(
            'naily',
            [{
                'args': {
                    'tasks_metadata': {'fault_tolerance_groups': []},
                    'task_uuid': sub_task.uuid,
                    'tasks_graph': {
                        None: [],
                        self.cluster.nodes[0].uid: [
                            {
                                'id': 'test_task',
                                'type': 'puppet',
                                'fail_on_error': True,
                                'parameters': {'cwd': '/'}
                            },
                        ]
                    },
                    'tasks_directory': {},
                    'dry_run': False,
                    'noop_run': False,
                },
                'respond_to': 'transaction_resp',
                'method': 'task_deploy',
                'api_version': '1'
            }]
        )
