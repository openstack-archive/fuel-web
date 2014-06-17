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

import re

from nailgun.db.sqlalchemy.models import Notification
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import fake_tasks


class TestErrors(BaseIntegrationTest):

    def tearDown(self):
        self._wait_for_threads()
        super(TestErrors, self).tearDown()

    @fake_tasks(error="provisioning")
    def test_deployment_error_during_provisioning(self):
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
        supertask = self.env.launch_deployment()
        self.env.wait_error(supertask, 60, re.compile(
            "Deployment has failed\. Check these nodes:\n'(First|Second)'"
        ))
        self.env.refresh_nodes()
        self.env.refresh_clusters()
        n_error = lambda n: (n.status, n.error_type) == ('error', 'provision')
        # Why sum is equal 1? It is NOT OBVIOUS that error occures only on one
        # of nodes and the choice is random. It is coded inside
        # nailgun.task.fake.FakeDeploymentThread. As this method is
        # decorated with fake_tasks(error="provisioning")
        # FakeDeploymentThread shuffles nodes and sets provisioning
        # error on one of those nodes
        self.assertEqual(
            sum(map(n_error, self.env.nodes)),
            1
        )
        self.assertEqual(supertask.cluster.status, 'error')

    @fake_tasks(error="provisioning", error_msg="Terrible error")
    def test_deployment_error_from_orchestrator(self):
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"name": "First",
                 "pending_addition": True},
                {"name": "Second",
                 "roles": ["compute"],
                 "pending_addition": True},
                {"name": "Third",
                 "roles": ["compute"],
                 "status": "error",
                 "error_type": "provision",
                 "error_msg": "I forgot about teapot!"}
            ]
        )
        supertask = self.env.launch_deployment()
        err_msg = "Deployment has failed. Terrible error"
        self.env.wait_error(supertask, 60, err_msg)
        self.assertIsNotNone(
            self.db.query(Notification).filter_by(message=err_msg).first()
        )
        self.assertIsNotNone(
            self.db.query(Notification).filter_by(
                node_id=self.env.nodes[2].id,
                message="Failed to deploy node 'Third': I forgot about teapot!"
            ).first()
        )
        self.env.refresh_nodes()
        self.env.refresh_clusters()
        n_error = lambda n: (n.status, n.error_type) == ('error', 'provision')
        self.assertIn(
            sum(map(n_error, self.env.nodes)),
            [1, 2]
        )
        self.assertEqual(supertask.cluster.status, 'error')

    @fake_tasks(error="deployment")
    def test_deployment_error_during_deployment(self):
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"name": "First",
                 "pending_addition": True},
                {"name": "Second",
                 "roles": ["compute"],
                 "pending_addition": True}])
        supertask = self.env.launch_deployment()
        self.env.wait_error(supertask, 60, re.compile(
            "Deployment has failed\. Check these nodes:\n'(First|Second)'"))
        self.env.refresh_nodes()
        self.env.refresh_clusters()
        n_error = lambda n: (n.status, n.error_type) == ('error', 'deploy')

        self.assertEqual(len(map(n_error, self.env.nodes)), 2)
        self.assertEqual(supertask.cluster.status, 'error')

    @fake_tasks(error="deployment", task_ready=True)
    def test_task_ready_node_error(self):
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
        supertask = self.env.launch_deployment()
        self.env.wait_error(supertask, 60, re.compile(
            "Deployment has failed\. Check these nodes:\n'(First|Second)'"
        ))
