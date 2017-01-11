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
from nailgun import objects

from nailgun.test import base


class TestDeploymentTasksHistory(base.BaseTestCase):
    tasks = [
        {'id': 'task11', 'task_name': 'task11',
         'parameters': {'name': 'task11'}},
        {'id': 'task12', 'task_name': 'task12',
         'parameters': {'name': 'task12'}},
        {'id': 'task21', 'task_name': 'task21',
         'parameters': {'name': 'task21'}},
        {'id': 'task22', 'task_name': 'task22',
         'parameters': {'name': 'task22'}},
        {'id': 'task31', 'task_name': 'task31',
         'parameters': {'name': 'task31'}},
    ]

    def setUp(self):
        super(TestDeploymentTasksHistory, self).setUp()
        self.maxDiff = None

        self.transaction = objects.Transaction.create(
            {'status': consts.TASK_STATUSES.ready,
             'tasks_snapshot': self.tasks}
        )
        objects.DeploymentHistoryCollection.create(
            self.transaction, {
                '0': self.tasks[:2],
                '2': self.tasks[2:4],
            }
        )

    def test_get_all_tasks(self):
        history = objects.DeploymentHistoryCollection.get_history(
            self.transaction
        )
        expected = []
        for n in (0, 2):
            for task in self.tasks[n: n + 2]:
                expected.append({
                    'task_name': task['task_name'],
                    'parameters': task['parameters'],
                    'node_id': str(n),
                    'status': consts.HISTORY_TASK_STATUSES.pending,
                    'time_start': None,
                    'time_end': None,
                })

        expected.append({
            'task_name': self.tasks[-1]['task_name'],
            'parameters': self.tasks[-1]['parameters'],
            'node_id': '-',
            'status': consts.HISTORY_TASK_STATUSES.skipped,
            'time_start': None,
            'time_end': None,
        })

        self.assertItemsEqual(expected, history)

    def test_get_tasks_by_node(self):
        history = objects.DeploymentHistoryCollection.get_history(
            self.transaction, nodes_ids=['0']
        )
        expected = [
            {
                'task_name': task['task_name'],
                'parameters': task['parameters'],
                'node_id': '0',
                'status': consts.HISTORY_TASK_STATUSES.pending,
                'time_start': None,
                'time_end': None,
            }
            for task in self.tasks[0: 2]
        ]

        self.assertItemsEqual(expected, history)

    def test_get_tasks_by_status_pending(self):
        history = objects.DeploymentHistoryCollection.get_history(
            self.transaction, statuses=[consts.HISTORY_TASK_STATUSES.pending]
        )
        expected = [
            {
                'task_name': task['task_name'],
                'parameters': task['parameters'],
                'node_id': str(n),
                'status': consts.HISTORY_TASK_STATUSES.pending,
                'time_start': None,
                'time_end': None,
            }
            for n in [0, 2]
            for task in self.tasks[n: n + 2]
        ]

        self.assertItemsEqual(expected, history)

    def test_get_tasks_by_status_skipped(self):
        history = objects.DeploymentHistoryCollection.get_history(
            self.transaction, statuses=[consts.HISTORY_TASK_STATUSES.skipped]
        )
        expected = [{
            'task_name': self.tasks[-1]['task_name'],
            'parameters': self.tasks[-1]['parameters'],
            'node_id': '-',
            'status': consts.HISTORY_TASK_STATUSES.skipped,
            'time_start': None,
            'time_end': None,
        }]

        self.assertItemsEqual(expected, history)

    def test_get_tasks_by_name(self):
        history = objects.DeploymentHistoryCollection.get_history(
            self.transaction, tasks_names=['task31', 'task11']
        )
        expected = [
            {
                'task_name': 'task11',
                'parameters': {'name': 'task11'},
                'node_id': '0',
                'status': consts.HISTORY_TASK_STATUSES.pending,
                'time_start': None,
                'time_end': None,
            },
            {
                'task_name': 'task31',
                'parameters': {'name': 'task31'},
                'node_id': '-',
                'status': consts.HISTORY_TASK_STATUSES.skipped,
                'time_start': None,
                'time_end': None,
            }
        ]

        self.assertItemsEqual(expected, history)

    def test_serialization(self):
        objects.DeploymentHistory.update_if_exist(
            self.transaction.id, '0', 'task11',
            status=consts.HISTORY_TASK_STATUSES.ready,
            custom={'message': 'test message'}, summary=None
        )
        history = objects.DeploymentHistoryCollection.get_history(
            self.transaction, tasks_names=['task31', 'task11']
        )

        expected = [
            {
                'task_name': 'task11',
                'parameters': {'name': 'task11'},
                'node_id': '0',
                'status': consts.HISTORY_TASK_STATUSES.pending,
                'time_start': None,
                'time_end': None,
                'message': 'test message'
            },
            {
                'task_name': 'task31',
                'parameters': {'name': 'task31'},
                'node_id': '-',
                'status': consts.HISTORY_TASK_STATUSES.skipped,
                'time_start': None,
                'time_end': None,
            }
        ]

        self.assertItemsEqual(expected, history)
