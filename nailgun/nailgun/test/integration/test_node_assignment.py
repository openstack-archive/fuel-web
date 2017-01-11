#    Copyright 2016 Mirantis, Inc.
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

import mock
from oslo_serialization import jsonutils

from nailgun import consts
from nailgun import rpc
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import fake_tasks
from nailgun.utils import reverse


class TestNodeAssignment(BaseIntegrationTest):

    def setUp(self):
        super(TestNodeAssignment, self).setUp()
        self.env.create(
            api=False,
            nodes_kwargs=[
                {"name": "First",
                 "pending_roles": ["controller"],
                 "pending_addition": True},
                {"name": "Second",
                 "pending_roles": ["compute"],
                 "pending_addition": True}
            ]
        )
        self.cluster = self.env.clusters[-1]

    @fake_tasks(fake_rpc=False, mock_rpc=False)
    @mock.patch('nailgun.rpc.cast')
    def test_reassign_role_to_deployed_node(self, _):
        # First deploy
        task = self.env.launch_deployment(cluster_id=self.cluster.id)

        for t in task.subtasks:
            rpc.receiver.NailgunReceiver().deploy_resp(
                task_uuid=t.uuid,
                status=consts.TASK_STATUSES.ready,
                progress=100,
                nodes=[{'uid': n.uid, 'status': consts.NODE_STATUSES.ready}
                       for n in self.cluster.nodes])

        # Update roles
        first_node = filter(
            lambda n: n.name == 'First', self.cluster.nodes)[0]
        second_node = filter(
            lambda n: n.name == 'Second', self.cluster.nodes)[0]

        assignment_data = [{
            "id": first_node.id,
            "roles": ['controller', 'cinder']}]
        self.app.post(
            reverse('NodeAssignmentHandler',
                    kwargs={'cluster_id': self.cluster.id}),
            jsonutils.dumps(assignment_data),
            headers=self.default_headers)

        unassignment_data = [{"id": second_node.id}]
        self.app.post(
            reverse('NodeUnassignmentHandler',
                    kwargs={'cluster_id': self.cluster.id}),
            jsonutils.dumps(unassignment_data),
            headers=self.default_headers)

        # Second deploy
        # In case of problems will raise an error
        self.app.put(reverse(
            'DeploySelectedNodes', kwargs={'cluster_id': self.cluster.id}),
            '{}', headers=self.default_headers)
