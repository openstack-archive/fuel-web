# -*- coding: utf-8 -*-

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
import functools

from mock import patch
from nailgun.test.base import fake_tasks
from nailgun.test.performance.base import BaseIntegrationLoadTestCase


class IntegrationClusterTests(BaseIntegrationLoadTestCase):

    MAX_EXEC_TIME = 60
    MAX_TOTAL_EXEC_TIME = 350

    def setUp(self):
        super(IntegrationClusterTests, self).setUp()
        self.env.create_nodes(self.NODES_NUM, api=True)
        self.cluster = self.env.create_cluster(api=False)
        controllers = 3
        created_controllers = 0
        nodes = []
        self.nodes_ids = []
        for node in self.env.nodes:
            if created_controllers < controllers:
                nodes.append({'id': node.id,
                              'role': ['controller'],
                              'cluster': self.cluster['id'],
                              'pending_addition': True})
                created_controllers += 1
            else:
                nodes.append({'id': node.id,
                              'role': ['compute'],
                              'cluster': self.cluster['id'],
                              'pending_addition': True})
            self.nodes_ids.append(str(node.id))
        self.put_handler('NodeCollectionHandler', nodes)

    @fake_tasks(fake_rpc=False, mock_rpc=False)
    @patch('nailgun.rpc.cast')
    def test_deploy(self, mock_rpc):
        self.provision(self.cluster['id'], self.nodes_ids)
        self.deployment(self.cluster['id'], self.nodes_ids)

    @fake_tasks()
    def test_put_cluster_changes(self):
        func = functools.partial(
            self.put_handler,
            'ClusterChangesHandler',
            [],
            handler_kwargs={'cluster_id': self.cluster['id']}
        )
        self.check_time_exec(func, 4)

    @fake_tasks()
    def test_put_cluster_changes_after_reset(self):
        self.deployment(self.cluster['id'], self.nodes_ids)
        func = functools.partial(
            self.put_handler,
            'ClusterResetHandler',
            [],
            handler_kwargs={'cluster_id': self.cluster['id']})
        self.check_time_exec(func, 10)
        func = functools.partial(
            self.put_handler,
            'ClusterChangesHandler',
            [],
            handler_kwargs={'cluster_id': self.cluster['id']}
        )
        self.check_time_exec(func, 10)
