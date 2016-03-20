#    Copyright 2014 Mirantis, Inc.
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

from nailgun import consts
from nailgun.db.sqlalchemy.models.task import Task
from nailgun.task import task
from nailgun.test import base


class TestMulticastNetworkManager(base.BaseIntegrationTest):

    def setUp(self):
        super(TestMulticastNetworkManager, self).setUp()
        self.cluster = self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"api": True},
                {"api": True},
            ]
        )

    def execute(self):
        multicast = Task(
            name='multicast_verification',
            cluster_id=self.cluster['id'])
        self.db.add(multicast)
        self.db.flush()
        task.MulticastVerificationTask(multicast).execute()
        return multicast

    @base.fake_tasks()
    def test_multicast_successfull_scenario(self):
        multicast_task = self.execute()
        self.assertEqual(multicast_task.status, consts.TASK_STATUSES.ready)

        corosync = multicast_task.cluster.attributes.editable['corosync']
        self.assertTrue(corosync['verified']['value'])

    @base.fake_tasks(prefix='error1')
    def test_multicast_no_message_from_node(self):
        self.assertEqual(self.execute().status, consts.TASK_STATUSES.error)

    @base.fake_tasks(prefix='error2')
    def test_multicast_no_messages_for_one_node(self):
        multicast = self.execute()
        self.assertEqual(multicast.status, consts.TASK_STATUSES.error)

        node_ids = [node['node_id'] for node in multicast.result]
        not_received = [node['not_received'] for node in multicast.result]
        self.assertTrue(any(node_ids == node for node in not_received))
        self.assertFalse(all(node_ids == node for node in not_received))
