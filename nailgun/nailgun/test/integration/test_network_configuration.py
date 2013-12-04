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

    def test_wrong_net_provider(self):
        resp = self.app.put(
            reverse(
                'NeutronNetworkConfigurationHandler',
                kwargs={'cluster_id': self.cluster.id}),
            json.dumps({}),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEquals(resp.status, 400)
        self.assertEquals(
            resp.body,
            u"Wrong net provider - environment uses 'nova_network'"
        )

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

    def test_admin_public_floating_untagged_others_tagged(self):
        resp = self.env.nova_networks_get(self.cluster.id)
        data = json.loads(resp.body)
        for net in data['networks']:
            if net['name'] in ('fuelweb_admin', 'public', 'floating'):
                self.assertIsNone(net['vlan_start'])
            else:
                self.assertIsNotNone(net['vlan_start'])

    def test_mgmt_storage_networks_have_no_gateway(self):
        resp = self.env.nova_networks_get(self.cluster.id)
        self.assertEquals(200, resp.status)
        data = json.loads(resp.body)
        for net in data['networks']:
            if net['name'] in ['management', 'storage']:
                self.assertIsNone(net['gateway'])

    def test_management_network_has_gw(self):
        net_meta = self.env.get_default_networks_metadata().copy()
        mgmt = filter(lambda n: n['name'] == 'management',
                      net_meta['nova_network']['networks'])[0]
        mgmt['use_gateway'] = True
        mgmt['gateway'] = '192.168.0.1'

        def get_new_networks_metadata():
            return net_meta

        self.env.get_default_networks_metadata = get_new_networks_metadata
        cluster = self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[{"pending_addition": True}]
        )

        resp = self.env.nova_networks_get(cluster['id'])
        data = json.loads(resp.body)
        mgmt = filter(lambda n: n['name'] == 'management',
                      data['networks'])[0]
        self.assertEquals(mgmt['gateway'], '192.168.0.1')
        strg = filter(lambda n: n['name'] == 'storage',
                      data['networks'])[0]
        self.assertIsNone(strg['gateway'])

    def test_management_network_gw_set_but_not_in_use(self):
        net_meta = self.env.get_default_networks_metadata().copy()
        mgmt = filter(lambda n: n['name'] == 'management',
                      net_meta['nova_network']['networks'])[0]
        mgmt['gateway'] = '192.168.0.1'
        self.assertEquals(mgmt['use_gateway'], False)

        def get_new_networks_metadata():
            return net_meta

        self.env.get_default_networks_metadata = get_new_networks_metadata
        cluster = self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[{"pending_addition": True}]
        )

        resp = self.env.nova_networks_get(cluster['id'])
        data = json.loads(resp.body)
        for n in data['networks']:
            if n['name'] in ('management', 'storage'):
                self.assertIsNone(n['gateway'])


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

        self.assertIn('public_vip', data)
        self.assertIn('management_vip', data)

    def test_not_found_cluster(self):
        resp = self.env.neutron_networks_get(self.cluster.id + 999,
                                             expect_errors=True)
        self.assertEquals(404, resp.status)

    def test_refresh_mask_on_cidr_change(self):
        response = self.env.neutron_networks_get(self.cluster.id)
        data = json.loads(response.body)

        mgmt = [n for n in data['networks']
                if n['name'] == 'management'][0]
        cidr = mgmt['cidr'].partition('/')[0] + '/25'
        mgmt['cidr'] = cidr
        mgmt['network_size'] = 128

        resp = self.env.neutron_networks_put(self.cluster.id, data)
        self.assertEquals(202, resp.status)
        task = json.loads(resp.body)
        self.assertEquals(task['status'], 'ready')

        self.db.refresh(self.cluster)
        mgmt_ng = [ng for ng in self.cluster.network_groups
                   if ng.name == 'management'][0]
        self.assertEquals(mgmt_ng.cidr, cidr)
        self.assertEquals(mgmt_ng.netmask, '255.255.255.128')

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

    def test_refresh_public_cidr_on_range_gw_change(self):
        data = json.loads(self.env.neutron_networks_get(self.cluster.id).body)
        publ = filter(lambda ng: ng['name'] == 'public', data['networks'])[0]
        self.assertEquals(publ['cidr'], '172.16.0.0/24')

        publ['gateway'] = '199.61.0.1'
        publ['ip_ranges'] = [['199.61.0.11', '199.61.0.33'],
                             ['199.61.0.55', '199.61.0.99']]
        virt_nets = data['neutron_parameters']['predefined_networks']
        virt_nets['net04_ext']['L3']['floating'] = ['199.61.0.111',
                                                    '199.61.0.122']

        resp = self.env.neutron_networks_put(self.cluster.id, data)
        self.assertEquals(202, resp.status)
        task = json.loads(resp.body)
        self.assertEquals(task['status'], 'ready')

        self.db.refresh(self.cluster)
        publ_ng = filter(lambda ng: ng.name == 'public',
                         self.cluster.network_groups)[0]
        self.assertEquals(publ_ng.cidr, '199.61.0.0/24')

    def test_refresh_public_cidr_on_netmask_change(self):
        data = json.loads(self.env.neutron_networks_get(self.cluster.id).body)
        publ = filter(lambda ng: ng['name'] == 'public', data['networks'])[0]
        self.assertEquals(publ['cidr'], '172.16.0.0/24')

        publ['netmask'] = '255.255.252.0'

        resp = self.env.neutron_networks_put(self.cluster.id, data)
        self.assertEquals(202, resp.status)
        task = json.loads(resp.body)
        self.assertEquals(task['status'], 'ready')

        self.db.refresh(self.cluster)
        publ_ng = filter(lambda ng: ng.name == 'public',
                         self.cluster.network_groups)[0]
        self.assertEquals(publ_ng.cidr, '172.16.0.0/22')

    def test_do_not_refresh_public_cidr_on_its_change(self):
        data = json.loads(self.env.neutron_networks_get(self.cluster.id).body)
        publ = filter(lambda ng: ng['name'] == 'public', data['networks'])[0]
        self.assertEquals(publ['cidr'], '172.16.0.0/24')

        publ['cidr'] = '199.61.39.160/28'

        # it is OK as public CIDR is ignored and nothing else is changed
        resp = self.env.neutron_networks_put(self.cluster.id, data)
        self.assertEquals(202, resp.status)
        task = json.loads(resp.body)
        self.assertEquals(task['status'], 'ready')

        self.db.refresh(self.cluster)
        publ_ng = filter(lambda ng: ng.name == 'public',
                         self.cluster.network_groups)[0]
        self.assertEquals(publ_ng.cidr, '172.16.0.0/24')

    def test_admin_public_untagged_others_tagged(self):
        resp = self.env.nova_networks_get(self.cluster.id)
        data = json.loads(resp.body)
        for net in data['networks']:
            if net['name'] in ('fuelweb_admin', 'public',):
                self.assertIsNone(net['vlan_start'])
            else:
                self.assertIsNotNone(net['vlan_start'])

    def test_mgmt_storage_networks_have_no_gateway(self):
        resp = self.env.neutron_networks_get(self.cluster.id)
        self.assertEquals(200, resp.status)
        data = json.loads(resp.body)
        for net in data['networks']:
            if net['name'] in ['management', 'storage']:
                self.assertIsNone(net['gateway'])

    def test_management_network_has_gw(self):
        net_meta = self.env.get_default_networks_metadata().copy()
        mgmt = filter(lambda n: n['name'] == 'management',
                      net_meta['neutron']['networks'])[0]
        mgmt['use_gateway'] = True

        def get_new_networks_metadata():
            return net_meta

        self.env.get_default_networks_metadata = get_new_networks_metadata
        cluster = self.env.create(
            cluster_kwargs={'net_provider': 'neutron',
                            'net_segment_type': 'gre'},
            nodes_kwargs=[{"pending_addition": True}]
        )

        resp = self.env.neutron_networks_get(cluster['id'])
        data = json.loads(resp.body)
        mgmt = filter(lambda n: n['name'] == 'management',
                      data['networks'])[0]
        self.assertEquals(mgmt['gateway'], '192.168.0.1')
        strg = filter(lambda n: n['name'] == 'storage',
                      data['networks'])[0]
        self.assertIsNone(strg['gateway'])


class TestNovaNetworkConfigurationHandlerHA(BaseIntegrationTest):
    def setUp(self):
        super(TestNovaNetworkConfigurationHandlerHA, self).setUp()
        cluster = self.env.create_cluster(api=True, mode='ha_compact')
        self.cluster = self.db.query(Cluster).get(cluster['id'])
        self.net_manager = NetworkManager

    def test_returns_management_vip_and_public_vip(self):
        resp = json.loads(self.env.nova_networks_get(self.cluster.id).body)

        self.assertEquals(
            resp['management_vip'],
            self.net_manager.assign_vip(self.cluster.id, 'management'))

        self.assertEquals(
            resp['public_vip'],
            self.net_manager.assign_vip(self.cluster.id, 'public'))
