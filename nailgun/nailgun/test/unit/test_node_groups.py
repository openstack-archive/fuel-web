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

from mock import patch

import json

from nailgun import consts
from nailgun.db import db
from nailgun.db.sqlalchemy.models import NetworkGroup
from nailgun import objects
from nailgun.test.base import BaseIntegrationTest
from nailgun.utils import reverse


class TestNodeGroups(BaseIntegrationTest):

    def setUp(self):
        super(TestNodeGroups, self).setUp()
        self.cluster = self.env.create_cluster(
            api=False,
            net_provider=consts.CLUSTER_NET_PROVIDERS.neutron,
            net_segment_type=consts.NEUTRON_SEGMENT_TYPES.gre
        )

    def test_nodegroup_creation(self):
        self.assertEquals(
            objects.NodeGroupCollection.get_by_cluster_id(
                self.cluster['id']).count(),
            1
        )

        resp = self.env.create_node_group()
        self.assertEquals(resp.status_code, 201)
        self.assertEquals(resp.json_body['cluster_id'], self.cluster['id'])

        self.assertEquals(
            objects.NodeGroupCollection.get_by_cluster_id(
                self.cluster['id']).count(),
            2
        )
        admin_network = objects.NetworkGroup.get_from_node_group_by_name(
            resp.json_body['id'], consts.NETWORKS.fuelweb_admin)
        self.assertTrue(admin_network.meta['configurable'])

    def test_nodegroup_assignment(self):
        cluster = self.env.create(
            cluster_kwargs={
                'api': True,
                'net_provider': consts.CLUSTER_NET_PROVIDERS.neutron,
                'net_segment_type': consts.NEUTRON_SEGMENT_TYPES.gre
            },
            nodes_kwargs=[{
                'roles': [],
                'pending_roles': ['controller'],
                'pending_addition': True,
                'api': True}]
        )
        node = self.env.nodes[0]

        resp = self.env.create_node_group(cluster_id=cluster.get('id'))
        ng_id = resp.json_body['id']

        resp = self.app.put(
            reverse('NodeHandler', kwargs={'obj_id': node['id']}),
            json.dumps({'group_id': ng_id}),
            headers=self.default_headers,
            expect_errors=False
        )

        self.assertEquals(resp.status_code, 200)
        self.assertEquals(node.group_id, ng_id)

    def test_assign_invalid_nodegroup(self):
        node = self.env.create_node()
        invalid_ng_id = -1
        resp = self.app.put(
            reverse('NodeHandler', kwargs={'obj_id': node['id']}),
            json.dumps({'group_id': invalid_ng_id}),
            headers=self.default_headers,
            expect_errors=True
        )

        message = resp.json_body['message']
        self.assertEquals(resp.status_code, 400)
        self.assertRegexpMatches(message, 'Cannot assign node group')

    def test_nodegroup_create_network(self):
        resp = self.env.create_node_group()
        response = resp.json_body

        nets = db().query(NetworkGroup).filter_by(group_id=response['id'])
        self.assertEquals(nets.count(), 5)

    @patch('nailgun.task.task.rpc.cast')
    def test_nodegroup_deletion(self, _):
        resp = self.env.create_node_group()
        response = resp.json_body
        group_id = response['id']

        self.app.delete(
            reverse(
                'NodeGroupHandler',
                kwargs={'obj_id': group_id}
            ),
            headers=self.default_headers,
            expect_errors=False
        )

        nets = db().query(NetworkGroup).filter_by(group_id=response['id'])
        self.assertEquals(nets.count(), 0)

    def test_nodegroup_vlan_segmentation_type(self):
        cluster = self.env.create_cluster(
            api=False,
            net_provider=consts.CLUSTER_NET_PROVIDERS.neutron,
            net_segment_type=consts.NEUTRON_SEGMENT_TYPES.vlan
        )
        resp = self.app.post(
            reverse('NodeGroupCollectionHandler'),
            json.dumps({'cluster_id': cluster['id'], 'name': 'test_ng'}),
            headers=self.default_headers,
            expect_errors=False
        )
        self.assertEquals(resp.status_code, 201)
        self.assertEquals(resp.json_body['cluster_id'], cluster['id'])

        self.assertEquals(
            objects.NodeGroupCollection.get_by_cluster_id(
                self.cluster['id']).count(),
            1
        )

    def test_nodegroup_tun_segmentation_type(self):
        cluster = self.env.create_cluster(
            api=False,
            net_provider=consts.CLUSTER_NET_PROVIDERS.neutron,
            net_segment_type=consts.NEUTRON_SEGMENT_TYPES.tun
        )
        resp = self.app.post(
            reverse('NodeGroupCollectionHandler'),
            json.dumps({'cluster_id': cluster['id'], 'name': 'test_ng'}),
            headers=self.default_headers,
            expect_errors=True
        )

        self.assertEquals(resp.status_code, 201)
        self.assertEquals(resp.json_body['cluster_id'], cluster['id'])

    def test_nodegroup_invalid_net_provider(self):
        cluster = self.env.create_cluster(
            api=False,
            net_provider='nova_network',
        )
        resp = self.app.post(
            reverse('NodeGroupCollectionHandler'),
            json.dumps({'cluster_id': cluster['id'], 'name': 'test_ng'}),
            headers=self.default_headers,
            expect_errors=True
        )

        self.assertEquals(resp.status_code, 403)

    def test_nodegroup_invalid_cluster_id(self):
        resp = self.app.post(
            reverse('NodeGroupCollectionHandler'),
            json.dumps({'cluster_id': 0, 'name': 'test_ng'}),
            headers=self.default_headers,
            expect_errors=True
        )

        self.assertEquals(resp.status_code, 404)

    def test_nodegroup_create_duplication(self):
        self.assertEquals(
            objects.NodeGroupCollection.get_by_cluster_id(
                self.cluster['id']).count(), 1)

        resp = self.env.create_node_group()
        self.assertEquals(resp.status_code, 201)
        self.assertEquals(resp.json_body['cluster_id'], self.cluster['id'])

        msg = "Node group .*{0}.* already exists in environment {1}".format(
            resp.json_body['name'], self.cluster['id'])
        with self.assertRaisesRegexp(Exception, msg):
            self.env.create_node_group()

        self.assertEquals(
            objects.NodeGroupCollection.get_by_cluster_id(
                self.cluster['id']).count(), 2)

    def test_nodegroup_rename(self):
        self.assertEquals(
            1,
            objects.NodeGroupCollection.get_by_cluster_id(
                self.cluster['id']).count())

        resp = self.env.create_node_group(name='nodegroup_to_be_renamed')
        self.assertEquals(201, resp.status_code)
        self.assertEquals(self.cluster['id'], resp.json_body['cluster_id'])

        self.assertEquals(
            2,
            objects.NodeGroupCollection.get_by_cluster_id(
                self.cluster['id']).count())

        nodegroup_name = 'test_ng_renamed'
        resp = self.app.put(
            reverse(
                'NodeGroupHandler',
                kwargs={'obj_id': resp.json_body['id']}),
            json.dumps(
                {'cluster_id': self.cluster['id'], 'name': nodegroup_name}),
            headers=self.default_headers,
            expect_errors=False
        )

        self.assertEquals(200, resp.status_code)
        self.assertEquals(self.cluster['id'], resp.json_body['cluster_id'])
        self.assertEquals(
            2,
            objects.NodeGroupCollection.get_by_cluster_id(
                self.cluster['id']).count())
        self.assertEquals(
            1,
            objects.NodeGroupCollection.get_by_cluster_id(
                self.cluster['id']).filter_by(name=nodegroup_name).count())

    def test_nodegroup_rename_same_nodegroup_using_same_name(self):
        self.assertEquals(
            1,
            objects.NodeGroupCollection.get_by_cluster_id(
                self.cluster['id']).count())

        nodegroup_name = 'nodegroup_to_be_renamed'
        resp = self.env.create_node_group(name=nodegroup_name)
        self.assertEquals(201, resp.status_code)
        self.assertEquals(self.cluster['id'], resp.json_body['cluster_id'])

        self.assertEquals(
            2,
            objects.NodeGroupCollection.get_by_cluster_id(
                self.cluster['id']).count())

        resp = self.app.put(
            reverse(
                'NodeGroupHandler',
                kwargs={'obj_id': resp.json_body['id']}),
            json.dumps(
                {'cluster_id': self.cluster['id'], 'name': nodegroup_name}),
            headers=self.default_headers,
            expect_errors=False
        )

        self.assertEquals(200, resp.status_code)
        self.assertEquals(self.cluster['id'], resp.json_body['cluster_id'])
        self.assertEquals(
            2,
            objects.NodeGroupCollection.get_by_cluster_id(
                self.cluster['id']).count())
        self.assertEquals(
            1,
            objects.NodeGroupCollection.get_by_cluster_id(
                self.cluster['id']).filter_by(name=nodegroup_name).count())

    def test_nodegroup_rename_using_existing_name(self):

        self.assertEquals(
            1,
            objects.NodeGroupCollection.get_by_cluster_id(
                self.cluster['id']).count())

        nodegroup_name = 'test_ng'
        ng_resp = self.env.create_node_group(name=nodegroup_name)
        self.assertEquals(201, ng_resp.status_code)
        self.assertEquals(self.cluster['id'], ng_resp.json_body['cluster_id'])

        self.assertEquals(
            2,
            objects.NodeGroupCollection.get_by_cluster_id(
                self.cluster['id']).count())

        new_ng_resp = self.env.create_node_group(name='new_group')
        self.assertEquals(201, new_ng_resp.status_code)
        self.assertEquals(
            self.cluster['id'], new_ng_resp.json_body['cluster_id'])

        self.assertEquals(
            3,
            objects.NodeGroupCollection.get_by_cluster_id(
                self.cluster['id']).count())

        resp = self.app.put(
            reverse(
                'NodeGroupHandler',
                kwargs={'obj_id': new_ng_resp.json_body['id']}),
            json.dumps(
                {'cluster_id': self.cluster['id'],
                 'name': nodegroup_name}),
            headers=self.default_headers,
            expect_errors=True
        )

        self.assertEquals(403, resp.status_code)
        self.assertEquals(
            resp.json_body['message'],
            "Node group '{0}' already exists in environment {1}.".format(
                nodegroup_name, self.cluster['id']))

        self.assertEquals(
            1,
            objects.NodeGroupCollection.get_by_cluster_id(
                self.cluster['id']).filter_by(name=nodegroup_name).count())
        self.assertEquals(
            3,
            objects.NodeGroupCollection.get_by_cluster_id(
                self.cluster['id']).count())

    def test_assign_nodegroup_to_node_in_another_cluster(self):
        self.env.create(
            cluster_kwargs={
                'api': True,
                'net_provider': consts.CLUSTER_NET_PROVIDERS.neutron,
                'net_segment_type': consts.NEUTRON_SEGMENT_TYPES.gre
            },
            nodes_kwargs=[{
                'roles': [],
                'pending_roles': ['controller'],
                'pending_addition': True,
                'api': True}]
        )

        empty_cluster = self.env.create_cluster(
            net_provider=consts.CLUSTER_NET_PROVIDERS.neutron,
            net_segment_type=consts.NEUTRON_SEGMENT_TYPES.gre
        )
        node = self.env.nodes[0]

        resp = self.env.create_node_group(cluster_id=empty_cluster.get('id'))
        ng_id = resp.json_body['id']

        resp = self.app.put(
            reverse('NodeHandler', kwargs={'obj_id': node['id']}),
            json.dumps({'group_id': ng_id}),
            headers=self.default_headers,
            expect_errors=True
        )

        message = resp.json_body['message']
        self.assertEquals(resp.status_code, 400)
        self.assertRegexpMatches(message, 'Cannot assign node group')

    def test_assign_nodegroup_to_node_not_in_cluster(self):
        node = self.env.create_node()

        resp = self.env.create_node_group()
        ng_id = resp.json_body['id']

        resp = self.app.put(
            reverse('NodeHandler', kwargs={'obj_id': node['id']}),
            json.dumps({'group_id': ng_id}),
            headers=self.default_headers,
            expect_errors=True
        )

        message = resp.json_body['message']
        self.assertEquals(resp.status_code, 400)
        self.assertRegexpMatches(message, 'Cannot assign node group')

    def test_net_config_is_consistent_after_nodegroup_is_created(self):
        resp = self.env.create_node_group()
        self.assertEquals(resp.status_code, 201)

        config = self.env.neutron_networks_get(self.cluster.id).json_body
        resp = self.env.neutron_networks_put(self.cluster.id, config)
        self.assertEqual(resp.status_code, 200)
