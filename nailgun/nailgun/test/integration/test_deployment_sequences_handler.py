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


class TestSequencesHandler(base.BaseIntegrationTest):
    def setUp(self):
        super(TestSequencesHandler, self).setUp()
        self.release = self.env.create_release(
            version='mitaka-9.0', operating_system=consts.RELEASE_OS.ubuntu
        )

    def _create_sequence(self, name, expect_errors=False, release_id=None):
        return self.app.post(
            reverse('SequenceCollectionHandler'),
            params=jsonutils.dumps(
                {
                    "name": name,
                    'release': release_id or self.release.id,
                    "graphs": [{'type': 'test_graph'}],
                }
            ),
            headers=self.default_headers,
            expect_errors=expect_errors
        )

    def test_create_new_sequence(self):
        self._create_sequence('test')
        sequence = objects.DeploymentSequence.get_by_name_for_release(
            self.release, 'test'
        )
        self.assertIsNotNone(sequence)
        self.assertEqual([{'type': 'test_graph'}], sequence.graphs)

    def test_create_sequence_with_same_name(self):
        self._create_sequence('test')
        resp = self._create_sequence('test', True)
        self.assertEqual(409, resp.status_code)
        release2 = self.env.create_release(
            version='newton-10.0', operating_system=consts.RELEASE_OS.ubuntu
        )
        self._create_sequence('test', release_id=release2.id)

    def test_update_sequence(self):
        resp = self._create_sequence('test')
        resp = self.app.put(
            reverse('SequenceHandler', {'obj_id': resp.json_body['id']}),
            params=jsonutils.dumps(
                {
                    "graphs": [{'type': 'test_graph2'}],
                }
            ),
            headers=self.default_headers
        )
        self.assertEqual([{'type': 'test_graph2'}], resp.json_body['graphs'])
        sequence = objects.DeploymentSequence.get_by_name_for_release(
            self.release, 'test'
        )
        self.assertEqual(resp.json_body['graphs'], sequence.graphs)

    def test_delete_sequence(self):
        resp = self._create_sequence('test')
        self.app.delete(
            reverse('SequenceHandler', {'obj_id': resp.json_body['id']}),
            headers=self.default_headers
        )
        sequence = objects.DeploymentSequence.get_by_name_for_release(
            self.release, 'test'
        )
        self.assertIsNone(sequence)

    def test_get_list_of_sequences_by_release(self):
        self._create_sequence('test')
        resp = self.app.get(
            reverse('SequenceCollectionHandler') +
            "?release={0}".format(self.release.id),
            headers=self.default_headers
        )
        sequences = resp.json_body
        self.assertEqual('test', sequences[0]['name'])

    def test_get_list_of_sequences_by_cluster(self):
        cluster = self.env.create(
            cluster_kwargs={'release_id': self.release.id}
        )
        self._create_sequence('test')
        resp = self.app.get(
            reverse('SequenceCollectionHandler') +
            "?cluster={0}".format(cluster.id),
            headers=self.default_headers
        )
        sequences = resp.json_body
        self.assertEqual('test', sequences[0]['name'])

    def test_get_list_of_all_sequences(self):
        self._create_sequence('test')
        resp = self.app.get(
            reverse('SequenceCollectionHandler'),
            headers=self.default_headers
        )
        sequences = resp.json_body
        self.assertEqual('test', sequences[0]['name'])


class TestSequenceExecutorHandler(base.BaseIntegrationTest):

    def setUp(self):
        super(TestSequenceExecutorHandler, self).setUp()
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

        self.sequence = objects.DeploymentSequence.create(
            {'name': 'test', 'release_id': self.cluster.release_id,
             'graphs': [{'type': 'test_graph'}]}
        )

        self.expected_metadata = {
            'fault_tolerance_groups': [],
            'node_statuses_transitions': {
                'successful': {'status': consts.NODE_STATUSES.ready},
                'failed': {'status': consts.NODE_STATUSES.error},
                'stopped': {'status': consts.NODE_STATUSES.stopped}}
        }

    @mock.patch('nailgun.transactions.manager.rpc')
    def test_execute_for_cluster(self, rpc_mock):

        resp = self.app.post(
            reverse('SequenceExecutorHandler',
                    kwargs={'obj_id': self.sequence.id}),
            params=jsonutils.dumps(
                {
                    "cluster": self.cluster.id,
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

    def test_execute_for_different_cluster(self):
        cluster2 = self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"status": consts.NODE_STATUSES.discover},
            ],
            release_kwargs={
                'version': 'newton-10.0',
                'operating_system': consts.RELEASE_OS.ubuntu
            }
        )
        resp = self.app.post(
            reverse('SequenceExecutorHandler',
                    kwargs={'obj_id': self.sequence.id}),
            params=jsonutils.dumps(
                {
                    "cluster": cluster2.id,
                    "debug": True,
                    "noop_run": True,
                    "dry_run": True,
                }
            ),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(404, resp.status_code)
