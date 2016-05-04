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
from nailgun.orchestrator.orchestrator_graph import GraphSolver
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import DeploymentTasksTestMixin
from nailgun.utils import reverse

NOT_EXISTING_CLUSTER_ID = 0


class BaseGraphTasksTests(BaseIntegrationTest):

    def setUp(self):
        super(BaseGraphTasksTests, self).setUp()
        self.cluster = self.env.create(
            nodes_kwargs=[
                {'roles': ['test-controller'], 'pending_addition': True},
            ])
        self.cluster = self.env.clusters[0]
        self.cluster.release.roles_metadata.setdefault('test-controller', {})

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
        - id: test-controller
          type: group
          role: test-controller
        - id: test-controller-1
          groups: [test-controller]
          type: shell
          requires: [test-controller-2]
          parameters:
            cmd: bash -c 'echo 1'
        - id: test-controller-2
          type: shell
          parameters:
            cmd: bash -c 'echo 1'
          groups: [test-controller]
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
        - id: test-controller-1
          groups: [test-controller]
          type: shell
          requires: [test-controller-2]
          parameters:
            cmd: bash -c 'echo 1'
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

    def test_upload_custom_deployment_graph_tasks(self):
        tasks = self.get_correct_tasks()
        resp = self.app.put(
            reverse('ReleaseDeploymentTasksHandler',
                    kwargs={'obj_id': self.cluster.release.id}) +
            '?graph_type=custom-graph',
            params=jsonutils.dumps(tasks),
            headers=self.default_headers,
        )
        release_tasks = objects.Release.get_deployment_tasks(
            self.cluster.release, 'custom-graph')

        # merged deployment tasks
        cluster_tasks = objects.Cluster.get_deployment_tasks(
            self.cluster, 'custom-graph')

        self._compare_tasks(resp.json, release_tasks)
        for task in resp.json:
            self.assertIn(task, cluster_tasks)

    def test_get_custom_deployment_graph_tasks(self):
        objects.DeploymentGraph.create_for_model(
            {'tasks': [
                {
                    'id': 'custom-task',
                    'type': 'puppet'
                }
            ]}, self.cluster.release, 'custom-graph')

        resp = self.app.get(
            reverse(
                'ReleaseDeploymentTasksHandler',
                kwargs={'obj_id': self.cluster.release.id}
            ) + '?graph_type=custom-graph',
            headers=self.default_headers
        )
        self.assertItemsEqual(
            resp.json,
            [
                {
                    'id': 'custom-task',
                    'task_name': 'custom-task',
                    'version': '1.0.0',
                    'type': 'puppet'
                }
            ]
        )

    @mock.patch('nailgun.task.task.rpc.cast')
    def test_run_deployment_with_cycles(self, mocked_rpc):
        tasks = self.get_tasks_with_cycles()
        with mock.patch.object(objects.Cluster, 'get_deployment_tasks',
                               return_value=tasks):

            self.emulate_nodes_provisioning(self.cluster.nodes)

            supertask = self.env.launch_deployment()
            self.assertEqual(supertask.status, consts.TASK_STATUSES.error)
            self.assertRegexpMatches(supertask.message, '.*cycles.*')

    @mock.patch('nailgun.task.task.rpc.cast')
    def test_run_deployment_with_incorrect_dependencies(self, mocked_rpc):
        tasks = self.get_tasks_with_incorrect_dependencies()
        with mock.patch.object(objects.Cluster, 'get_deployment_tasks',
                               return_value=tasks):
            self.emulate_nodes_provisioning(self.cluster.nodes)
            supertask = self.env.launch_deployment()
            self.assertEqual(supertask.status, consts.TASK_STATUSES.error)
            self.assertRegexpMatches(supertask.message,
                                     ".*can't be in requires.*")

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

    maxDiff = None

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
        self.assertItemsEqual(resp.json, release_tasks)

    def test_get_custom_deployment_graph_tasks(self):
        objects.DeploymentGraph.create_for_model(
            {'tasks': [
                {
                    'id': 'custom-task',
                    'type': 'puppet'
                }
            ]}, self.cluster, 'custom-graph')

        resp = self.app.get(
            reverse(
                'ClusterDeploymentTasksHandler',
                kwargs={'obj_id': self.cluster.id}
            ) + '?graph_type=custom-graph',
            headers=self.default_headers
        )
        self.assertItemsEqual(
            resp.json,
            [
                {
                    'id': 'custom-task',
                    'task_name': 'custom-task',
                    'version': '1.0.0',
                    'type': 'puppet'
                }
            ]
        )

    def test_upload_deployment_tasks(self):
        tasks = self.get_correct_tasks()
        resp = self.app.put(
            reverse('ClusterDeploymentTasksHandler',
                    kwargs={'obj_id': self.cluster.id}),
            params=jsonutils.dumps(tasks),
            headers=self.default_headers,
        )
        cluster_own_tasks = objects.Cluster.get_own_deployment_tasks(
            self.cluster)
        cluster_tasks = objects.Cluster.get_deployment_tasks(self.cluster)

        self._compare_tasks(resp.json, cluster_own_tasks)
        # cluster tasks is a merged tasks with underlying release tasks
        for task in resp.json:
            self.assertIn(task, cluster_tasks)

    def test_upload_custom_deployment_graph_tasks(self):
        tasks = self.get_correct_tasks()
        resp = self.app.put(
            reverse('ClusterDeploymentTasksHandler',
                    kwargs={'obj_id': self.cluster.id}) +
            '?graph_type=custom-graph',
            params=jsonutils.dumps(tasks),
            headers=self.default_headers,
        )
        cluster_own_tasks = objects.Cluster.get_own_deployment_tasks(
            self.cluster, 'custom-graph')
        cluster_tasks = objects.Cluster.get_deployment_tasks(
            self.cluster, 'custom-graph')

        self._compare_tasks(resp.json, cluster_own_tasks)
        for task in resp.json:
            self.assertIn(task, cluster_tasks)

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
        cluster_own_tasks = objects.Cluster.get_own_deployment_tasks(
            self.cluster)
        cluster_tasks = objects.Cluster.get_deployment_tasks(self.cluster)

        self._compare_tasks(resp.json, cluster_own_tasks)
        # cluster tasks is a merged tasks with underlying release tasks
        for task in resp.json:
            self.assertIn(task, cluster_tasks)

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


class TestClusterPluginsGraphHandler(BaseGraphTasksTests,
                                     DeploymentTasksTestMixin):
    deployment_tasks = [
        {'id': 'test-task', 'type': 'puppet'}
    ]

    def setUp(self):
        super(TestClusterPluginsGraphHandler, self).setUp()
        self.env.create_plugin(
            cluster=self.cluster,
            package_version='5.0.0',
            deployment_tasks=self.deployment_tasks)

    def test_get_deployment_tasks(self):
        resp = self.app.get(
            reverse('ClusterPluginsDeploymentTasksHandler',
                    kwargs={'obj_id': self.cluster.id}),
            headers=self.default_headers,
        )
        self.assertEqual(resp.status_code, 200)
        self._compare_tasks(self.deployment_tasks, resp.json)

    def test_get_custom_deployment_tasks_empty(self):
        resp = self.app.get(
            reverse('ClusterPluginsDeploymentTasksHandler',
                    kwargs={'obj_id': self.cluster.id}) +
            '?graph_type=non-existing-custom',
            headers=self.default_headers,
        )
        self.assertEqual(resp.status_code, 200)
        self._compare_tasks([], resp.json)

    def test_post_deployment_tasks_fail(self):
        resp = self.app.post(
            reverse('ClusterPluginsDeploymentTasksHandler',
                    kwargs={'obj_id': self.cluster.id}),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(resp.status_code, 405)

    def test_put_deployment_tasks_fail(self):
        resp = self.app.put(
            reverse('ClusterPluginsDeploymentTasksHandler',
                    kwargs={'obj_id': self.cluster.id}),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(resp.status_code, 405)

    def test_get_plugins_deployment_tasks_not_existing_cluster_fail(self):
        resp = self.app.get(
            reverse('ClusterPluginsDeploymentTasksHandler',
                    kwargs={'obj_id': NOT_EXISTING_CLUSTER_ID}),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(resp.status_code, 404)


class TestReleasePluginsGraphHandler(BaseGraphTasksTests,
                                     DeploymentTasksTestMixin):
    deployment_tasks = [
        {'id': 'test-task', 'type': 'puppet'}
    ]

    def setUp(self):
        super(TestReleasePluginsGraphHandler, self).setUp()
        objects.DeploymentGraph.create_for_model(
            {'tasks': self.deployment_tasks},
            self.cluster.release,
            'custom-graph')

    def test_get_deployment_tasks(self):
        resp = self.app.get(
            reverse('ClusterReleaseDeploymentTasksHandler',
                    kwargs={'obj_id': self.cluster.id}),
            headers=self.default_headers,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json), 25)    # default release tasks

    def test_get_existing_custom_deployment_tasks(self):
        resp = self.app.get(
            reverse('ClusterReleaseDeploymentTasksHandler',
                    kwargs={'obj_id': self.cluster.id}) +
            '?graph_type=custom-graph',
            headers=self.default_headers,
        )
        self.assertEqual(resp.status_code, 200)
        self._compare_tasks(self.deployment_tasks, resp.json)

    def test_not_existing_custom_deployment_tasks(self):
        resp = self.app.get(
            reverse('ClusterReleaseDeploymentTasksHandler',
                    kwargs={'obj_id': self.cluster.id}) +
            '?graph_type=not-existing-custom-graph',
            headers=self.default_headers,
        )
        self.assertEqual(resp.status_code, 200)
        self._compare_tasks([], resp.json)

    def test_post_deployment_tasks_fail(self):
        resp = self.app.post(
            reverse('ClusterReleaseDeploymentTasksHandler',
                    kwargs={'obj_id': self.cluster.id}),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(resp.status_code, 405)

    def test_put_deployment_tasks_fail(self):
        resp = self.app.put(
            reverse('ClusterReleaseDeploymentTasksHandler',
                    kwargs={'obj_id': self.cluster.id}),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(resp.status_code, 405)

    def test_get_release_deployment_tasks_not_existing_cluster_fail(self):
        resp = self.app.get(
            reverse('ClusterReleaseDeploymentTasksHandler',
                    kwargs={'obj_id': NOT_EXISTING_CLUSTER_ID}),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(resp.status_code, 404)


class TestStartEndTaskPassedCorrectly(BaseGraphTasksTests):

    def assert_passed_correctly(self, url, **kwargs):
        with mock.patch.object(GraphSolver,
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
        self.cluster = self.env.create()

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


class TestCustomTaskDeployGraph(BaseGraphTasksTests):

    content_type = 'text/vnd.graphviz'

    def test_with_custom_graph(self):
        self.env.create()
        cluster = self.env.clusters[-1]

        objects.DeploymentGraph.create_for_model(
            {
                'tasks': [
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
            },
            cluster,
            'custom-graph'
        )

        resp = self.app.get(
            reverse('TaskDeployGraph', kwargs={
                'cluster_id': cluster.id,
                'graph_type': 'custom-graph'
            }) + '?graph_type=custom-graph',
            expect_errors=True
        )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content_type, self.content_type)
        self.assertIn('"pre-A" -> pre_deployment', resp.body)
        self.assertIn('"pre-A" -> "pre-B"', resp.body)
        self.assertIn('"pre-A" -> "pre-C"', resp.body)

    def test_with_custom_graph_validator_fail(self):
        self.env.create()
        cluster = self.env.clusters[-1]

        objects.DeploymentGraph.create_for_model(
            {
                'tasks': []
            },
            cluster,
            'custom-graph'
        )

        resp = self.app.get(
            reverse('TaskDeployGraph', kwargs={
                'cluster_id': cluster.id,
                'graph_type': 'custom-graph'
            }) + '?graph_type=custom-graph&parents_for=upload_nodes_info',
            expect_errors=True
        )

        self.assertEqual(resp.status_code, 400)
        self.assertIn(
            'Task upload_nodes_info is not present in graph',
            resp.body)


class TestTaskDeployCustomGraph(BaseGraphTasksTests):

    content_type = 'text/vnd.graphviz'

    def setUp(self):
        super(TestTaskDeployCustomGraph, self).setUp()
        self.cluster = self.env.create()

    def test_get_custom_tasks(self):
        objects.DeploymentGraph.create_for_model(
            {'tasks': [
                {'id': 'pre_deployment', 'type': 'stage'},
                {'id': 'custom-task', 'required_for': ['pre_deployment'],
                 'type': 'puppet'},
            ]}, self.cluster, 'custom-graph')

        resp = self.app.get(
            reverse('TaskDeployGraph', kwargs={
                'cluster_id': self.cluster.id,
            }) + '?graph_type=custom-graph',
        )
        self.assertIn('"custom-task" -> pre_deployment;', resp.body)
