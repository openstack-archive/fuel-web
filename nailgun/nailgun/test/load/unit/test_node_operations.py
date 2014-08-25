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

from nailgun import consts
from nailgun.openstack.common import jsonutils
from nailgun.test.load.base import BaseUnitLoadTestCase


class NodeOperationsLoadTest(BaseUnitLoadTestCase):

    @classmethod
    def setUpClass(cls):
        super(NodeOperationsLoadTest, cls).setUpClass()
        cls.env.create_nodes(cls.NODES_NUM, cluster_id=cls.cluster['id'])

    def get_node_handler(self, handler_name, id_value):
        return self.get_handler(handler_name, id_value, id_name='node_id')

    def test_put_node(self):
        for node in self.env.nodes:
            func = functools.partial(
                self.put_handler,
                'NodeHandler',
                {'status': consts.NODE_STATUSES.ready},
                handler_kwargs={'obj_id': node.id}
            )
            self.check_time_exec(func)

    def test_get_nodes(self):
        func = functools.partial(
            self.get_handler,
            'NodeCollectionHandler',
            self.cluster['id'],
            id_name='cluster_id'
        )
        self.check_time_exec(func, 2)

    def test_get_defaults_disk(self):
        for node in self.env.nodes:
            func = functools.partial(
                self.get_node_handler,
                'NodeDefaultsDisksHandler',
                node.id
            )
            self.check_time_exec(func)

    def test_get_volumes_info(self):
        for node in self.env.nodes:
            func = functools.partial(
                self.get_node_handler,
                'NodeVolumesInformationHandler',
                node.id
            )
            self.check_time_exec(func)

    def test_get_node_nic(self):
        for node in self.env.nodes:
            func = functools.partial(
                self.get_node_handler,
                'NodeNICsHandler',
                node.id
            )
            self.check_time_exec(func)

    def test_put_nodes_nics(self):
        nodes_list = []
        for node in self.env.nodes:
            resp = self.get_node_handler(
                'NodeNICsHandler',
                node.id
            )
            self.assertEquals(200, resp.status_code)
            interfaces = jsonutils.loads(resp.body)
            nodes_list.append({'id': node.id, 'interfaces': interfaces})
        func = functools.partial(
            self.put_handler,
            'NodeCollectionNICsHandler',
            nodes_list
        )
        self.check_time_exec(func)

    def test_get_allocation_stats(self):
        func = functools.partial(
            self.get_handler,
            'NodesAllocationStatsHandler',
            None
        )
        self.check_time_exec(func)

    def test_add_delete_nodes(self):
        nodes_delete_list = []
        nodes_add_list = []
        self.cluster = self.env.create_cluster(api=True)
        for node in self.env.nodes:
            nodes_delete_list.append({'id': node.id, 'cluster': None})
            nodes_add_list.append({
                                   'id': node.id,
                                   'cluster': self.cluster['id']
                                   })
        func = functools.partial(
            self.put_handler,
            'NodeCollectionHandler',
            nodes_delete_list
        )
        self.check_time_exec(func, 40)
        func = functools.partial(
            self.put_handler,
            'NodeCollectionHandler',
            nodes_add_list
        )
        self.check_time_exec(func, 30)
