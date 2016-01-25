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

import copy
import json
import six

from nailgun.api.v1.validators.node_group import NodeGroupValidator
from nailgun import consts
from nailgun.db import db
from nailgun.db.sqlalchemy import models
from nailgun.errors import errors
from nailgun import objects
from nailgun.test.base import BaseIntegrationTest
from nailgun.utils import reverse


class TestNodeGroups(BaseIntegrationTest):

    segmentation_type = consts.NEUTRON_SEGMENT_TYPES.gre

    def setUp(self):
        super(TestNodeGroups, self).setUp()
        self.cluster = self.env.create(
            release_kwargs={'version': '1111-8.0'},
            cluster_kwargs={
                'api': False,
                'net_provider': consts.CLUSTER_NET_PROVIDERS.neutron,
                'net_segment_type': self.segmentation_type
            }
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

        nets = db().query(models.NetworkGroup).filter_by(
            group_id=response['id'])
        self.assertEquals(nets.count(), 5)

    def _check_node_group_deleted(self, node_group_id):
        self.app.delete(
            reverse(
                'NodeGroupHandler',
                kwargs={'obj_id': node_group_id}
            ),
            headers=self.default_headers,
            expect_errors=False
        )

        node_group = db().query(models.NodeGroup).filter_by(
            id=node_group_id
        ).first()
        self.assertIsNone(node_group)

        nets = db().query(models.NetworkGroup).filter_by(
            group_id=node_group_id)
        self.assertEquals(nets.count(), 0)

    @patch('nailgun.task.task.rpc.cast')
    def test_nodegroup_deletion_without_nodes(self, _):
        resp = self.env.create_node_group()
        response = resp.json_body
        group_id = response['id']

        self._check_node_group_deleted(group_id)

    @patch('nailgun.task.task.rpc.cast')
    def test_node_group_deleted_with_neworks_in_bootstrap_only(self, _):
        node_group = self.env.create_node_group(api=False,
                                                cluster_id=self.cluster.id)
        self.env.create_nodes(2, group_id=node_group.id)
        self._check_node_group_deleted(node_group.id)

    def test_validate_delete_default_node_group_error(self):
        default_ng = objects.Cluster.get_default_group(self.cluster)

        with self.assertRaises(errors.CannotDelete) as err:
            NodeGroupValidator.validate_delete(data={}, instance=default_ng)

        self.assertEqual(err.exception.message,
                         'Default node group cannot be deleted.')

    def test_delete_non_default_node_group_error(self):
        node_group = self.env.create_node_group(api=False,
                                                cluster_id=self.cluster.id)
        self.env.create_node(group_id=node_group.id)
        self.env.create_node(group_id=node_group.id,
                             status=consts.NODE_STATUSES.error)

        with self.assertRaises(errors.CannotDelete) as err:
            NodeGroupValidator.validate_delete(data={}, instance=node_group)

        self.assertEqual(err.exception.message,
                         'Node group can be deleted only when all its nodes '
                         'are in bootstrap state.')

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

    def test_creation_not_allowed_when_ready_nodes(self):
        cluster = self.env.create(
            release_kwargs={'version': '1111-7.0'},
            nodes_kwargs=[{'status': consts.NODE_STATUSES.ready},
                          {'status': consts.NODE_STATUSES.error}]
        )
        resp = self.env.create_node_group(expect_errors=True,
                                          cluster_id=cluster['id'])
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json_body['message'],
                         "Reconfiguration of nodes after the "
                         "deployment is allowed only for "
                         "environments 8.0 or greater."
                         )

    def test_creation_allowed_when_ready_nodes_for_80(self):
        self.env.create_node(cluster_id=self.cluster['id'],
                             status=consts.NODE_STATUSES.ready)
        resp = self.env.create_node_group(cluster_id=self.cluster['id'])
        self.assertEqual(resp.status_code, 201)

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

    def test_validate_create_node_group_with_default_flag_fail(self):
        data = json.dumps(
            {'cluster_id': self.cluster['id'],
             'name': 'test',
             'is_default': True}
        )
        with self.assertRaises(errors.NotAllowed) as err:
            NodeGroupValidator.validate(data)

        self.assertEqual(
            err.exception.message,
            "Default node group is created only by Nailgun."
        )

    def test_validate_updating_node_group_default_flag_not_allowed(self):
        ng = objects.Cluster.get_default_group(self.cluster)

        data = json.dumps(
            {'cluster_id': self.cluster['id'],
             'name': ng.name,
             'is_default': not(ng.is_default)}
        )
        with self.assertRaises(errors.NotAllowed) as err:
            NodeGroupValidator.validate_update(data, ng)

        self.assertEqual(
            err.exception.message,
            "'default' flag for node group cannot be changed"
        )

    def test_validate_updating_cluster_id_not_allowed(self):
        ng = objects.Cluster.get_default_group(self.cluster)

        data = json.dumps({'cluster_id': -1, 'name': ng.name})
        with self.assertRaises(errors.NotAllowed) as err:
            NodeGroupValidator.validate_update(data, ng)

        self.assertEqual(
            err.exception.message,
            "Node group cannot be assigned to other cluster "
            "after creation."
        )

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

    def test_default_group_created_at_cluster_creation(self):
        self.env.create_cluster()
        cluster = self.env.clusters[0]
        self.assertTrue(cluster.node_groups[0].is_default)

    @patch('nailgun.task.task.rpc.cast')
    def test_net_config_is_valid_after_nodegroup_is_created(self, _):
        # API validator does not allow to setup networks w/o gateways when
        # cluster has multiple node groups. Since now, no additional actions
        # are required from user to get valid configuration after new node
        # group is created, i.e. this network configuration will pass through
        # the API validator.
        resp = self.env.create_node_group()
        self.assertEquals(resp.status_code, 201)

        config = self.env.neutron_networks_get(self.cluster.id).json_body
        resp = self.env.neutron_networks_put(self.cluster.id, config)
        self.assertEqual(resp.status_code, 200)

    def test_all_networks_have_gw_after_nodegroup_is_created(self):
        resp = self.env.create_node_group()
        self.assertEquals(resp.status_code, 201)

        for network in self.cluster.network_groups:
            if network.meta['notation'] is not None:
                self.assertTrue(network.meta['use_gateway'])
                self.assertIsNotNone(network.gateway)

    def test_intersecting_ip_deleted_after_nodegroup_is_created(self):
        net_roles = copy.copy(
            self.env.clusters[0].release.network_roles_metadata)
        net_roles.append({
            'id': 'stor/vip',
            'default_mapping': consts.NETWORKS.storage,
            'properties': {
                'subnet': True,
                'gateway': False,
                'vip': [{
                    'name': 'my-vip',
                    'node_roles': ['controller'],
                }]
            }})
        self.env.clusters[0].release.network_roles_metadata = net_roles
        self.db.flush()
        # VIPs are allocated on this call
        config = self.env.neutron_networks_get(self.cluster.id).json_body
        # Storage network has no GW by default
        vip_config = config['vips']['my-vip']['ipaddr']
        self.assertEqual(
            1,
            self.db.query(models.IPAddr).filter_by(ip_addr=vip_config).count()
        )

        resp = self.env.create_node_group()
        self.assertEquals(resp.status_code, 201)

        # VIP address was deleted
        self.assertEqual(
            0,
            self.db.query(models.IPAddr).filter_by(ip_addr=vip_config).count()
        )
        # Storage GW has this address now
        resp = self.env.neutron_networks_get(self.cluster.id)
        self.assertEquals(resp.status_code, 200)
        config = resp.json_body
        for net in config['networks']:
            if net['name'] == consts.NETWORKS.storage:
                self.assertEqual(vip_config, net['gateway'])
                break
        else:
            self.fail('No storage network found')
        # VIP is allocated to different address
        self.assertNotEqual(vip_config, config['vips']['my-vip']['ipaddr'])

    @patch('nailgun.task.task.rpc.cast')
    def test_ensure_gateways_present_cuts_ranges(self, _):
        # setup particular networks without gateways
        networks = {
            'public': {'cidr': '199.101.9.0/24',
                       'ip_ranges': [['199.101.9.1', '199.101.9.1'],
                                     ['199.101.9.5', '199.101.9.111']]},
            'management': {'cidr': '199.101.1.0/24'},
            'storage': {'cidr': '199.101.2.0/24'},
        }
        config = self.env.neutron_networks_get(self.cluster.id).json_body
        for net in config['networks']:
            if net['name'] in networks:
                for pkey, pval in six.iteritems(networks[net['name']]):
                    net[pkey] = pval
                net['meta']['use_gateway'] = False
        config['networking_parameters']['floating_ranges'] = [
            ['199.101.9.122', '199.101.9.233']]
        resp = self.env.neutron_networks_put(self.cluster.id, config)
        self.assertEquals(resp.status_code, 200)

        ranges_before = {
            'public': [['199.101.9.1', '199.101.9.1'],
                       ['199.101.9.5', '199.101.9.111']],
            'management': [['199.101.1.1', '199.101.1.254']],
            'storage': [['199.101.2.1', '199.101.2.254']],
        }
        config = self.env.neutron_networks_get(self.cluster.id).json_body
        for net in config['networks']:
            if net['name'] in networks:
                self.assertEqual(ranges_before[net['name']], net['ip_ranges'])

        objects.Cluster.get_network_manager(self.cluster).\
            ensure_gateways_present_in_default_node_group(self.cluster)

        ranges_after = {
            'public': [['199.101.9.5', '199.101.9.111']],
            'management': [['199.101.1.2', '199.101.1.254']],
            'storage': [['199.101.2.2', '199.101.2.254']],
        }
        config = self.env.neutron_networks_get(self.cluster.id).json_body
        for net in config['networks']:
            if net['name'] in networks:
                self.assertEqual(ranges_after[net['name']], net['ip_ranges'])

    def test_ensure_gateways_present_is_executed_once(self):
        with patch.object(
                objects.Cluster.get_network_manager(self.cluster),
                'ensure_gateways_present_in_default_node_group') as \
                ensure_mock:

            for n in range(2):
                resp = self.env.create_node_group(name='group{0}'.format(n))
                self.assertEquals(resp.status_code, 201)
                # one call is made when first custom node group is being added
                # no more calls after that
                self.assertEqual(
                    ensure_mock.call_count, 1,
                    'Method was called {0} time(s) unexpectedly, '
                    'current node group: {1}'.format(ensure_mock.call_count,
                                                     resp.json_body['name']))


class TestNodeGroupsVlan(TestNodeGroups):

    segmentation_type = consts.NEUTRON_SEGMENT_TYPES.vlan


class TestNodeGroupsTun(TestNodeGroups):

    segmentation_type = consts.NEUTRON_SEGMENT_TYPES.tun
