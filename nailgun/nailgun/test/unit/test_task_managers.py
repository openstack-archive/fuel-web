#    Copyright 2015 Mirantis, Inc.
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

import datetime

from nailgun import consts
from nailgun.db import db
from nailgun.db.sqlalchemy import models
from nailgun import errors
from nailgun.task import manager

from nailgun.test.base import BaseTestCase


class TestTaskManagerCheckRunningTasks(BaseTestCase):

    def setUp(self):
        super(TestTaskManagerCheckRunningTasks, self).setUp()
        self.cluster = self.env.create()
        self.task_manager = manager.TaskManager(cluster_id=self.cluster.id)

    def test_fails_if_there_is_task(self):
        task = models.Task(
            name=consts.TASK_NAMES.deployment, cluster_id=self.cluster.id,
            status=consts.TASK_STATUSES.pending
        )
        db.add(task)
        db.flush()

        self.assertRaises(
            errors.TaskAlreadyRunning, self.task_manager.check_running_task
        )

    def test_does_not_fail_if_there_is_deleted_task(self):
        task = models.Task(name=consts.TASK_NAMES.deployment,
                           deleted_at=datetime.datetime.now(),
                           cluster_id=self.cluster.id)
        db.add(task)
        db.flush()
        self.assertNotRaises(
            errors.TaskAlreadyRunning, self.task_manager.check_running_task
        )
