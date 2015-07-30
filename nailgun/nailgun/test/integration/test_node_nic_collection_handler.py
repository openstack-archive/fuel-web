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

import itertools
import operator

import six

from oslo_serialization import jsonutils

from nailgun import consts
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import fake_tasks
from nailgun.utils import reverse


class TestNodeCollectionNICsHandler(BaseIntegrationTest):

    def test_put_handler_with_one_node(self):
        cluster = self.env.create_cluster(api=True)
        mac = self.env.generate_random_mac()
        meta = {}
        self.env.set_interfaces_in_meta(meta, [
            {'name': 'eth0', 'mac': mac, 'pxe': True},
            {'name': 'eth1', 'mac': self.env.generate_random_mac()}])
        node = self.env.create_node(api=True, meta=meta, mac=mac,
                                    cluster_id=cluster['id'])

        resp_get = self.app.get(
            reverse('NodeNICsHandler', kwargs={'node_id': node['id']}),
            headers=self.default_headers)
        self.assertEqual(resp_get.status_code, 200)

        a_nets = filter(lambda nic: nic['mac'] == mac,
                        resp_get.json_body)[0]['assigned_networks']
        for resp_nic in resp_get.json_body:
            if resp_nic['mac'] == mac:
                resp_nic['assigned_networks'] = []
            else:
                resp_nic['assigned_networks'].extend(a_nets)
                resp_nic['assigned_networks'].sort()
        nodes_list = [{'id': node['id'], 'interfaces': resp_get.json_body}]

        resp_put = self.app.put(
            reverse('NodeCollectionNICsHandler'),
            jsonutils.dumps(nodes_list),
            headers=self.default_headers)
        self.assertEqual(resp_put.status_code, 200)
        self.assertEqual(resp_put.json_body, nodes_list)

    @fake_tasks()
    def test_interface_changes_added(self):
        # Creating cluster with node
        self.env.create_cluster()
        cluster = self.env.clusters[0]
        self.env.create_nodes_w_interfaces_count(
            roles=['controller'],
            pending_addition=True,
            cluster_id=cluster.id,
            nodes_count=1,
            if_count=4
        )
        # Deploying cluster
        deployment_task = self.env.launch_deployment()
        self.env.wait_ready(deployment_task)

        def filter_changes(chg_type, chg_list):
            return filter(lambda x: x.get('name') == chg_type, chg_list)

        # cluster = self.env.clusters[0]
        changes = filter_changes(
            consts.CLUSTER_CHANGES.interfaces,
            cluster['changes']
        )
        # Checking no interfaces change after cluster deployed
        self.assertEquals(0, len(changes))

        node_id = self.env.nodes[0].id
        # Change node status to be able to update its interfaces
        self.env.nodes[0].status = 'discover'
        self.db.flush()
        # Getting nics
        resp = self.env.node_nics_get(node_id)

        # Updating nics
        self.env.node_nics_put(node_id, resp.json_body)
        # Checking 'interfaces' change in cluster changes
        changes = filter_changes(
            consts.CLUSTER_CHANGES.interfaces,
            cluster['changes']
        )
        self.assertEquals(1, len(changes))

    def test_interface_changes_locking(self):
        lock_vs_status = {
            consts.NODE_STATUSES.discover: False,
            consts.NODE_STATUSES.error: False,
            consts.NODE_STATUSES.provisioning: True,
            consts.NODE_STATUSES.provisioned: True,
            consts.NODE_STATUSES.deploying: True,
            consts.NODE_STATUSES.ready: True,
            consts.NODE_STATUSES.removing: True}
        meta = self.env.default_metadata()
        meta['interfaces'] = [{'name': 'eth0', 'pxe': True},
                              {'name': 'eth1'}]
        self.env.create_node(
            roles=['controller'],
            meta=meta
        )
        node = self.env.nodes[0]
        for status, lock in six.iteritems(lock_vs_status):
            node.status = status
            self.db.flush()
            # Getting nics
            resp = self.env.node_nics_get(node.id)
            # Updating nics
            resp = self.env.node_nics_put(
                node.id, resp.json_body, expect_errors=lock)
            self.assertEqual(resp.status_code, 400 if lock else 200)


class TestNodeCollectionNICsDefaultHandler(BaseIntegrationTest):

    def setUp(self):
        super(TestNodeCollectionNICsDefaultHandler, self).setUp()

        # two nodes in one cluster
        self.cluster = self.env.create(
            nodes_kwargs=[
                {'roles': ['controller'], 'mac': '01:01:01:01:01:01'},
                {'roles': ['compute'], 'mac': '02:02:02:02:02:02'}])

        # one node in another cluster
        self.env.create(
            nodes_kwargs=[
                {'roles': ['controller'], 'mac': '03:03:03:03:03:03'}])

        # one node outside clusters
        self.env.create_node(api=True, mac='04:04:04:04:04:04')

    def test_get_w_cluster_id(self):
        # get nics of cluster and check that response is ok
        resp = self.app.get(
            '{url}?cluster_id={cluster_id}'.format(
                url=reverse('NodeCollectionNICsDefaultHandler'),
                cluster_id=self.cluster['id']),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)

        # check response
        self.assertEqual(len(resp.json_body), 2)

        macs = [iface['mac'] for node in resp.json_body for iface in node]
        self.assertTrue('01:01:01:01:01:01' in macs)
        self.assertTrue('02:02:02:02:02:02' in macs)
        self.assertFalse('03:03:03:03:03:03' in macs)

    def test_get_wo_cluster_id(self):
        # get nics of cluster and check that response is ok
        resp = self.app.get(
            reverse('NodeCollectionNICsDefaultHandler'),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)

        # check response
        self.assertEqual(len(resp.json_body), 3)

        macs = [iface['mac'] for node in resp.json_body for iface in node]
        self.assertTrue('01:01:01:01:01:01' in macs)
        self.assertTrue('02:02:02:02:02:02' in macs)
        self.assertTrue('03:03:03:03:03:03' in macs)


class BaseTestNodeNICsNamesHandler(BaseIntegrationTest):
    CLUSTER_COUNT = 3
    NODE_IF_COUNT = 3

    def setUp(self):
        super(BaseTestNodeNICsNamesHandler, self).setUp()
        # Create CLUSTER_COUNT clusters with nodes in them
        # self.env.clusters[n] will have n nodes in it
        # Each node will have NODE_IF_COUNT interfaces
        for i in range(self.CLUSTER_COUNT):
            self.env.create_cluster(api=False)
        # Create a standalone node
        self.env.create_nodes_w_interfaces_count(
            1, if_count=self.NODE_IF_COUNT, add_bus_info=True)
        # Create nodes in clusters
        for node_count, cluster in enumerate(self.env.clusters):
            if node_count == 0:
                continue
            self.env.create_nodes_w_interfaces_count(
                node_count, if_count=self.NODE_IF_COUNT,
                add_bus_info=True, cluster_id=cluster.id)

    def _get_filter(self, attr_name, attr_value):
        def attr_filter(obj):
            if getattr(obj, attr_name) == attr_value:
                return True
            else:
                return False
        return attr_filter

    def _get_env_nic_ids(self, cluster_id=None, node_ids=None,
                         mac=None, bus=None):
        env_nics = []
        for node in self.env.nodes:
            include_this_node = True
            if cluster_id is not None:
                if node.cluster_id != cluster_id:
                    include_this_node = False
            elif node_ids is not None:
                if node.id not in node_ids:
                    include_this_node = False
            if include_this_node:
                env_nics.extend(node.nic_interfaces)
        if mac is not None:
            env_nics = filter(self._get_filter('mac', mac), env_nics)
        if bus is not None:
            env_nics = filter(self._get_filter('bus_info', bus), env_nics)
        return map(operator.attrgetter('id'), env_nics)

    def _extract_nic_ids(self, data):
        return map(operator.itemgetter('id'), data)


class TestNodeNICsNamesHandler(BaseTestNodeNICsNamesHandler):

    def test_get_wo_filters(self):
        # Get all interfaces on all nodes through API and check
        # that they are the same as what we've created during setUp
        for node in self.env.nodes:
            resp = self.app.get(reverse('NodeNICsNamesHandler',
                                        {'node_id': node.id}),
                                headers=self.default_headers)
            self.assertEqual(resp.status_code, 200)
            api_nics = self._extract_nic_ids(resp.json)
            env_nics = self._get_env_nic_ids(node_ids=[node.id])
            self.assertItemsEqual(api_nics, env_nics)

    def test_get_invalid_node_id(self):
        # Check that API returns an error if invalid node_id is specified
        node_id = max(self.env.nodes, key=operator.attrgetter('id')).id + 1
        resp = self.app.get(reverse('NodeNICsNamesHandler',
                                    {'node_id': node_id}),
                            headers=self.default_headers,
                            expect_errors=True)
        self.assertEqual(resp.status_code, 404)

    def test_get_by_mac(self):
        # Get all created interfaces by their MAC addresses
        for node in self.env.nodes:
            for nic in node.nic_interfaces:
                resp = self.app.get(reverse('NodeNICsNamesHandler',
                                            {'node_id': node.id}),
                                    params={'mac': nic.mac},
                                    headers=self.default_headers)
                self.assertEqual(resp.status_code, 200)
                api_nics = self._extract_nic_ids(resp.json)
                env_nics = self._get_env_nic_ids(node_ids=[node.id],
                                                 mac=nic.mac)
                self.assertItemsEqual(api_nics, env_nics)

    def test_get_by_bus(self):
        # Get created interfaces by bus info
        for node in self.env.nodes:
            for nic in node.nic_interfaces:
                resp = self.app.get(reverse('NodeNICsNamesHandler',
                                            {'node_id': node.id}),
                                    params={'bus_info': nic.bus_info},
                                    headers=self.default_headers)
                self.assertEqual(resp.status_code, 200)
                api_nics = self._extract_nic_ids(resp.json)
                env_nics = self._get_env_nic_ids(node_ids=[node.id],
                                                 bus=nic.bus_info)
                self.assertItemsEqual(api_nics, env_nics)

    def test_get_by_mac_and_bus(self):
        # Check that API returns an error if both mac
        # and bus_info are specified in the request
        resp = self.app.get(reverse('NodeNICsNamesHandler',
                                    {'node_id': self.env.nodes[0].id}),
                            params={'mac': 1, 'bus_info': 1},
                            headers=self.default_headers,
                            expect_errors=True)
        self.assertEqual(resp.status_code, 400)

    def test_put_valid_data(self):
        # Check that API correctly renames interfaces
        # if valid data is supplied

        for node in self.env.nodes:
            # First, get all interfaces
            resp = self.app.get(reverse('NodeNICsNamesHandler',
                                        {'node_id': node.id}),
                                headers=self.default_headers)

            # Then rename all of them
            new_names = []
            for nic in resp.json:
                new_name = "renamed-{0}".format(nic['name'])
                new_names.append({'id': nic['id'], 'name': new_name})
            resp = self.app.put(reverse('NodeNICsNamesHandler',
                                        {'node_id': node.id}),
                                jsonutils.dumps(new_names),
                                headers=self.default_headers)
            self.assertEqual(resp.status_code, 200)

            # Get all interfaces again and check that they were renamed
            resp = self.app.get(reverse('NodeNICsNamesHandler',
                                        {'node_id': node.id}),
                                headers=self.default_headers)
            actual_names = [{'id': nic['id'], 'name': nic['name']}
                            for nic in resp.json]
            self.assertItemsEqual(new_names, actual_names)

    def test_put_nonexistent_nic_id(self):
        # Check that API returns an error if nonexistent NIC id is specified
        nic_id = max(self._get_env_nic_ids()) + 1
        data = [{'id': nic_id, 'name': 'test'}]
        resp = self.app.put(reverse('NodeNICsNamesHandler',
                                    {'node_id': self.env.nodes[0].id}),
                            jsonutils.dumps(data),
                            headers=self.default_headers,
                            expect_errors=True)
        self.assertEqual(resp.status_code, 404)

    def test_put_not_owned_nic_id(self):
        # Check that API returns an error if specified NIC
        # does not belong to node for which the API is called
        node_id = self.env.nodes[0].id
        # Take NIC from another node
        nic_id = self.env.nodes[1].nic_interfaces[0].id
        data = [{'id': nic_id, 'name': 'test'}]
        resp = self.app.put(reverse('NodeNICsNamesHandler',
                                    {'node_id': node_id}),
                            jsonutils.dumps(data),
                            headers=self.default_headers,
                            expect_errors=True)
        self.assertEqual(resp.status_code, 409)

    def test_put_duplicate_nic_name(self):
        # Check that API returns an error if duplicate name is specified
        for node in self.env.nodes:
            # First, get all interfaces
            resp = self.app.get(reverse('NodeNICsNamesHandler',
                                        {'node_id': node.id}),
                                headers=self.default_headers)

            # Then rename all of them to the same name
            new_names = [{'id': nic['id'], 'name': 'same_name'}
                         for nic in resp.json]
            resp = self.app.put(reverse('NodeNICsNamesHandler',
                                        {'node_id': node.id}),
                                jsonutils.dumps(new_names),
                                headers=self.default_headers,
                                expect_errors=True)
            self.assertEqual(resp.status_code, 409)


class TestNodeCollectionNICsNamesHandler(BaseTestNodeNICsNamesHandler):

    def test_get_wo_filters(self):
        # Get all interfaces on all nodes through API and check
        # that they are the same as what we've created during setUp
        resp = self.app.get(reverse('NodeCollectionNICsNamesHandler'),
                            headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)
        api_nics = self._extract_nic_ids(resp.json)
        env_nics = self._get_env_nic_ids()
        self.assertItemsEqual(api_nics, env_nics)

    def test_get_by_cluster_id(self):
        # Get all interfaces on all nodes in a specified cluster
        for cluster in self.env.clusters:
            resp = self.app.get(reverse('NodeCollectionNICsNamesHandler'),
                                params={'cluster_id': cluster.id},
                                headers=self.default_headers)
            self.assertEqual(resp.status_code, 200)
            api_nics = self._extract_nic_ids(resp.json)
            env_nics = self._get_env_nic_ids(cluster_id=cluster.id)
            self.assertItemsEqual(api_nics, env_nics)

    def test_get_by_node_ids(self):
        # Get all interfaces on specified nodes
        # all combinations of node ids are tested, i.e.
        # [1], [2], [3], [1, 2], [1, 3], [2, 3], [1, 2, 3]
        node_ids = map(operator.attrgetter('id'), self.env.nodes)
        for node_count in range(1, len(node_ids) + 1):
            for node_id in itertools.combinations(node_ids, node_count):
                resp = self.app.get(reverse('NodeCollectionNICsNamesHandler'),
                                    params={'node_id': node_id},
                                    headers=self.default_headers)
                self.assertEqual(resp.status_code, 200)
                api_nics = self._extract_nic_ids(resp.json)
                env_nics = self._get_env_nic_ids(node_ids=node_id)
                self.assertItemsEqual(api_nics, env_nics)

    def test_get_by_cluster_id_and_node_id(self):
        # Check that API returns an error if both cluster_id
        # and node_id are specified in the request
        resp = self.app.get(reverse('NodeCollectionNICsNamesHandler'),
                            params={'cluster_id': 1, 'node_id': 1},
                            headers=self.default_headers,
                            expect_errors=True)
        self.assertEqual(resp.status_code, 400)

    def test_get_invalid_node_id(self):
        # Check that API returns an error if invalid node_id is specified
        resp = self.app.get(reverse('NodeCollectionNICsNamesHandler'),
                            params={'node_id': [1, 'a']},
                            headers=self.default_headers,
                            expect_errors=True)
        self.assertEqual(resp.status_code, 400)

    def test_get_by_mac(self):
        # Get all created interfaces by their MAC addresses
        env_macs = []
        for node in self.env.nodes:
            env_macs.extend(map(operator.attrgetter('mac'),
                                node.nic_interfaces))
        for mac in env_macs:
            resp = self.app.get(reverse('NodeCollectionNICsNamesHandler'),
                                params={'mac': mac},
                                headers=self.default_headers)
            self.assertEqual(resp.status_code, 200)
            api_nics = self._extract_nic_ids(resp.json)
            env_nics = self._get_env_nic_ids(mac=mac)
            self.assertItemsEqual(api_nics, env_nics)

    def test_get_by_bus(self):
        # Get created interfaces by bus info
        env_bus = []
        for node in self.env.nodes:
            env_bus.extend(map(operator.attrgetter('bus_info'),
                               node.nic_interfaces))
        for bus in env_bus:
            resp = self.app.get(reverse('NodeCollectionNICsNamesHandler'),
                                params={'bus_info': bus},
                                headers=self.default_headers)
            self.assertEqual(resp.status_code, 200)
            api_nics = self._extract_nic_ids(resp.json)
            env_nics = self._get_env_nic_ids(bus=bus)
            self.assertItemsEqual(api_nics, env_nics)

    def test_get_by_mac_and_bus(self):
        # Check that API returns an error if both mac
        # and bus_info are specified in the request
        resp = self.app.get(reverse('NodeCollectionNICsNamesHandler'),
                            params={'mac': 1, 'bus_info': 1},
                            headers=self.default_headers,
                            expect_errors=True)
        self.assertEqual(resp.status_code, 400)

    def test_put_valid_data(self):
        # Check that API correctly renames interfaces
        # if valid data is supplied

        # First, get all interfaces
        resp = self.app.get(reverse('NodeCollectionNICsNamesHandler'),
                            headers=self.default_headers)

        # Then rename all of them
        new_names = []
        for nic in resp.json:
            new_name = "renamed-{0}".format(nic['name'])
            new_names.append({'id': nic['id'], 'name': new_name})
        resp = self.app.put(reverse('NodeCollectionNICsNamesHandler'),
                            jsonutils.dumps(new_names),
                            headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)

        # Get all interfaces again and check that they were renamed
        resp = self.app.get(reverse('NodeCollectionNICsNamesHandler'),
                            headers=self.default_headers)
        actual_names = [{'id': nic['id'], 'name': nic['name']}
                        for nic in resp.json]
        self.assertItemsEqual(new_names, actual_names)

    def test_put_nonexistent_nic_id(self):
        # Check that API returns an error if nonexistent NIC id is specified
        nic_id = max(self._get_env_nic_ids()) + 1
        data = [{'id': nic_id, 'name': 'test'}]
        resp = self.app.put(reverse('NodeCollectionNICsNamesHandler'),
                            jsonutils.dumps(data),
                            headers=self.default_headers,
                            expect_errors=True)
        self.assertEqual(resp.status_code, 404)

    def test_put_duplicate_nic_name(self):
        # Check that API returns an error if duplicate name is specified

        # First, get all interfaces
        resp = self.app.get(reverse('NodeCollectionNICsNamesHandler'),
                            headers=self.default_headers)

        # Then rename all of them to the same name
        new_names = [{'id': nic['id'], 'name': 'same_name'}
                     for nic in resp.json]
        resp = self.app.put(reverse('NodeCollectionNICsNamesHandler'),
                            jsonutils.dumps(new_names),
                            headers=self.default_headers,
                            expect_errors=True)
        self.assertEqual(resp.status_code, 409)
