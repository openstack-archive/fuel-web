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

from nailgun.openstack.common import jsonutils

from nailgun.db.sqlalchemy.models import Notification

from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import fake_tasks
from nailgun.test.base import reverse


class TestResetEnvironment(BaseIntegrationTest):

    def tearDown(self):
        self._wait_for_threads()
        super(TestResetEnvironment, self).tearDown()

    @fake_tasks(
        godmode=True,
        recover_nodes=False,
        ia_nodes_count=1
    )
    def test_reset_environment(self):
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
        cluster_db = self.env.clusters[0]
        supertask = self.env.launch_deployment()
        self.env.wait_ready(supertask, 60)

        for n in cluster_db.nodes:
            self.assertEqual(n.status, "ready")
            self.assertEqual(n.pending_addition, False)

        reset_task = self.env.reset_environment()
        self.env.wait_ready(reset_task, 60)

        self.assertEqual(cluster_db.status, "new")

        for n in cluster_db.nodes:
            self.assertEqual(n.online, False)
            self.assertEqual(n.status, "discover")
            self.assertEqual(n.pending_addition, True)
            self.assertEqual(n.roles, [])
            self.assertNotEqual(n.pending_roles, [])

        msg = (
            u"Fuel couldn't reach these nodes during "
            u"environment resetting: '{0}'. Manual "
            u"check may be needed."
        )

        self.assertEqual(
            self.db.query(Notification).filter(
                Notification.topic == "warning"
            ).filter(
                Notification.message.in_([
                    msg.format("First"),
                    msg.format("Second")
                ])
            ).count(),
            1
        )

    @fake_tasks(
        godmode=True,
        recover_nodes=False,
        ia_nodes_count=1
    )
    def test_reset_node_pending_statuses(self):
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"pending_addition": True},
            ]
        )
        cluster_db = self.env.clusters[0]
        node_db = self.env.nodes[0]

        # deploy environment
        deploy_task = self.env.launch_deployment()
        self.env.wait_ready(deploy_task, 60)

        # mark node as pending_deletion
        self.app.put(
            reverse('NodeCollectionHandler'),
            jsonutils.dumps([{
                'id': node_db.id,
                'cluster_id': cluster_db.id,
                'pending_deletion': True,
            }]),
            headers=self.default_headers
        )

        # reset environment
        reset_task = self.env.reset_environment()
        self.env.wait_ready(reset_task, 60)

        # check node statuses
        self.env.refresh_nodes()
        self.assertEqual(node_db.pending_addition, True)
        self.assertEqual(node_db.pending_deletion, False)
