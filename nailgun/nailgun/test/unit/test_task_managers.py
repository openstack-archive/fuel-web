# -*- coding: utf-8 -*-

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

from nailgun.db import db
from nailgun.db.sqlalchemy import models
from nailgun.errors import errors
from nailgun.task.manager import DeploymentCheckMixin
from nailgun.test.base import BaseTestCase


class TestDeploymentCheckMixin(BaseTestCase):

    def setUp(self):
        super(TestDeploymentCheckMixin, self).setUp()
        self.env.create()
        self.cluster = self.env.clusters[0]

    def test_fails_if_there_is_task(self):
        for task_name in DeploymentCheckMixin.deployment_tasks:
            task = models.Task(name=task_name, cluster_id=self.cluster.id)
            db.add(task)
            db.flush()
            self.assertRaisesWithMessage(
                errors.DeploymentAlreadyStarted,
                'Cannot perform the actions because there are '
                'running tasks {0}'.format([task]),
                DeploymentCheckMixin.check_no_running_deployment,
                self.cluster)

            db.query(models.Task).delete()
