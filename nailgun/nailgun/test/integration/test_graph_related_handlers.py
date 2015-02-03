# -*- coding: utf-8 -*-

#    Copyright 2014 Mirantis, Inc.
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
import yaml

from nailgun import objects
from nailgun.openstack.common import jsonutils
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import reverse


class BaseGraphTasksTests(BaseIntegrationTest):

    def setUp(self):
        super(BaseGraphTasksTests, self).setUp()
        self.env.create()
        self.cluster = self.env.clusters[0]

    def get_correct_tasks(self):
        yaml_tasks = """
        - id: primary-controller
          type: group
          role: [primary-controller]
          required_for: [deploy]
          parameters:
            strategy:
              type: one_by_one
        - id: controller
          type: group
          role: [primary-controller]
          requires: [primary-controller]
          required_for: [deploy]
          parameters:
            strategy:
              type: parallel
              amount: 2
        """
        return yaml.load(yaml_tasks)

    def get_corrupted_tasks(self):
        yaml_tasks = """
        - id: primary-controller
          required_for: [deploy]
          parameters:
            strategy:
              type: one_by_one
        """
        return yaml.load(yaml_tasks)

    def get_tasks_with_cycles(self):
        yaml_tasks = """
        - id: primary-controller
          type: role
          requires: [controller]
        - id: controller
          type: role
          requires: [primary-controller]
        """
        return yaml.load(yaml_tasks)


class TestReleaseGraphHandler(BaseGraphTasksTests):

    def test_get_deployment_tasks(self):
        resp = self.app.get(
            reverse('ReleaseDeploymentTasksHandler',
                    kwargs={'obj_id': self.cluster.release_id}),
            headers=self.default_headers,
        )
        release_tasks = objects.Release.get_deployment_tasks(
            self.cluster.release)
        self.assertEqual(resp.json, release_tasks)

    def test_upload_deployment_tasks(self):
        tasks = self.get_correct_tasks()
        resp = self.app.put(
            reverse('ReleaseDeploymentTasksHandler',
                    kwargs={'obj_id': self.cluster.release_id}),
            params=jsonutils.dumps(tasks),
            headers=self.default_headers,
        )
        release_tasks = objects.Release.get_deployment_tasks(
            self.cluster.release)
        self.assertEqual(release_tasks, resp.json)

    def test_upload_tasks_without_type(self):
        tasks = self.get_corrupted_tasks()
        resp = self.app.put(
            reverse('ReleaseDeploymentTasksHandler',
                    kwargs={'obj_id': self.cluster.release_id}),
            params=jsonutils.dumps(tasks),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(resp.status_code, 400)

    def test_upload_tasks_with_cycles(self):
        tasks = self.get_tasks_with_cycles()
        resp = self.app.put(
            reverse('ReleaseDeploymentTasksHandler',
                    kwargs={'obj_id': self.cluster.release_id}),
            params=jsonutils.dumps(tasks),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(resp.status_code, 400)

    def test_post_tasks(self):
        resp = self.app.post(
            reverse('ReleaseDeploymentTasksHandler',
                    kwargs={'obj_id': self.cluster.release_id}),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(resp.status_code, 405)

    def test_delete_tasks(self):
        resp = self.app.delete(
            reverse('ReleaseDeploymentTasksHandler',
                    kwargs={'obj_id': self.cluster.release_id}),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(resp.status_code, 405)


class TestClusterGraphHandler(BaseGraphTasksTests):

    def test_get_deployment_tasks(self):
        resp = self.app.get(
            reverse('ClusterDeploymentTasksHandler',
                    kwargs={'obj_id': self.cluster.id}),
            headers=self.default_headers,
        )
        cluster_tasks = objects.Cluster.get_deployment_tasks(self.cluster)
        self.assertEqual(resp.json, cluster_tasks)

    def test_deployment_tasks_equals_to_release(self):
        resp = self.app.get(
            reverse('ClusterDeploymentTasksHandler',
                    kwargs={'obj_id': self.cluster.id}),
            headers=self.default_headers,
        )
        release_tasks = objects.Release.get_deployment_tasks(
            self.cluster.release)
        self.assertEqual(resp.json, release_tasks)

    def test_upload_deployment_tasks(self):
        tasks = self.get_correct_tasks()
        resp = self.app.put(
            reverse('ClusterDeploymentTasksHandler',
                    kwargs={'obj_id': self.cluster.id}),
            params=jsonutils.dumps(tasks),
            headers=self.default_headers,
        )
        cluster_tasks = objects.Cluster.get_deployment_tasks(self.cluster)
        self.assertEqual(cluster_tasks, resp.json)

    def test_upload_tasks_without_type(self):
        tasks = self.get_corrupted_tasks()
        resp = self.app.put(
            reverse('ClusterDeploymentTasksHandler',
                    kwargs={'obj_id': self.cluster.id}),
            params=jsonutils.dumps(tasks),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(resp.status_code, 400)

    def test_upload_tasks_with_cycles(self):
        tasks = self.get_tasks_with_cycles()
        resp = self.app.put(
            reverse('ClusterDeploymentTasksHandler',
                    kwargs={'obj_id': self.cluster.id}),
            params=jsonutils.dumps(tasks),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(resp.status_code, 400)

    def test_post_tasks(self):
        resp = self.app.post(
            reverse('ClusterDeploymentTasksHandler',
                    kwargs={'obj_id': self.cluster.id}),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(resp.status_code, 405)

    def test_delete_tasks(self):
        resp = self.app.delete(
            reverse('ClusterDeploymentTasksHandler',
                    kwargs={'obj_id': self.cluster.id}),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(resp.status_code, 405)


@mock.patch('nailgun.api.v1.handlers.base.deployment_graph.DeploymentGraph')
class TestEndTaskPassedCorrectly(BaseGraphTasksTests):

    def assert_end_passed_correctly(self, url, graph_mock):
        resp = self.app.get(
            url,
            params={'end': 'task'},
            headers=self.default_headers,
        )
        self.assertEqual(resp.status_code, 200)
        graph_mock().find_subgraph.assert_called_with('task')

    def test_end_passed_correctly_for_cluster(self, graph_mock):
        self.assert_end_passed_correctly(
            reverse('ClusterDeploymentTasksHandler',
                    kwargs={'obj_id': self.cluster.id}),
            graph_mock)

    def test_end_passed_correctly_for_release(self, graph_mock):
        self.assert_end_passed_correctly(
            reverse('ReleaseDeploymentTasksHandler',
                    kwargs={'obj_id': self.cluster.release.id}),
            graph_mock)


class TestTaskDeployGraph(BaseGraphTasksTests):

    def setUp(self):
        super(TestTaskDeployGraph, self).setUp()
        self.env.create(
            nodes_kwargs=[
                {'roles': ['controller'], 'pending_addition': True},
                {'roles': ['controller'], 'pending_addition': True},
                {'roles': ['compute'], 'pending_addition': True},
            ]
        )

        self.cluster = self.env.clusters[0]

    @mock.patch.object(objects.Cluster, 'get_deployment_tasks')
    def test_get_all_tasks(self, m_get_tasks):
        m_get_tasks.return_value = [
            {'id': 'pre_deployment'},
            {'id': 'task-A', 'required_for': ['pre_deployment']},
        ]
        resp = self.app.get(
            reverse('TaskDeployGraph', kwargs={'cluster_id': self.cluster.id})
        )
        content_type = 'text/vnd.graphviz'
        self.assertEqual(resp.content_type, content_type)
        self.assertIn('"task-A" -> pre_deployment', resp.body)

    def test_use_certain_tasks(self):
        self.env.create(
            nodes_kwargs=[
                {'roles': ['controller'], 'pending_addition': True},
            ]
        )
        resp = self.app.post(
            reverse('TaskDeployGraph', kwargs={'cluster_id': self.cluster.id}),
            jsonutils.dumps(['deploy_legacy', ])
        )
        content_type = 'text/vnd.graphviz'
        self.assertEqual(resp.content_type, content_type)

    def test_error_raised_on_non_existent_tasks(self):
        self.env.create(
            nodes_kwargs=[
                {'roles': ['controller'], 'pending_addition': True},
            ]
        )
        resp = self.app.post(
            reverse('TaskDeployGraph', kwargs={'cluster_id': self.cluster.id}),
            jsonutils.dumps(['faketask', ]),
            expect_errors=True
        )
        self.assertEqual(resp.status_code, 400)
