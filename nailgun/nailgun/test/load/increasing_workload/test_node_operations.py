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
from nailgun.test.load.increasing_workload.base_load import BaseLoadTestCase


class NodeOperationsLoadTest(BaseLoadTestCase):

    def get_node_handler(self, handler_name, id_value):
        return self.get_handler(handler_name, id_value, id_name='node_id')

    def post_node(self):
        node_template = {
            'name': 'n',
            'status': consts.NODE_STATUSES.discover,
            'roles': [],
            'platform_name': None,
            'cluster_id': None,
            'ip': '127.0.0.1',
            'pending_addition': True,
            'mac': self.env.generate_random_mac(),
            'os_platform': 'op',
            'manufacturer': 'm',
        }
        return self.post_handler('NodeCollectionHandler', node_template)

    def test_get_node(self):
        node = self.env.create_node()
        func = functools.partial(
            self.get_handler,
            'NodeHandler',
            node.id
        )
        times = self.growing_nodes_executor(func)
        self.check_degradation(times)

    def test_put_node(self):
        node = self.env.create_node()
        func = functools.partial(
            self.put_handler,
            'NodeHandler',
            {'status': consts.NODE_STATUSES.ready},
            handler_kwargs={'obj_id': node.id}
        )
        times = self.growing_nodes_executor(func)
        self.check_degradation(times)

    def test_post_node(self):
        times = self.growing_nodes_executor(self.post_node)
        self.check_degradation(times)

    def test_get_nodes(self):
        cluster = self.env.create_cluster()
        cluster_id = cluster['id']
        func = functools.partial(
            self.get_handler,
            'NodeCollectionHandler',
            cluster_id,
            id_name='cluster_id'
        )
        times = self.growing_nodes_executor(
            func,
            cluster_id=cluster_id,
            roles=['compute']
        )
        self.check_degradation(times, degradation_rate=3.0)

    def test_put_nodes(self):
        cluster = self.env.create_cluster()
        cluster_id = cluster['id']
        node = self.env.create_node(cluster_id=cluster_id)
        func = functools.partial(
            self.put_handler,
            'NodeCollectionHandler',
            [{'id': node.id, 'status': consts.NODE_STATUSES.ready}]
        )
        times = self.growing_nodes_executor(func, cluster_id=cluster_id)
        self.check_degradation(times)

    def test_put_node_agent(self):
        cluster = self.env.create_cluster()
        cluster_id = cluster['id']
        node = self.env.create_node(cluster_id=cluster_id)
        func = functools.partial(
            self.put_handler,
            'NodeAgentHandler',
            {'id': node.id, 'ip': '127.0.0.1'}
        )
        times = self.growing_nodes_executor(func, cluster_id=cluster_id)
        self.check_degradation(times)

    def test_get_node_disk(self):
        cluster = self.env.create_cluster()
        cluster_id = cluster['id']
        node = self.env.create_node(cluster_id=cluster_id)
        func = functools.partial(
            self.get_node_handler,
            'NodeDisksHandler',
            node.id
        )
        times = self.growing_nodes_executor(func, cluster_id=cluster_id)
        self.check_degradation(times)

    def test_put_node_disk(self):
        cluster = self.env.create_cluster()
        cluster_id = cluster['id']
        node = self.env.create_node(cluster_id=cluster_id)
        disks_data = [
            {'extra': [], 'size': 953305, 'id': 'sda', 'volumes': [],
             'name': 'sda'},
            {'extra': [], 'size': 0, 'id': 'sdf',
             'volumes': [{'name': 'os', 'size': 0}], 'name': 'sdf'}
        ]
        func = functools.partial(
            self.put_handler,
            'NodeDisksHandler',
            disks_data,
            handler_kwargs={'node_id': node.id}
        )
        times = self.growing_nodes_executor(func, cluster_id=cluster_id)
        self.check_degradation(times)

    def test_get_defaults_disk(self):
        node = self.env.create_node()
        func = functools.partial(
            self.get_node_handler,
            'NodeDefaultsDisksHandler',
            node.id
        )
        times = self.growing_nodes_executor(func)
        self.check_degradation(times)

    def test_get_volumes_info(self):
        cluster = self.env.create_cluster()
        cluster_id = cluster['id']
        node = self.env.create_node(cluster_id=cluster_id)
        func = functools.partial(
            self.get_node_handler,
            'NodeVolumesInformationHandler',
            node.id
        )
        times = self.growing_nodes_executor(func, cluster_id=cluster_id)
        self.check_degradation(times)

    def test_get_node_nic(self):
        cluster = self.env.create_cluster()
        cluster_id = cluster['id']
        node = self.env.create_node(cluster_id=cluster_id)
        func = functools.partial(
            self.get_node_handler,
            'NodeNICsHandler',
            node.id
        )
        times = self.growing_nodes_executor(func, cluster_id=cluster_id)
        self.check_degradation(times)

    def test_put_node_nics(self):
        cluster = self.env.create_cluster()
        cluster_id = cluster['id']
        node = self.env.create_node(cluster_id=cluster_id)

        resp = self.get_node_handler('NodeNICsHandler', node.id)
        self.assertEquals(200, resp.status_code)
        interfaces = jsonutils.loads(resp.body)
        func = functools.partial(
            self.put_handler,
            'NodeNICsHandler',
            interfaces,
            handler_kwargs={'node_id': node.id}
        )
        times = self.growing_nodes_executor(func, cluster_id=cluster_id)
        self.check_degradation(times)

    def test_get_node_nics_default(self):
        cluster = self.env.create_cluster()
        cluster_id = cluster['id']
        node = self.env.create_node(cluster_id=cluster_id)
        func = functools.partial(
            self.get_node_handler,
            'NodeNICsDefaultHandler',
            node.id
        )
        times = self.growing_nodes_executor(func, cluster_id=cluster_id)
        self.check_degradation(times)

    def test_put_nodes_nics(self):
        cluster = self.env.create_cluster()
        cluster_id = cluster['id']
        node = self.env.create_node(cluster_id=cluster_id)
        resp = self.get_node_handler(
            'NodeNICsHandler',
            node.id
        )
        self.assertEquals(200, resp.status_code)
        interfaces = jsonutils.loads(resp.body)
        nodes_list = [{'id': node['id'], 'interfaces': interfaces}]
        func = functools.partial(
            self.put_handler,
            'NodeCollectionNICsHandler',
            nodes_list
        )
        times = self.growing_nodes_executor(func, cluster_id=cluster_id)
        self.check_degradation(times)

    def test_get_allocation_stats(self):
        cluster = self.env.create_cluster()
        cluster_id = cluster['id']
        func = functools.partial(
            self.get_handler,
            'NodesAllocationStatsHandler',
            None
        )
        times = self.growing_nodes_executor(func, cluster_id=cluster_id)
        self.check_degradation(times)
