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
