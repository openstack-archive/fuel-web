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

from nailgun.db import db
from nailgun.db.sqlalchemy.models.task import Task

from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import fake_tasks


class TestStopDeployment(BaseIntegrationTest):

    def setUp(self):
        super(TestStopDeployment, self).setUp()
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"name": "First",
                 "pending_addition": True},
                {"name": "Second",
                 "roles": ["compute"],
                 "pending_addition": True}
            ]
        )
        self.cluster = self.env.clusters[0]
        self.controller = self.env.nodes[0]
        self.compute = self.env.nodes[1]
        self.node_uids = [n.uid for n in self.cluster.nodes][:3]

    def tearDown(self):
        self._wait_for_threads()
        super(TestStopDeployment, self).tearDown()

    @fake_tasks()
    def test_stop_deployment(self):
        supertask = self.env.launch_deployment()
        deploy_task_uuid = supertask.uuid
        stop_task = self.env.stop_deployment()
        self.env.wait_ready(stop_task, 60)
        self.assertIsNone(
            db().query(Task).filter_by(
                uuid=deploy_task_uuid
            ).first()
        )
        self.assertEquals(self.cluster.status, "stopped")
        self.assertEquals(stop_task.progress, 100)

        for n in self.cluster.nodes:
            self.assertEquals(n.online, False)
            self.assertEquals(n.roles, [])
            self.assertNotEquals(n.pending_roles, [])

    @fake_tasks(tick_interval=3)
    def test_stop_provisioning(self):
        provisioning_task = self.env.launch_provisioning_selected(
            self.node_uids
        )
        stop_task_resp = self.env.stop_deployment(
            expect_http=400
        )
        self.db.refresh(provisioning_task)
        self.assertEquals(
            stop_task_resp,
            u"Provisioning interruption for environment "
            u"'{0}' is not implemented right now".format(
                self.cluster.id
            )
        )
