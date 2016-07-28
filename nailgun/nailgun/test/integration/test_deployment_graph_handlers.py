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
import six

from nailgun.objects import DeploymentGraph
from nailgun.test.base import BaseIntegrationTest
from nailgun.utils import reverse


class TestGraphHandlers(BaseIntegrationTest):

    maxDiff = None

    def setUp(self):
        super(TestGraphHandlers, self).setUp()
        self.cluster = self.env.create_cluster(api=False)
        plugin_data = {
            'releases': [
                {
                    'repository_path': 'repositories/ubuntu',
                    'version': self.cluster.release.version,
                    'os': self.cluster.release.operating_system.lower(),
                    'mode': [self.cluster.mode],
                }
            ],
            'cluster': self.cluster,
            'enabled': True,
        }
        self.plugin = self.env.create_plugin(**plugin_data)
        self.custom_graph = DeploymentGraph.create_for_model(
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
        self.env.db().commit()

    def test_graphs_list_request(self):
        default_graph = DeploymentGraph.get_for_model(self.cluster)

        expected_list = [
            {
                'id': DeploymentGraph.get_for_model(
                    self.cluster.release, graph_type='default').id,
                'name': None,
                'relations': [{
                    'model_id': self.cluster.release.id,
                    'model': 'release',
                    'type': 'default'
                }]
            },
            {
                'id': self.custom_graph.id,
                'name': 'custom-graph-name',
                'relations': [{
                    'type': 'custom-graph',
                    'model': 'cluster',
                    'model_id': self.cluster.id
                }]
            },
            {
                'id': default_graph.id,
                'relations': [
                    {
                        'model': 'cluster',
                        'model_id': self.cluster.id,
                        'type': 'default'
                    }
                ],
                'name': None
            }
        ]
        response = self.app.get(
            reverse(
                'DeploymentGraphCollectionHandler',
                kwargs={}
            ),
            headers=self.default_headers
        ).json_body
        for r in response:
            r.pop('tasks')
        self.assertItemsEqual(expected_list, response)

    def test_graphs_list_filtered_release_and_plugin(self):
        expected_list = [
            {
                'id': DeploymentGraph.get_for_model(
                    self.cluster.release, graph_type='default').id,
                'name': None,
                'relations': [{
                    'model_id': self.cluster.release.id,
                    'model': 'release',
                    'type': 'default'
                }]
            },
            {
                'id': DeploymentGraph.get_for_model(
                    self.plugin, graph_type='default').id,
                'name': None,
                'relations': [
                    {
                        'model_id': self.plugin.id,
                        'model': 'plugin',
                        'type': 'default'
                    }
                ],
            }
        ]

        response = self.app.get(
            reverse(
                'DeploymentGraphCollectionHandler',
                kwargs={}
            ) + '?releases={}&plugins={}'.format(
                self.cluster.release.id,
                self.plugin.id
            ),
            headers=self.default_headers
        ).json_body

        for r in response:
            r.pop('tasks')
        self.assertItemsEqual(expected_list, response)

    def test_graphs_list_filtered_cluster(self):
        expected_list = [
            {
                'id': DeploymentGraph.get_for_model(
                    self.cluster.release, graph_type='default').id,
                'name': None,
                'relations': [{
                    'model_id': self.cluster.release.id,
                    'model': 'release',
                    'type': 'default'
                }]
            },
            {
                'id': DeploymentGraph.get_for_model(self.cluster).id,
                'name': None,
                'relations': [{
                    'model_id': self.cluster.id,
                    'model': 'cluster',
                    'type': 'default'
                }]
            },
            {
                'id': DeploymentGraph.get_for_model(
                    self.cluster, graph_type='custom-graph').id,
                'name': 'custom-graph-name',
                'relations': [{
                    'model_id': self.cluster.id,
                    'model': 'cluster',
                    'type': 'custom-graph'
                }]
            },
            {
                'id': DeploymentGraph.get_for_model(self.plugin).id,
                'name': None,
                'relations': [{
                    'model_id': self.plugin.id,
                    'model': 'plugin',
                    'type': 'default'
                }],
             }
        ]

        response = self.app.get(
            reverse(
                'DeploymentGraphCollectionHandler',
                kwargs={}
            ) + '?clusters={}'.format(self.cluster.id),
            headers=self.default_headers
        ).json_body

        for r in response:
            r.pop('tasks')
        self.assertItemsEqual(expected_list, response)

    def test_graphs_by_id_request(self):
        resp = self.app.get(
            reverse(
                'DeploymentGraphHandler',
                kwargs={'obj_id': self.custom_graph.id}
            ),
            headers=self.default_headers
        )
        self.assertItemsEqual(
            {
                'id': self.custom_graph.id,
                'name': 'custom-graph-name',
                'tasks': [{
                    'id': 'custom-task',
                    'type': 'puppet',
                    'version': '1.0.0'
                }],
                'relations': [{
                    'model': 'cluster',
                    'model_id': self.cluster.id,
                    'type': 'custom-graph'
                }],
            },
            resp.json_body
        )

    def test_graph_update(self):

        resp = self.app.put(
            reverse(
                'DeploymentGraphHandler',
                kwargs={'obj_id': self.custom_graph.id}
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
                'relations': [{
                    'model': 'cluster',
                    'model_id': self.cluster.id,
                    'type': 'custom-graph'
                }],
                'id': self.custom_graph.id
            },
            resp.json_body
        )

        resp = self.app.patch(
            reverse(
                'DeploymentGraphHandler',
                kwargs={'obj_id': self.custom_graph.id}
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
                'relations': [{
                    'model': 'cluster',
                    'model_id': self.cluster.id,
                    'type': 'custom-graph'
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
                kwargs={'obj_id': graph_id}
            ),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(204, resp.status_code)
        graph = DeploymentGraph.get_by_uid(graph_id)
        self.assertIsNone(graph)
        resp = self.app.get(
            reverse(
                'DeploymentGraphHandler',
                kwargs={'obj_id': graph_id}
            ),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(404, resp.status_code)

    def test_graph_update_fail_on_bad_schema(self):
        resp = self.app.put(
            reverse(
                'DeploymentGraphHandler',
                kwargs={'obj_id': self.custom_graph.id}
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
                kwargs={'obj_id': not_existing_id}
            ),
            '{}',
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(404, resp.status_code)


class TestLinkedGraphHandlers(BaseIntegrationTest):

    maxDiff = None

    def setUp(self):
        super(TestLinkedGraphHandlers, self).setUp()
        self.cluster = self.env.create_cluster(api=False)
        plugin_data = {
            'releases': [
                {
                    'repository_path': 'repositories/ubuntu',
                    'version': self.cluster.release.version,
                    'os': self.cluster.release.operating_system.lower(),
                    'mode': [self.cluster.mode],
                }
            ],
            'cluster': self.cluster,
            'enabled': True,
        }
        self.plugin = self.env.create_plugin(**plugin_data)
        self.env.db().commit()

        custom_graph1_data = {
            'name': 'custom-graph-name1',
            'tasks': [{
                'id': 'custom-task1',
                'type': 'puppet'
            }]
        }
        custom_graph2_data = {
            'name': 'custom-graph-name2',
            'tasks': [{
                'id': 'custom-task2',
                'type': 'puppet'
            }]
        }
        # replace default release graph with empty version to avoid
        # because it's default graph have special content
        DeploymentGraph.delete(
            DeploymentGraph.get_for_model(self.cluster.release))
        DeploymentGraph.create_for_model({}, self.cluster.release)
        self.custom_graphs = {
            'Cluster': {
                'model': self.cluster,
                'graphs': [
                    DeploymentGraph.create_for_model(
                        custom_graph1_data,
                        self.cluster,
                        graph_type='custom-graph1'),
                    DeploymentGraph.create_for_model(
                        custom_graph2_data,
                        self.cluster,
                        graph_type='custom-graph2')
                ]
            },
            'Release': {
                'model': self.cluster.release,
                'graphs': [
                    DeploymentGraph.create_for_model(
                        custom_graph1_data,
                        self.cluster.release,
                        graph_type='custom-graph1'),
                    DeploymentGraph.create_for_model(
                        custom_graph2_data,
                        self.cluster.release,
                        graph_type='custom-graph2'),
                ]
            },
            'Plugin': {
                'model': self.plugin,
                'graphs': [
                    DeploymentGraph.create_for_model(
                        custom_graph1_data,
                        self.plugin,
                        graph_type='custom-graph1'),
                    DeploymentGraph.create_for_model(
                        custom_graph2_data,
                        self.plugin,
                        graph_type='custom-graph2')
                ]
            }
        }

    def test_create_graph(self):
        for related_class, ref_graph in six.iteritems(self.custom_graphs):
            resp = self.app.post(
                reverse(
                    '{0}DeploymentGraphHandler'.format(related_class),
                    kwargs={
                        'obj_id': ref_graph['model'].id,
                        'graph_type': 'created-graph'
                    }
                ),
                jsonutils.dumps({
                    'name': 'custom-graph-name',
                    'tasks': [{
                        'id': 'test-task2',
                        'type': 'puppet'
                    }]
                }),
                headers=self.default_headers,
                expect_errors=True
            )
            self.assertEqual(200, resp.status_code)
            self.assertEqual(1, len(resp.json_body.get('tasks')))
            self.assertEqual('custom-graph-name', resp.json_body.get('name'))

    def test_create_graph_fail_on_existing(self):
        for related_class, ref_graph in six.iteritems(self.custom_graphs):
            resp = self.app.post(
                reverse(
                    '{0}DeploymentGraphHandler'.format(related_class),
                    kwargs={
                        'obj_id': ref_graph['model'].id,
                        'graph_type': 'default'
                    }
                ),
                jsonutils.dumps({
                    'name': 'custom-graph-name',
                    'tasks': [{
                        'id': 'test-task2',
                        'type': 'puppet'
                    }]
                }),
                headers=self.default_headers,
                expect_errors=True
            )
            self.assertEqual(409, resp.status_code)
            self.assertEqual(
                'Deployment graph with type "default" already exist.',
                resp.json_body.get('message'))

    def test_get_graph(self):
        for related_class, ref_graph in six.iteritems(self.custom_graphs):
            resp = self.app.get(
                reverse(
                    '{0}DeploymentGraphHandler'.format(related_class),
                    kwargs={
                        'obj_id': ref_graph['model'].id,
                        'graph_type': 'custom-graph1'
                    }
                ),
                headers=self.default_headers
            )
            self.assertEqual(200, resp.status_code)
            self.assertEqual(1, len(resp.json_body.get('tasks')))
            self.assertEqual('custom-graph-name1', resp.json_body.get('name'))

    def test_get_not_existing(self):
        for related_class, ref_graph in six.iteritems(self.custom_graphs):
            resp = self.app.get(
                reverse(
                    '{0}DeploymentGraphHandler'.format(related_class),
                    kwargs={
                        'obj_id': ref_graph['model'].id,
                        'graph_type': 'no-such-type'
                    }
                ),
                headers=self.default_headers,
                expect_errors=True
            )
            self.assertEqual(404, resp.status_code)
            self.assertEqual(
                "Graph with type: no-such-type is not defined",
                resp.json_body['message'])

    def test_existing_graph_update(self):
        for related_class, ref_graph in six.iteritems(self.custom_graphs):
            resp = self.app.put(
                reverse(
                    '{0}DeploymentGraphHandler'.format(related_class),
                    kwargs={
                        'obj_id': ref_graph['model'].id,
                        'graph_type': 'custom-graph1'
                    }
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

            graph_id = DeploymentGraph.get_for_model(
                ref_graph['model'], 'custom-graph1').id

            self.assertEqual(200, resp.status_code)
            self.assertEqual(
                {
                    'id': graph_id,
                    'name': 'updated-graph-name',
                    'tasks': [{
                        'id': 'test-task2',
                        'type': 'puppet',
                        'task_name': 'test-task2',
                        'version': '2.0.0'
                    }],
                    'relations': [{
                        'model': related_class.lower(),
                        'model_id': ref_graph['model'].id,
                        'type': 'custom-graph1'
                    }]

                },
                resp.json_body
            )

    def test_not_existing_graph_update(self):
        for related_class, ref_graph in six.iteritems(self.custom_graphs):
            resp = self.app.patch(
                reverse(
                    '{0}DeploymentGraphHandler'.format(related_class),
                    kwargs={
                        'obj_id': ref_graph['model'].id,
                        'graph_type': 'new-type'
                    }
                ),
                jsonutils.dumps({
                    'name': 'updated-graph-name',
                    'tasks': [{
                        'id': 'test-task2',
                        'type': 'puppet'
                    }]
                }),
                headers=self.default_headers,
                expect_errors=True
            )

            self.assertEqual(404, resp.status_code)

    def test_linked_graphs_list_handler(self):
        for related_class, ref_graph in six.iteritems(self.custom_graphs):
            resp = self.app.get(
                reverse(
                    '{0}DeploymentGraphCollectionHandler'.format(
                        related_class),
                    kwargs={
                        'obj_id': ref_graph['model'].id,
                    }
                ),
                headers=self.default_headers,
                expect_errors=True
            )
            default_graph = DeploymentGraph.get_for_model(ref_graph['model'])
            self.assertEqual(200, resp.status_code)
            self.assertItemsEqual(
                [
                    {
                        'id': ref_graph['graphs'][0].id,
                        'name': 'custom-graph-name1',
                        'tasks': [{
                            'id': 'custom-task1',
                            'task_name': 'custom-task1',
                            'type': 'puppet',
                            'version': '1.0.0'
                        }],
                        'relations': [{
                            'model': related_class.lower(),
                            'model_id': ref_graph['model'].id,
                            'type': 'custom-graph1'
                        }],
                    },
                    {
                        'id': ref_graph['graphs'][1].id,
                        'name': 'custom-graph-name2',
                        'tasks': [{
                            'id': 'custom-task2',
                            'task_name': 'custom-task2',
                            'type': 'puppet',
                            'version': '1.0.0'
                        }],
                        'relations': [{
                            'model': related_class.lower(),
                            'model_id': ref_graph['model'].id,
                            'type': 'custom-graph2'
                        }],
                    },
                    {
                        'tasks': [],
                        'id': default_graph.id,
                        'relations': [
                            {
                                'model': related_class.lower(),
                                'model_id': ref_graph['model'].id,
                                'type': 'default'
                            }
                        ],
                        'name': None
                    }
                ],
                resp.json_body
            )

    def test_linked_graph_deletion_delete(self):
        for related_class, ref_graph in six.iteritems(self.custom_graphs):
            resp = self.app.delete(
                reverse(
                    '{0}DeploymentGraphHandler'.format(related_class),
                    kwargs={
                        'obj_id': ref_graph['model'].id,
                        'graph_type': 'custom-graph1'
                    }
                ),
                headers=self.default_headers,
            )
            self.assertEqual(200, resp.status_code)

    def test_linked_graph_collection_should_not_delete(self):
        for related_class, ref_graph in six.iteritems(self.custom_graphs):
            resp = self.app.delete(
                reverse(
                    '{0}DeploymentGraphCollectionHandler'.format(
                        related_class),
                    kwargs={
                        'obj_id': ref_graph['model'].id,
                    }
                ),
                headers=self.default_headers,
                expect_errors=True
            )
            self.assertEqual(405, resp.status_code)
