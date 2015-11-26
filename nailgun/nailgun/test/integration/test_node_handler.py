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
            'meta': node.meta,
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
        self.env.wait_ready(deployment_task)

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

        nm = objects.Cluster.get_network_manager(node.cluster)
        admin_ng = nm.get_admin_network_group(node.id)
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


class TestNodeCollectionHandler(BaseIntegrationTest):

    def setUp(self):
        super(TestNodeCollectionHandler, self).setUp()
        self.cluster = self.env.create_cluster(
            api=False,
            net_provider=consts.CLUSTER_NET_PROVIDERS.neutron,
            net_segment_type=consts.NEUTRON_SEGMENT_TYPES.gre
        )

    def _compose_url(self, url, **kwargs):
        url += '?'
        for key, value in kwargs.items():
            url += '{0}={1}&'.format(key, str(value).lower())
        return url

    def test_node_get_by_cluster_id(self):
        cluster2 = self.env.create_cluster(api=False)
        node1 = self.env.create_node(cluster_id=cluster2.id)
        node2 = self.env.create_node(cluster_id=cluster2.id)
        self.env.create_node(cluster_id=self.cluster.id)
        self.env.create_node()
        node_ids = [node1['id'], node2['id'], ]

        resp = self.app.get(
            self._compose_url(
                reverse('NodeCollectionHandler'), cluster_id=cluster2.id),
            headers=self.default_headers)

        self.assertEqual(200, resp.status_code)
        self.assertEqual(len(resp.json_body), 2)
        response_node_ids = [n['id'] for n in resp.json_body]
        self.assertTrue(all([nid in response_node_ids for nid in node_ids]))

    def test_node_get_by_group_id(self):
        nodegroups = []
        for i in range(3):
            nodegroup = self.env.create_node_group(
                name='ng{0}'.format(i), api=False)
            nodegroups.append(nodegroup.id)
        node1 = self.env.create_node(group_id=nodegroups[0])
        node2 = self.env.create_node(group_id=nodegroups[0])
        self.env.create_node(group_id=nodegroups[1])
        self.env.create_node(group_id=nodegroups[2])
        node_ids = [node1['id'], node2['id'], ]

        resp = self.app.get(
            self._compose_url(
                reverse('NodeCollectionHandler'), group_id=nodegroups[0]),
            headers=self.default_headers)

        self.assertEqual(200, resp.status_code)
        self.assertEqual(len(resp.json_body), 2)
        response_node_ids = [n['id'] for n in resp.json_body]
        self.assertTrue(all([nid in response_node_ids for nid in node_ids]))

    def test_node_get_by_status(self):
        node1 = self.env.create_node(status=consts.NODE_STATUSES.discover)
        node2 = self.env.create_node(status=consts.NODE_STATUSES.discover)
        self.env.create_node(status=consts.NODE_STATUSES.removing)
        self.env.create_node(status=consts.NODE_STATUSES.provisioning)
        node_ids = [node1['id'], node2['id'], ]

        resp = self.app.get(
            self._compose_url(
                reverse('NodeCollectionHandler'),
                status=consts.NODE_STATUSES.discover),
            headers=self.default_headers)

        self.assertEqual(200, resp.status_code)
        self.assertEqual(len(resp.json_body), 2)
        response_node_ids = [n['id'] for n in resp.json_body]
        self.assertTrue(all([nid in response_node_ids for nid in node_ids]))

    def test_node_get_offline(self):
        node1 = self.env.create_node(online=False)
        node2 = self.env.create_node(online=False)
        self.env.create_node(online=True)
        self.env.create_node(online=True)
        node_ids = [node1['id'], node2['id'], ]

        resp = self.app.get(
            self._compose_url(
                reverse('NodeCollectionHandler'), online=False),
            headers=self.default_headers)

        self.assertEqual(200, resp.status_code)
        self.assertEqual(len(resp.json_body), 2)
        response_node_ids = [n['id'] for n in resp.json_body]
        self.assertTrue(all([nid in response_node_ids for nid in node_ids]))

    def test_node_get_online(self):
        node1 = self.env.create_node(online=True)
        node2 = self.env.create_node(online=True)
        self.env.create_node(online=False)
        self.env.create_node(online=False)
        node_ids = [node1['id'], node2['id'], ]

        resp = self.app.get(
            self._compose_url(
                reverse('NodeCollectionHandler'), online=True),
            headers=self.default_headers)

        self.assertEqual(200, resp.status_code)
        self.assertEqual(len(resp.json_body), 2)
        response_node_ids = [n['id'] for n in resp.json_body]
        self.assertTrue(all([nid in response_node_ids for nid in node_ids]))

    def test_node_get_by_roles(self):
        node1 = self.env.create_node(
            cluster_id=self.cluster.id, roles=['controller', 'cinder', ])
        node2 = self.env.create_node(
            cluster_id=self.cluster.id, roles=['compute', 'cinder', ])
        self.env.create_node(
            cluster_id=self.cluster.id, roles=['base-os', 'compute'])
        self.env.create_node(
            cluster_id=self.cluster.id, roles=['controller'])
        node_ids = [node1['id'], node2['id'], ]

        resp = self.app.get(
            self._compose_url(
                reverse('NodeCollectionHandler'), roles='cinder'),
            headers=self.default_headers)

        self.assertEqual(200, resp.status_code)
        self.assertEqual(len(resp.json_body), 2)
        response_node_ids = [n['id'] for n in resp.json_body]
        self.assertTrue(all([nid in response_node_ids for nid in node_ids]))

    def test_node_get_by_several_roles(self):
        node1 = self.env.create_node(
            cluster_id=self.cluster.id, roles=['controller', 'cinder', ])
        node2 = self.env.create_node(
            cluster_id=self.cluster.id, roles=['compute', 'cinder', ])
        node3 = self.env.create_node(
            cluster_id=self.cluster.id, roles=['base-os', 'compute', ])
        self.env.create_node(
            cluster_id=self.cluster.id, roles=['base-os', ])
        node_ids = [node1['id'], node2['id'], node3['id'], ]

        url = self._compose_url(reverse('NodeCollectionHandler'))
        url += 'roles={0}&roles={1}'.format('controller', 'compute')
        resp = self.app.get(url, headers=self.default_headers)

        self.assertEqual(200, resp.status_code)
        self.assertEqual(len(resp.json_body), 3)
        response_node_ids = [n['id'] for n in resp.json_body]
        self.assertTrue(all([nid in response_node_ids for nid in node_ids]))

    def test_node_get_by_unexisting_status(self):
        node1 = self.env.create_node(status=consts.NODE_STATUSES.discover)
        node2 = self.env.create_node(status=consts.NODE_STATUSES.discover)
        node3 = self.env.create_node(status=consts.NODE_STATUSES.removing)
        node4 = self.env.create_node(status=consts.NODE_STATUSES.provisioning)
        node_ids = [node1['id'], node2['id'], node3['id'], node4['id'], ]

        resp = self.app.get(
            self._compose_url(
                reverse('NodeCollectionHandler'), status='test'),
            headers=self.default_headers)

        self.assertEqual(200, resp.status_code)
        self.assertEqual(len(resp.json_body), 4)
        response_node_ids = [n['id'] for n in resp.json_body]
        self.assertTrue(all([nid in response_node_ids for nid in node_ids]))

    def test_node_get_by_cluster_id_group_id_status_online_roles(self):
        nodegroup = self.env.create_node_group(api=False)
        node = self.env.create_node(
            cluster_id=self.cluster.id,
            group_id=nodegroup.id,
            status=consts.NODE_STATUSES.discover,
            online=True,
            roles=['controller', ])
        self.env.create_node()
        self.env.create_node()

        resp = self.app.get(
            self._compose_url(
                reverse('NodeCollectionHandler'),
                cluster_id=self.cluster.id,
                group_id=nodegroup.id,
                status=consts.NODE_STATUSES.discover,
                online=True,
                roles='controller'),
            headers=self.default_headers)

        self.assertEqual(200, resp.status_code)
        self.assertEqual(len(resp.json_body), 1)
        self.assertEqual(resp.json_body[0]['id'], node.id)
