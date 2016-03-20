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
import operator

from oslo_serialization import jsonutils
from six.moves import range
import unittest2

from nailgun import consts
from nailgun import objects
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import fake_tasks
from nailgun.utils import reverse


class TestVerifyNetworkTaskManagers(BaseIntegrationTest):

    def setUp(self):
        super(TestVerifyNetworkTaskManagers, self).setUp()

        meta1 = self.env.generate_interfaces_in_meta(2)
        meta2 = self.env.generate_interfaces_in_meta(2)

        mac1 = meta1['interfaces'][0]['mac']
        mac2 = meta2['interfaces'][0]['mac']

        self.env.create(
            cluster_kwargs={
                'net_provider': consts.CLUSTER_NET_PROVIDERS.neutron},
            nodes_kwargs=[
                {"api": True, "meta": meta1, "mac": mac1},
                {"api": True, "meta": meta2, "mac": mac2},
            ])
        self.cluster = self.env.clusters[0]

    @fake_tasks()
    def test_network_verify_task_managers_dhcp_on_master(self, _):
        task = self.env.launch_verify_networks()
        self.assertEqual(task.status, consts.TASK_STATUSES.ready)

    @fake_tasks()
    def test_network_verify_compares_received_with_cached(self, _):
        resp = self.env.neutron_networks_get(self.cluster.id)

        self.assertEqual(200, resp.status_code)
        nets = resp.json_body

        nets['networks'][-1]["vlan_start"] = 500
        task = self.env.launch_verify_networks(nets)
        self.assertEqual(task.status, consts.TASK_STATUSES.ready)

    @fake_tasks(fake_rpc=False)
    def test_network_verify_fails_if_admin_intersection(self, mocked_rpc):
        resp = self.env.neutron_networks_get(self.cluster.id)
        self.assertEqual(200, resp.status_code)
        nets = resp.json_body

        admin_ng = objects.NetworkGroup.get_admin_network_group()

        # find first non-admin network
        network = next((
            net for net in nets['networks']
            if net['name'] != consts.NETWORKS.fuelweb_admin),
            None)
        network['cidr'] = admin_ng.cidr

        task = self.env.launch_verify_networks(nets)
        self.assertEqual(task.status, consts.TASK_STATUSES.error)
        self.assertIn(
            "Address space intersection between networks:\n",
            task.message)
        self.assertIn("admin (PXE)", task.message)
        self.assertIn(network['name'], task.message)
        self.assertEqual(mocked_rpc.called, False)

    @fake_tasks(fake_rpc=False)
    def test_network_verify_fails_if_untagged_intersection(self, mocked_rpc):
        resp = self.env.neutron_networks_get(self.cluster.id)
        self.assertEqual(200, resp.status_code)
        nets = resp.json_body

        for net in nets['networks']:
            if net['name'] in ('storage',):
                net['vlan_start'] = None

        task = self.env.launch_verify_networks(nets)
        self.assertEqual(task.status, consts.TASK_STATUSES.error)
        self.assertIn(
            'Some untagged networks are assigned to the same physical '
            'interface. You should assign them to different physical '
            'interfaces. Affected:\n',
            task.message
        )
        for n in self.env.nodes:
            self.assertIn('"storage"', task.message)
        self.assertEqual(mocked_rpc.called, False)

    def check_verify_networks_less_than_2_online_nodes_error(self):
        resp = self.env.neutron_networks_get(self.cluster.id)
        nets = resp.json_body

        task = self.env.launch_verify_networks(nets)
        self.db.refresh(task)
        self.assertEqual(task.status, consts.TASK_STATUSES.error)
        error_msg = 'At least two online nodes are required to be in ' \
                    'the environment for network verification.'
        self.assertEqual(task.message, error_msg)

    @fake_tasks()
    def test_verify_networks_1_node_error(self, _):
        self.db.delete(self.env.nodes[0])
        self.db.flush()
        self.check_verify_networks_less_than_2_online_nodes_error()

    @fake_tasks()
    def test_verify_networks_1_online_node_error(self, _):
        self.env.nodes[0].online = False
        self.db.flush()
        self.check_verify_networks_less_than_2_online_nodes_error()

    @fake_tasks()
    def test_verify_networks_offline_nodes_notice(self, _):
        self.env.create_node(api=True,
                             cluster_id=self.cluster.id,
                             online=False)
        resp = self.env.neutron_networks_get(self.cluster.id)
        nets = resp.json_body

        task = self.env.launch_verify_networks(nets)
        self.assertEqual(task.cache['args']['offline'], 1)
        self.assertEqual(task.status, consts.TASK_STATUSES.ready)

        error_msg = 'Notice: 1 node(s) were offline during connectivity ' \
                    'check so they were skipped from the check.'
        self.assertEqual(task.message, error_msg)

    @fake_tasks()
    def test_network_verify_when_env_not_ready(self, _):
        cluster_db = self.env.clusters[0]
        blocking_statuses = (
            consts.CLUSTER_STATUSES.deployment,
        )
        for status in blocking_statuses:
            cluster_db.status = status
            self.db.flush()

            resp = self.env.neutron_networks_get(self.cluster.id)
            nets = resp.json_body

            task = self.env.launch_verify_networks(nets)
            self.assertEqual(task.status, consts.TASK_STATUSES.error)
            error_msg = (
                "Environment is not ready to run network verification "
                "because it is in '{0}' state.".format(status)
            )
            self.assertEqual(task.message, error_msg)

    @fake_tasks()
    def test_network_verify_if_old_task_is_running(self, _):
        resp = self.env.neutron_networks_get(self.cluster.id)
        nets = resp.body

        self.env.create_task(
            name="verify_networks",
            status=consts.TASK_STATUSES.running,
            cluster_id=self.cluster.id)

        resp = self.app.put(
            reverse(
                'NeutronNetworkConfigurationVerifyHandler',
                kwargs={'cluster_id': self.cluster.id}),
            nets,
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(400, resp.status_code)

    @unittest2.skip('Multicast is always disabled.')
    @fake_tasks(fake_rpc=False)
    def test_multicast_enabled_when_corosync_section_present(self, mocked_rpc):
        self.env.launch_verify_networks()
        self.assertIn('subtasks', mocked_rpc.call_args[0][1])
        subtasks = mocked_rpc.call_args[0][1]['subtasks']
        self.assertEqual(len(subtasks), 2)
        dhcp_subtask, multicast = subtasks[0], subtasks[1]
        self.assertEqual(dhcp_subtask['method'], 'check_dhcp')
        self.assertEqual(multicast['method'], 'multicast_verification')

    @unittest2.skip('Multicast is always disabled.')
    @fake_tasks(fake_rpc=False)
    def test_multicast_disabled_when_corosync_is_not_present(self, mocked_rpc):
        editable = copy.deepcopy(self.env.clusters[0].attributes.editable)
        del editable['corosync']
        self.env.clusters[0].attributes.editable = editable
        self.env.launch_verify_networks()
        self.assertIn('subtasks', mocked_rpc.call_args[0][1])
        subtasks = mocked_rpc.call_args[0][1]['subtasks']
        self.assertEqual(len(subtasks), 1)
        dhcp_subtask = subtasks[0]
        self.assertEqual(dhcp_subtask['method'], 'check_dhcp')


class TestVerifyNetworksDisabled(BaseIntegrationTest):

    def setUp(self):
        super(TestVerifyNetworksDisabled, self).setUp()
        meta = self.env.default_metadata()
        self.env.set_interfaces_in_meta(meta, [{
            "mac": "00:00:00:00:00:66",
            "max_speed": 1000,
            "name": "eth0",
            "current_speed": 1000
        }, {
            "mac": "00:00:00:00:00:77",
            "max_speed": 1000,
            "name": "eth1",
            "current_speed": None
        }, {
            "mac": "00:00:00:00:00:88",
            "max_speed": 1000,
            "name": "eth2",
            "current_speed": None}])
        self.env.create(
            cluster_kwargs={'status': consts.CLUSTER_STATUSES.operational,
                            'net_provider': 'neutron',
                            'net_segment_type': 'vlan'},
            nodes_kwargs=[
                {
                    'api': False,
                },
                {
                    'api': False,
                },
            ]
        )
        self.cluster = self.env.clusters[0]

    @fake_tasks()
    def test_network_verification_neutron_with_vlan_segmentation(self, _):
        task = self.env.launch_verify_networks()
        self.assertEqual(task.status, consts.TASK_STATUSES.ready)


class TestNetworkVerificationWithBonds(BaseIntegrationTest):

    def setUp(self):
        super(TestNetworkVerificationWithBonds, self).setUp()
        meta1 = self.env.default_metadata()
        meta2 = self.env.default_metadata()
        self.env.set_interfaces_in_meta(meta1, [
            {"name": "eth0", "mac": "00:00:00:00:00:66",
             "pxe": True},
            {"name": "eth1", "mac": "00:00:00:00:00:77"},
            {"name": "eth2", "mac": "00:00:00:00:00:88"}]
        )
        self.env.set_interfaces_in_meta(meta2, [
            {"name": "eth0", "mac": "00:00:00:00:11:66", "current_speed": 100,
             "pxe": True},
            {"name": "eth1", "mac": "00:00:00:00:22:77", "current_speed": 100},
            {"name": "eth2", "mac": "00:00:00:00:33:88", "current_speed": 100}]
        )
        self.env.create(
            cluster_kwargs={
                'net_provider': consts.CLUSTER_NET_PROVIDERS.neutron,
                'net_segment_type': 'gre'
            },
            nodes_kwargs=[
                {'api': True,
                 'pending_addition': True,
                 'meta': meta1},
                {'api': True,
                 'pending_addition': True,
                 'meta': meta2}
            ]
        )

        for node in self.env.nodes:
            data, admin_nic, other_nic, empty_nic = self.verify_nics(node)
            self.env.make_bond_via_api("ovs-bond0",
                                       consts.BOND_MODES.balance_slb,
                                       [other_nic["name"], empty_nic["name"]],
                                       node["id"])
            self.verify_bonds(node)

    def verify_nics(self, node):
        resp = self.app.get(
            reverse('NodeNICsHandler',
                    kwargs={'node_id': node['id']}),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)

        admin_nic, other_nic, empty_nic = None, None, None
        for nic in resp.json_body:
            net_names = [n['name'] for n in nic['assigned_networks']]
            if 'fuelweb_admin' in net_names:
                admin_nic = nic
            elif net_names:
                other_nic = nic
            else:
                empty_nic = nic
        self.assertTrue(admin_nic and other_nic and empty_nic)
        return resp.json_body, admin_nic, other_nic, empty_nic

    def verify_bonds(self, node):
        resp = self.env.node_nics_get(node["id"])
        self.assertEqual(resp.status_code, 200)

        bond = filter(lambda nic: nic["type"] ==
                      consts.NETWORK_INTERFACE_TYPES.bond,
                      resp.json_body)
        self.assertEqual(len(bond), 1)
        self.assertEqual(bond[0]["name"], "ovs-bond0")

    @property
    def expected_args(self):
        expected_networks = [
            {u'vlans': [0, 101, 102, 103], u'iface': u'eth0'},
            {u'vlans': [0], u'iface': u'eth1'},
            {u'vlans': [0], u'iface': u'eth2'}
        ]
        expected_bonds = {
            u'ovs-bond0': [u'eth1', u'eth2']
        }

        _expected_args = []
        for node in self.env.nodes:
            _expected_args.append({
                u'uid': node['id'],
                u'name': node['name'],
                u'status': node['status'],
                u'networks': expected_networks,
                u'bonds': expected_bonds,
                u'excluded_networks': []
            })

        return _expected_args

    @property
    def expected_args_deployed(self):
        expected_networks = [
            {u'vlans': [0, 101, 102, 103], u'iface': u'eth0'},
            {u'vlans': [0], u'iface': u'ovs-bond0'},
        ]

        _expected_args = []
        for node in self.env.nodes:
            _expected_args.append({
                u'uid': node['id'],
                u'name': node['name'],
                u'status': node['status'],
                u'networks': expected_networks,
                u'excluded_networks': []
            })

        return _expected_args

    @fake_tasks()
    def test_network_verification_neutron_with_bonds(self, _):
        task = self.env.launch_verify_networks()
        self.assertEqual(task.status, consts.TASK_STATUSES.ready)
        self.assertEqual(task.cache['args']['nodes'], self.expected_args)

    @fake_tasks()
    def test_network_verification_neutron_with_bonds_warn(self, _):
        resp = self.app.get(
            reverse(
                'NeutronNetworkConfigurationHandler',
                kwargs={'cluster_id': self.env.clusters[0].id}
            ),
            headers=self.default_headers
        )
        resp = self.app.put(
            reverse(
                'NeutronNetworkConfigurationVerifyHandler',
                kwargs={'cluster_id': self.env.clusters[0].id}),
            resp.body,
            headers=self.default_headers,
            expect_errors=True
        )
        # When run tasks synchronously, API returns 200 - task is finished
        self.assertEqual(200, resp.status_code)
        self.assertEqual(
            resp.json_body['result'],
            {u'warning': [u"Node '{0}': interface 'ovs-bond0' slave NICs have "
                          u"different or unrecognized speeds".format(
                              self.env.nodes[0].name)]})

    @fake_tasks()
    def test_network_verification_on_bootstrap_nodes_with_lacp_bonds(self, _):
        expected_task_args = []
        for node in self.env.nodes:
            # Bond interfaces with LACP
            for bond in node.bond_interfaces:
                bond.mode = consts.BOND_MODES.l_802_3ad
            expected_task_args.append({
                u'uid': node['id'],
                u'name': node['name'],
                u'status': node['status'],
                u'networks': [
                    {u'vlans': [0, 101, 102, 103], u'iface': u'eth0'}
                ],
                u'bonds': {u'ovs-bond0': [u'eth1', u'eth2']},
                u'excluded_networks': [
                    {u'iface': u'eth1'},
                    {u'iface': u'eth2'}
                ]
            })

        task = self.env.launch_verify_networks()
        self.assertEqual(task.status, consts.TASK_STATUSES.ready)
        self.assertEqual(task.cache['args']['nodes'], expected_task_args)

    @fake_tasks()
    def test_network_vcerification_on_deployed_nodes_with_lacp_bonds(self, _):
        for node in self.env.nodes:
            # Bond interfaces with LACP
            for bond in node.bond_interfaces:
                bond.mode = consts.BOND_MODES.l_802_3ad

        deployment_task = self.env.launch_deployment()
        self.assertEqual(deployment_task.status, consts.TASK_STATUSES.ready)

        verify_network_task = self.env.launch_verify_networks()
        self.assertEqual(
            verify_network_task.cache['args']['nodes'],
            self.expected_args_deployed
        )


class TestNetworkVerificationWithTemplates(BaseIntegrationTest):

    def setUp(self):
        super(TestNetworkVerificationWithTemplates, self).setUp()

    def create_env(self, net_type=consts.NEUTRON_SEGMENT_TYPES.vlan):
        meta1 = self.env.default_metadata()
        meta2 = self.env.default_metadata()
        meta3 = self.env.default_metadata()

        self.env.set_interfaces_in_meta(meta1, [
            {"name": "eth0", "mac": "00:00:00:00:00:66"},
            {"name": "eth1", "mac": "00:00:00:00:00:77"},
            {"name": "eth2", "mac": "00:00:00:00:00:88"},
            {"name": "eth3", "mac": "00:00:00:00:00:99"}]
        )
        self.env.set_interfaces_in_meta(meta2, [
            {"name": "eth0", "mac": "00:00:00:00:11:66"},
            {"name": "eth1", "mac": "00:00:00:00:11:77"},
            {"name": "eth2", "mac": "00:00:00:00:11:88"},
            {"name": "eth3", "mac": "00:00:00:00:11:99"}]
        )
        self.env.set_interfaces_in_meta(meta3, [
            {"name": "eth0", "mac": "00:00:00:00:22:66"},
            {"name": "eth1", "mac": "00:00:00:00:22:77"},
            {"name": "eth2", "mac": "00:00:00:00:22:88"},
            {"name": "eth3", "mac": "00:00:00:00:22:99"}]
        )
        self.cluster = self.env.create(
            release_kwargs={'version': 'liberty-8.0'},
            cluster_kwargs={
                'net_provider': consts.CLUSTER_NET_PROVIDERS.neutron,
                'net_segment_type': net_type,
            },
            nodes_kwargs=[{
                'api': True,
                'pending_addition': True,
                'meta': meta1,
                'roles': ['controller'],
            }, {
                'api': True,
                'pending_addition': True,
                'meta': meta2,
                'roles': ['compute', 'cinder'],
            }, {
                'api': True,
                'pending_addition': True,
                'meta': meta3,
                'roles': ['compute'],
            }]
        )

        template = self.env.read_fixtures(['network_template_80'])[0]
        template.pop('pk')
        self.upload_template(self.cluster['id'], template)

        if net_type == consts.NEUTRON_SEGMENT_TYPES.vlan:
            self.private_vlan_ids = list(range(1000, 1031))
        else:
            self.private_vlan_ids = []

    @property
    def expected_bonds(self):
        return [
            None,
            None,
            None,
        ]

    @property
    def expected_networks_on_undeployed_node(self):
        compute_networks = [
            {u'vlans': [0], u'iface': u'eth0'},
            {u'vlans': [104], u'iface': u'eth1'},
            {u'vlans': [0], u'iface': u'eth2'},
            {u'vlans': [101] + self.private_vlan_ids, u'iface': u'eth3'},
        ]

        return [
            [
                {u'vlans': [0], u'iface': u'eth0'},
                {u'vlans': [104], u'iface': u'eth1'},
            ],
            compute_networks,
            compute_networks,
        ]

    @property
    def expected_networks_on_deployed_node(self):
        compute_networks = [
            {u'vlans': [0], u'iface': u'eth0'},
            {u'vlans': [104], u'iface': u'eth1'},
            {u'vlans': [0], u'iface': u'eth2'},
            {u'vlans': [101] + self.private_vlan_ids,
             u'iface': u'eth3'},
        ]

        return [
            [
                {u'vlans': [0], u'iface': u'eth0'},
                {u'vlans': [104], u'iface': u'eth1'},
            ],
            compute_networks,
            compute_networks,
        ]

    def upload_template(self, cluster_id, template):
        resp = self.app.put(
            reverse(
                'TemplateNetworkConfigurationHandler',
                kwargs={'cluster_id': cluster_id},
            ),
            jsonutils.dumps(template),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(resp.status_code, 200)

    def verify_networks(self, expected_networks, expected_bonds=None):
        task = self.env.launch_verify_networks()

        for i, node in enumerate(task.cache['args']['nodes']):
            networks = sorted(node['networks'],
                              key=operator.itemgetter('iface'))
            self.assertEqual(
                networks, expected_networks[i])

            if expected_bonds and expected_bonds[i] is not None:
                self.assertEqual(node['bonds'], expected_bonds[i])

            if expected_bonds is None:
                self.assertNotIn('bonds', node)

    @fake_tasks()
    def test_get_ifaces_on_undeployed_node(self, _):
        self.create_env()
        self.verify_networks(
            self.expected_networks_on_undeployed_node,
            self.expected_bonds)

    @fake_tasks()
    def test_get_ifaces_on_deployed_node(self, _):
        self.create_env()
        deployment_task = self.env.launch_deployment()
        self.assertEqual(deployment_task.status, consts.TASK_STATUSES.ready)

        self.verify_networks(
            self.expected_networks_on_deployed_node)

    @fake_tasks()
    def test_get_ifaces_for_gre_network(self, _):
        self.create_env(consts.NEUTRON_SEGMENT_TYPES.gre)
        self.verify_networks(
            self.expected_networks_on_undeployed_node,
            self.expected_bonds)

    @fake_tasks()
    def test_get_ifaces_for_tun_network(self, _):
        self.create_env(consts.NEUTRON_SEGMENT_TYPES.tun)
        self.verify_networks(
            self.expected_networks_on_undeployed_node,
            self.expected_bonds)


class TestVerifyNovaFlatDHCP(BaseIntegrationTest):

    def setUp(self):
        super(TestVerifyNovaFlatDHCP, self).setUp()
        nodes_kwargs = []
        for role in ['controller', 'compute', 'cinder']:
            nodes_kwargs.append(
                {
                    'roles': [role],
                    'mac': self.env.generate_random_mac(),
                    'api': True,
                }
            )

        self.env.create(
            cluster_kwargs={
                'net_provider': consts.CLUSTER_NET_PROVIDERS.nova_network},
            nodes_kwargs=nodes_kwargs,
        )
        self.cluster = self.env.clusters[0]

    @fake_tasks()
    def test_flat_dhcp_verify(self, _):
        nets = self.env.nova_networks_get(self.cluster.id).json_body
        public = next(
            (net for net in nets['networks']
             if net['name'] == consts.NETWORKS.public))
        ip_range = ['172.16.0.35', '172.16.0.38']
        public['ip_ranges'] = [ip_range]
        public['meta']['ip_range'] = ip_range
        self.env.nova_networks_put(self.cluster.id, nets)

        resp = self.env.launch_verify_networks(expect_errors=True)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json_body['message'],
                         "Not enough free IP addresses in ranges "
                         "[172.16.0.35-172.16.0.38] of 'public' network")


class TestVerifyNeutronVlan(BaseIntegrationTest):

    def setUp(self):
        super(TestVerifyNeutronVlan, self).setUp()
        meta1 = self.env.default_metadata()
        meta2 = self.env.default_metadata()
        self.env.set_interfaces_in_meta(meta1, [
            {"name": "eth0", "mac": "00:00:00:00:00:66"},
            {"name": "eth1", "mac": "00:00:00:00:00:77"},
            {"name": "eth2", "mac": "00:00:00:00:00:88"}])
        self.env.set_interfaces_in_meta(meta2, [
            {"name": "eth0", "mac": "00:00:00:00:01:66"},
            {"name": "eth1", "mac": "00:00:00:00:01:77"},
            {"name": "eth2", "mac": "00:00:00:00:01:88"}])
        self.env.create(
            cluster_kwargs={
                'net_provider': consts.CLUSTER_NET_PROVIDERS.neutron,
                'net_segment_type': 'vlan'
            },
            nodes_kwargs=[
                {
                    'api': True,
                    'pending_addition': True,
                    'meta': meta1,
                    'roles': ['controller'],
                },
                {
                    'api': True,
                    'pending_addition': True,
                    'meta': meta2,
                    'roles': ['compute'],
                }]
        )

    @fake_tasks()
    def test_verify_networks_after_stop(self, _):
        cluster = self.env.clusters[0]
        deploy_task = self.env.launch_deployment()
        self.assertEqual(deploy_task.status, consts.TASK_STATUSES.ready)

        # FIXME(aroma): remove when stop action will be reworked for ha
        # cluster. To get more details, please, refer to [1]
        # [1]: https://bugs.launchpad.net/fuel/+bug/1529691
        objects.Cluster.set_deployed_before_flag(cluster, value=False)

        stop_task = self.env.stop_deployment()
        self.assertEqual(stop_task.status, consts.TASK_STATUSES.ready)
        self.db.refresh(cluster)
        self.assertEqual(cluster.status, consts.CLUSTER_STATUSES.stopped)
        # Moving nodes online by hands. Our fake threads do this with
        # random success
        for node in sorted(cluster.nodes, key=lambda n: n.id):
            node.online = True
        self.db.commit()
        verify_task = self.env.launch_verify_networks()
        self.assertEqual(verify_task.status, consts.TASK_STATUSES.ready)

    @fake_tasks(fake_rpc=False)
    def test_network_verification_neutron_with_vlan_segmentation(
            self, mocked_rpc):
        # get Neutron L2 VLAN ID range
        vlan_rng_be = self.env.clusters[0].network_config.vlan_range
        vlan_rng = set(range(vlan_rng_be[0], vlan_rng_be[1] + 1))

        # get nodes NICs for private network
        resp = self.app.get(reverse('NodeCollectionHandler'),
                            headers=self.default_headers)
        self.assertEqual(200, resp.status_code)
        priv_nics = {}
        for node in resp.json_body:
            for net in node['network_data']:
                if net['name'] == 'private':
                    priv_nics[node['id']] = net['dev']
                    break

        # check private VLAN range for nodes in Verify parameters
        task = self.env.launch_verify_networks()
        self.assertEqual(task.status, consts.TASK_STATUSES.running)
        for node in task.cache['args']['nodes']:
            for net in node['networks']:
                if net['iface'] == priv_nics[node['uid']]:
                    self.assertTrue(vlan_rng <= set(net['vlans']))
                    break

    @fake_tasks()
    def test_network_verification_parameters_w_one_node_having_public(self, _):
        # Decrease VLAN range and set public VLAN
        resp = self.env.neutron_networks_get(self.env.clusters[0].id)
        nets = resp.json_body
        nets['networking_parameters']['vlan_range'] = [1000, 1004]
        for net in nets['networks']:
            if net['name'] == consts.NETWORKS.public:
                net['vlan_start'] = 333
        resp = self.env.neutron_networks_put(self.env.clusters[0].id, nets)
        self.assertEqual(resp.status_code, 200)

        task = self.env.launch_verify_networks()
        self.assertEqual(task.status, consts.TASK_STATUSES.ready)
        # Public VLANs are not being checked on both nodes
        for n in range(2):
            self.assertEqual(
                task.cache['args']['nodes'][n]['networks'],
                [{'vlans': [0, 101, 102, 1000, 1001, 1002, 1003, 1004],
                  'iface': 'eth0'}])

    @fake_tasks()
    def test_network_verify_parameters_w_two_nodes_having_public(self, _):
        self.env.create_nodes_w_interfaces_count(
            nodes_count=1,
            if_count=3,
            api=True,
            pending_addition=True,
            roles=['controller'],
            cluster_id=self.env.clusters[0].id)
        # Decrease VLAN range and set public VLAN
        resp = self.env.neutron_networks_get(self.env.clusters[0].id)
        nets = resp.json_body
        nets['networking_parameters']['vlan_range'] = [1000, 1004]
        for net in nets['networks']:
            if net['name'] == consts.NETWORKS.public:
                net['vlan_start'] = 333
        resp = self.env.neutron_networks_put(self.env.clusters[0].id, nets)
        self.assertEqual(resp.status_code, 200)

        task = self.env.launch_verify_networks()
        self.assertEqual(task.status, consts.TASK_STATUSES.ready)
        eth0_vlans = {'iface': 'eth0',
                      'vlans': [0, 101, 102, 1000, 1001, 1002, 1003, 1004]}
        eth1_vlans = {'iface': 'eth1',
                      'vlans': [333]}
        # There is public VLAN on 1st controller node
        self.assertEqual(
            task.cache['args']['nodes'][0]['networks'],
            [eth0_vlans, eth1_vlans])
        # There is no public VLAN on compute node
        self.assertEqual(
            task.cache['args']['nodes'][1]['networks'],
            [eth0_vlans])
        # There is public VLAN on 2nd controller node
        self.assertEqual(
            task.cache['args']['nodes'][2]['networks'],
            [eth0_vlans, eth1_vlans])

    @fake_tasks()
    def test_repo_availability_tasks_are_created(self, _):
        task = self.env.launch_verify_networks()
        self.assertEqual(task.status, consts.TASK_STATUSES.ready)

        check_repo_tasks = filter(
            lambda t: t.name in (
                consts.TASK_NAMES.check_repo_availability,
                consts.TASK_NAMES.check_repo_availability_with_setup),
            task.subtasks)

        msg = "envs >= 6.1 must have check repo availability tasks"
        self.assertTrue(bool(check_repo_tasks), msg)

    @fake_tasks()
    def test_repo_availability_tasks_are_not_created(self, _):
        self.env.clusters[0].release.version = '2014.1-6.0'
        self.db.flush()

        task = self.env.launch_verify_networks()

        check_repo_tasks = filter(
            lambda t: t.name in (
                consts.TASK_NAMES.check_repo_availability,
                consts.TASK_NAMES.check_repo_availability_with_setup),
            task.subtasks)

        msg = "envs < 6.1 must not have check repo availability tasks"
        self.assertFalse(bool(check_repo_tasks), msg)
