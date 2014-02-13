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

from mock import patch

from nailgun.db.sqlalchemy.models import Task
from nailgun.errors import errors
from nailgun.task.helpers import TaskHelper
from nailgun.task.task import CheckBeforeDeploymentTask
from nailgun.test.base import BaseTestCase
from nailgun.volumes.manager import VolumeManager


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

    def test_update_nodes_to_error_if_deployment_task_failed(self):
        self.cluster.nodes[0].status = 'deploying'
        self.cluster.nodes[0].progress = 12
        task = Task(name='deployment', cluster=self.cluster, status='error')
        self.db.add(task)
        self.db.commit()

        TaskHelper.update_cluster_status(task.uuid)

        self.assertEquals(self.cluster.status, 'error')
        self.node_should_be_error_with_type(self.cluster.nodes[0], 'deploy')
        self.nodes_should_not_be_error(self.cluster.nodes[1:])

    def test_update_cluster_to_error_if_deploy_task_failed(self):
        task = Task(name='deploy', cluster=self.cluster, status='error')
        self.db.add(task)
        self.db.commit()

        TaskHelper.update_cluster_status(task.uuid)

        self.assertEquals(self.cluster.status, 'error')

    def test_update_nodes_to_error_if_provision_task_failed(self):
        self.cluster.nodes[0].status = 'provisioning'
        self.cluster.nodes[0].progress = 12
        task = Task(name='provision', cluster=self.cluster, status='error')
        self.db.add(task)
        self.db.commit()

        TaskHelper.update_cluster_status(task.uuid)

        self.assertEquals(self.cluster.status, 'error')
        self.node_should_be_error_with_type(self.cluster.nodes[0], 'provision')
        self.nodes_should_not_be_error(self.cluster.nodes[1:])

    def test_update_cluster_to_operational(self):
        task = Task(name='deploy', cluster=self.cluster, status='ready')
        self.db.add(task)
        self.db.commit()

        TaskHelper.update_cluster_status(task.uuid)

        self.assertEquals(self.cluster.status, 'operational')

    def test_update_if_parent_task_is_ready_all_nodes_should_be_ready(self):
        for node in self.cluster.nodes:
            node.status = 'ready'
            node.progress = 100

        self.cluster.nodes[0].status = 'deploying'
        self.cluster.nodes[0].progress = 24

        task = Task(name='deploy', cluster=self.cluster, status='ready')
        self.db.add(task)
        self.db.commit()

        TaskHelper.update_cluster_status(task.uuid)

        self.assertEquals(self.cluster.status, 'operational')

        for node in self.cluster.nodes:
            self.assertEquals(node.status, 'ready')
            self.assertEquals(node.progress, 100)

    def test_update_cluster_status_if_task_was_already_in_error_status(self):
        for node in self.cluster.nodes:
            node.status = 'provisioning'
            node.progress = 12

        task = Task(name='provision', cluster=self.cluster, status='error')
        self.db.add(task)
        self.db.commit()

        TaskHelper.update_task_status(task.uuid, 'error', 100)

        self.assertEquals(self.cluster.status, 'error')
        self.assertEquals(task.status, 'error')

        for node in self.cluster.nodes:
            self.assertEquals(node.status, 'error')
            self.assertEquals(node.progress, 0)

    def test_do_not_set_cluster_to_error_if_validation_failed(self):
        for task_name in ['check_before_deployment', 'check_networks']:
            supertask = Task(
                name='deploy',
                cluster=self.cluster,
                status='error')

            check_task = Task(
                name=task_name,
                cluster=self.cluster,
                status='error')

            supertask.subtasks.append(check_task)
            self.db.add(check_task)
            self.db.commit()

            TaskHelper.update_cluster_status(supertask.uuid)
            self.assertEquals(self.cluster.status, 'new')


class TestCheckBeforeDeploymentTask(BaseTestCase):

    def setUp(self):
        super(TestCheckBeforeDeploymentTask, self).setUp()
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[{'roles': ['controller']}])

        self.env.create_node()
        self.node = self.env.nodes[0]
        self.cluster = self.env.clusters[0]
        self.task = Task(cluster_id=self.env.clusters[0].id)
        self.env.db.add(self.task)
        self.env.db.commit()

    def set_node_status(self, status):
        self.node.status = status
        self.env.db.commit()
        self.assertEquals(self.node.status, status)

    def set_node_error_type(self, error_type):
        self.node.error_type = error_type
        self.env.db.commit()
        self.assertEquals(self.node.error_type, error_type)

    def is_checking_required(self):
        return CheckBeforeDeploymentTask._is_disk_checking_required(self.node)

    def test_is_disk_checking_required(self):
        self.set_node_status('ready')
        self.assertFalse(self.is_checking_required())

        self.set_node_status('deploying')
        self.assertFalse(self.is_checking_required())

        self.set_node_status('discover')
        self.assertTrue(self.is_checking_required())

    def test_is_disk_checking_required_in_case_of_error(self):
        self.set_node_status('error')
        self.set_node_error_type('provision')
        self.assertTrue(self.is_checking_required())

        self.set_node_error_type('deploy')
        self.assertFalse(self.is_checking_required())

    def test_check_volumes_and_disks_do_not_run_if_node_ready(self):
        self.set_node_status('ready')

        with patch.object(
                VolumeManager,
                'check_disk_space_for_deployment') as check_mock:
            CheckBeforeDeploymentTask._check_disks(self.task)
            self.assertFalse(check_mock.called)

        with patch.object(
                VolumeManager,
                'check_volume_sizes_for_deployment') as check_mock:
            CheckBeforeDeploymentTask._check_volumes(self.task)
            self.assertFalse(check_mock.called)

    def test_check_volumes_and_disks_run_if_node_not_ready(self):
        self.set_node_status('discover')

        with patch.object(
                VolumeManager,
                'check_disk_space_for_deployment') as check_mock:
            CheckBeforeDeploymentTask._check_disks(self.task)

            self.assertEquals(check_mock.call_count, 1)

        with patch.object(
                VolumeManager,
                'check_volume_sizes_for_deployment') as check_mock:
            CheckBeforeDeploymentTask._check_volumes(self.task)

            self.assertEquals(check_mock.call_count, 1)

    def test_check_nodes_online_raises_exception(self):
        self.node.online = False
        self.env.db.commit()

        self.assertRaises(
            errors.NodeOffline,
            CheckBeforeDeploymentTask._check_nodes_are_online,
            self.task)

    def test_check_nodes_online_do_not_raise_exception_node_to_deletion(self):
        self.node.online = False
        self.node.pending_deletion = True
        self.env.db.commit()

        CheckBeforeDeploymentTask._check_nodes_are_online(self.task)
