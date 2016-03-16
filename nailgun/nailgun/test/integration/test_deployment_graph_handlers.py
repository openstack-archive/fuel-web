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
from oslo_serialization import jsonutils

from nailgun.objects import DeploymentGraph
from nailgun.test.base import BaseIntegrationTest
from nailgun.utils import reverse


class TestHandlers(BaseIntegrationTest):

    def setUp(self):
        super(TestHandlers, self).setUp()
        self.cluster = self.env.create_cluster(api=False)
        self.custom_graph = DeploymentGraph.upsert_for_model(
            {
                'name': 'custom-graph-name',
                'tasks': [{
                    'id': 'custom-task',
                    'type': 'puppet'
                }]
            },
            self.cluster,
            graph_type='custom-graph'
        )

    def tearDown(self):
        super(TestHandlers, self).tearDown()

    def test_graphs_list_request(self):
        expected_list = [
            {
                u'tasks_count': 25,
                u'graph_id': DeploymentGraph.get_for_model(
                    self.cluster.release, graph_type='default').id,
                u'relations': [{
                    u'model_id': self.cluster.release.id,
                    u'model': u'Release',
                    u'type': u'default'
                }]
            },
            {
                u'tasks_count': 1,
                u'graph_id': self.custom_graph.id,
                u'relations': [{
                    u'type': u'custom-graph',
                    u'model': u'Cluster',
                    u'model_id': self.cluster.id
                }]
            }
        ]
        resp = self.app.get(
            reverse(
                'DeploymentGraphCollectionHandler',
                kwargs={}
            ),
            headers=self.default_headers
        )
        self.assertItemsEqual(expected_list, resp.json_body)

    def test_graphs_by_id_request(self):

        resp = self.app.get(
            reverse(
                'DeploymentGraphHandler',
                kwargs={'graph_id': self.custom_graph.id}
            ),
            headers=self.default_headers
        )
        self.assertItemsEqual(
            {
                'id': self.custom_graph.id,
                'name': 'custom-graph-name',
                'tasks': [{
                    'id': 'custom-task',
                    'type': 'puppet'
                }]
            },
            resp.json_body
        )

    def test_graph_update(self):

        resp = self.app.put(
            reverse(
                'DeploymentGraphHandler',
                kwargs={'graph_id': self.custom_graph.id}
            ),
            jsonutils.dumps({
                'name': 'updated-graph-name',
                'tasks': [{
                    'id': 'test-task2',
                    'type': 'puppet',
                    'version': '2.0.0'
                }]
            }),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        self.assertEqual(
            {
                'name': 'updated-graph-name',
                'tasks': [{
                    'id': 'test-task2',
                    'type': 'puppet',
                    'task_name': 'test-task2',
                    'version': '2.0.0'
                }],
                'id': self.custom_graph.id
            },
            resp.json_body
        )

        resp = self.app.put(
            reverse(
                'DeploymentGraphHandler',
                kwargs={'graph_id': self.custom_graph.id}
            ),
            jsonutils.dumps({
                'name': 'updated-graph-name2'
            }),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        self.assertEqual(
            {
                'name': 'updated-graph-name2',
                'tasks': [{
                    'id': 'test-task2',
                    'type': 'puppet',
                    'task_name': 'test-task2',
                    'version': '2.0.0'
                }],
                'id': self.custom_graph.id
            },
            resp.json_body
        )

    def test_graph_delete(self):
        graph_id = self.custom_graph.id
        resp = self.app.delete(
            reverse(
                'DeploymentGraphHandler',
                kwargs={'graph_id': graph_id}
            ),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(204, resp.status_code)
        graph = DeploymentGraph.get_by_uid(graph_id)
        self.assertIsNone(graph)

    def test_graph_update_fail_on_bad_schema(self):
        resp = self.app.put(
            reverse(
                'DeploymentGraphHandler',
                kwargs={'graph_id': self.custom_graph.id}
            ),
            jsonutils.dumps({
                'no-such-field': 'BOOM'
            }),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(400, resp.status_code)
        self.assertEqual(
            "Additional properties are not allowed "
            "(u'no-such-field' was unexpected)", resp.json_body['message'])

    def test_graph_update_fail_on_not_existing_id(self):
        not_existing_id = 100500

        resp = self.app.put(
            reverse(
                'DeploymentGraphHandler',
                kwargs={'graph_id': not_existing_id}
            ),
            '{}',
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(404, resp.status_code)
