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
import random

from oslo_serialization import jsonutils

from nailgun import consts
from nailgun.test.base import fake_tasks
from nailgun.test.performance import base
from nailgun.test.utils import random_string


class NodeOperationsLoadTest(base.BaseUnitLoadTestCase):

    @classmethod
    def setUpClass(cls):
        super(NodeOperationsLoadTest, cls).setUpClass()
        cls.env.create_nodes(cls.NODES_NUM, cluster_id=cls.cluster['id'])

    @base.evaluate_unit_performance
    def test_put_node(self):
        func = functools.partial(
            self.put_handler,
            'NodeHandler',
            {'status': consts.NODE_STATUSES.ready,
             'name': random_string(20)},
            handler_kwargs={'obj_id': random.choice(self.env.nodes).id}
        )
        self.check_time_exec(func)

    @base.evaluate_unit_performance
    def test_get_nodes(self):
        func = functools.partial(
            self.get_handler,
            'NodeCollectionHandler',
            handler_kwargs={'cluster_id': self.cluster['id']}
        )
        self.check_time_exec(func, 6)

    @base.evaluate_unit_performance
    def test_get_defaults_disk(self):
        func = functools.partial(
            self.get_handler,
            'NodeDefaultsDisksHandler',
            handler_kwargs={'node_id': random.choice(self.env.nodes).id}
        )
        self.check_time_exec(func)

    @base.evaluate_unit_performance
    def test_get_volumes_info(self):
        func = functools.partial(
            self.get_handler,
            'NodeVolumesInformationHandler',
            handler_kwargs={'node_id': random.choice(self.env.nodes).id}
        )
        self.check_time_exec(func)

    @base.evaluate_unit_performance
    def test_get_node_nic(self):
        func = functools.partial(
            self.get_handler,
            'NodeNICsHandler',
            handler_kwargs={'node_id': random.choice(self.env.nodes).id}
        )
        self.check_time_exec(func)

    @base.evaluate_unit_performance
    def test_put_nodes_nics(self):
        # node's nics can be changed only in discover or error state
        for node in self.env.nodes:
            node.status = consts.NODE_STATUSES.discover

        self.env.db.flush()

        nodes_list = []
        for node in self.env.nodes:
            resp = self.get_handler(
                'NodeNICsHandler',
                handler_kwargs={'node_id': node.id}
            )
            self.assertEquals(200, resp.status_code)
            interfaces = jsonutils.loads(resp.body)
            nodes_list.append({'id': node.id, 'interfaces': interfaces})
        func = functools.partial(
            self.put_handler,
            'NodeCollectionNICsHandler',
            nodes_list
        )
        self.check_time_exec(func, 14)

    @base.evaluate_unit_performance
    def test_get_allocation_stats(self):
        func = functools.partial(
            self.get_handler,
            'NodesAllocationStatsHandler'
        )
        self.check_time_exec(func)

    @base.evaluate_unit_performance
    def test_add_node_to_cluster_then_remove_from_cluster(self):
        nodes_delete_list = []
        nodes_add_list = []
        self.cluster = self.env.create_cluster(api=True)
        for node in self.env.nodes:
            nodes_delete_list.append({'id': node.id, 'cluster': None})
            nodes_add_list.append({'id': node.id,
                                   'cluster': self.cluster['id']})
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

    @fake_tasks()
    @base.evaluate_unit_performance
    def test_provision_nodes(self, _):
        func = functools.partial(
            self.put_handler,
            'ProvisionSelectedNodes',
            {},
            handler_kwargs={'cluster_id': self.cluster.id},
        )

        for node in self.cluster.nodes:
            node.pending_addition = True

        self.env.db.commit()

        self.check_time_exec(func, 30)

        for node in self.cluster.nodes:
            node.pending_addition = False

        self.env.db.commit()

    @base.evaluate_unit_performance
    def test_node_collection_network_interface_controllers_retrieve(self):
        func = functools.partial(
            self.get_handler,
            'NodeCollectionNICsDefaultHandler',
        )

        self.check_time_exec(func, 20)
