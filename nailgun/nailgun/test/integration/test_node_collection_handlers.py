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

from oslo_serialization import jsonutils

from nailgun import consts
from nailgun.db.sqlalchemy.models import Node
from nailgun.db.sqlalchemy.models import Notification
from nailgun.test.base import BaseIntegrationTest
from nailgun.utils import reverse


class TestHandlers(BaseIntegrationTest):

    def test_node_list_empty(self):
        resp = self.app.get(
            reverse('NodeCollectionHandler'),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        self.assertEqual([], resp.json_body)

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
        notif_api = resp.json_body[0]
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
        self.assertEqual(200, resp.status_code)
        self.assertEqual(1, len(resp.json_body))
        self.assertEqual(
            self.env.nodes[1].id,
            resp.json_body[0]['id']
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
        self.assertEqual(200, resp.status_code)
        self.assertEqual(1, len(resp.json_body))
        self.assertEqual(self.env.nodes[0].id, resp.json_body[0]['id'])

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
        self.assertEqual(200, resp.status_code)
        self.assertEqual(2, len(resp.json_body))

    def test_node_get_with_cluster_and_assigned_ip_addrs(self):
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"pending_addition": True, "api": True},
                {"pending_addition": True, "api": True}
            ]
        )

        self.env.network_manager.assign_ips(
            self.env.clusters[-1],
            self.env.nodes,
            "management"
        )

        resp = self.app.get(
            reverse('NodeCollectionHandler'),
            headers=self.default_headers
        )

        self.assertEqual(200, resp.status_code)
        self.assertEqual(2, len(resp.json_body))

    def test_node_creation(self):
        resp = self.app.post(
            reverse('NodeCollectionHandler'),
            jsonutils.dumps({'mac': self.env.generate_random_mac(),
                             'meta': self.env.default_metadata(),
                             'status': 'discover'}),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual('discover', resp.json_body['status'])

    def test_node_update(self):
        node = self.env.create_node(api=False)
        resp = self.app.put(
            reverse('NodeCollectionHandler'),
            jsonutils.dumps([{'mac': node.mac, 'manufacturer': 'new'}]),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)
        resp = self.app.get(
            reverse('NodeCollectionHandler'),
            headers=self.default_headers
        )
        node = self.db.query(Node).get(node.id)
        self.assertEqual('new', node.manufacturer)

    def test_node_update_empty_mac_or_id(self):
        node = self.env.create_node(api=False)

        resp = self.app.put(
            reverse('NodeCollectionHandler'),
            jsonutils.dumps([{'manufacturer': 'man0'}]),
            headers=self.default_headers,
            expect_errors=True)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(
            resp.json_body["message"],
            "Neither MAC nor ID is specified"
        )

        resp = self.app.put(
            reverse('NodeCollectionHandler'),
            jsonutils.dumps([{'id': node.id,
                              'mac': None,
                              'manufacturer': 'man4'}]),
            headers=self.default_headers,
            expect_errors=True)
        self.assertEqual(resp.status_code, 400)
        self.assertIn(
            "schema['properties']['mac']",
            resp.json_body["message"]
        )
        self.assertIn(
            "None is not of type 'string'",
            resp.json_body["message"]
        )

        resp = self.app.put(
            reverse('NodeCollectionHandler'),
            jsonutils.dumps([{'mac': node.mac,
                              'manufacturer': 'man5'}]),
            headers=self.default_headers
        )
        self.assertEqual(resp.status_code, 200)

        resp = self.app.put(
            reverse('NodeCollectionHandler'),
            jsonutils.dumps([{'id': node.id,
                              'manufacturer': 'man6'}]),
            headers=self.default_headers
        )
        self.assertEqual(resp.status_code, 200)

        resp = self.app.put(
            reverse('NodeCollectionHandler'),
            jsonutils.dumps([{'mac': node.mac,
                              'manufacturer': 'man7'}]),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)

        resp = self.app.put(
            reverse('NodeCollectionHandler'),
            jsonutils.dumps([{'id': node.id,
                              'mac': node.mac,
                              'manufacturer': 'man8'}]),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)

    def node_update_with_invalid_id(self):
        node = self.env.create_node(api=False)

        resp = self.app.put(
            reverse('NodeCollectionHandler'),
            jsonutils.dumps([{'id': 'new_id',
                              'mac': node.mac}]),
            headers=self.default_headers,
            expect_errors=True)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(
            resp.json_body["message"],
            "Invalid ID specified"
        )

    def test_node_update_agent_discover(self):
        self.env.create_node(
            api=False,
            status='provisioning',
            meta=self.env.default_metadata()
        )
        node_db = self.env.nodes[0]
        resp = self.app.put(
            reverse('NodeAgentHandler'),
            jsonutils.dumps(
                {'mac': node_db.mac,
                 'status': 'discover', 'manufacturer': 'new'}
            ),
            headers=self.default_headers
        )
        self.assertEqual(resp.status_code, 200)
        resp = self.app.get(
            reverse('NodeCollectionHandler'),
            headers=self.default_headers
        )
        node_db = self.db.query(Node).get(node_db.id)
        self.assertEqual('new', node_db.manufacturer)
        self.assertEqual('provisioning', node_db.status)

    def test_node_timestamp_updated_only_by_agent(self):
        node = self.env.create_node(api=False)
        timestamp = node.timestamp
        resp = self.app.put(
            reverse('NodeCollectionHandler'),
            jsonutils.dumps([
                {'mac': node.mac, 'status': 'discover',
                 'manufacturer': 'old'}
            ]),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)
        node = self.db.query(Node).get(node.id)
        self.assertEqual(node.timestamp, timestamp)

        resp = self.app.put(
            reverse('NodeAgentHandler'),
            jsonutils.dumps(
                {'mac': node.mac, 'status': 'discover',
                 'manufacturer': 'new'}
            ),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)
        node = self.db.query(Node).get(node.id)
        self.assertNotEqual(node.timestamp, timestamp)
        self.assertEqual('new', node.manufacturer)

    def test_agent_caching(self):
        node = self.env.create_node(api=False)
        resp = self.app.put(
            reverse('NodeAgentHandler'),
            jsonutils.dumps({
                'mac': node.mac,
                'manufacturer': 'new',
                'agent_checksum': 'test'
            }),
            headers=self.default_headers)
        response = resp.json_body
        self.assertEqual(resp.status_code, 200)
        self.assertFalse('cached' in response and response['cached'])
        resp = self.app.put(
            reverse('NodeAgentHandler'),
            jsonutils.dumps({
                'mac': node.mac,
                'manufacturer': 'new',
                'agent_checksum': 'test'
            }),
            headers=self.default_headers)
        response = resp.json_body
        self.assertEqual(resp.status_code, 200)
        self.assertTrue('cached' in response and response['cached'])

    def test_agent_updates_node_by_interfaces(self):
        node = self.env.create_node(api=False)
        interface = node.meta['interfaces'][0]

        resp = self.app.put(
            reverse('NodeAgentHandler'),
            jsonutils.dumps({
                'mac': '00:00:00:00:00:00',
                'meta': {
                    'interfaces': [interface]},
            }),
            headers=self.default_headers)

        self.assertEqual(resp.status_code, 200)

    def test_node_create_ip_not_in_admin_range(self):
        node = self.env.create_node(api=False)

        # Set IP outside of admin network range on eth1
        node.meta['interfaces'][1]['ip'] = '10.21.0.3'
        self.app.put(
            reverse('NodeAgentHandler'),
            jsonutils.dumps({
                'mac': node.mac,
                'meta': node.meta,
            }),
            headers=self.default_headers)

        self.env.network_manager.update_interfaces_info(node)

        # node.mac == eth0 mac so eth0 should now be admin interface
        admin_iface = self.env.network_manager.get_admin_interface(node)

        self.assertEqual(admin_iface.name, 'eth0')

    def test_node_create_ext_mac(self):
        node1 = self.env.create_node(
            api=False
        )
        node2_json = {
            "mac": self.env.generate_random_mac(),
            "meta": self.env.default_metadata(),
            "status": "discover"
        }
        node2_json["meta"]["interfaces"][0]["mac"] = node1.mac
        resp = self.app.post(
            reverse('NodeCollectionHandler'),
            jsonutils.dumps(node2_json),
            headers=self.default_headers,
            expect_errors=True)
        self.assertEqual(resp.status_code, 409)

    def test_node_create_without_mac(self):
        node = self.env.create_node(
            api=True,
            exclude=["mac"],
            expect_http=400,
            expected_error="No mac address specified"
        )
        self.assertEqual(node, None)

    def test_node_create_with_invalid_disk_model(self):
        meta = self.env.default_metadata()
        meta['disks'][0]['model'] = None

        node = self.env.create_node(
            api=True,
            expect_http=201,
            meta=meta
        )
        self.assertIsNotNone(node)

    def test_node_create_mac_validation(self):
        # entry format: (mac_address, http_response_code)
        maccaddresses = (
            # invalid macaddresses
            ('60a44c3528ff', 400),
            ('60:a4:4c:35:28', 400),
            ('60:a4:4c:35:28:fg', 400),
            ('76:DC:7C:CA:G4:75', 400),
            ('76-DC-7C-CA-G4-75', 400),

            # valid macaddresses
            ('60:a4:4c:35:28:ff', 201),
            ('48-2C-6A-1E-59-3D', 201),
        )

        for mac, http_code in maccaddresses:
            response = self.app.post(
                reverse('NodeCollectionHandler'),
                jsonutils.dumps({
                    'mac': mac,
                    'status': 'discover',
                }),
                headers=self.default_headers,
                expect_errors=(http_code != 201)
            )
            self.assertEqual(response.status_code, http_code)

    def test_node_update_ext_mac(self):
        meta = self.env.default_metadata()
        node1 = self.env.create_node(
            api=False,
            mac=meta["interfaces"][0]["mac"],
            meta={}
        )
        node1_json = {
            "mac": self.env.generate_random_mac(),
            "meta": meta
        }
        # We want to be sure that new mac is not equal to old one
        self.assertNotEqual(node1.mac, node1_json["mac"])

        # Here we are trying to update node
        resp = self.app.put(
            reverse('NodeCollectionHandler'),
            jsonutils.dumps([node1_json]),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(resp.status_code, 200)

        # Here we are checking if node mac is successfully updated
        self.assertEqual(node1_json["mac"], resp.json_body[0]["mac"])
        self.assertEqual(meta, resp.json_body[0]["meta"])

    def test_duplicated_node_create_fails(self):
        node = self.env.create_node(api=False)
        resp = self.app.post(
            reverse('NodeCollectionHandler'),
            jsonutils.dumps({'mac': node.mac, 'status': 'discover'}),
            headers=self.default_headers,
            expect_errors=True)
        self.assertEqual(409, resp.status_code)

    def test_node_creation_fail(self):
        resp = self.app.post(
            reverse('NodeCollectionHandler'),
            jsonutils.dumps({'mac': self.env.generate_random_mac(),
                             'meta': self.env.default_metadata(),
                             'status': 'error'}),
            headers=self.default_headers,
            expect_errors=True)
        self.assertEqual(resp.status_code, 403)

    def test_reset_cluster_name_when_unassign_node(self):
        node_name = 'new_node_name'
        self.env.create(
            nodes_kwargs=[
                {'pending_roles': ['controller'],
                 'pending_addition': True,
                 'name': node_name}])

        node = self.env.nodes[0]

        resp = self.app.put(
            reverse('NodeCollectionHandler'),
            jsonutils.dumps([{'id': node.id,
                              'cluster_id': None,
                              'pending_roles': []}]),
            headers=self.default_headers)
        self.assertEqual(200, resp.status_code)
        self.assertEqual(1, len(resp.json_body))
        self.assertEqual(node.id, resp.json_body[0]['id'])
        self.assertEqual(node.name, node_name)
        self.assertEqual(node.cluster, None)
        self.assertEqual(node.pending_roles, [])

    def test_discovered_node_unified_name(self):
        node_mac = self.env.generate_random_mac()

        def node_name_test(mac):
            self.env.create_node(
                api=True,
                **{'mac': mac}
            )

            node = self.app.get(reverse('NodeCollectionHandler')).json_body[0]
            self.assertEqual(node['name'],
                             'Untitled ({0})'.format(node_mac[-5:]))

        node_name_test(node_mac.upper())

        node_id = self.app.get(
            reverse('NodeCollectionHandler')
        ).json_body[0]['id']

        self.app.delete(
            reverse('NodeHandler', {'obj_id': node_id})
        )

        node_name_test(node_mac.lower())

    def test_node_get_by_cluster_id(self):

        cluster1 = self.env.create(
            cluster_kwargs={"api": False},
            nodes_kwargs=[{}, {}])
        self.env.create(
            cluster_kwargs={"api": False},
            nodes_kwargs=[
                {'cluster_id': None},
                {'cluster_id': None}])

        resp = self.app.get(
            reverse('NodeCollectionHandler'),
            params={'cluster_id': cluster1.id},
            headers=self.default_headers)

        self.assertEqual(200, resp.status_code)
        self.assertItemsEqual(
            [n['id'] for n in resp.json_body],
            [cluster1.nodes[0].id, cluster1.nodes[1].id, ])

    def test_node_get_by_wrong_cluster_id(self):
        wrong_cluster_id = 'wcid'

        resp = self.app.get(
            reverse('NodeCollectionHandler'),
            params={'cluster_id': wrong_cluster_id},
            headers=self.default_headers,
            expect_errors=True)

        self.assertEqual(400, resp.status_code)
        self.assertIn('Failed validating', resp.json_body['message'])
        self.assertIn(
            "'{0}' is not valid".format(wrong_cluster_id),
            resp.json_body['message'])

    def test_node_get_by_group_id(self):
        self.env.create_cluster(api=False)
        nodegroups = []
        for i in range(3):
            nodegroup = self.env.create_node_group(
                name='ng{0}'.format(i), api=False)
            nodegroups.append(nodegroup.id)

        cluster = self.env.create(
            cluster_kwargs={"api": False},
            nodes_kwargs=[
                {'group_id': nodegroups[0]},
                {'group_id': nodegroups[0]},
                {'group_id': nodegroups[1]},
                {'group_id': nodegroups[2]}])

        resp = self.app.get(
            reverse('NodeCollectionHandler'),
            params={'group_id': nodegroups[0]},
            headers=self.default_headers)

        self.assertEqual(200, resp.status_code)
        self.assertItemsEqual(
            [n['id'] for n in resp.json_body],
            [cluster.nodes[0].id, cluster.nodes[1].id, ])

    def test_node_get_by_empty_group_id(self):
        self.env.create_cluster(api=False)
        nodegroups = []
        for i in range(2):
            nodegroup = self.env.create_node_group(
                name='ng{0}'.format(i), api=False)
            nodegroups.append(nodegroup.id)
        cluster = self.env.create(
            cluster_kwargs={"api": False},
            nodes_kwargs=[
                {'group_id': None},
                {'group_id': None},
                {'group_id': nodegroups[0]},
                {'group_id': nodegroups[1]}
            ])
        cluster.nodes[0].group_id = None
        cluster.nodes[1].group_id = None
        self.db.flush()

        resp = self.app.get(
            reverse('NodeCollectionHandler'),
            params={'group_id': ''},
            headers=self.default_headers)

        self.assertEqual(200, resp.status_code)
        self.assertEqual(len(resp.json_body), 2)
        self.assertItemsEqual(
            [n['id'] for n in resp.json_body],
            [cluster.nodes[0].id, cluster.nodes[1].id, ])

    def test_node_get_by_wrong_group_id(self):
        wrong_group_id = 'wgid'

        resp = self.app.get(
            reverse('NodeCollectionHandler'),
            params={'group_id': wrong_group_id},
            headers=self.default_headers,
            expect_errors=True)

        self.assertEqual(400, resp.status_code)
        self.assertIn('Failed validating', resp.json_body['message'])
        self.assertIn(
            "'{0}' is not valid under any of the given schemas".format(
                wrong_group_id),
            resp.json_body['message'])

    def test_node_get_by_status(self):
        cluster = self.env.create(
            cluster_kwargs={"api": False},
            nodes_kwargs=[
                {'status': consts.NODE_STATUSES.discover},
                {'status': consts.NODE_STATUSES.discover},
                {'status': consts.NODE_STATUSES.removing},
                {'status': consts.NODE_STATUSES.provisioning}])

        resp = self.app.get(
            reverse('NodeCollectionHandler'),
            params={'status': consts.NODE_STATUSES.discover},
            headers=self.default_headers)

        self.assertEqual(200, resp.status_code)
        self.assertItemsEqual(
            [n['id'] for n in resp.json_body],
            [cluster.nodes[0].id, cluster.nodes[1].id, ])

    def test_node_get_by_none_status(self):
        resp = self.app.get(
            reverse('NodeCollectionHandler'),
            params={'status': None},
            headers=self.default_headers,
            expect_errors=True)

        self.assertEqual(400, resp.status_code)
        self.assertIn("'None' is not one of", resp.json_body['message'])
        self.assertIn('Failed validating', resp.json_body['message'])

    def test_node_get_by_wrong_status(self):
        wrong_status_value = 'wsv'

        resp = self.app.get(
            reverse('NodeCollectionHandler'),
            params={'status': wrong_status_value},
            headers=self.default_headers,
            expect_errors=True)

        self.assertEqual(400, resp.status_code)
        self.assertIn(
            "'{0}' is not one of".format(wrong_status_value),
            resp.json_body['message'])
        self.assertIn("Failed validating 'enum'", resp.json_body['message'])

    def test_node_get_offline(self):
        cluster = self.env.create(
            cluster_kwargs={"api": False},
            nodes_kwargs=[
                {'online': False},
                {'online': False},
                {'online': True},
                {'online': True}])

        resp = self.app.get(
            reverse('NodeCollectionHandler'),
            params={'online': False},
            headers=self.default_headers)

        self.assertEqual(200, resp.status_code)
        self.assertItemsEqual(
            [n['id'] for n in resp.json_body],
            [cluster.nodes[0].id, cluster.nodes[1].id, ])

    def test_node_get_online(self):
        cluster = self.env.create(
            cluster_kwargs={"api": False},
            nodes_kwargs=[
                {'online': True},
                {'online': True},
                {'online': False},
                {'online': False}])

        resp = self.app.get(
            reverse('NodeCollectionHandler'),
            params={'online': True},
            headers=self.default_headers)

        self.assertEqual(200, resp.status_code)
        self.assertItemsEqual(
            [n['id'] for n in resp.json_body],
            [cluster.nodes[0].id, cluster.nodes[1].id, ])

    def test_node_get_by_wrong_online_value(self):
        wrong_online_value = 'wrongvalue'

        resp = self.app.get(
            reverse('NodeCollectionHandler'),
            params={'online': 'wrongvalue'},
            headers=self.default_headers,
            expect_errors=True)

        self.assertEqual(400, resp.status_code)
        self.assertIn(
            "'{0}' is not of type 'boolean'".format(wrong_online_value),
            resp.json_body['message'])

    def test_node_get_by_roles(self):
        cluster = self.env.create(
            cluster_kwargs={"api": False},
            nodes_kwargs=[
                {'roles': ['controller', 'cinder', ]},
                {'roles': ['compute', 'cinder', ]},
                {'roles': ['base-os', 'compute', ]},
                {'roles': ['controller', ]}])

        resp = self.app.get(
            reverse('NodeCollectionHandler'),
            params={'roles': 'cinder'},
            headers=self.default_headers)

        self.assertEqual(200, resp.status_code)
        self.assertItemsEqual(
            [n['id'] for n in resp.json_body],
            [cluster.nodes[0].id, cluster.nodes[1].id, ])

    def test_node_get_by_several_roles(self):
        cluster = self.env.create(
            cluster_kwargs={"api": False},
            nodes_kwargs=[
                {'roles': ['controller', 'cinder', ]},
                {'roles': ['compute', 'cinder', ]},
                {'roles': ['base-os', 'compute']},
                {'roles': ['base-os']}])

        resp = self.app.get(
            reverse('NodeCollectionHandler'),
            params={'roles': ['controller', 'compute', ]},
            headers=self.default_headers)

        self.assertEqual(200, resp.status_code)
        self.assertItemsEqual(
            [n['id'] for n in resp.json_body],
            [cluster.nodes[0].id, cluster.nodes[1].id, cluster.nodes[2].id, ])

    def test_node_get_by_unexisting_role(self):
        self.env.create(
            cluster_kwargs={"api": False},
            nodes_kwargs=[
                {'roles': ['controller', 'cinder', ]},
                {'roles': ['compute', 'cinder', ]},
                {'roles': ['base-os', 'compute', ]},
                {'roles': ['base-os', ]}])

        resp = self.app.get(
            reverse('NodeCollectionHandler'),
            params={'roles': ['unexisting_role', ]},
            headers=self.default_headers)

        self.assertEqual(200, resp.status_code)
        self.assertEqual(0, len(resp.json_body))

    def test_node_get_by_wrong_input_data(self):
        cluster = self.env.create(
            cluster_kwargs={"api": False},
            nodes_kwargs=[
                {'status': consts.NODE_STATUSES.discover},
                {'status': consts.NODE_STATUSES.discover},
                {'status': consts.NODE_STATUSES.removing},
                {'status': consts.NODE_STATUSES.provisioning}])

        resp = self.app.get(
            reverse('NodeCollectionHandler'),
            params={'status': consts.NODE_STATUSES.discover,
                    'foo': 'bar',
                    '_': 'wrongparameter'},
            headers=self.default_headers)

        self.assertEqual(200, resp.status_code)
        self.assertItemsEqual(
            [n['id'] for n in resp.json_body],
            [cluster.nodes[0].id, cluster.nodes[1].id, ])

    def test_node_get_by_cluster_id_group_id_status_online_roles(self):
        cluster = self.env.create(
            cluster_kwargs={"api": False},
            nodes_kwargs=[
                {'status': consts.NODE_STATUSES.error,
                 'online': True,
                 'roles': ['controller', ]},
                {}, {}])

        resp = self.app.get(
            reverse('NodeCollectionHandler'),
            params={
                'cluster_id': cluster.id,
                'group_id': cluster.nodes[0].group_id,
                'status': consts.NODE_STATUSES.error,
                'online': True,
                'roles': ['controller', ]
            },
            headers=self.default_headers)

        self.assertEqual(200, resp.status_code)
        self.assertEqual(len(resp.json_body), 1)
        self.assertEqual(resp.json_body[0]['id'], cluster.nodes[0].id)
