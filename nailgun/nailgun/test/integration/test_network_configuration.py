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

from mock import patch

from oslo_serialization import jsonutils
from sqlalchemy.sql import not_

from nailgun import consts
from nailgun.db.sqlalchemy.models import Cluster
from nailgun.db.sqlalchemy.models import NetworkGroup
from nailgun.network.manager import NetworkManager
from nailgun.test.base import BaseIntegrationTest
from nailgun.utils import reverse


class TestNovaNetworkConfigurationHandlerMultinode(BaseIntegrationTest):
    def setUp(self):
        super(TestNovaNetworkConfigurationHandlerMultinode, self).setUp()
        cluster = self.env.create_cluster(api=True)
        self.cluster = self.db.query(Cluster).get(cluster['id'])

    def test_get_request_should_return_net_manager_and_networks(self):
        resp = self.env.nova_networks_get(self.cluster.id)
        data = resp.json_body
        cluster = self.db.query(Cluster).get(self.cluster.id)

        self.assertEqual(data['networking_parameters']['net_manager'],
                         self.cluster.network_config.net_manager)
        for network_group in cluster.network_groups:
            network = [i for i in data['networks']
                       if i['id'] == network_group.id][0]

            keys = [
                'name',
                'group_id',
                'vlan_start',
                'cidr',
                'id']

            for key in keys:
                self.assertEqual(network[key], getattr(network_group, key))

    def test_not_found_cluster(self):
        resp = self.env.nova_networks_get(self.cluster.id + 999,
                                          expect_errors=True)
        self.assertEqual(404, resp.status_code)

    def test_change_net_manager(self):
        self.assertEqual(self.cluster.network_config.net_manager,
                         'FlatDHCPManager')

        new_net_manager = {
            'networking_parameters': {'net_manager': 'VlanManager'}
        }
        self.env.nova_networks_put(self.cluster.id, new_net_manager)

        self.db.refresh(self.cluster)
        self.assertEqual(
            self.cluster.network_config.net_manager,
            new_net_manager['networking_parameters']['net_manager'])

    def test_change_dns_nameservers(self):
        new_dns_nameservers = {
            'networking_parameters': {
                'dns_nameservers': [
                    "208.67.222.222",
                    "208.67.220.220"
                ]
            }
        }
        self.env.nova_networks_put(self.cluster.id, new_dns_nameservers)

        self.db.refresh(self.cluster)
        self.assertEqual(
            self.cluster.network_config.dns_nameservers,
            new_dns_nameservers['networking_parameters']['dns_nameservers']
        )

    def test_refresh_mask_on_cidr_change(self):
        resp = self.env.nova_networks_get(self.cluster.id)
        data = resp.json_body

        mgmt = [n for n in data['networks']
                if n['name'] == 'management'][0]
        cidr = mgmt['cidr'].partition('/')[0] + '/25'
        mgmt['cidr'] = cidr

        resp = self.env.nova_networks_put(self.cluster.id, data)
        self.assertEqual(resp.status_code, 200)
        task = resp.json_body
        self.assertEqual(task['status'], consts.TASK_STATUSES.ready)

        self.db.refresh(self.cluster)
        mgmt_ng = [ng for ng in self.cluster.network_groups
                   if ng.name == 'management'][0]
        self.assertEqual(mgmt_ng.cidr, cidr)

    def test_wrong_net_provider(self):
        resp = self.app.put(
            reverse(
                'NeutronNetworkConfigurationHandler',
                kwargs={'cluster_id': self.cluster.id}),
            jsonutils.dumps({}),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(
            resp.json_body["message"],
            u"Wrong net provider - environment uses 'nova_network'"
        )

    def test_do_not_update_net_manager_if_validation_is_failed(self):
        new_net_manager = {
            'networking_parameters': {'net_manager': 'VlanManager'},
            'networks': [{'id': 500, 'vlan_start': 500}]
        }
        self.env.nova_networks_put(self.cluster.id, new_net_manager,
                                   expect_errors=True)

        self.db.refresh(self.cluster)
        self.assertNotEqual(
            self.cluster.network_config.net_manager,
            new_net_manager['networking_parameters']['net_manager'])

    def test_network_group_update_changes_network(self):
        network = self.db.query(NetworkGroup).filter(
            not_(NetworkGroup.name == consts.NETWORKS.fuelweb_admin)
        ).first()
        self.assertIsNotNone(network)
        new_vlan_id = 500  # non-used vlan id
        new_nets = {'networks': [{'id': network.id,
                                  'vlan_start': new_vlan_id}]}

        resp = self.env.nova_networks_put(self.cluster.id, new_nets)
        self.assertEqual(resp.status_code, 200)
        self.db.refresh(network)
        self.assertEqual(network.vlan_start, 500)

    def test_update_networks_and_net_manager(self):
        network = self.db.query(NetworkGroup).filter(
            not_(NetworkGroup.name == consts.NETWORKS.fuelweb_admin)
        ).first()
        new_vlan_id = 500  # non-used vlan id
        new_net = {'networking_parameters': {'net_manager': 'VlanManager'},
                   'networks': [{'id': network.id, 'vlan_start': new_vlan_id}]}
        self.env.nova_networks_put(self.cluster.id, new_net)

        self.db.refresh(self.cluster)
        self.db.refresh(network)
        self.assertEqual(
            self.cluster.network_config.net_manager,
            new_net['networking_parameters']['net_manager'])
        self.assertEqual(network.vlan_start, new_vlan_id)

    def test_networks_update_fails_with_wrong_net_id(self):
        new_nets = {'networks': [{'id': 500,
                                  'vlan_start': 500}]}

        resp = self.env.nova_networks_put(self.cluster.id, new_nets,
                                          expect_errors=True)
        self.assertEqual(200, resp.status_code)
        task = resp.json_body
        self.assertEqual(task['status'], consts.TASK_STATUSES.error)
        self.assertEqual(
            task['message'],
            'Invalid network ID: 500'
        )

    def test_admin_public_floating_untagged_others_tagged(self):
        resp = self.env.nova_networks_get(self.cluster.id)
        data = resp.json_body
        for net in data['networks']:
            if net['name'] in (consts.NETWORKS.fuelweb_admin,
                               consts.NETWORKS.public,
                               consts.NETWORKS.fixed):
                self.assertIsNone(net['vlan_start'])
            else:
                self.assertIsNotNone(net['vlan_start'])

    def test_mgmt_storage_networks_have_no_gateway(self):
        resp = self.env.nova_networks_get(self.cluster.id)
        self.assertEqual(200, resp.status_code)
        data = resp.json_body
        for net in data['networks']:
            if net['name'] in ['management', 'storage']:
                self.assertIsNone(net['gateway'])

    def test_management_network_has_gw(self):
        net_meta = self.env.get_default_networks_metadata().copy()
        mgmt = filter(lambda n: n['name'] == 'management',
                      net_meta['nova_network']['networks'])[0]
        mgmt['use_gateway'] = True
        mgmt['gateway'] = '192.168.0.1'

        cluster = self.env.create(
            cluster_kwargs={},
            release_kwargs={'networks_metadata': net_meta, 'api': False},
            nodes_kwargs=[{"pending_addition": True}]
        )

        resp = self.env.nova_networks_get(cluster['id'])
        data = resp.json_body
        mgmt = filter(lambda n: n['name'] == 'management',
                      data['networks'])[0]
        self.assertEqual(mgmt['gateway'], '192.168.0.1')
        strg = filter(lambda n: n['name'] == 'storage',
                      data['networks'])[0]
        self.assertIsNone(strg['gateway'])

    def test_management_network_gw_set_but_not_in_use(self):
        net_meta = self.env.get_default_networks_metadata().copy()
        mgmt = filter(lambda n: n['name'] == 'management',
                      net_meta['nova_network']['networks'])[0]
        mgmt['gateway'] = '192.168.0.1'
        self.assertEqual(mgmt['use_gateway'], False)

        cluster = self.env.create(
            cluster_kwargs={},
            release_kwargs={'networks_metadata': net_meta, 'api': False},
            nodes_kwargs=[{"pending_addition": True}]
        )

        resp = self.env.nova_networks_get(cluster['id'])
        data = resp.json_body
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
        resp = self.env.neutron_networks_get(self.cluster.id)
        data = resp.json_body
        cluster = self.db.query(Cluster).get(self.cluster.id)

        self.assertEqual(data['networking_parameters']['segmentation_type'],
                         self.cluster.network_config.segmentation_type)
        for network_group in cluster.network_groups:
            network = [i for i in data['networks']
                       if i['id'] == network_group.id][0]

            keys = [
                'name',
                'group_id',
                'vlan_start',
                'cidr',
                'id']

            for key in keys:
                self.assertEqual(network[key], getattr(network_group, key))

    def test_get_request_should_return_vips(self):
        resp = self.env.neutron_networks_get(self.cluster.id)
        data = resp.json_body

        self.assertIn('public_vip', data)
        self.assertIn('management_vip', data)

    def test_not_found_cluster(self):
        resp = self.env.neutron_networks_get(self.cluster.id + 999,
                                             expect_errors=True)
        self.assertEqual(404, resp.status_code)

    def test_refresh_mask_on_cidr_change(self):
        resp = self.env.neutron_networks_get(self.cluster.id)
        data = resp.json_body

        mgmt = [n for n in data['networks']
                if n['name'] == 'management'][0]
        cidr = mgmt['cidr'].partition('/')[0] + '/25'
        mgmt['cidr'] = cidr

        resp = self.env.neutron_networks_put(self.cluster.id, data)
        self.assertEqual(200, resp.status_code)
        task = resp.json_body
        self.assertEqual(task['status'], consts.TASK_STATUSES.ready)

        self.db.refresh(self.cluster)
        mgmt_ng = [ng for ng in self.cluster.network_groups
                   if ng.name == 'management'][0]
        self.assertEqual(mgmt_ng.cidr, cidr)

    def test_do_not_update_net_segmentation_type(self):
        resp = self.env.neutron_networks_get(self.cluster.id)
        data = resp.json_body
        data['networking_parameters']['segmentation_type'] = 'vlan'

        resp = self.env.neutron_networks_put(self.cluster.id, data,
                                             expect_errors=True)
        self.assertEqual(200, resp.status_code)
        task = resp.json_body
        self.assertEqual(task['status'], consts.TASK_STATUSES.error)
        self.assertEqual(
            task['message'],
            "Change of 'segmentation_type' is prohibited"
        )

    def test_network_group_update_changes_network(self):
        resp = self.env.neutron_networks_get(self.cluster.id)
        data = resp.json_body
        network = self.db.query(NetworkGroup).get(data['networks'][0]['id'])
        self.assertIsNotNone(network)

        data['networks'][0]['vlan_start'] = 500  # non-used vlan id

        resp = self.env.neutron_networks_put(self.cluster.id, data)
        self.assertEqual(resp.status_code, 200)

        self.db.refresh(network)
        self.assertEqual(network.vlan_start, 500)

    def test_update_networks_fails_if_change_net_segmentation_type(self):
        resp = self.env.neutron_networks_get(self.cluster.id)
        data = resp.json_body
        network = self.db.query(NetworkGroup).get(data['networks'][0]['id'])
        self.assertIsNotNone(network)

        data['networks'][0]['vlan_start'] = 500  # non-used vlan id
        data['networking_parameters']['segmentation_type'] = 'vlan'

        resp = self.env.neutron_networks_put(self.cluster.id, data,
                                             expect_errors=True)
        self.assertEqual(200, resp.status_code)
        task = resp.json_body
        self.assertEqual(task['status'], consts.TASK_STATUSES.error)
        self.assertEqual(
            task['message'],
            "Change of 'segmentation_type' is prohibited"
        )

    def test_networks_update_fails_with_wrong_net_id(self):
        new_nets = {'networks': [{'id': 500,
                                  'name': 'new',
                                  'vlan_start': 500}]}

        resp = self.env.neutron_networks_put(self.cluster.id, new_nets,
                                             expect_errors=True)
        self.assertEqual(200, resp.status_code)
        task = resp.json_body
        self.assertEqual(task['status'], consts.TASK_STATUSES.error)
        self.assertEqual(
            task['message'],
            'Invalid network ID: 500'
        )

    def test_refresh_public_cidr_on_its_change(self):
        data = self.env.neutron_networks_get(self.cluster.id).json_body
        publ = filter(lambda ng: ng['name'] == 'public', data['networks'])[0]
        self.assertEqual(publ['cidr'], '172.16.0.0/24')

        publ['cidr'] = '199.61.0.0/24'
        publ['gateway'] = '199.61.0.1'
        publ['ip_ranges'] = [['199.61.0.11', '199.61.0.33'],
                             ['199.61.0.55', '199.61.0.99']]
        data['networking_parameters']['floating_ranges'] = \
            [['199.61.0.111', '199.61.0.122']]

        resp = self.env.neutron_networks_put(self.cluster.id, data)
        self.assertEqual(200, resp.status_code)
        task = resp.json_body
        self.assertEqual(task['status'], consts.TASK_STATUSES.ready)

        self.db.refresh(self.cluster)
        publ_ng = filter(lambda ng: ng.name == 'public',
                         self.cluster.network_groups)[0]
        self.assertEqual(publ_ng.cidr, '199.61.0.0/24')

    def test_set_ip_range(self):
        ng_names = (consts.NETWORKS.management,
                    consts.NETWORKS.storage,
                    consts.NETWORKS.private)
        for idx, ng_name in enumerate(ng_names):
            data = self.env.neutron_networks_get(self.cluster.id).json_body
            ng_data = filter(lambda ng: ng['name'] == ng_name,
                             data['networks'])[0]

            net_template = '99.61.{0}'.format(idx)
            ng_data['cidr'] = net_template + '.0/24'
            ng_data['gateway'] = net_template + '.1'
            ng_data['meta']['notation'] = consts.NETWORK_NOTATION.ip_ranges
            ng_data['ip_ranges'] = [
                [net_template + '.11', net_template + '.33'],
                [net_template + '.55', net_template + '.99']]

            resp = self.env.neutron_networks_put(self.cluster.id, data)
            self.assertEqual(200, resp.status_code)
            task = resp.json_body
            self.assertEqual(task['status'], consts.TASK_STATUSES.ready)

            self.db.refresh(self.cluster)
            ng_db = filter(lambda ng: ng.name == ng_name,
                           self.cluster.network_groups)[0]
            self.assertEqual(ng_db.cidr, net_template + '.0/24')
            self.assertEqual(ng_db.meta['notation'], 'ip_ranges')
            self.assertEqual(ng_db.ip_ranges[0].first, net_template + '.11')
            self.assertEqual(ng_db.ip_ranges[0].last, net_template + '.33')
            self.assertEqual(ng_db.ip_ranges[1].first, net_template + '.55')
            self.assertEqual(ng_db.ip_ranges[1].last, net_template + '.99')

    def test_admin_public_untagged_others_tagged(self):
        resp = self.env.neutron_networks_get(self.cluster.id)
        data = resp.json_body
        for net in data['networks']:
            if net['name'] in ('fuelweb_admin', 'public',):
                self.assertIsNone(net['vlan_start'])
            else:
                self.assertIsNotNone(net['vlan_start'])

    def test_mgmt_storage_networks_have_no_gateway(self):
        resp = self.env.neutron_networks_get(self.cluster.id)
        self.assertEqual(200, resp.status_code)
        data = resp.json_body
        for net in data['networks']:
            if net['name'] in ['management', 'storage']:
                self.assertIsNone(net['gateway'])

    def test_management_network_has_gw(self):
        net_meta = self.env.get_default_networks_metadata().copy()
        mgmt = filter(lambda n: n['name'] == 'management',
                      net_meta['neutron']['networks'])[0]
        mgmt['use_gateway'] = True

        cluster = self.env.create(
            cluster_kwargs={'net_provider': 'neutron',
                            'net_segment_type': 'gre'},
            release_kwargs={'networks_metadata': net_meta, 'api': False},
            nodes_kwargs=[{"pending_addition": True}]
        )

        resp = self.env.neutron_networks_get(cluster['id'])
        data = resp.json_body
        mgmt = filter(lambda n: n['name'] == 'management',
                      data['networks'])[0]
        self.assertEqual(mgmt['gateway'], '192.168.0.1')
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
        resp = self.env.nova_networks_get(self.cluster.id).json_body

        self.assertEqual(
            resp['management_vip'],
            self.net_manager.assign_vip(self.cluster, 'management'))

        self.assertEqual(
            resp['public_vip'],
            self.net_manager.assign_vip(self.cluster, 'public'))


class TestAdminNetworkConfiguration(BaseIntegrationTest):

    @patch.dict('nailgun.db.sqlalchemy.fixman.settings.ADMIN_NETWORK', {
        "cidr": "192.168.0.0/24",
        "size": "256",
        "first": "192.168.0.129",
        "last": "192.168.0.254"
    })
    def setUp(self):
        super(TestAdminNetworkConfiguration, self).setUp()
        self.cluster = self.env.create(
            cluster_kwargs={
                "api": True
            },
            nodes_kwargs=[
                {"pending_addition": True, "api": True}
            ]
        )

    def test_netconfig_error_when_admin_cidr_match_other_network_cidr(self):
        resp = self.env.nova_networks_get(self.cluster['id'])
        nets = resp.json_body
        resp = self.env.nova_networks_put(self.cluster['id'], nets,
                                          expect_errors=True)
        self.assertEqual(resp.status_code, 200)
        task = resp.json_body
        self.assertEqual(task['status'], consts.TASK_STATUSES.error)
        self.assertEqual(task['progress'], 100)
        self.assertEqual(task['name'], 'check_networks')
        self.assertIn("Address space intersection between networks:\n"
                      "admin (PXE), management.",
                      task['message'])

    def test_deploy_error_when_admin_cidr_match_other_network_cidr(self):
        resp = self.env.cluster_changes_put(self.cluster['id'],
                                            expect_errors=True)
        self.assertEqual(resp.status_code, 200)
        task = resp.json_body
        self.assertEqual(task['status'], consts.TASK_STATUSES.error)
        self.assertEqual(task['progress'], 100)
        self.assertEqual(task['name'], 'deploy')
        self.assertIn("Address space intersection between networks:\n"
                      "admin (PXE), management.",
                      task['message'])
