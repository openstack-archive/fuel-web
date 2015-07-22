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
from oslo.serialization import jsonutils
import yaml

from nailgun import consts
from nailgun.objects import objects
from nailgun.orchestrator.deployment_graph import DeploymentGraph
from nailgun.test.base import BaseIntegrationTest
from nailgun.utils import reverse


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


class TestStartEndTaskPassedCorrectly(BaseGraphTasksTests):

    def assert_passed_correctly(self, url, **kwargs):
        with mock.patch.object(DeploymentGraph,
                               'find_subgraph') as mfind_subgraph:
            resp = self.app.get(
                url,
                params=kwargs,
                headers=self.default_headers,
            )
        self.assertEqual(resp.status_code, 200)
        defaults = {'start': None, 'end': None}
        defaults.update(kwargs)
        mfind_subgraph.assert_called_with(**defaults)

    def test_end_passed_correctly_for_cluster(self):
        self.assert_passed_correctly(
            reverse('ClusterDeploymentTasksHandler',
                    kwargs={'obj_id': self.cluster.id}), end='task')

    def test_end_passed_correctly_for_release(self):
        self.assert_passed_correctly(
            reverse('ReleaseDeploymentTasksHandler',
                    kwargs={'obj_id': self.cluster.release.id}), end='task')

    def test_start_passed_correctly_release(self):
        self.assert_passed_correctly(
            reverse('ReleaseDeploymentTasksHandler',
                    kwargs={'obj_id': self.cluster.release.id}), start='task')

    def test_start_passed_correctly_cluster(self):
        self.assert_passed_correctly(
            reverse('ClusterDeploymentTasksHandler',
                    kwargs={'obj_id': self.cluster.id}), end='task')

    def test_start_end_passed_correctly_cluster(self):
        self.assert_passed_correctly(
            reverse('ClusterDeploymentTasksHandler',
                    kwargs={'obj_id': self.cluster.id}),
            end='task', start='another_task')

    def test_start_end_passed_correctly_release(self):
        self.assert_passed_correctly(
            reverse('ReleaseDeploymentTasksHandler',
                    kwargs={'obj_id': self.cluster.release.id}),
            end='task', start='another_task')


@mock.patch.object('nailgun.objects.cluster.Cluster', 'get_deployment_tasks')
class TestTaskDeployGraph(BaseGraphTasksTests):

    content_type = 'text/vnd.graphviz'

    def setUp(self):
        super(TestTaskDeployGraph, self).setUp()
        self.env.create()

        self.cluster = self.env.clusters[0]
        self.tasks = [
            {'id': 'pre_deployment', 'type': 'stage'},
            {'id': 'deploy', 'type': 'stage'},
            {'id': 'post_deployment', 'type': 'stage'},
            {'id': 'pre-A', 'required_for': ['pre_deployment'],
             'type': 'puppet'},
            {'id': 'pre-B', 'required_for': ['pre_deployment'],
             'type': 'puppet', 'requires': ['pre-A']},
            {'id': 'pre-C', 'required_for': ['pre_deployment'],
             'type': 'puppet', 'requires': ['pre-A', 'pre-D']},
            {'id': 'pre-D', 'required_for': ['pre_deployment'],
             'type': 'puppet'},
        ]

    def test_get_all_tasks(self, m_get_tasks):
        m_get_tasks.return_value = self.tasks
        resp = self.app.get(
            reverse('TaskDeployGraph', kwargs={'cluster_id': self.cluster.id})
        )
        self.assertEqual(resp.content_type, self.content_type)
        self.assertIn('"pre-A" -> pre_deployment', resp.body)
        self.assertIn('"pre-A" -> "pre-B"', resp.body)
        self.assertIn('"pre-A" -> "pre-C"', resp.body)

    def test_use_certain_tasks(self, m_get_tasks):
        m_get_tasks.return_value = self.tasks
        resp = self.app.get(
            reverse('TaskDeployGraph', kwargs={
                'cluster_id': self.cluster.id,
            }) + '?tasks=pre-A,pre-C',
        )
        self.assertEqual(resp.content_type, self.content_type)
        self.assertIn('"pre-A" -> "pre-B"', resp.body)
        self.assertIn('"pre-A" -> "pre-C"', resp.body)

    def test_error_raised_on_non_existent_tasks(self, m_get_tasks):
        m_get_tasks.return_value = self.tasks
        resp = self.app.get(
            reverse('TaskDeployGraph', kwargs={
                'cluster_id': self.cluster.id,
            }) + '?tasks=nonexistent',
            expect_errors=True,
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Tasks nonexistent are not present in deployment graph',
                      resp.body)

    def test_use_single_task(self, m_get_tasks):
        m_get_tasks.return_value = self.tasks
        resp = self.app.get(
            reverse('TaskDeployGraph', kwargs={
                'cluster_id': self.cluster.id,
            }) + '?parents_for=pre-B',
        )
        self.assertEqual(resp.content_type, self.content_type)
        self.assertIn('"pre-A" -> "pre-B"', resp.body)
        self.assertNotIn('pre_deployment', resp.body)
        self.assertNotIn('pre-C', resp.body)

    def test_error_raised_on_non_existent_signle_task(self, m_get_tasks):
        m_get_tasks.return_value = self.tasks
        resp = self.app.get(
            reverse('TaskDeployGraph', kwargs={
                'cluster_id': self.cluster.id,
            }) + '?parents_for=nonexistent',
            expect_errors=True,
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Task nonexistent is not present in graph', resp.body)

    def test_single_task_from_tasks_subset(self, m_get_tasks):
        """If only pre-B and pre-A tasks will be executed,
        what requirements pre-C will have?
        """
        m_get_tasks.return_value = self.tasks
        resp = self.app.get(
            reverse('TaskDeployGraph', kwargs={
                'cluster_id': self.cluster.id,
            }) + '?tasks=pre-B,pre-A&parents_for=pre-C',
        )
        self.assertEqual(resp.content_type, self.content_type)
        self.assertIn('"pre-A" -> "pre-C"', resp.body)
        self.assertIn('"pre-D" -> "pre-C"', resp.body)
        self.assertNotIn('pre_deployment', resp.body)
        self.assertNotIn('pre-B', resp.body)

    def test_remove_tasks_by_type(self, m_get_tasks):
        tasks = []
        for task_type in consts.INTERNAL_TASKS:
            tasks.append({
                'id': 'task-{0}'.format(task_type),
                'type': task_type,
            })
        m_get_tasks.return_value = tasks

        resp = self.app.get(
            reverse('TaskDeployGraph', kwargs={
                'cluster_id': self.cluster.id,
            }) + '?remove={0}'.format(
                ','.join(consts.INTERNAL_TASKS)),
        )

        for task in tasks:
            self.assertNotIn(task['id'], resp.body)

    def test_remove_non_existent_type(self, m_get_tasks):
        m_get_tasks.return_value = self.tasks
        resp = self.app.get(
            reverse('TaskDeployGraph', kwargs={
                'cluster_id': self.cluster.id,
            }) + '?remove=nonexistent',
            expect_errors=True,
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Task types nonexistent do not exist', resp.body)
