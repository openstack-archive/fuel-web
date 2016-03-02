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

from nailgun import objects

from nailgun.orchestrator.deployment_serializers import \
    get_serializer_for_cluster
from nailgun.orchestrator.neutron_serializers import \
    NeutronNetworkDeploymentSerializer90
from nailgun.orchestrator.neutron_serializers import \
    NeutronNetworkTemplateSerializer90

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

    def check_selective_gateway(self, net_template=None):
        node = self.env.create_node(
            cluster_id=self.cluster.id,
            roles=['controller'], primary_roles=['controller']
        )
        objects.Cluster.set_network_template(self.cluster, net_template)
        objects.Cluster.prepare_for_deployment(self.cluster)

        serializer = get_serializer_for_cluster(self.cluster)
        net_serializer = serializer.get_net_provider_serializer(self.cluster)
        nm = objects.Cluster.get_network_manager(self.cluster)
        networks_list = nm.get_node_networks(node)
        networks = {net['name']: net for net in networks_list}
        endpoints = net_serializer.generate_network_scheme(
            node, networks_list)['endpoints']

        self.assertIsNone(networks['management']['gateway'])
        self.assertNotIn('vendor_specific', endpoints['br-mgmt'])

        self.assertIsNotNone(networks['public']['gateway'])
        self.assertIn('vendor_specific', endpoints['br-ex'])
        self.assertEqual(endpoints['br-ex']['vendor_specific'],
                         {'provider_gateway': '172.16.0.1'})

    def test_selective_gateway_in_deployment_serializer(self):
        self.check_selective_gateway()

    def test_selective_gateway_in_template_serializer(self):
        self.check_selective_gateway(self.net_template)


class TestSerializeInterfaceDriversData90(
    TestSerializer90Mixin,
    TestSerializeInterfaceDriversData80
):
    pass
