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

import nailgun

from nailgun import objects

from nailgun.db.sqlalchemy.models.task import Task

from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import fake_tasks


class TestStopDeployment(BaseIntegrationTest):

    def setUp(self):
        super(TestStopDeployment, self).setUp()
        self.env.create(
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

    @fake_tasks(recover_nodes=False)
    def test_stop_deployment(self):
        supertask = self.env.launch_deployment()
        deploy_task_uuid = supertask.uuid
        stop_task = self.env.stop_deployment()
        self.env.wait_ready(stop_task, 60)
        self.assertIsNone(
            self.db.query(Task).filter_by(
                uuid=deploy_task_uuid
            ).first()
        )
        self.assertEquals(self.cluster.status, "stopped")
        self.assertEquals(stop_task.progress, 100)

        for n in self.cluster.nodes:
            self.assertEquals(n.online, False)
            self.assertEquals(n.roles, [])
            self.assertNotEquals(n.pending_roles, [])

    @fake_tasks(fake_rpc=False, mock_rpc=False)
    @patch('nailgun.rpc.cast')
    def test_admin_ip_in_args(self, mocked_rpc):
        self.env.launch_deployment()
        self.env.stop_deployment()
        args, kwargs = nailgun.task.manager.rpc.cast.call_args
        for n in args[1]["args"]["nodes"]:
            self.assertIn("admin_ip", n)
            n_db = objects.Node.get_by_uid(n["uid"])
            self.assertEquals(
                n["admin_ip"],
                objects.Node.get_network_manager(
                    n_db
                ).get_admin_ip_for_node(n_db)
            )

    @fake_tasks(recover_nodes=False, tick_interval=1)
    def test_stop_provisioning(self):
        provision_task = self.env.launch_provisioning_selected(
            self.node_uids
        )
        provision_task_uuid = provision_task.uuid
        stop_task = self.env.stop_deployment()
        self.env.wait_ready(stop_task, 60)
        self.assertIsNone(
            self.db().query(Task).filter_by(
                uuid=provision_task_uuid
            ).first()
        )
        self.assertEquals(self.cluster.status, "stopped")
        self.assertEquals(stop_task.progress, 100)
