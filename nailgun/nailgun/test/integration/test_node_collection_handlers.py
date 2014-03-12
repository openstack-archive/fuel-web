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

from nailgun.db.sqlalchemy.models import Node
from nailgun.db.sqlalchemy.models import Notification
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import reverse


class TestHandlers(BaseIntegrationTest):
    def test_node_list_empty(self):
        resp = self.app.get(
            reverse('NodeCollectionHandler'),
            headers=self.default_headers
        )
        self.assertEquals(200, resp.status_code)
        response = json.loads(resp.body)
        self.assertEquals([], response)

    def test_notification_node_id(self):
        node = self.env.create_node(
            api=True,
            meta=self.env.default_metadata()
        )
        notif = self.db.query(Notification).first()
        self.assertEqual(node['id'], notif.node_id)
        resp = self.app.get(
            reverse('NotificationCollectionHandler'),
            headers=self.default_headers
        )
        notif_api = json.loads(resp.body)[0]
        self.assertEqual(node['id'], notif_api['node_id'])

    def test_node_get_with_cluster(self):
        self.env.create(
            cluster_kwargs={"api": True},
            nodes_kwargs=[
                {"cluster_id": None},
                {},
            ]
        )
        cluster = self.env.clusters[0]

        resp = self.app.get(
            reverse('NodeCollectionHandler'),
            params={'cluster_id': cluster.id},
            headers=self.default_headers
        )
        self.assertEquals(200, resp.status_code)
        response = json.loads(resp.body)
        self.assertEquals(1, len(response))
        self.assertEquals(
            self.env.nodes[1].id,
            response[0]['id']
        )

    def test_node_get_with_cluster_None(self):
        self.env.create(
            cluster_kwargs={"api": True},
            nodes_kwargs=[
                {"cluster_id": None},
                {},
            ]
        )

        resp = self.app.get(
            reverse('NodeCollectionHandler'),
            params={'cluster_id': ''},
            headers=self.default_headers
        )
        self.assertEquals(200, resp.status_code)
        response = json.loads(resp.body)
        self.assertEquals(1, len(response))
        self.assertEquals(self.env.nodes[0].id, response[0]['id'])

    def test_node_get_without_cluster_specification(self):
        self.env.create(
            cluster_kwargs={"api": True},
            nodes_kwargs=[
                {"cluster_id": None},
                {},
            ]
        )

        resp = self.app.get(
            reverse('NodeCollectionHandler'),
            headers=self.default_headers
        )
        self.assertEquals(200, resp.status_code)
        response = json.loads(resp.body)
        self.assertEquals(2, len(response))

    def test_node_get_with_cluster_and_assigned_ip_addrs(self):
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"pending_addition": True, "api": True},
                {"pending_addition": True, "api": True}
            ]
        )

        self.env.network_manager.assign_ips(
            [n.id for n in self.env.nodes],
            "management"
        )

        resp = self.app.get(
            reverse('NodeCollectionHandler'),
            headers=self.default_headers
        )

        self.assertEquals(200, resp.status_code)
        response = json.loads(resp.body)
        self.assertEquals(2, len(response))

    def test_node_creation(self):
        resp = self.app.post(
            reverse('NodeCollectionHandler'),
            json.dumps({'mac': 'ASDFAAASDFAA',
                        'meta': self.env.default_metadata(),
                        'status': 'discover'}),
            headers=self.default_headers)
        self.assertEquals(resp.status_code, 201)
        response = json.loads(resp.body)
        self.assertEquals('discover', response['status'])

    def test_node_update(self):
        node = self.env.create_node(api=False)
        resp = self.app.put(
            reverse('NodeCollectionHandler'),
            json.dumps([{'mac': node.mac, 'manufacturer': 'new'}]),
            headers=self.default_headers)
        self.assertEquals(resp.status_code, 200)
        resp = self.app.get(
            reverse('NodeCollectionHandler'),
            headers=self.default_headers
        )
        node = self.db.query(Node).get(node.id)
        self.assertEquals('new', node.manufacturer)

    def test_node_update_empty_mac_or_id(self):
        node = self.env.create_node(api=False)

        resp = self.app.put(
            reverse('NodeCollectionHandler'),
            json.dumps([{'manufacturer': 'man0'}]),
            headers=self.default_headers,
            expect_errors=True)
        self.assertEquals(resp.status_code, 400)
        self.assertEquals(resp.body, "Neither MAC nor ID is specified")

        resp = self.app.put(
            reverse('NodeCollectionHandler'),
            json.dumps([{'mac': None,
                         'manufacturer': 'man1'}]),
            headers=self.default_headers,
            expect_errors=True)
        self.assertEquals(resp.status_code, 400)
        self.assertEquals(resp.body, "Neither MAC nor ID is specified")

        resp = self.app.put(
            reverse('NodeCollectionHandler'),
            json.dumps([{'id': None,
                         'manufacturer': 'man2'}]),
            headers=self.default_headers,
            expect_errors=True)
        self.assertEquals(resp.status_code, 400)
        self.assertEquals(resp.body, "Neither MAC nor ID is specified")

        resp = self.app.put(
            reverse('NodeCollectionHandler'),
            json.dumps([{'mac': None,
                         'id': None,
                         'manufacturer': 'man3'}]),
            headers=self.default_headers,
            expect_errors=True)
        self.assertEquals(resp.status_code, 400)
        self.assertEquals(resp.body, "Neither MAC nor ID is specified")

        resp = self.app.put(
            reverse('NodeCollectionHandler'),
            json.dumps([{'id': node.id,
                         'mac': None,
                         'manufacturer': 'man4'}]),
            headers=self.default_headers,
            expect_errors=True)
        self.assertEquals(resp.status_code, 400)
        self.assertEquals(resp.body, "Null MAC is specified")

        resp = self.app.put(
            reverse('NodeCollectionHandler'),
            json.dumps([{'id': None,
                         'mac': node.mac,
                         'manufacturer': 'man5'}]),
            headers=self.default_headers)
        self.assertEquals(resp.status_code, 200)

        resp = self.app.put(
            reverse('NodeCollectionHandler'),
            json.dumps([{'id': node.id,
                         'manufacturer': 'man6'}]),
            headers=self.default_headers)
        self.assertEquals(resp.status_code, 200)

        resp = self.app.put(
            reverse('NodeCollectionHandler'),
            json.dumps([{'mac': node.mac,
                         'manufacturer': 'man7'}]),
            headers=self.default_headers)
        self.assertEquals(resp.status_code, 200)

        resp = self.app.put(
            reverse('NodeCollectionHandler'),
            json.dumps([{'id': node.id,
                         'mac': node.mac,
                         'manufacturer': 'man8'}]),
            headers=self.default_headers)
        self.assertEquals(resp.status_code, 200)

    def node_update_with_invalid_id(self):
        node = self.env.create_node(api=False)

        resp = self.app.put(
            reverse('NodeCollectionHandler'),
            json.dumps([{'id': 'new_id',
                         'mac': node.mac}]),
            headers=self.default_headers,
            expect_errors=True)
        self.assertEquals(resp.status_code, 400)
        self.assertEquals(resp.body, "Invalid ID specified")

    def test_node_update_agent_discover(self):
        self.env.create_node(
            api=False,
            status='provisioning',
            meta=self.env.default_metadata()
        )
        node_db = self.env.nodes[0]
        resp = self.app.put(
            reverse('NodeCollectionHandler'),
            json.dumps([
                {'mac': node_db.mac, 'is_agent': True,
                 'status': 'discover', 'manufacturer': 'new'}
            ]),
            headers=self.default_headers
        )
        self.assertEquals(resp.status_code, 200)
        resp = self.app.get(
            reverse('NodeCollectionHandler'),
            headers=self.default_headers
        )
        node_db = self.db.query(Node).get(node_db.id)
        self.assertEquals('new', node_db.manufacturer)
        self.assertEquals('provisioning', node_db.status)

    def test_node_timestamp_updated_only_by_agent(self):
        node = self.env.create_node(api=False)
        timestamp = node.timestamp
        resp = self.app.put(
            reverse('NodeCollectionHandler'),
            json.dumps([
                {'mac': node.mac, 'status': 'discover',
                 'manufacturer': 'old'}
            ]),
            headers=self.default_headers)
        self.assertEquals(resp.status_code, 200)
        node = self.db.query(Node).get(node.id)
        self.assertEquals(node.timestamp, timestamp)

        resp = self.app.put(
            reverse('NodeCollectionHandler'),
            json.dumps([
                {'mac': node.mac, 'status': 'discover',
                 'manufacturer': 'new', 'is_agent': True}
            ]),
            headers=self.default_headers)
        self.assertEquals(resp.status_code, 200)
        node = self.db.query(Node).get(node.id)
        self.assertNotEquals(node.timestamp, timestamp)
        self.assertEquals('new', node.manufacturer)

    def test_node_create_ip_not_in_admin_range(self):
        node = self.env.create_node(api=False)

        # Set IP outside of admin network range on eth1
        node.meta['interfaces'][1]['ip'] = '10.21.0.3'
        self.env.network_manager.update_interfaces_info(node)

        # node.mac == eth0 mac so eth0 should now be admin interface
        self.assertEquals(node.admin_interface.name, 'eth0')

    def test_node_create_ext_mac(self):
        node1 = self.env.create_node(
            api=False
        )
        node2_json = {
            "mac": self.env._generate_random_mac(),
            "meta": self.env.default_metadata()
        }
        node2_json["meta"]["interfaces"][0]["mac"] = node1.mac
        resp = self.app.post(
            reverse('NodeCollectionHandler'),
            json.dumps(node2_json),
            headers=self.default_headers,
            expect_errors=True)
        self.assertEquals(resp.status_code, 409)

    def test_node_create_without_mac(self):
        node = self.env.create_node(
            api=True,
            exclude=["mac"],
            expect_http=400,
            expect_message="No mac address specified"
        )
        self.assertEquals(node, None)

    def test_node_update_ext_mac(self):
        meta = self.env.default_metadata()
        node1 = self.env.create_node(
            api=False,
            mac=meta["interfaces"][0]["mac"],
            meta={}
        )
        node1_json = {
            "mac": self.env._generate_random_mac(),
            "meta": meta
        }
        # We want to be sure that new mac is not equal to old one
        self.assertNotEqual(node1.mac, node1_json["mac"])

        # Here we are trying to update node
        resp = self.app.put(
            reverse('NodeCollectionHandler'),
            json.dumps([node1_json]),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(resp.status_code, 200)
        response = json.loads(resp.body)
        # Here we are checking if node mac is successfully updated
        self.assertEqual(node1_json["mac"], response[0]["mac"])
        self.assertEqual(meta, response[0]["meta"])

    def test_duplicated_node_create_fails(self):
        node = self.env.create_node(api=False)
        resp = self.app.post(
            reverse('NodeCollectionHandler'),
            json.dumps({'mac': node.mac}),
            headers=self.default_headers,
            expect_errors=True)
        self.assertEquals(409, resp.status_code)

    def test_node_creation_fail(self):
        resp = self.app.post(
            reverse('NodeCollectionHandler'),
            json.dumps({'mac': 'ASDFAAASDF22',
                        'meta': self.env.default_metadata(),
                        'status': 'error'}),
            headers=self.default_headers,
            expect_errors=True)
        self.assertEquals(resp.status_code, 403)

    def test_reset_cluster_name_when_unassign_node(self):
        self.env.create(
            nodes_kwargs=[
                {'pending_roles': ['controller'],
                 'pending_addition': True,
                 'name': 'new_node'}])

        node = self.env.nodes[0]
        default_name = 'Untitled ({0})'.format(node.mac[-5:])

        resp = self.app.put(
            reverse('NodeCollectionHandler'),
            json.dumps([{'id': node.id,
                         'cluster_id': None,
                         'pending_roles': []}]),
            headers=self.default_headers)
        self.assertEquals(200, resp.status_code)
        response = json.loads(resp.body)
        self.assertEquals(1, len(response))
        self.assertEquals(node.id, response[0]['id'])
        self.assertEquals(node.name, default_name)
        self.assertEquals(node.cluster, None)
        self.assertEquals(node.pending_roles, [])
