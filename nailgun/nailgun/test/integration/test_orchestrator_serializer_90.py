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

from nailgun import consts
from nailgun import objects
from nailgun.orchestrator import deployment_graph
from nailgun.orchestrator import deployment_serializers

from nailgun.orchestrator.neutron_serializers import \
    NeutronNetworkDeploymentSerializer90
from nailgun.orchestrator.neutron_serializers import \
    NeutronNetworkTemplateSerializer90

from nailgun.test.integration.test_orchestrator_serializer import \
    BaseDeploymentSerializer
from nailgun.test.integration.test_orchestrator_serializer_80 import \
    TestBlockDeviceDevicesSerialization80
from nailgun.test.integration.test_orchestrator_serializer_80 import \
    TestDeploymentAttributesSerialization80
from nailgun.test.integration.test_orchestrator_serializer_80 import \
    TestDeploymentHASerializer80
from nailgun.test.integration.test_orchestrator_serializer_80 import \
    TestDeploymentTasksSerialization80
from nailgun.test.integration.test_orchestrator_serializer_80 import \
    TestMultiNodeGroupsSerialization80
from nailgun.test.integration.test_orchestrator_serializer_80 import \
    TestNetworkTemplateSerializer80
from nailgun.test.integration.test_orchestrator_serializer_80 import \
    TestSerializeInterfaceDriversData80


class TestSerializer90Mixin(object):
    env_version = "liberty-9.0"


class TestBlockDeviceDevicesSerialization90(
    TestSerializer90Mixin,
    TestBlockDeviceDevicesSerialization80
):
    pass


class TestDeploymentAttributesSerialization90(
    TestSerializer90Mixin,
    TestDeploymentAttributesSerialization80
):
    pass


class TestDeploymentHASerializer90(
    TestSerializer90Mixin,
    TestDeploymentHASerializer80
):
    def test_glance_properties(self):
        self.check_no_murano_data()


class TestDeploymentTasksSerialization90(
    TestSerializer90Mixin,
    TestDeploymentTasksSerialization80
):
    pass


class TestMultiNodeGroupsSerialization90(
    TestSerializer90Mixin,
    TestMultiNodeGroupsSerialization80
):
    pass


class TestNetworkTemplateSerializer90(
    TestSerializer90Mixin,
    TestNetworkTemplateSerializer80
):
    legacy_serializer = NeutronNetworkDeploymentSerializer90
    template_serializer = NeutronNetworkTemplateSerializer90


class TestSerializeInterfaceDriversData90(
    TestSerializer90Mixin,
    TestSerializeInterfaceDriversData80
):
    pass


class TestSriovSerialization90(
    TestSerializer90Mixin,
    BaseDeploymentSerializer
):
    def setUp(self, *args):
        super(TestSriovSerialization90, self).setUp()
        self.env.create(
            release_kwargs={'version': self.env_version},
            cluster_kwargs={
                'mode': consts.CLUSTER_MODES.ha_compact,
                'net_provider': consts.CLUSTER_NET_PROVIDERS.neutron,
                'net_segment_type': consts.NEUTRON_SEGMENT_TYPES.vlan,
                'status': consts.CLUSTER_STATUSES.new},
        )
        self.env.create_nodes_w_interfaces_count(
            nodes_count=1, if_count=3, cluster_id=self.env.clusters[0].id,
            pending_roles=['compute'], pending_addition=True)

    def serialize(self):
        objects.Cluster.prepare_for_deployment(self.env.clusters[0])
        graph = deployment_graph.AstuteGraph(self.env.clusters[0])
        return deployment_serializers.serialize(
            graph, self.env.clusters[0], self.env.nodes)

    def test_nic_sriov_info_is_serialized(self):
        for nic in self.env.nodes[0].nic_interfaces:
            if not nic.assigned_networks_list:
                nic_sriov = nic
                nic.interface_properties['sriov'] = {
                    'enabled': True,
                    'sriov_numvfs': 8,
                    'sriov_totalvfs': 8,
                    'available': True,
                    'pci_id': '1234:5678'
                }
                objects.NIC.update(
                    nic, {'interface_properties': nic.interface_properties})
                break
        else:
            self.fail('NIC without assigned networks was not found')

        node0 = self.serialize()[0]
        self.assertEqual(
            node0['quantum_settings']['supported_pci_vendor_devs'],
            ['1234:5678']
        )
        for trans in node0['network_scheme']['transformations']:
            if trans.get('name') == nic_sriov.name:
                self.assertEqual(
                    trans['vendor_specific'],
                    {
                        'sriov_numvfs': 8,
                        'physnet': 'physnet2'
                    }
                )
                self.assertEqual(trans['provider'], 'sriov')
                break
        else:
            self.fail('NIC with SR-IOV enabled was not found')
