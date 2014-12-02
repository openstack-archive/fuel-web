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


from nailgun import consts
from nailgun import objects

from nailgun.db.sqlalchemy.models import Node
from nailgun.openstack.common import jsonutils
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import fake_tasks
from nailgun.test.base import reverse


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
        self.assertEqual(resp.status_code, 204)

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

        # add node to environment: this makes us possible to reach
        # buggy code
        self.env.create(
            nodes_kwargs=[
                {'roles': ['controller'], 'pending_addition': True},
            ]
        )

        # prepare data to put
        node = self.env.nodes[0]
        node.meta['disks'] = []

        node = {
            'id': node.id,
            'meta': node.meta,
            'mac': node.mac,
            'status': node.status
        }

        # get node info
        before_count = get_notifications_count(node_id=node['id'])

        # put new info
        for i in range(5):
            response = self.app.put(
                reverse('NodeAgentHandler'),
                jsonutils.dumps(node),
                headers=self.default_headers
            )
            self.assertEqual(response.status_code, 200)

        # check there's not create notification
        after_count = get_notifications_count(node_id=node['id'])
        self.assertEqual(before_count, after_count)

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
                             'ip': ipaddress}),
            headers=self.default_headers)

        self.assertNotEqual(node.ip, ipaddress)

        ipaddress = '10.20.0.25'
        self.app.put(
            reverse('NodeAgentHandler'),
            jsonutils.dumps({'id': node.id,
                             'ip': ipaddress}),
            headers=self.default_headers)

        self.assertEqual(node.ip, ipaddress)

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
