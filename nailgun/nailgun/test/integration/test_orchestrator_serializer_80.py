# -*- coding: utf-8 -*-

#    Copyright 2015 Mirantis, Inc.
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

from copy import deepcopy
import mock
import six

import nailgun

from nailgun import consts
from nailgun.db.sqlalchemy import models
from nailgun import objects
from nailgun import rpc

from nailgun.orchestrator.deployment_graph import AstuteGraph
from nailgun.orchestrator.deployment_serializers import \
    get_serializer_for_cluster
from nailgun.orchestrator.neutron_serializers import \
    NeutronNetworkDeploymentSerializer80
from nailgun.orchestrator.neutron_serializers import \
    NeutronNetworkTemplateSerializer80
from nailgun.test.integration.test_orchestrator_serializer import \
    BaseDeploymentSerializer
from nailgun.test.integration.test_orchestrator_serializer import \
    TestSerializeInterfaceDriversData
from nailgun.test.integration.test_orchestrator_serializer_70 import \
    TestDeploymentHASerializer70


class TestSerializer80Mixin(object):
    env_version = "liberty-8.0"
    task_deploy = False

    def _check_baremetal_neutron_attrs(self, cluster):
        self.env._set_additional_component(cluster, 'ironic', True)
        self.env.create_node(cluster_id=cluster.id,
                             roles=['controller'])
        objects.Cluster.prepare_for_deployment(cluster)
        serialized_for_astute = self.serializer.serialize(
            cluster, cluster.nodes)
        for node in serialized_for_astute:
            expected_network = {
                "network_type": "flat",
                "segment_id": None,
                "router_ext": False,
                "physnet": "physnet-ironic"
            }
            self.assertEqual(expected_network, node['quantum_settings']
                             ['predefined_networks']['baremetal']['L2'])
            self.assertIn("physnet-ironic",
                          node['quantum_settings']['L2']['phys_nets'])
            self.assertEqual(consts.DEFAULT_BRIDGES_NAMES.br_ironic,
                             (node['quantum_settings']['L2']['phys_nets']
                              ["physnet-ironic"]["bridge"]))


class TestNetworkTemplateSerializer80(
    TestSerializer80Mixin,
    BaseDeploymentSerializer
):
    env_version = 'liberty-8.0'
    legacy_serializer = NeutronNetworkDeploymentSerializer80
    template_serializer = NeutronNetworkTemplateSerializer80

    def setUp(self, *args):
        super(TestNetworkTemplateSerializer80, self).setUp()
        self.env.create(
            release_kwargs={'version': self.env_version},
            cluster_kwargs={
                'mode': consts.CLUSTER_MODES.ha_compact,
                'net_provider': consts.CLUSTER_NET_PROVIDERS.neutron,
                'net_segment_type': consts.NEUTRON_SEGMENT_TYPES.vlan})
        self.net_template = self.env.read_fixtures(['network_template_80'])[0]
        self.cluster = self.env.clusters[-1]

    def test_get_net_provider_serializer(self):
        serializer = get_serializer_for_cluster(self.cluster)
        self.cluster.network_config.configuration_template = None

        net_serializer = serializer.get_net_provider_serializer(self.cluster)
        self.assertIs(net_serializer, self.legacy_serializer)

        self.cluster.network_config.configuration_template = \
            self.net_template
        net_serializer = serializer.get_net_provider_serializer(self.cluster)
        self.assertIs(net_serializer, self.template_serializer)

    def test_baremetal_neutron_attrs(self):
        brmtl_template = deepcopy(
            self.net_template['adv_net_template']['default'])
        brmtl_template['network_assignments']['baremetal'] = {
            'ep': 'br-baremetal'}
        brmtl_template['templates_for_node_role']['controller'].append(
            'baremetal')
        brmtl_template['nic_mapping']['default']['if8'] = 'eth7'
        brmtl_template['network_scheme']['baremetal'] = {
            'endpoints': ['br-baremetal'],
            'transformations': [],
            'roles': {'baremetal': 'br-baremetal'}}
        self.cluster.network_config.configuration_template = {
            'adv_net_template': {'default': brmtl_template}, 'pk': 1}
        serializer_type = get_serializer_for_cluster(self.cluster)
        self.serializer = serializer_type(AstuteGraph(self.cluster))
        self._check_baremetal_neutron_attrs(self.cluster)

    def test_network_schemes_priorities(self):
        expected = [
            {
                "action": "add-br",
                "name": "br-prv",
                "provider": "ovs"
            },
            {
                "action": "add-br",
                "name": "br-aux"
            },
            {
                "action": "add-patch",
                "bridges": [
                    "br-prv",
                    "br-aux"
                ],
                "provider": "ovs",
                "mtu": 65000
            },
            {
                "action": "add-port",
                "bridge": "br-aux",
                "name": "eth3.101"
            },
            {
                "action": "add-br",
                "name": "br-fw-admin"
            },
            {
                "action": "add-port",
                "bridge": "br-fw-admin",
                "name": "eth0"
            },
            {
                "action": "add-br",
                "name": "br-mgmt"
            },
            {
                "action": "add-port",
                "bridge": "br-mgmt",
                "name": "eth1.104"
            },
            {
                "action": "add-br",
                "name": "br-storage"
            },
            {
                "action": "add-port",
                "bridge": "br-storage",
                "name": "eth2"
            }
        ]

        objects.Cluster.set_network_template(
            self.cluster,
            self.net_template
        )

        node = self.env.create_nodes_w_interfaces_count(
            1, 8, roles=['compute', 'cinder'],
            cluster_id=self.cluster.id
        )[0]

        serializer = get_serializer_for_cluster(self.cluster)
        net_serializer = serializer.get_net_provider_serializer(self.cluster)

        nm = objects.Cluster.get_network_manager(self.cluster)
        network_scheme = net_serializer.generate_network_scheme(
            node, nm.get_node_networks(node))
        self.assertEqual(expected, network_scheme['transformations'])


class TestDeploymentTasksSerialization80(
    TestSerializer80Mixin,
    BaseDeploymentSerializer
):
    tasks_for_rerun = {"globals", "netconfig"}

    def setUp(self):
        super(TestDeploymentTasksSerialization80, self).setUp()
        self.env.create(
            release_kwargs={'version': self.env_version},
            cluster_kwargs={
                'mode': consts.CLUSTER_MODES.ha_compact,
                'net_provider': consts.CLUSTER_NET_PROVIDERS.neutron,
                'net_segment_type': consts.NEUTRON_SEGMENT_TYPES.vlan,
                'status': consts.CLUSTER_STATUSES.operational},
            nodes_kwargs=[
                {'roles': ['controller'],
                 'status': consts.NODE_STATUSES.ready}]
        )

        self.cluster = self.env.clusters[-1]
        if not self.task_deploy:
            self.env.disable_task_deploy(self.cluster)

    def add_node(self, role):
        return self.env.create_node(
            cluster_id=self.cluster.id,
            pending_roles=[role],
            pending_addition=True
        )

    def get_rpc_args(self):
        self.env.launch_deployment()
        args, kwargs = nailgun.task.manager.rpc.cast.call_args
        return args[1][1]['args']

    def check_add_compute_for_task_deploy(self, new_node_uid, rpc_message):
        tasks_graph = rpc_message['tasks_graph']
        for node_id, tasks in six.iteritems(tasks_graph):
            if node_id is None:
                # skip virtual node
                continue

            task_ids = {
                t['id'] for t in tasks
                if t['type'] != consts.ORCHESTRATOR_TASK_TYPES.skipped
            }
            if node_id == new_node_uid:
                # all tasks are run on a new node
                self.assertTrue(
                    self.tasks_for_rerun.issubset(task_ids))
            else:
                # only selected tasks are run on a deployed node
                self.assertEqual(self.tasks_for_rerun, task_ids)

    def check_add_compute_for_granular_deploy(self, new_node_uid, rpc_message):
        for node in rpc_message['deployment_info']:
            task_ids = {t['id'] for t in node['tasks']}
            if node['tasks'][0]['uids'] == [new_node_uid]:
                # all tasks are run on a new node
                self.assertTrue(
                    self.tasks_for_rerun.issubset(task_ids))
            else:
                # only selected tasks are run on a deployed node
                self.assertItemsEqual(self.tasks_for_rerun, task_ids)

    def check_add_controller_for_task_deploy(self, rpc_message):
        tasks_graph = rpc_message['tasks_graph']
        for node_id, tasks in six.iteritems(tasks_graph):
            if node_id is None:
                # skip virtual node
                continue

            task_ids = {
                t['id'] for t in tasks
                if t['type'] != consts.ORCHESTRATOR_TASK_TYPES.skipped
            }
            self.assertTrue(self.tasks_for_rerun.issubset(task_ids))

    def check_add_controller_for_granular_deploy(self, rpc_message):
        for node in rpc_message['deployment_info']:
            task_ids = {t['id'] for t in node['tasks']}
            # controller is redeployed when other one is added
            # so all tasks are run on all nodes
            self.assertTrue(
                self.tasks_for_rerun.issubset(task_ids))

    @mock.patch('nailgun.rpc.cast')
    def test_add_compute(self, _):
        new_node = self.add_node('compute')
        rpc_deploy_message = self.get_rpc_args()
        if self.task_deploy:
            self.check_add_compute_for_task_deploy(
                new_node.uid, rpc_deploy_message
            )
        else:
            self.check_add_compute_for_granular_deploy(
                new_node.uid, rpc_deploy_message
            )

    @mock.patch('nailgun.rpc.cast')
    def test_add_controller(self, _):
        self.add_node('controller')
        rpc_deploy_message = self.get_rpc_args()

        if self.task_deploy:
            self.check_add_controller_for_task_deploy(rpc_deploy_message)
        else:
            self.check_add_controller_for_granular_deploy(rpc_deploy_message)


class TestDeploymentAttributesSerialization80(
    TestSerializer80Mixin,
    BaseDeploymentSerializer
):
    env_version = 'liberty-8.0'

    def setUp(self):
        super(TestDeploymentAttributesSerialization80, self).setUp()
        self.cluster = self.env.create(
            release_kwargs={
                'version': self.env_version,
                'operating_system': consts.RELEASE_OS.ubuntu},
            cluster_kwargs={
                'mode': consts.CLUSTER_MODES.ha_compact,
                'net_provider': consts.CLUSTER_NET_PROVIDERS.neutron,
                'net_segment_type': consts.NEUTRON_SEGMENT_TYPES.vlan})
        self.cluster_db = self.db.query(models.Cluster).get(self.cluster['id'])
        serializer_type = get_serializer_for_cluster(self.cluster_db)
        self.serializer = serializer_type(AstuteGraph(self.cluster_db))

    def test_neutron_attrs(self):
        self.env.create_node(
            cluster_id=self.cluster_db.id,
            roles=['controller'], primary_roles=['controller']
        )
        objects.Cluster.prepare_for_deployment(self.cluster_db)
        serialized_for_astute = self.serializer.serialize(
            self.cluster_db, self.cluster_db.nodes)
        for node in serialized_for_astute:
            self.assertEqual(
                {
                    "bridge": consts.DEFAULT_BRIDGES_NAMES.br_floating,
                    "vlan_range": None
                },
                node['quantum_settings']['L2']['phys_nets']['physnet1']
            )
            l2 = (node["quantum_settings"]["predefined_networks"]
                  [self.cluster_db.network_config.floating_name]["L2"])

            self.assertEqual("physnet1", l2["physnet"])
            self.assertEqual("flat", l2["network_type"])

    def test_baremetal_transformations(self):
        self.env._set_additional_component(self.cluster_db, 'ironic', True)
        self.env.create_node(cluster_id=self.cluster_db.id,
                             roles=['primary-controller'])
        objects.Cluster.prepare_for_deployment(self.cluster_db)
        serialized_for_astute = self.serializer.serialize(
            self.cluster_db, self.cluster_db.nodes)
        for node in serialized_for_astute:
            transformations = node['network_scheme']['transformations']
            baremetal_brs = filter(lambda t: t.get('name') ==
                                   consts.DEFAULT_BRIDGES_NAMES.br_baremetal,
                                   transformations)
            baremetal_ports = filter(lambda t: t.get('name') == "eth0.104",
                                     transformations)
            expected_patch = {
                'action': 'add-patch',
                'bridges': [consts.DEFAULT_BRIDGES_NAMES.br_ironic,
                            consts.DEFAULT_BRIDGES_NAMES.br_baremetal],
                'provider': 'ovs'}
            self.assertEqual(len(baremetal_brs), 1)
            self.assertEqual(len(baremetal_ports), 1)
            self.assertEqual(baremetal_ports[0]['bridge'],
                             consts.DEFAULT_BRIDGES_NAMES.br_baremetal)
            self.assertIn(expected_patch, transformations)

    def test_disks_attrs(self):
        disks = [
            {
                "model": "TOSHIBA MK1002TS",
                "name": "sda",
                "disk": "sda",
                "size": 1004886016
            },
        ]
        expected_node_volumes_hash = [
            {
                u'name': u'sda',
                u'extra': [],
                u'free_space': 330,
                u'volumes': [
                    {
                        u'type': u'boot',
                        u'size': 300
                    },
                    {
                        u'mount': u'/boot',
                        u'type': u'partition',
                        u'file_system': u'ext2',
                        u'name': u'Boot',
                        u'size': 200
                    },
                    {
                        u'type': u'lvm_meta_pool',
                        u'size': 64
                    },
                    {
                        u'vg': u'os',
                        u'type': u'pv',
                        u'lvm_meta_size': 64,
                        u'size': 394
                    },
                    {
                        u'vg': u'vm',
                        u'type': u'pv',
                        u'lvm_meta_size': 0,
                        u'size': 0
                    }
                ],
                u'type': u'disk',
                u'id': u'sda',
                u'size': 958
            },
            {
                u'_allocate_size': u'min',
                u'label': u'Base System',
                u'min_size': 19456,
                u'volumes': [
                    {
                        u'mount': u'/',
                        u'size': -3766,
                        u'type': u'lv',
                        u'name': u'root',
                        u'file_system': u'ext4'
                    },
                    {
                        u'mount': u'swap',
                        u'size': 4096,
                        u'type': u'lv',
                        u'name': u'swap',
                        u'file_system': u'swap'
                    }
                ],
                u'type': u'vg',
                u'id': u'os'
            },
            {
                u'_allocate_size': u'all',
                u'label': u'Virtual Storage',
                u'min_size': 5120,
                u'volumes': [
                    {
                        u'mount': u'/var/lib/nova',
                        u'size': 0,
                        u'type': u'lv',
                        u'name': u'nova',
                        u'file_system': u'xfs'
                    }
                ],
                u'type': u'vg',
                u'id': u'vm'
            }
        ]
        self.env.create_node(
            cluster_id=self.cluster_db.id,
            roles=['compute'],
            meta={"disks": disks},
        )
        objects.Cluster.prepare_for_deployment(self.cluster_db)
        serialized_for_astute = self.serializer.serialize(
            self.cluster_db, self.cluster_db.nodes)
        for node in serialized_for_astute:
            self.assertIn("node_volumes", node)
            self.assertItemsEqual(
                expected_node_volumes_hash, node["node_volumes"])

    def test_attributes_contains_plugins(self):
        self.env.create_plugin(
            cluster=self.cluster_db,
            name='plugin_1',
            attributes_metadata={'name': 'plugin_1'},
            package_version='4.0.0',
            fuel_version=['8.0'])
        self.env.create_plugin(
            cluster=self.cluster_db,
            name='plugin_2',
            attributes_metadata={'name': 'plugin_2'},
            package_version='4.0.0',
            fuel_version=['8.0'])
        self.env.create_plugin(
            cluster=self.cluster_db,
            enabled=False,
            name='plugin_3',
            attributes_metadata={'name': 'plugin_3'},
            package_version='4.0.0',
            fuel_version=['8.0'])

        expected_plugins_list = ['plugin_1', 'plugin_2']
        self.env.create_node(
            cluster_id=self.cluster_db.id,
            roles=['compute']
        )
        objects.Cluster.prepare_for_deployment(self.cluster_db)
        serialized_for_astute = self.serializer.serialize(
            self.cluster_db, self.cluster_db.nodes)
        for node in serialized_for_astute:
            self.assertIn('plugins', node)
            self.assertItemsEqual(
                expected_plugins_list, node['plugins'])
            self.assertTrue(all(name in node for name
                                in expected_plugins_list))

    def test_common_attributes_contains_plugin_metadata(self):
        expected_value = 'check_value'
        plugin = self.env.create_plugin(
            cluster=self.cluster_db,
            name='test_plugin',
            package_version='4.0.0',
            fuel_version=['8.0'],
            attributes_metadata={
                'config': {
                    'description': "Description",
                    'weight': 52,
                    'value': expected_value
                }
            }
        )
        attrs = self.serializer.get_common_attrs(self.cluster_db)
        self.assertIn('test_plugin', attrs)
        self.assertIn('metadata', attrs['test_plugin'])
        self.assertEqual(
            plugin.id, attrs['test_plugin']['metadata']['plugin_id']
        )
        self.assertEqual(expected_value, attrs['test_plugin']['config'])


class TestMultiNodeGroupsSerialization80(BaseDeploymentSerializer):
    env_version = 'liberty-8.0'

    def setUp(self):
        super(TestMultiNodeGroupsSerialization80, self).setUp()
        cluster = self.env.create(
            release_kwargs={'version': self.env_version},
            cluster_kwargs={
                'net_provider': consts.CLUSTER_NET_PROVIDERS.neutron,
                'net_segment_type': consts.NEUTRON_SEGMENT_TYPES.vlan}
        )
        self.env.create_nodes_w_interfaces_count(
            nodes_count=3,
            if_count=2,
            roles=['controller', 'cinder'],
            pending_addition=True,
            cluster_id=cluster['id'])
        self.cluster_db = self.db.query(models.Cluster).get(cluster['id'])
        serializer_type = get_serializer_for_cluster(self.cluster_db)
        self.serializer = serializer_type(AstuteGraph(self.cluster_db))

    def _add_node_group_with_node(self, cidr_start, node_address):
        node_group = self.env.create_node_group(
            api=False, cluster_id=self.cluster_db.id,
            name='ng_' + cidr_start + '_' + str(node_address))

        with mock.patch.object(rpc, 'cast'):
            resp = self.env.setup_networks_for_nodegroup(
                cluster_id=self.cluster_db.id, node_group=node_group,
                cidr_start=cidr_start)
        self.assertEqual(resp.status_code, 200)

        self.db.query(models.Task).filter_by(
            name=consts.TASK_NAMES.update_dnsmasq
        ).delete(synchronize_session=False)

        self.env.create_nodes_w_interfaces_count(
            nodes_count=1,
            if_count=2,
            roles=['compute'],
            pending_addition=True,
            cluster_id=self.cluster_db.id,
            group_id=node_group.id,
            ip='{0}.9.{1}'.format(cidr_start, node_address))

    def _check_routes_count(self, count):
        objects.Cluster.prepare_for_deployment(self.cluster_db)
        facts = self.serializer.serialize(
            self.cluster_db, self.cluster_db.nodes)

        for node in facts:
            endpoints = node['network_scheme']['endpoints']
            for name, descr in six.iteritems(endpoints):
                if descr['IP'] == 'none':
                    self.assertNotIn('routes', descr)
                else:
                    self.assertEqual(len(descr['routes']), count)

    def test_routes_with_no_shared_networks_2_nodegroups(self):
        self._add_node_group_with_node('199.99', 3)
        # all networks have different CIDRs
        self._check_routes_count(1)

    def test_routes_with_no_shared_networks_3_nodegroups(self):
        self._add_node_group_with_node('199.99', 3)
        self._add_node_group_with_node('199.77', 3)
        # all networks have different CIDRs
        self._check_routes_count(2)

    def test_routes_with_shared_networks_3_nodegroups(self):
        self._add_node_group_with_node('199.99', 3)
        self._add_node_group_with_node('199.99', 4)
        # networks in two racks have equal CIDRs
        self._check_routes_count(1)


class TestBlockDeviceDevicesSerialization80(BaseDeploymentSerializer):
    env_version = 'liberty-8.0'

    def setUp(self):
        super(TestBlockDeviceDevicesSerialization80, self).setUp()
        self.cluster = self.env.create(
            release_kwargs={'version': self.env_version},
            cluster_kwargs={
                'mode': consts.CLUSTER_MODES.ha_compact,
                'net_provider': consts.CLUSTER_NET_PROVIDERS.neutron,
                'net_segment_type': consts.NEUTRON_SEGMENT_TYPES.vlan})
        self.cluster_db = self.db.query(models.Cluster).get(self.cluster['id'])
        serializer_type = get_serializer_for_cluster(self.cluster_db)
        self.serializer = serializer_type(AstuteGraph(self.cluster_db))

    def test_block_device_disks(self):
        self.env.create_node(
            cluster_id=self.cluster_db.id,
            roles=['cinder-block-device']
        )
        self.env.create_node(
            cluster_id=self.cluster_db.id,
            roles=['controller']
        )
        objects.Cluster.prepare_for_deployment(self.cluster_db)
        serialized_for_astute = self.serializer.serialize(
            self.cluster_db, self.cluster_db.nodes)
        for node in serialized_for_astute:
            self.assertIn("node_volumes", node)
            for node_volume in node["node_volumes"]:
                if node_volume["id"] == "cinder-block-device":
                    self.assertEqual(node_volume["volumes"], [])
                else:
                    self.assertNotEqual(node_volume["volumes"], [])


class TestSerializeInterfaceDriversData80(
    TestSerializer80Mixin,
    TestSerializeInterfaceDriversData
):
    pass


class TestDeploymentHASerializer80(
    TestSerializer80Mixin,
    TestDeploymentHASerializer70
):
    pass
