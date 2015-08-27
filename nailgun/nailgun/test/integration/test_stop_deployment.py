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
from nailgun import consts
from nailgun.db.sqlalchemy.models.notification import Notification
from nailgun.db.sqlalchemy.models.task import Task
from nailgun import objects
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

    @fake_tasks(recover_nodes=False, tick_interval=1)
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
        self.assertEqual(self.cluster.status, "stopped")
        self.assertEqual(stop_task.progress, 100)

        for n in self.cluster.nodes:
            self.assertEqual(n.online, False)
            self.assertEqual(n.roles, [])
            self.assertNotEqual(n.pending_roles, [])

        notification = self.db.query(Notification).filter_by(
            cluster_id=stop_task.cluster_id
        ).order_by(
            Notification.datetime.desc()
        ).first()

        self.assertRegexpMatches(
            notification.message,
            'Please reset the environment if you want to redeploy it.')

    @fake_tasks(fake_rpc=False, mock_rpc=False)
    @patch('nailgun.rpc.cast')
    def test_admin_ip_in_args(self, mocked_rpc):
        self.env.launch_deployment()
        self.env.stop_deployment()
        args, kwargs = nailgun.task.manager.rpc.cast.call_args
        for n in args[1]["args"]["nodes"]:
            self.assertIn("admin_ip", n)
            n_db = objects.Node.get_by_uid(n["uid"])
            self.assertEqual(
                n["admin_ip"],
                objects.Cluster.get_network_manager(
                    n_db.cluster
                ).get_admin_ip_for_node(n_db.id)
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
        self.assertEqual(self.cluster.status, "stopped")
        self.assertEqual(stop_task.progress, 100)

    @patch('nailgun.rpc.cast')
    def test_latest_task_is_sent(self, mocked_rpc):
        for uuid, status in [(1, consts.TASK_STATUSES.ready),
                             (2, consts.TASK_STATUSES.running)]:

            self.env.create_task(
                name=consts.TASK_NAMES.deployment,
                uuid="deploy-{0}".format(uuid),
                status=status,
                cluster_id=self.cluster.id)
            self.env.create_task(
                name=consts.TASK_NAMES.provision,
                uuid="provision-{0}".format(uuid),
                status=status,
                cluster_id=self.cluster.id)

        self.env.stop_deployment()

        rpc_args_list = nailgun.task.manager.rpc.cast.call_args_list
        self.assertEqual(len(rpc_args_list), 2)
        provision, deploy = rpc_args_list
        (_, deploy_args), _ = deploy
        (_, provision_args), _ = provision
        self.assertEqual(deploy_args['args']['stop_task_uuid'],
                         'deploy-2')
        self.assertEqual(provision_args['args']['stop_task_uuid'],
                         'provision-2')
