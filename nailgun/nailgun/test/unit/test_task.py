# -*- coding: utf-8 -*-
#    Copyright 2013 Mirantis, Inc.
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

from nailgun.api.models import Task
from nailgun.task.helpers import TaskHelper
from nailgun.test.base import BaseTestCase


class TestHelperUpdateClusterStatus(BaseTestCase):

    def setUp(self):
        super(TestHelperUpdateClusterStatus, self).setUp()
        self.env.create(
            cluster_kwargs={
                'mode': 'ha_compact'},
            nodes_kwargs=[
                {'roles': ['controller']},
                {'roles': ['compute']},
                {'roles': ['cinder']}])

    def node_should_be_error_with_type(self, node, error_type):
        self.assertEquals(node.status, 'error')
        self.assertEquals(node.error_type, error_type)
        self.assertEquals(node.progress, 0)

    def nodes_should_not_be_error(self, nodes):
        for node in nodes:
            self.assertEquals(node.status, 'discover')

    @property
    def cluster(self):
        return self.env.clusters[0]

    @property
    def nodes(self):
        return sorted(self.cluster.nodes, key=lambda n: n.id)

    def test_update_nodes_to_error_if_deployment_task_failed(self):
        self.nodes[0].status = 'deploying'
        self.nodes[0].progress = 12
        task = Task(name='deployment', cluster=self.cluster, status='error')
        self.db.add(task)
        self.db.commit()

        TaskHelper.update_cluster_status(task.uuid)

        self.assertEquals(self.cluster.status, 'error')
        self.node_should_be_error_with_type(self.nodes[0], 'deploy')
        self.nodes_should_not_be_error(self.nodes[1:])

    def test_update_cluster_to_error_if_deploy_task_failed(self):
        task = Task(name='deploy', cluster=self.cluster, status='error')
        self.db.add(task)
        self.db.commit()

        TaskHelper.update_cluster_status(task.uuid)

        self.assertEquals(self.cluster.status, 'error')

    def test_update_nodes_to_error_if_provision_task_failed(self):
        self.nodes[0].status = 'provisioning'
        self.nodes[0].progress = 12
        task = Task(name='provision', cluster=self.cluster, status='error')
        self.db.add(task)
        self.db.commit()

        TaskHelper.update_cluster_status(task.uuid)

        self.assertEquals(self.cluster.status, 'error')
        self.node_should_be_error_with_type(self.nodes[0], 'provision')
        self.nodes_should_not_be_error(self.nodes[1:])

    def test_update_cluster_to_operational(self):
        task = Task(name='deploy', cluster=self.cluster, status='ready')
        self.db.add(task)
        self.db.commit()

        TaskHelper.update_cluster_status(task.uuid)

        self.assertEquals(self.cluster.status, 'operational')

    def test_update_if_parent_task_is_ready_all_nodes_should_be_ready(self):
        for node in self.nodes:
            node.status = 'ready'
            node.progress = 100

        self.nodes[0].status = 'deploying'
        self.nodes[0].progress = 24

        task = Task(name='deploy', cluster=self.cluster, status='ready')
        self.db.add(task)
        self.db.commit()

        TaskHelper.update_cluster_status(task.uuid)

        self.assertEquals(self.cluster.status, 'operational')

        for node in self.nodes:
            self.assertEquals(node.status, 'ready')
            self.assertEquals(node.progress, 100)
