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

from nailgun import consts
from nailgun.db.sqlalchemy.models import Task
from nailgun.test.base import BaseTestCase
from nailgun.test.base import fake_tasks
from nailgun.utils import reverse


class TestTaskHandlers(BaseTestCase):

    def setUp(self):
        super(TestTaskHandlers, self).setUp()
        self.cluster_db = self.env.create(
            nodes_kwargs=[
                {"roles": ["controller"]}
            ]
        )

    def test_task_deletion(self):
        task = Task(
            name='deployment',
            cluster=self.cluster_db,
            status=consts.TASK_STATUSES.ready,
            progress=100
        )
        self.db.add(task)
        self.db.flush()
        resp = self.app.delete(
            reverse(
                'TaskHandler',
                kwargs={'obj_id': task.id}
            ),
            headers=self.default_headers
        )
        self.assertEqual(resp.status_code, 204)
        resp = self.app.get(
            reverse(
                'TaskHandler',
                kwargs={'obj_id': task.id}
            ),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(resp.status_code, 404)

    def test_running_task_deletion(self):
        task = Task(
            name='deployment',
            cluster=self.cluster_db,
            status=consts.TASK_STATUSES.running,
            progress=10
        )
        self.db.add(task)
        self.db.flush()
        resp = self.app.delete(
            reverse(
                'TaskHandler',
                kwargs={'obj_id': task.id}
            ) + "?force=0",
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(resp.status_code, 400)

    def test_forced_deletion_of_running_task_(self):
        task = Task(
            name='deployment',
            cluster=self.cluster_db,
            status=consts.TASK_STATUSES.running,
            progress=10
        )
        self.db.add(task)
        self.db.flush()

        resp = self.app.delete(
            reverse(
                'TaskHandler',
                kwargs={'obj_id': task.id}
            ) + "?force=1",
            headers=self.default_headers
        )
        self.assertEqual(resp.status_code, 204)
        resp = self.app.get(
            reverse(
                'TaskHandler',
                kwargs={'obj_id': task.id}
            ),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(resp.status_code, 404)

    def test_soft_deletion_behavior(self):
        task = Task(
            name=consts.TASK_NAMES.deployment,
            cluster=self.cluster_db,
            status=consts.TASK_STATUSES.running,
            progress=10
        )
        self.db.add(task)
        self.db.flush()
        resp = self.app.delete(
            reverse(
                'TaskHandler',
                kwargs={'obj_id': task.id}
            ) + "?force=1",
            headers=self.default_headers
        )
        self.assertEqual(resp.status_code, 204)
        resp = self.app.get(
            reverse(
                'TaskHandler',
                kwargs={'obj_id': task.id}
            ),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(resp.status_code, 404)
        self.assertTrue(self.db().query(Task).get(task.id))

    @fake_tasks()
    def test_delete_task_does_not_affect_cluster_status(self):
        self.env.create(
            nodes_kwargs=[
                {'roles': ['controller'],
                 'status': consts.NODE_STATUSES.discover,
                 'pending_addition': True}],
            release_kwargs={
                'operating_system': consts.RELEASE_OS.ubuntu,
                'version': 'mitaka-9.0'
            }
        )
        cluster = self.env.clusters[-1]
        supertask = self.env.launch_deployment(cluster_id=cluster.id)
        self.db.refresh(cluster)
        self.assertEqual(consts.CLUSTER_STATUSES.operational, cluster.status)
        resp = self.app.delete(
            reverse(
                'TaskHandler',
                kwargs={'obj_id': supertask.id}
            ),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(204, resp.status_code)
        self.db.refresh(supertask)
        self.assertIsNotNone(supertask.deleted_at)
        for t in supertask.subtasks:
            self.assertIsNotNone(t.deleted_at)
        self.db.refresh(cluster)
        self.assertEqual(consts.CLUSTER_STATUSES.operational, cluster.status)

    def test_task_contains_field_parent(self):
        parent_task = Task(
            name=consts.TASK_NAMES.deployment,
            cluster=self.cluster_db,
            status=consts.TASK_STATUSES.running,
            progress=10
        )
        child_task = parent_task.create_subtask(
            name=consts.TASK_NAMES.deployment,
            status=consts.TASK_STATUSES.running,
            progress=10
        )

        cluster_tasks = self.app.get(
            reverse(
                'TaskCollectionHandler',
                kwargs={'cluster_id': self.cluster_db.id}
            ),
            headers=self.default_headers
        ).json_body

        child_task_data = next(
            t for t in cluster_tasks if t['id'] == child_task.id
        )

        self.assertEqual(parent_task.id, child_task_data['parent_id'])
        parent_task_data = next(
            t for t in cluster_tasks if t['id'] == parent_task.id
        )
        self.assertIsNone(parent_task_data['parent_id'])
