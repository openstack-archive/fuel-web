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
                {"status": consts.NODE_STATUSES.provisioned},
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
        self.expected_metadata = {
            'fault_tolerance_groups': [],
            'node_statuses_transitions': {
                'successful': {'status': consts.NODE_STATUSES.ready},
                'failed': {'status': consts.NODE_STATUSES.error},
                'stopped': {'status': consts.NODE_STATUSES.stopped}}
        }

    @mock.patch('nailgun.transactions.manager.rpc')
    def test_execute(self, rpc_mock):
        resp = self.app.post(
            reverse('GraphsExecutorHandler'),
            params=jsonutils.dumps(
                {
                    "cluster": self.cluster.id,
                    "graphs": [{"type": "test_graph"}],
                    "debug": True,
                    "noop_run": True,
                    "dry_run": True,
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
                    'tasks_metadata': self.expected_metadata,
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
                    'dry_run': True,
                    'noop_run': True,
                    'debug': True
                },
                'respond_to': 'transaction_resp',
                'method': 'task_deploy',
                'api_version': '1'
            }]
        )

    @mock.patch('nailgun.transactions.manager.rpc')
    def test_execute_w_subgraph(self, rpc_mock):
        resp = self.app.post(
            reverse('GraphsExecutorHandler'),
            params=jsonutils.dumps(
                {
                    "cluster": self.cluster.id,
                    "graphs": [{"type": "test_graph"}],
                    "debug": True,
                    "noop_run": True,
                    "dry_run": True,
                    "subgraphs": [{"start": "primary-database",
                                   "end": "keystone-db"
                                   }
                                  ]
                }
            ),
            headers=self.default_headers
        )
        self.assertEqual(202, resp.status_code)
        task = objects.Task.get_by_uid(resp.json_body['id'])
        sub_task = task.subtasks[0]
        self.expected_metadata['subgraphs'] = [
            {"start": "primary-database",
             "end": "keystone-db"}
        ]
        rpc_mock.cast.assert_called_once_with(
            'naily',
            [{
                'args': {
                    'tasks_metadata': self.expected_metadata,
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
                    'dry_run': True,
                    'noop_run': True,
                    'debug': True
                },
                'respond_to': 'transaction_resp',
                'method': 'task_deploy',
                'api_version': '1'
            }]
        )
