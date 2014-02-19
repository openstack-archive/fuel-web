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

from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import fake_tasks


class TestResetEnvironment(BaseIntegrationTest):

    def tearDown(self):
        self._wait_for_threads()
        super(TestResetEnvironment, self).tearDown()

    @fake_tasks(godmode=True, recover_nodes=False)
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
            self.assertEquals(n.status, "ready")
            self.assertEquals(n.pending_addition, False)

        reset_task = self.env.reset_environment()
        self.env.wait_ready(reset_task, 60)

        self.assertEquals(cluster_db.status, "new")

        for n in cluster_db.nodes:
            self.assertEquals(n.online, False)
            self.assertEquals(n.status, "discover")
            self.assertEquals(n.pending_addition, True)
            self.assertEquals(n.roles, [])
            self.assertNotEquals(n.pending_roles, [])
