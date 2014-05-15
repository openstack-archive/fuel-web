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


from nailgun.db.sqlalchemy.models import Task
from nailgun.test.base import BaseTestCase
from nailgun.test.base import fake_tasks
from nailgun.test.base import reverse


class TestTaskHandlers(BaseTestCase):

    @fake_tasks(godmode=True)
    def test_task_deletion(self):
        self.env.create(
            nodes_kwargs=[
                {"roles": ["controller"]}
            ]
        )
        verify_task = self.env.launch_verify_networks()
        task_id = verify_task.id
        self.env.wait_error(verify_task, 60)
        resp = self.app.delete(
            reverse(
                'TaskHandler',
                kwargs={'obj_id': task_id}
            ),
            headers=self.default_headers
        )
        self.assertEqual(resp.status_code, 204)
        resp = self.app.get(
            reverse(
                'TaskHandler',
                kwargs={'obj_id': task_id}
            ),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(resp.status_code, 404)

    def test_forced_task_deletion(self):
        self.env.create(
            nodes_kwargs=[
                {"roles": ["controller"]}
            ]
        )
        task = Task(
            name='deployment',
            cluster=self.env.clusters[0],
            status='running',
            progress=10
        )
        self.db.add(task)
        self.db.commit()
        resp = self.app.delete(
            reverse(
                'TaskHandler',
                kwargs={'obj_id': task.id}
            ) + "?force=0",
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(resp.status_code, 400)
        resp = self.app.delete(
            reverse(
                'TaskHandler',
                kwargs={'obj_id': task.id}
            ) + "?force=1",
            headers=self.default_headers
        )
        self.assertEqual(resp.status_code, 204)
