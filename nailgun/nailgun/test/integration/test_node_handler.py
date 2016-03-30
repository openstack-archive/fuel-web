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

import copy

import netaddr
from oslo_serialization import jsonutils

from nailgun import consts
from nailgun import objects

from nailgun.db.sqlalchemy.models import Node
from nailgun.db.sqlalchemy.models import Notification
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import fake_tasks
from nailgun.utils import reverse


class TestHandlers(BaseIntegrationTest):

    def test_node_get(self):
        node = self.env.create_node(api=False)
        resp = self.app.get(
            reverse('NodeHandler', kwargs={'obj_id': node.id}),
            headers=self.default_headers)
        self.assertEqual(200, resp.status_code)
        self.assertEqual(node.id, resp.json_body['id'])
        self.assertEqual(node.name, resp.json_body['name'])
        self.assertEqual(node.mac, resp.json_body['mac'])
        self.assertEqual(
            node.pending_addition, resp.json_body['pending_addition'])
        self.assertEqual(
            node.pending_deletion, resp.json_body['pending_deletion'])
        self.assertEqual(node.status, resp.json_body['status'])
        self.assertEqual(
            node.meta['cpu']['total'],
            resp.json_body['meta']['cpu']['total']
        )
        self.assertEqual(node.meta['disks'], resp.json_body['meta']['disks'])
        self.assertEqual(node.meta['memory'], resp.json_body['meta']['memory'])

    def test_node_creation_fails_with_wrong_id(self):
        node_id = '080000000003'
        resp = self.app.post(
            reverse('NodeCollectionHandler'),
            jsonutils.dumps({'id': node_id,
                             'mac': self.env.generate_random_mac(),
                             'status': 'discover'}),
            headers=self.default_headers,
            expect_errors=True)
        self.assertEqual(400, resp.status_code)

    def test_node_deletion(self):
        node = self.env.create_node(api=False)
        resp = self.app.delete(
            reverse('NodeHandler', kwargs={'obj_id': node.id}),
            "",
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(resp.status_code, 200)

    def test_node_valid_metadata_gets_updated(self):
        new_metadata = self.env.default_metadata()
        node = self.env.create_node(api=False)
        resp = self.app.put(
            reverse('NodeHandler', kwargs={'obj_id': node.id}),
            jsonutils.dumps({'meta': new_metadata}),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)
        self.db.refresh(node)

        nodes = self.db.query(Node).filter(
            Node.id == node.id
        ).all()
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0].meta, new_metadata)

    def test_node_hostname_gets_updated(self):
        node = self.env.create_node(api=False)
        resp = self.app.put(
            reverse('NodeHandler', kwargs={'obj_id': node.id}),
            jsonutils.dumps({'hostname': 'new-name'}),
            headers=self.default_headers)
        self.assertEqual(200, resp.status_code)
        self.db.refresh(node)
        # lets put the same hostname again
        resp = self.app.put(
            reverse('NodeHandler', kwargs={'obj_id': node.id}),
            jsonutils.dumps({'hostname': 'new-name'}),
            headers=self.default_headers)
        self.assertEqual(200, resp.status_code)
        self.db.refresh(node)

        nodes = self.db.query(Node).filter(
            Node.id == node.id
        ).all()
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0].hostname, 'new-name')

    def test_node_hostname_gets_updated_invalid(self):
        node = self.env.create_node(api=False)
        resp = self.app.put(
            reverse('NodeHandler', kwargs={'obj_id': node.id}),
            jsonutils.dumps({'hostname': '!#invalid_%&name'}),
            headers=self.default_headers,
            expect_errors=True)
        self.assertEqual(400, resp.status_code)

    def test_node_hostname_gets_updated_ssl_conflict(self):
        cluster = self.env.create_cluster(api=False)
        node = self.env.create_node(cluster_id=cluster.id)

        cluster_attrs = objects.Cluster.get_editable_attributes(cluster)
        test_hostname = 'test-hostname'
        cluster_attrs['public_ssl']['hostname']['value'] = test_hostname
        objects.Cluster.update_attributes(
            cluster, {'editable': cluster_attrs})

        resp = self.app.put(
            reverse('NodeHandler', kwargs={'obj_id': node.id}),
            jsonutils.dumps({'hostname': test_hostname}),
            headers=self.default_headers,
            expect_errors=True)
        self.assertEqual(400, resp.status_code)
        self.assertEqual(
            "New hostname '{0}' conflicts with public TLS endpoint"
            .format(test_hostname), resp.json_body['message'])

    def test_node_hostname_gets_updated_after_provisioning_starts(self):
        node = self.env.create_node(api=False,
                                    status=consts.NODE_STATUSES.provisioning)
        resp = self.app.put(
            reverse('NodeHandler', kwargs={'obj_id': node.id}),
            jsonutils.dumps({'hostname': 'new-name'}),
            headers=self.default_headers,
            expect_errors=True)
        self.assertEqual(403, resp.status_code)
        self.assertEqual(
            'Node hostname may be changed only before provisioning.',
            resp.json_body['message'])

    def test_node_hostname_gets_updated_duplicate(self):
        node = self.env.create_node(api=False)

        resp = self.app.put(
            reverse('NodeHandler', kwargs={'obj_id': node.id}),
            jsonutils.dumps({'hostname': 'new-name'}),
            headers=self.default_headers)
        self.assertEqual(200, resp.status_code)
        self.db.refresh(node)

        node_2 = self.env.create_node(api=False)

        resp = self.app.put(
            reverse('NodeHandler', kwargs={'obj_id': node_2.id}),
            jsonutils.dumps({'hostname': 'new-name'}),
            headers=self.default_headers,
            expect_errors=True)
        self.assertEqual(409, resp.status_code)

    def test_node_valid_status_gets_updated(self):
        node = self.env.create_node(api=False)
        params = {'status': 'error'}
        resp = self.app.put(
            reverse('NodeHandler', kwargs={'obj_id': node.id}),
            jsonutils.dumps(params),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)

    def test_node_action_flags_are_set(self):
        flags = ['pending_addition', 'pending_deletion']
        node = self.env.create_node(api=False)
        for flag in flags:
            resp = self.app.put(
                reverse('NodeHandler', kwargs={'obj_id': node.id}),
                jsonutils.dumps({flag: True}),
                headers=self.default_headers
            )
            self.assertEqual(resp.status_code, 200)
        self.db.refresh(node)

        node_from_db = self.db.query(Node).filter(
            Node.id == node.id
        ).first()
        for flag in flags:
            self.assertEqual(getattr(node_from_db, flag), True)

    def test_put_returns_400_if_no_body(self):
        node = self.env.create_node(api=False)
        resp = self.app.put(
            reverse('NodeHandler', kwargs={'obj_id': node.id}),
            "",
            headers=self.default_headers,
            expect_errors=True)
        self.assertEqual(resp.status_code, 400)

    def test_put_returns_400_if_wrong_status(self):
        node = self.env.create_node(api=False)
        params = {'status': 'invalid_status'}
        resp = self.app.put(
            reverse('NodeHandler', kwargs={'obj_id': node.id}),
            jsonutils.dumps(params),
            headers=self.default_headers,
            expect_errors=True)
        self.assertEqual(resp.status_code, 400)

    def test_do_not_create_notification_if_disks_meta_is_empty(self):

        def get_notifications_count(**kwargs):
            return objects.NotificationCollection.count(
                objects.NotificationCollection.filter_by(None, **kwargs)
            )

        self.env.create(
            nodes_kwargs=[
                {'roles': ['controller'], 'pending_addition': True},
            ]
        )

        node = self.env.nodes[0]
        node.meta['disks'] = []
        node = {
            'id': node.id,
            'meta': node.meta,
            'mac': node.mac,
            'status': node.status
        }

        before_count = get_notifications_count(node_id=node['id'])

        for i in range(5):
            response = self.app.put(
                reverse('NodeAgentHandler'),
                jsonutils.dumps(node),
                headers=self.default_headers
            )
            self.assertEqual(response.status_code, 200)

        # check there's no notification created
        after_count = get_notifications_count(node_id=node['id'])
        self.assertEqual(before_count, after_count)

    def test_no_volumes_changes_if_node_is_locked(self):

        self.env.create(
            nodes_kwargs=[
                {'roles': ['controller'], 'pending_addition': True,
                 'status': consts.NODE_STATUSES.ready},
            ]
        )

        node = self.env.nodes[0]
        node_data = {
            'id': node.id,
            'meta': copy.deepcopy(node.meta),
            'mac': node.mac,
            'status': node.status
        }
        node_data['meta']['disks'] = []

        response = self.app.put(
            reverse('NodeAgentHandler'),
            jsonutils.dumps(node_data),
            headers=self.default_headers
        )
        self.assertEqual(response.status_code, 200)
        # check volumes data wasn't reset
        self.assertGreater(len(node.meta['disks']), 0)

    @fake_tasks()
    def test_interface_changes_for_new_node(self):
        # Creating cluster with node
        self.env.create(
            cluster_kwargs={
                'name': 'test_name'
            },
            nodes_kwargs=[
                {'roles': ['controller'], 'pending_addition': True}
            ]
        )
        cluster = self.env.clusters[0]

        def filter_changes(chg_type, chg_list):
            return filter(lambda x: x.get('name') == chg_type, chg_list)

        changes = filter_changes(
            consts.CLUSTER_CHANGES.interfaces,
            cluster['changes']
        )
        # Checking interfaces change added after node creation
        self.assertEquals(1, len(changes))

        deployment_task = self.env.launch_deployment()
        self.assertEqual(deployment_task.status, consts.TASK_STATUSES.ready)

        changes = filter_changes(
            consts.CLUSTER_CHANGES.interfaces,
            cluster['changes']
        )
        # Checking no interfaces change after deployment
        self.assertEquals(0, len(changes))

    def test_update_node_with_wrong_ip(self):
        node = self.env.create_node(
            api=False, ip='10.20.0.2',
            status=consts.NODE_STATUSES.deploying)

        ipaddress = '192.168.0.10'
        self.app.put(
            reverse('NodeAgentHandler'),
            jsonutils.dumps({'id': node.id,
                             'ip': ipaddress,
                             'status': consts.NODE_STATUSES.discover}),
            headers=self.default_headers)

        self.assertEqual(node.ip, ipaddress)
        self.assertEqual(node.status, consts.NODE_STATUSES.error)
        notif = self.db.query(Notification).filter_by(
            node_id=node.id,
            topic='error'
        ).first()
        self.assertRegexpMatches(notif.message,
                                 "that does not match any Admin network")

        admin_ng = objects.NetworkGroup.get_admin_network_group(node)
        ipaddress = str(netaddr.IPRange(admin_ng.ip_ranges[0].first,
                                        admin_ng.ip_ranges[0].last)[1])
        self.app.put(
            reverse('NodeAgentHandler'),
            jsonutils.dumps({'id': node.id,
                             'ip': ipaddress}),
            headers=self.default_headers)

        self.assertEqual(node.ip, ipaddress)
        self.assertEqual(node.status, consts.NODE_STATUSES.discover)

    def test_update_node_with_none_ip(self):
        node = self.env.create_node(api=False, ip='10.20.0.2')

        ipaddress = None
        resp = self.app.put(
            reverse('NodeAgentHandler'),
            jsonutils.dumps({'id': node.id,
                             'ip': ipaddress}),
            headers=self.default_headers,
            expect_errors=True)
        self.assertEqual(resp.status_code, 400)

        ipaddress = '10.20.0.4'
        resp = self.app.put(
            reverse('NodeAgentHandler'),
            jsonutils.dumps({'id': node.id,
                             'ip': ipaddress}),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)

    def test_do_not_update_interfaces_on_incorrect_ip(self):
        self.env.create(
            nodes_kwargs=[
                {'api': False, 'status': consts.NODE_STATUSES.ready},
            ])
        node = self.env.nodes[0]
        node.interfaces[1].ip_addr = '172.16.0.2'   # set public net ip

        # get node representation
        resp = self.app.get(
            reverse('NodeHandler', kwargs={'obj_id': node.id}),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)
        node_json = resp.json

        # deployed nodes have ip=null and pxe=false
        for iface in node_json['meta']['interfaces']:
            iface.pop('ip', None)
            iface['pxe'] = False

        # pick not-admin interface, and pass its ip & mac on node level
        node_json.update({
            'ip': node.interfaces[1].ip_addr,
            'mac': node.interfaces[1].mac,
        })
        resp = self.app.put(
            reverse('NodeAgentHandler'),
            jsonutils.dumps(node_json),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)

        # check that nothing is broken: admin network isn't jumped to
        # another interface
        self.assertIsNotNone(
            next((net for net in node.interfaces[0].assigned_networks
                 if net['name'] == consts.NETWORKS.fuelweb_admin), None))
        self.assertIsNone(
            next((net for net in node.interfaces[1].assigned_networks
                 if net['name'] == consts.NETWORKS.fuelweb_admin), None))

    def test_get_node_attributes(self):
        node = self.env.create_node(api=False)
        fake_attributes = {
            'group1': {
                'metadata': {},
                'comp1': {
                    'value': 42
                }
            }
        }
        node.attributes.update(fake_attributes)
        resp = self.app.get(
            reverse('NodeAttributesHandler', kwargs={'node_id': node.id}),
            headers=self.default_headers)
        self.assertEqual(200, resp.status_code)
        self.assertEqual(fake_attributes, resp.json_body)

    def test_put_node_attributes(self):
        node = self.env.create_node(api=False)
        fake_attributes = {
            'group1': {
                'metadata': {},
                'comp1': {
                    'type': 'text',
                    'value': '42'
                }
            },
            'group2': {
                'comp2': {
                    'type': 'text',
                    'value': 'value1'
                }
            },
            'cpu_pinning': {},
            'hugepages': {
                'comp1': {
                    'type': 'text',
                    'value': '1',
                },
            },
        }
        node.attributes.update(fake_attributes)
        update_attributes = {
            'group1': {
                'comp1': {
                    'type': 'text',
                    'value': '41'
                }
            }
        }
        resp = self.app.put(
            reverse('NodeAttributesHandler', kwargs={'node_id': node.id}),
            jsonutils.dumps(update_attributes),
            headers=self.default_headers)

        fake_attributes['group1']['comp1']['value'] = '41'
        self.assertEqual(200, resp.status_code)
        self.assertEqual(fake_attributes, resp.json_body)
