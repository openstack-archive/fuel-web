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


from nailgun.test import base
from nailgun.task import manager


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

    def tearDown(self):
        self._wait_for_threads()
        super(TestMulticastNetworkManager, self).tearDown()

    @base.fake_tasks()
    def test_multicast_successfull_scenario(self):
        multicast = manager.MulticastTaskManager(cluster_id=self.cluster['id'])
        task = multicast.execute()
        self.env.wait_ready(task, timeout=10)

    @base.fake_tasks(prefix='error1')
    def test_multicast_no_message_from_node(self):
        multicast = manager.MulticastTaskManager(cluster_id=self.cluster['id'])
        task = multicast.execute()
        self.env.wait_error(task, timeout=10)

    @base.fake_tasks(prefix='error2')
    def test_multicast_no_messages_for_one_node(self):
        multicast = manager.MulticastTaskManager(cluster_id=self.cluster['id'])
        task = multicast.execute()
        self.env.wait_error(task, timeout=10)
        node_ids = [node['node_id'] for node in task.result]
        not_received = [node['not_received'] for node in task.result]
        self.assertTrue(any(node_ids == node for node in not_received))
        self.assertFalse(all(node_ids == node for node in not_received))
