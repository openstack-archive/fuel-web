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

import json

from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import reverse


class TestHandlers(BaseIntegrationTest):

    def test_put_handler_with_one_node(self):
        cluster = self.env.create_cluster(api=True)
        mac = '123'
        meta = {}
        self.env.set_interfaces_in_meta(meta, [
            {'name': 'eth0', 'mac': mac},
            {'name': 'eth1', 'mac': '654'}])
        node = self.env.create_node(api=True, meta=meta, mac=mac,
                                    cluster_id=cluster['id'])
        resp = self.app.get(
            reverse('NodeNICsHandler', kwargs={'node_id': node['id']}),
            headers=self.default_headers)
        self.assertEquals(resp.status, 200)
        interfaces = json.loads(resp.body)
        an_key = 'assigned_networks'
        used_iface = filter(lambda x: x[an_key], interfaces)[0]
        another_iface = filter(
            lambda x: x['id'] != used_iface['id'],
            interfaces
        )[0]
        used_iface[an_key], another_iface[an_key] = (
            another_iface[an_key], used_iface[an_key]
        )
        node_json = interfaces
        resp = self.app.put(
            reverse('NodeNICsHandler', kwargs={'node_id': node['id']}),
            json.dumps(node_json),
            headers=self.default_headers)
        self.assertEquals(resp.status, 200)
        new_response = json.loads(resp.body)
        self.assertEquals(new_response, node_json)

    def test_collection_put_handler_with_one_node(self):
        cluster = self.env.create_cluster(api=True)
        mac = '123'
        meta = {}
        self.env.set_interfaces_in_meta(meta, [
            {'name': 'eth0', 'mac': mac},
            {'name': 'eth1', 'mac': '654'}])
        node = self.env.create_node(api=True, meta=meta, mac=mac,
                                    cluster_id=cluster['id'])
        resp = self.app.get(
            reverse('NodeNICsHandler', kwargs={'node_id': node['id']}),
            headers=self.default_headers)
        self.assertEquals(resp.status, 200)
        interfaces = json.loads(resp.body)
        an_key = 'assigned_networks'
        used_iface = filter(lambda x: x[an_key], interfaces)[0]
        another_iface = filter(
            lambda x: x['id'] != used_iface['id'],
            interfaces
        )[0]
        used_iface[an_key], another_iface[an_key] = (
            another_iface[an_key], used_iface[an_key]
        )
        node_json = [{u'id': node['id'], u'interfaces': interfaces}]
        resp = self.app.put(
            reverse('NodeCollectionNICsHandler'),
            json.dumps(node_json),
            headers=self.default_headers)
        self.assertEquals(resp.status, 200)
        new_response = json.loads(resp.body)
        self.assertEquals(new_response, node_json)

    def test_try_to_assign_not_all_networks(self):
        cluster = self.env.create_cluster(api=True)
        mac = '123'
        meta = {}
        self.env.set_interfaces_in_meta(meta, [
            {'name': 'eth0', 'mac': mac},
            {'name': 'eth1', 'mac': '654'}])
        node = self.env.create_node(api=True, meta=meta, mac=mac,
                                    cluster_id=cluster['id'])
        resp = self.app.get(
            reverse('NodeNICsHandler', kwargs={'node_id': node['id']}),
            headers=self.default_headers)
        self.assertEquals(resp.status, 200)
        interfaces = json.loads(resp.body)
        node_json = [{u'id': node['id'], u'interfaces': interfaces}]
        an_key = 'assigned_networks'
        used_iface = filter(lambda x: x[an_key], interfaces)[0]
        used_iface[an_key].pop()
        resp = self.app.put(
            reverse('NodeCollectionNICsHandler'),
            json.dumps(node_json),
            headers=self.default_headers,
            expect_errors=True)
        self.assertEquals(resp.status, 500)
