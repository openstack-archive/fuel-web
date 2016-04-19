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

from nailgun import consts
from nailgun.objects import deployment_history
from nailgun.test import base

TASKS_GRAPH = {
    None: [
        {'id': 'post_deployment_start'},
        {'id': 'post_deployment_end'}
    ],
    '1': [
        {'id': 'dns-client'},
        {'id': 'hiera'}
    ]
}


class TestDeploymentHistoryObject(base.BaseTestCase):

    def setUp(self):
        super(TestDeploymentHistoryObject, self).setUp()
        self.cluster = self.env.create()
        self.task = self.env.create_task(
            name=consts.TASK_NAMES.deployment,
            status=consts.TASK_STATUSES.running,
            cluster_id=self.cluster.id)
        self.node_id = '1'
        self.deployment_graph_task_name = 'dns-client'
        self._setup_deployment_history()
        self.history = deployment_history.DeploymentHistory.find_history(
            task_id=self.task.id,
            node_id=self.node_id,
            deployment_graph_task_name=self.deployment_graph_task_name)

    def _setup_deployment_history(self):
        deployment_history.DeploymentHistoryCollection.create(
            self.task,
            TASKS_GRAPH)

    def test_deployment_history_create(self):
        histories = deployment_history.DeploymentHistoryCollection.\
            get_history(self.task.id).all()
        self.assertEqual(len(histories), 4)

        db_task_names = set()
        for history in histories:
            db_task_names.add(history.deployment_graph_task_name)
        input_task_names = set()
        for node in TASKS_GRAPH:
            for task in TASKS_GRAPH[node]:
                input_task_names.add(task['id'])

        self.assertEqual(len(db_task_names & input_task_names), 4)
        self.assertEqual(histories[0].status,
                         consts.HISTORY_TASK_STATUSES.pending)

    def test_deployment_history_update_if_exist(self):
        deployment_history.DeploymentHistory.update_if_exist(
            task_id=self.task.id,
            node_id=self.node_id,
            deployment_graph_task_name=self.deployment_graph_task_name,
            status=consts.HISTORY_TASK_STATUSES.running,
            custom={})

        history = deployment_history.DeploymentHistory.find_history(
            task_id=self.task.id,
            node_id=self.node_id,
            deployment_graph_task_name=self.deployment_graph_task_name)

        self.assertEqual(history.status, consts.HISTORY_TASK_STATUSES.running)

    def test_history_move_from_pending_to_running_status(self):
        deployment_history.DeploymentHistory.to_running(self.history)
        self.assertEqual(self.history.status,
                         consts.HISTORY_TASK_STATUSES.running)
        self.assertIsNotNone(self.history.time_start)

    def test_history_move_from_pending_to_pending_status(self):
        deployment_history.DeploymentHistory.to_pending(self.history)
        self.assertEqual(self.history.status,
                         consts.HISTORY_TASK_STATUSES.pending)
        self.assertIsNone(self.history.time_start)

    def test_history_move_from_pending_to_skipped_status(self):
        deployment_history.DeploymentHistory.to_skipped(self.history)
        self.assertEqual(self.history.status,
                         consts.HISTORY_TASK_STATUSES.skipped)
        self.assertIsNotNone(self.history.time_start)
        self.assertIsNotNone(self.history.time_end)

    def test_history_does_not_move_from_pending_to_ready_status(self):
        deployment_history.DeploymentHistory.to_ready(self.history)
        self.assertEqual(self.history.status,
                         consts.HISTORY_TASK_STATUSES.pending)
        self.assertIsNone(self.history.time_start)

    def test_history_does_not_move_from_pending_to_error_status(self):
        deployment_history.DeploymentHistory.to_error(self.history)
        self.assertEqual(self.history.status,
                         consts.HISTORY_TASK_STATUSES.pending)
        self.assertIsNone(self.history.time_start)

    def test_history_move_from_running_to_ready_status(self):
        self.history.status = consts.HISTORY_TASK_STATUSES.running
        deployment_history.DeploymentHistory.to_ready(self.history)
        self.assertEqual(self.history.status,
                         consts.HISTORY_TASK_STATUSES.ready)
        self.assertIsNotNone(self.history.time_end)

    def test_history_move_from_running_to_error_status(self):
        self.history.status = consts.HISTORY_TASK_STATUSES.running
        deployment_history.DeploymentHistory.to_error(self.history)
        self.assertEqual(self.history.status,
                         consts.HISTORY_TASK_STATUSES.error)
        self.assertIsNotNone(self.history.time_end)

    def test_history_move_from_running_to_skipped_status(self):
        self.history.status = consts.HISTORY_TASK_STATUSES.running
        deployment_history.DeploymentHistory.to_skipped(self.history)
        self.assertEqual(self.history.status,
                         consts.HISTORY_TASK_STATUSES.skipped)
        self.assertIsNotNone(self.history.time_end)

    def test_history_does_not_move_from_running_to_running_status(self):
        self.history.status = consts.HISTORY_TASK_STATUSES.running
        deployment_history.DeploymentHistory.to_running(self.history)
        self.assertEqual(self.history.status,
                         consts.HISTORY_TASK_STATUSES.running)
        self.assertIsNone(self.history.time_end)

    def test_history_does_not_move_from_running_to_pending_status(self):
        self.history.status = consts.HISTORY_TASK_STATUSES.running
        deployment_history.DeploymentHistory.to_pending(self.history)
        self.assertEqual(self.history.status,
                         consts.HISTORY_TASK_STATUSES.running)
        self.assertIsNone(self.history.time_end)

    def test_history_does_not_move_from_ready_to_ready_status(self):
        self.history.status = consts.HISTORY_TASK_STATUSES.ready
        deployment_history.DeploymentHistory.to_ready(self.history)
        self.assertEqual(self.history.status,
                         consts.HISTORY_TASK_STATUSES.ready)

    def test_history_does_not_move_from_ready_to_error_status(self):
        self.history.status = consts.HISTORY_TASK_STATUSES.ready
        deployment_history.DeploymentHistory.to_error(self.history)
        self.assertEqual(self.history.status,
                         consts.HISTORY_TASK_STATUSES.ready)

    def test_history_does_not_move_from_ready_to_skipped_status(self):
        self.history.status = consts.HISTORY_TASK_STATUSES.ready
        deployment_history.DeploymentHistory.to_skipped(self.history)
        self.assertEqual(self.history.status,
                         consts.HISTORY_TASK_STATUSES.ready)

    def test_history_does_not_move_from_ready_to_running_status(self):
        self.history.status = consts.HISTORY_TASK_STATUSES.ready
        deployment_history.DeploymentHistory.to_running(self.history)
        self.assertEqual(self.history.status,
                         consts.HISTORY_TASK_STATUSES.ready)

    def test_history_does_not_move_from_ready_to_pending_status(self):
        self.history.status = consts.HISTORY_TASK_STATUSES.ready
        deployment_history.DeploymentHistory.to_pending(self.history)
        self.assertEqual(self.history.status,
                         consts.HISTORY_TASK_STATUSES.ready)

    def test_history_does_not_move_from_error_to_ready_status(self):
        self.history.status = consts.HISTORY_TASK_STATUSES.error
        deployment_history.DeploymentHistory.to_ready(self.history)
        self.assertEqual(self.history.status,
                         consts.HISTORY_TASK_STATUSES.error)

    def test_history_does_not_move_from_error_to_error_status(self):
        self.history.status = consts.HISTORY_TASK_STATUSES.error
        deployment_history.DeploymentHistory.to_error(self.history)
        self.assertEqual(self.history.status,
                         consts.HISTORY_TASK_STATUSES.error)

    def test_history_does_not_move_from_error_to_skipped_status(self):
        self.history.status = consts.HISTORY_TASK_STATUSES.error
        deployment_history.DeploymentHistory.to_skipped(self.history)
        self.assertEqual(self.history.status,
                         consts.HISTORY_TASK_STATUSES.error)

    def test_history_does_not_move_from_error_to_running_status(self):
        self.history.status = consts.HISTORY_TASK_STATUSES.error
        deployment_history.DeploymentHistory.to_running(self.history)
        self.assertEqual(self.history.status,
                         consts.HISTORY_TASK_STATUSES.error)

    def test_history_does_not_move_from_error_to_pending_status(self):
        self.history.status = consts.HISTORY_TASK_STATUSES.error
        deployment_history.DeploymentHistory.to_pending(self.history)
        self.assertEqual(self.history.status,
                         consts.HISTORY_TASK_STATUSES.error)

    def test_history_does_not_move_from_skipped_to_ready_status(self):
        self.history.status = consts.HISTORY_TASK_STATUSES.skipped
        deployment_history.DeploymentHistory.to_ready(self.history)
        self.assertEqual(self.history.status,
                         consts.HISTORY_TASK_STATUSES.skipped)

    def test_history_does_not_move_from_skipped_to_error_status(self):
        self.history.status = consts.HISTORY_TASK_STATUSES.skipped
        deployment_history.DeploymentHistory.to_error(self.history)
        self.assertEqual(self.history.status,
                         consts.HISTORY_TASK_STATUSES.skipped)

    def test_history_does_not_move_from_skipped_to_skipped_status(self):
        self.history.status = consts.HISTORY_TASK_STATUSES.skipped
        deployment_history.DeploymentHistory.to_skipped(self.history)
        self.assertEqual(self.history.status,
                         consts.HISTORY_TASK_STATUSES.skipped)

    def test_history_does_not_move_from_skipped_to_running_status(self):
        self.history.status = consts.HISTORY_TASK_STATUSES.skipped
        deployment_history.DeploymentHistory.to_running(self.history)
        self.assertEqual(self.history.status,
                         consts.HISTORY_TASK_STATUSES.skipped)

    def test_history_does_not_move_from_skipped_to_pending_status(self):
        self.history.status = consts.HISTORY_TASK_STATUSES.skipped
        deployment_history.DeploymentHistory.to_pending(self.history)
        self.assertEqual(self.history.status,
                         consts.HISTORY_TASK_STATUSES.skipped)
