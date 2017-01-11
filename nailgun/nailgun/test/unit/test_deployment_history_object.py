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
        self._create_deployment_history()
        self.history = deployment_history.DeploymentHistory.find_history(
            task_id=self.task.id,
            node_id=self.node_id,
            deployment_graph_task_name=self.deployment_graph_task_name)

    def _create_deployment_history(self):
        deployment_history.DeploymentHistoryCollection.create(
            self.task,
            TASKS_GRAPH)

    def _check_status_transitions(self, from_status, to_status, allowed,
                                  setup_start_time=False,
                                  setup_end_time=False):
        self.history.status = from_status
        self.history.time_start = None
        self.history.time_end = None

        getattr(deployment_history.DeploymentHistory, 'to_' + to_status)(
            self.history)
        if allowed:
            self.assertEqual(self.history.status, to_status)
        else:
            self.assertEqual(self.history.status, from_status)
        if setup_start_time:
            self.assertIsNotNone(self.history.time_start)
        else:
            self.assertIsNone(self.history.time_start)
        if setup_end_time:
            self.assertIsNotNone(self.history.time_end)
        else:
            self.assertIsNone(self.history.time_end)

    def test_deployment_history_create(self):
        histories = deployment_history.DeploymentHistoryCollection.\
            get_history(self.task)
        self.assertEqual(len(histories), 4)

        db_task_names = {h['task_name'] for h in histories}
        input_task_names = set()
        for node in TASKS_GRAPH:
            for task in TASKS_GRAPH[node]:
                input_task_names.add(task['id'])

        self.assertEqual(len(db_task_names & input_task_names), 4)
        self.assertEqual(histories[0]['status'],
                         consts.HISTORY_TASK_STATUSES.pending)

    def test_deployment_history_update_if_exist(self):
        deployment_history.DeploymentHistory.update_if_exist(
            task_id=self.task.id,
            node_id=self.node_id,
            deployment_graph_task_name=self.deployment_graph_task_name,
            status=consts.HISTORY_TASK_STATUSES.running,
            summary={},
            custom={})

        history = deployment_history.DeploymentHistory.find_history(
            task_id=self.task.id,
            node_id=self.node_id,
            deployment_graph_task_name=self.deployment_graph_task_name)

        self.assertEqual(history.status, consts.HISTORY_TASK_STATUSES.running)

    def test_history_move_from_pending(self):
        self._check_status_transitions(
            from_status=consts.HISTORY_TASK_STATUSES.pending,
            to_status=consts.HISTORY_TASK_STATUSES.running,
            allowed=True,
            setup_start_time=True,
            setup_end_time=False)
        self._check_status_transitions(
            from_status=consts.HISTORY_TASK_STATUSES.pending,
            to_status=consts.HISTORY_TASK_STATUSES.skipped,
            allowed=True,
            setup_start_time=True,
            setup_end_time=True)
        self._check_status_transitions(
            from_status=consts.HISTORY_TASK_STATUSES.pending,
            to_status=consts.HISTORY_TASK_STATUSES.pending,
            allowed=False,
            setup_start_time=False,
            setup_end_time=False)
        self._check_status_transitions(
            from_status=consts.HISTORY_TASK_STATUSES.pending,
            to_status=consts.HISTORY_TASK_STATUSES.ready,
            allowed=False,
            setup_start_time=False,
            setup_end_time=False)
        self._check_status_transitions(
            from_status=consts.HISTORY_TASK_STATUSES.pending,
            to_status=consts.HISTORY_TASK_STATUSES.error,
            allowed=False,
            setup_start_time=False,
            setup_end_time=False)

    def test_history_move_from_running(self):
        self._check_status_transitions(
            from_status=consts.HISTORY_TASK_STATUSES.running,
            to_status=consts.HISTORY_TASK_STATUSES.running,
            allowed=False,
            setup_start_time=False,
            setup_end_time=False)
        self._check_status_transitions(
            from_status=consts.HISTORY_TASK_STATUSES.running,
            to_status=consts.HISTORY_TASK_STATUSES.skipped,
            allowed=False,
            setup_start_time=False,
            setup_end_time=False)
        self._check_status_transitions(
            from_status=consts.HISTORY_TASK_STATUSES.running,
            to_status=consts.HISTORY_TASK_STATUSES.pending,
            allowed=False,
            setup_start_time=False,
            setup_end_time=False)
        self._check_status_transitions(
            from_status=consts.HISTORY_TASK_STATUSES.running,
            to_status=consts.HISTORY_TASK_STATUSES.ready,
            allowed=True,
            setup_start_time=False,
            setup_end_time=True)
        self._check_status_transitions(
            from_status=consts.HISTORY_TASK_STATUSES.running,
            to_status=consts.HISTORY_TASK_STATUSES.error,
            allowed=True,
            setup_start_time=False,
            setup_end_time=True)

    def test_history_move_from_ready(self):
        self._check_status_transitions(
            from_status=consts.HISTORY_TASK_STATUSES.ready,
            to_status=consts.HISTORY_TASK_STATUSES.running,
            allowed=False,
            setup_start_time=False,
            setup_end_time=False)
        self._check_status_transitions(
            from_status=consts.HISTORY_TASK_STATUSES.ready,
            to_status=consts.HISTORY_TASK_STATUSES.ready,
            allowed=False,
            setup_start_time=False,
            setup_end_time=False)
        self._check_status_transitions(
            from_status=consts.HISTORY_TASK_STATUSES.ready,
            to_status=consts.HISTORY_TASK_STATUSES.skipped,
            allowed=False,
            setup_start_time=False,
            setup_end_time=False)
        self._check_status_transitions(
            from_status=consts.HISTORY_TASK_STATUSES.ready,
            to_status=consts.HISTORY_TASK_STATUSES.pending,
            allowed=False,
            setup_start_time=False,
            setup_end_time=False)
        self._check_status_transitions(
            from_status=consts.HISTORY_TASK_STATUSES.ready,
            to_status=consts.HISTORY_TASK_STATUSES.error,
            allowed=False,
            setup_start_time=False,
            setup_end_time=False)

    def test_history_move_from_skipped(self):
        self._check_status_transitions(
            from_status=consts.HISTORY_TASK_STATUSES.skipped,
            to_status=consts.HISTORY_TASK_STATUSES.running,
            allowed=False,
            setup_start_time=False,
            setup_end_time=False)
        self._check_status_transitions(
            from_status=consts.HISTORY_TASK_STATUSES.skipped,
            to_status=consts.HISTORY_TASK_STATUSES.ready,
            allowed=False,
            setup_start_time=False,
            setup_end_time=False)
        self._check_status_transitions(
            from_status=consts.HISTORY_TASK_STATUSES.skipped,
            to_status=consts.HISTORY_TASK_STATUSES.skipped,
            allowed=False,
            setup_start_time=False,
            setup_end_time=False)
        self._check_status_transitions(
            from_status=consts.HISTORY_TASK_STATUSES.skipped,
            to_status=consts.HISTORY_TASK_STATUSES.pending,
            allowed=False,
            setup_start_time=False,
            setup_end_time=False)
        self._check_status_transitions(
            from_status=consts.HISTORY_TASK_STATUSES.skipped,
            to_status=consts.HISTORY_TASK_STATUSES.error,
            allowed=False,
            setup_start_time=False,
            setup_end_time=False)

    def test_history_move_from_error(self):
        self._check_status_transitions(
            from_status=consts.HISTORY_TASK_STATUSES.error,
            to_status=consts.HISTORY_TASK_STATUSES.running,
            allowed=False,
            setup_start_time=False,
            setup_end_time=False)
        self._check_status_transitions(
            from_status=consts.HISTORY_TASK_STATUSES.error,
            to_status=consts.HISTORY_TASK_STATUSES.ready,
            allowed=False,
            setup_start_time=False,
            setup_end_time=False)
        self._check_status_transitions(
            from_status=consts.HISTORY_TASK_STATUSES.error,
            to_status=consts.HISTORY_TASK_STATUSES.skipped,
            allowed=False,
            setup_start_time=False,
            setup_end_time=False)
        self._check_status_transitions(
            from_status=consts.HISTORY_TASK_STATUSES.error,
            to_status=consts.HISTORY_TASK_STATUSES.pending,
            allowed=False,
            setup_start_time=False,
            setup_end_time=False)
        self._check_status_transitions(
            from_status=consts.HISTORY_TASK_STATUSES.error,
            to_status=consts.HISTORY_TASK_STATUSES.error,
            allowed=False,
            setup_start_time=False,
            setup_end_time=False)
