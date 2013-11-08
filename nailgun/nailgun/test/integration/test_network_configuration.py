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

from sqlalchemy.sql import not_

from nailgun.api.models import Cluster
from nailgun.api.models import NetworkGroup
from nailgun.network.manager import NetworkManager
from nailgun.test.base import BaseIntegrationTest


class TestNovaNetworkConfigurationHandlerMultinode(BaseIntegrationTest):
    def setUp(self):
        super(TestNovaNetworkConfigurationHandlerMultinode, self).setUp()
        cluster = self.env.create_cluster(api=True)
        self.cluster = self.db.query(Cluster).get(cluster['id'])

    def test_get_request_should_return_net_manager_and_networks(self):
        response = self.env.nova_networks_get(self.cluster.id)
        data = json.loads(response.body)
        cluster = self.db.query(Cluster).get(self.cluster.id)

        self.assertEquals(data['net_manager'], self.cluster.net_manager)
        for network_group in cluster.network_groups:
            network = [i for i in data['networks']
                       if i['id'] == network_group.id][0]

            keys = [
                'network_size',
                'name',
                'amount',
                'cluster_id',
                'vlan_start',
                'cidr',
                'id']

            for key in keys:
                self.assertEquals(network[key], getattr(network_group, key))

    def test_not_found_cluster(self):
        resp = self.env.nova_networks_get(self.cluster.id + 999,
                                          expect_errors=True)
        self.assertEquals(404, resp.status)

    def test_change_net_manager(self):
        new_net_manager = {'net_manager': 'VlanManager'}
        self.env.nova_networks_put(self.cluster.id, new_net_manager)

        self.db.refresh(self.cluster)
        self.assertEquals(
            self.cluster.net_manager,
            new_net_manager['net_manager'])

    def test_change_dns_nameservers(self):
        new_dns_nameservers = {
            'dns_nameservers': {
                "nameservers": [
                    "208.67.222.222",
                    "208.67.220.220"
                ]
            }
        }
        self.env.nova_networks_put(self.cluster.id, new_dns_nameservers)

        self.db.refresh(self.cluster)
        self.assertEquals(
            self.cluster.dns_nameservers,
            new_dns_nameservers['dns_nameservers']['nameservers']
        )

    def test_refresh_mask_on_cidr_change(self):
        response = self.env.nova_networks_get(self.cluster.id)
        data = json.loads(response.body)

        mgmt = [n for n in data['networks']
                if n['name'] == 'management'][0]
        cidr = mgmt['cidr'].partition('/')[0] + '/25'
        mgmt['cidr'] = cidr
        mgmt['network_size'] = 128

        resp = self.env.nova_networks_put(self.cluster.id, data)
        self.assertEquals(resp.status, 202)
        task = json.loads(resp.body)
        self.assertEquals(task['status'], 'ready')

        self.db.refresh(self.cluster)
        mgmt_ng = [ng for ng in self.cluster.network_groups
                   if ng.name == 'management'][0]
        self.assertEquals(mgmt_ng.cidr, cidr)
        self.assertEquals(mgmt_ng.netmask, '255.255.255.128')

    def test_do_not_update_net_manager_if_validation_is_failed(self):
        new_net_manager = {'net_manager': 'VlanManager',
                           'networks': [{'id': 500, 'vlan_start': 500}]}
        self.env.nova_networks_put(self.cluster.id, new_net_manager,
                                   expect_errors=True)

        self.db.refresh(self.cluster)
        self.assertNotEquals(
            self.cluster.net_manager,
            new_net_manager['net_manager'])

    def test_network_group_update_changes_network(self):
        network = self.db.query(NetworkGroup).filter(
            not_(NetworkGroup.name == "fuelweb_admin")
        ).first()
        self.assertIsNotNone(network)
        new_vlan_id = 500  # non-used vlan id
        new_nets = {'networks': [{'id': network.id,
                                  'vlan_start': new_vlan_id}]}

        resp = self.env.nova_networks_put(self.cluster.id, new_nets)
        self.assertEquals(resp.status, 202)
        self.db.refresh(network)
        self.assertEquals(len(network.networks), 1)
        self.assertEquals(network.networks[0].vlan_id, 500)

    def test_update_networks_and_net_manager(self):
        network = self.db.query(NetworkGroup).filter(
            not_(NetworkGroup.name == "fuelweb_admin")
        ).first()
        new_vlan_id = 500  # non-used vlan id
        new_net = {'net_manager': 'VlanManager',
                   'networks': [{'id': network.id, 'vlan_start': new_vlan_id}]}
        self.env.nova_networks_put(self.cluster.id, new_net)

        self.db.refresh(self.cluster)
        self.db.refresh(network)
        self.assertEquals(
            self.cluster.net_manager,
            new_net['net_manager'])
        self.assertEquals(network.networks[0].vlan_id, new_vlan_id)

    def test_networks_update_fails_with_wrong_net_id(self):
        new_nets = {'networks': [{'id': 500,
                                  'vlan_start': 500}]}

        resp = self.env.nova_networks_put(self.cluster.id, new_nets,
                                          expect_errors=True)
        self.assertEquals(202, resp.status)
        task = json.loads(resp.body)
        self.assertEquals(task['status'], 'error')
        self.assertEquals(
            task['message'],
            'Invalid network ID: 500'
        )


class TestNeutronNetworkConfigurationHandlerMultinode(BaseIntegrationTest):
    def setUp(self):
        super(TestNeutronNetworkConfigurationHandlerMultinode, self).setUp()
        cluster = self.env.create_cluster(api=True,
                                          net_provider='neutron',
                                          net_segment_type='gre',
                                          mode='ha_compact'
                                          )
        self.cluster = self.db.query(Cluster).get(cluster['id'])

    def test_get_request_should_return_net_provider_segment_and_networks(self):
        response = self.env.neutron_networks_get(self.cluster.id)
        data = json.loads(response.body)
        cluster = self.db.query(Cluster).get(self.cluster.id)

        self.assertEquals(data['net_provider'],
                          self.cluster.net_provider)
        self.assertEquals(data['net_segment_type'],
                          self.cluster.net_segment_type)
        for network_group in cluster.network_groups:
            network = [i for i in data['networks']
                       if i['id'] == network_group.id][0]

            keys = [
                'network_size',
                'name',
                'amount',
                'cluster_id',
                'vlan_start',
                'cidr',
                'id']

            for key in keys:
                self.assertEquals(network[key], getattr(network_group, key))

    def test_get_request_should_return_vips(self):
        response = self.env.neutron_networks_get(self.cluster.id)
        data = json.loads(response.body)

        self.assertIn('management_vip', data)
        self.assertIn('storage_vip', data)
        self.assertIn('public_vip', data)

    def test_not_found_cluster(self):
        resp = self.env.neutron_networks_get(self.cluster.id + 999,
                                             expect_errors=True)
        self.assertEquals(404, resp.status)

    def test_refresh_mask_on_cidr_change(self):
        response = self.env.neutron_networks_get(self.cluster.id)
        data = json.loads(response.body)

        publ = [n for n in data['networks']
                if n['name'] == 'public'][0]
        cidr = publ['cidr'].partition('/')[0] + '/23'
        publ['cidr'] = cidr

        resp = self.env.neutron_networks_put(self.cluster.id, data)
        self.assertEquals(202, resp.status)
        task = json.loads(resp.body)
        self.assertEquals(task['status'], 'ready')

        self.db.refresh(self.cluster)
        publ_ng = [ng for ng in self.cluster.network_groups
                   if ng.name == 'public'][0]
        self.assertEquals(publ_ng.cidr, cidr)
        self.assertEquals(publ_ng.netmask, '255.255.254.0')

    def test_do_not_update_net_segmentation_type(self):
        resp = self.env.neutron_networks_get(self.cluster.id)
        data = json.loads(resp.body)
        data['neutron_parameters']['segmentation_type'] = 'vlan'

        resp = self.env.neutron_networks_put(self.cluster.id, data,
                                             expect_errors=True)
        self.assertEquals(202, resp.status)
        task = json.loads(resp.body)
        self.assertEquals(task['status'], 'error')
        self.assertEquals(
            task['message'],
            "Change of 'segmentation_type' is prohibited"
        )

    def test_network_group_update_changes_network(self):
        resp = self.env.neutron_networks_get(self.cluster.id)
        data = json.loads(resp.body)
        network = self.db.query(NetworkGroup).get(data['networks'][0]['id'])
        self.assertIsNotNone(network)

        data['networks'][0]['vlan_start'] = 500  # non-used vlan id

        resp = self.env.neutron_networks_put(self.cluster.id, data)
        self.assertEquals(resp.status, 202)

        self.db.refresh(network)
        self.assertEquals(len(network.networks), 1)
        self.assertEquals(network.networks[0].vlan_id, 500)

    def test_update_networks_fails_if_change_net_segmentation_type(self):
        resp = self.env.neutron_networks_get(self.cluster.id)
        data = json.loads(resp.body)
        network = self.db.query(NetworkGroup).get(data['networks'][0]['id'])
        self.assertIsNotNone(network)

        data['networks'][0]['vlan_start'] = 500  # non-used vlan id
        data['neutron_parameters']['segmentation_type'] = 'vlan'

        resp = self.env.neutron_networks_put(self.cluster.id, data,
                                             expect_errors=True)
        self.assertEquals(202, resp.status)
        task = json.loads(resp.body)
        self.assertEquals(task['status'], 'error')
        self.assertEquals(
            task['message'],
            "Change of 'segmentation_type' is prohibited"
        )

    def test_networks_update_fails_with_wrong_net_id(self):
        new_nets = {'networks': [{'id': 500,
                                  'name': 'new',
                                  'vlan_start': 500}]}

        resp = self.env.neutron_networks_put(self.cluster.id, new_nets,
                                             expect_errors=True)
        self.assertEquals(202, resp.status)
        task = json.loads(resp.body)
        self.assertEquals(task['status'], 'error')
        self.assertEquals(
            task['message'],
            'Invalid network ID: 500'
        )


class TestNovaNetworkConfigurationHandlerHA(BaseIntegrationTest):
    def setUp(self):
        super(TestNovaNetworkConfigurationHandlerHA, self).setUp()
        cluster = self.env.create_cluster(api=True, mode='ha_compact')
        self.cluster = self.db.query(Cluster).get(cluster['id'])
        self.net_manager = NetworkManager()

    def test_returns_management_vip_and_public_vip(self):
        resp = json.loads(self.env.nova_networks_get(self.cluster.id).body)

        self.assertEquals(
            resp['management_vip'],
            self.net_manager.assign_vip(self.cluster.id, 'management'))

        self.assertEquals(
            resp['public_vip'],
            self.net_manager.assign_vip(self.cluster.id, 'public'))
