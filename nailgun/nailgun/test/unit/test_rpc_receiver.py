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

from nailgun.errors import errors
from nailgun.test.base import BaseTestCase

from nailgun.db.sqlalchemy.models import Task
from nailgun.task.helpers import TaskHelper


class TestUtils(BaseTestCase):

    def test_get_task_by_uuid_returns_task(self):
        task = Task(name='deploy')
        self.db.add(task)
        self.db.commit()
        task_by_uuid = TaskHelper.get_task_by_uuid(task.uuid)
        self.assertEqual(task.uuid, task_by_uuid.uuid)

    def test_get_task_by_uuid_raises_error(self):
        self.assertRaises(errors.CannotFindTask,
                          TaskHelper.get_task_by_uuid,
                          'not_found_uuid')
