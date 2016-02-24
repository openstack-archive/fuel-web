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

from oslo_serialization import jsonutils
import yaml

from nailgun import consts
from nailgun import objects
from nailgun.orchestrator.deployment_graph import DeploymentGraph
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import DeploymentTasksTestMixin
from nailgun.utils import reverse


class BaseGraphTasksTests(BaseIntegrationTest):

    def setUp(self):
        super(BaseGraphTasksTests, self).setUp()
        self.env.create()
        self.cluster = self.env.clusters[0]

    def get_correct_tasks(self):
        yaml_tasks = """
        - id: deploy_start
          type: stage
          requires: [pre_deployment_end]
        - id: deploy_end
          type: stage
          version: 1.0.0
          requires: [deploy_start]
        - id: pre_deployment_start
          type: stage
        - id: pre_deployment_end
          type: stage
          requires: [pre_deployment_start]
        - id: primary-controller
          type: group
          role: [primary-controller]
          required_for: [deploy_end]
          requires: [deploy_start]
          parameters:
            strategy:
              type: one_by_one
        - id: test-controller
          type: group
          role: [test-controller]
          requires: [primary-controller]
          required_for: [deploy_end]
          parameters:
            strategy:
              type: parallel
              amount: 2
        """
        return yaml.load(yaml_tasks)

    def get_corrupted_tasks(self):
        yaml_tasks = """
        - id: test-controller
          required_for: [deploy_end]
          parameters:
            strategy:
              type: one_by_one
        """
        return yaml.load(yaml_tasks)

    def get_tasks_with_unsuported_role(self):
        yaml_tasks = """
        - id: test-controller
          role: "test-controller"
          parameters:
            strategy:
              type: one_by_one
        """
        return yaml.load(yaml_tasks)

    def get_tasks_with_cycles(self):
        yaml_tasks = """
        - id: test-controller-1
          type: role
          requires: [test-controller-2]
        - id: test-controller-2
          type: role
          requires: [test-controller-1]
        """
        return yaml.load(yaml_tasks)

    def get_tasks_with_incorrect_dependencies(self):
        yaml_tasks = """
        - id: test-controller
          type: group
          role: [test-controller]
          required_for: [non_existing_stage]
          parameters:
            strategy:
              type: one_by_one
        """
        return yaml.load(yaml_tasks)

    def get_tasks_with_cross_dependencies(self):
        yaml_tasks = """
        - id: test-controller
          type: group
          version: 2.0.0
          role: [test-controller]
          cross-depends:
             - name: test-compute
               role: '*'
               polcy: any
          parameters:
            strategy:
              type: one_by_one
        - id: test-compute
          type: group
          version: 2.0.0
          role: [test-compute]
          cross-depends:
              - name: test-cinder
                role: [test_cinder]
          parameters:
            strategy:
              type: one_by_one
        - id: test-cinder
          type: group
          version: 2.0.0
          role: [test-cinder]
          parameters:
            strategy:
              type: one_by_one
        """
        return yaml.load(yaml_tasks)

    def get_tasks_cross_dependencies_without_name(self):
        yaml_tasks = """
        - id: test-controller
          type: group
          role: [test-controller]
          cross-depends:
             - role: '*'
               polcy: any
          parameters:
            strategy:
              type: one_by_one
        """
        return yaml.load(yaml_tasks)


class TestReleaseGraphHandler(BaseGraphTasksTests, DeploymentTasksTestMixin):

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
        self._compare_tasks(resp.json, release_tasks)

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

    def test_upload_tasks_with_incorrect_dependencies(self):
        tasks = self.get_tasks_with_incorrect_dependencies()
        resp = self.app.put(
            reverse('ReleaseDeploymentTasksHandler',
                    kwargs={'obj_id': self.cluster.release_id}),
            params=jsonutils.dumps(tasks),
            headers=self.default_headers,
            expect_errors=True
        )

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(
            "Tasks 'non_existing_stage' can't be in requires|required_for|"
            "groups|tasks for [test-controller] because they don't exist in "
            "the graph", resp.json_body['message'])

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


class TestClusterGraphHandler(BaseGraphTasksTests, DeploymentTasksTestMixin):

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
        self._compare_tasks(resp.json, cluster_tasks)

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

    def test_upload_tasks_with_incorrect_dependencies(self):
        tasks = self.get_tasks_with_incorrect_dependencies()
        resp = self.app.put(
            reverse('ClusterDeploymentTasksHandler',
                    kwargs={'obj_id': self.cluster.id}),
            params=jsonutils.dumps(tasks),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(
            "Tasks 'non_existing_stage' can't be in requires|required_for|"
            "groups|tasks for [test-controller] because they don't exist in "
            "the graph", resp.json_body['message'])

    def test_upload_tasks_without_unsupported_role(self):
        tasks = self.get_tasks_with_unsuported_role()
        resp = self.app.put(
            reverse('ClusterDeploymentTasksHandler',
                    kwargs={'obj_id': self.cluster.id}),
            params=jsonutils.dumps(tasks),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(resp.status_code, 400)

    def test_upload_tasks_with_cross_dependencies(self):
        tasks = self.get_tasks_with_cross_dependencies()
        resp = self.app.put(
            reverse('ClusterDeploymentTasksHandler',
                    kwargs={'obj_id': self.cluster.id}),
            params=jsonutils.dumps(tasks),
            headers=self.default_headers,
        )
        cluster_tasks = objects.Cluster.get_deployment_tasks(self.cluster)
        self.assertEqual(cluster_tasks, resp.json)

    def test_upload_cross_dependencies_without_name(self):
        tasks = self.get_tasks_cross_dependencies_without_name()
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


@mock.patch.object(objects.Cluster, 'get_deployment_tasks')
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
