# -*- coding: utf-8 -*-

#    Copyright 2016 Mirantis, Inc.
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

import unittest

from nailgun import consts
from nailgun import objects
from nailgun.orchestrator import deployment_serializers
from nailgun.test.integration.test_orchestrator_serializer import \
    BaseDeploymentSerializer
from nailgun.test.integration import test_orchestrator_serializer_90


class TestSerializer10_0Mixin(object):
    env_version = "newton-10.0"
    task_deploy = True

    @classmethod
    def create_serializer(cls, cluster):
        serializer_type = deployment_serializers.get_serializer_for_cluster(
            cluster
        )
        return serializer_type(None)


class TestDeploymentHASerializer100(
        test_orchestrator_serializer_90.TestDeploymentHASerializer90):

    env_version = 'newton-10.0'

    def test_remove_nodes_from_common_attrs(self):
        cluster_db = self.env.clusters[0]
        serializer = self.create_serializer(cluster_db)

        common_attrs = serializer.get_common_attrs(cluster_db)
        self.assertNotIn('nodes', common_attrs)


class TestDeploymentAttributesSerialization10_0(
    TestSerializer10_0Mixin,
    BaseDeploymentSerializer
):

    def setUp(self, *args):
        super(TestDeploymentAttributesSerialization10_0, self).setUp()
        self.env.create(
            release_kwargs={'version': self.env_version},
            cluster_kwargs={
                'mode': consts.CLUSTER_MODES.ha_compact},
            nodes_kwargs=[{'roles': ['controller']}]
        )
        self.cluster = self.env.clusters[0]

    def serialize(self):
        objects.Cluster.prepare_for_deployment(self.cluster)
        serializer = self.create_serializer(self.cluster)
        return serializer.serialize(self.cluster, self.env.nodes)

    @unittest.skip('Should be rewritten')
    def test_bond_attributes_exist_in_network_schema(self):
        expected_attributes = {
            'mode': {
                'type': 'select',
                'values': ['balance-rr'],
                'value': 'balance-rr',
                'label': 'Mode'}}
        bond_config = self.env.get_default_plugin_bond_config()
        node = self.env.nodes[0]
        nic_names = [iface.name for iface in node.nic_interfaces]
        self.env.make_bond_via_api(
            'lnx_bond', '', nic_names, node.id,
            bond_properties={'mode': consts.BOND_MODES.balance_rr},
            attrs=bond_config)
        serialized_data = self.serialize()[0]
        for t in serialized_data['network_scheme']['transformations']:
            if t.get('name') == 'lnx_bond':
                self.assertDictEqual(
                    expected_attributes, t['attributes'])

    def test_interface_attributes_exist_in_network_schema(self):
        expected_attributes = {
            'offloading': {
                'disable': {
                    'value': False,
                    'label': 'Disable offloading',
                    'type': 'checkbox',
                    'weight': 10
                },
                'metadata': {
                    'label': 'Offloading',
                    'weight': 10
                },
                'modes': {
                    'description': 'Offloading modes',
                    'value': {},
                    'label': 'Offloading modes',
                    'type': 'offloading_modes',
                    'weight': 20
                }
            },
            'mtu': {
                'value': {
                    'value': None,
                    'label': 'MTU',
                    'type': 'text',
                    'weight': 10
                },
                'metadata': {
                    'label': 'MTU',
                    'weight': 20
                }
            },
            'sriov': {
                'enabled': {
                    'value': False,
                    'label': 'SRIOV enabled',
                    'type': 'checkbox',
                    'weight': 10
                },
                'physnet': {
                    'value': 'physnet2',
                    'label': 'Physical network',
                    'type': 'text',
                    'weight': 30
                },
                'metadata': {
                    'label': 'SRIOV',
                    'weight': 30
                },
                'numvfs': {
                    'value': None,
                    'label': 'Virtual functions',
                    'weight': 20,
                    'type': 'number',
                    'min': 0
                },
            },
            'dpdk': {
                'enabled': {
                    'value': False,
                    'label': 'DPDK enabled',
                    'type': 'checkbox',
                    'weight': 10
                },
                'metadata': {
                    'label': 'DPDK',
                    'weight': 40
                }
            }
        }
        serialized_data = self.serialize()[0]
        node = self.env.nodes[0]
        nic_names = [iface.name for iface in node.nic_interfaces]
        interfaces = serialized_data['network_scheme']['interfaces']
        for nic_name in nic_names:
            self.assertDictEqual(
                expected_attributes, interfaces[nic_name]['attributes'])
