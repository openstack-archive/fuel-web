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

from nailgun.orchestrator import deployment_serializers as ds
from nailgun.test import base

CREDS = {'tenant': {'value': 'NONDEFAULT'}}


class BaseTestNeutronDeploymentSerializer(base.BaseTestCase):
    def setUp(self):
        super(BaseTestNeutronDeploymentSerializer, self).setUp()
        self.env.create(cluster_kwargs={'net_provider': 'neutron'})
        self.cluster = self.env.clusters[0]


class NetworkTenantNameMixin(object):
    def verify_network_tenant(self, network):
        self.assertEqual(network['tenant'], CREDS['tenant']['value'])

    @patch(('nailgun.orchestrator.deployment_serializers.objects.'
            'Cluster.get_creds'), return_value=CREDS)
    def test_internal_network_changes_tenant_name(self, creds):
        int_network = self.serializer._generate_internal_network(self.cluster)
        self.verify_network_tenant(int_network)

    @patch(('nailgun.orchestrator.deployment_serializers.objects.'
            'Cluster.get_creds'), return_value=CREDS)
    def test_external_network_changes_tenant_name(self, creds):
        ext_network = self.serializer.generate_external_network(self.cluster)
        self.verify_network_tenant(ext_network)

    @patch(('nailgun.orchestrator.deployment_serializers.objects.'
            'Cluster.get_creds'), return_value=CREDS)
    def test_predefined_networks_tenant_name(self, creds):
        predefined_network = self.serializer.generate_predefined_networks(
            self.cluster)
        self.verify_network_tenant(predefined_network['net04'])
        self.verify_network_tenant(predefined_network['net04_ext'])


class TestNeutronDeploymentSerializer(BaseTestNeutronDeploymentSerializer,
                                      NetworkTenantNameMixin):
    serializer = ds.NeutronNetworkDeploymentSerializer


class TestNeutronDeploymentSerializer80(BaseTestNeutronDeploymentSerializer,
                                        NetworkTenantNameMixin):
    serializer = ds.NeutronNetworkDeploymentSerializer80

    def test_external_network(self):
        self.cluster.network_config.floating_ranges = [
            ["172.16.0.130", "172.16.0.150"],
            ["172.16.0.200", "172.16.0.254"]
        ]
        external_net = self.serializer.generate_external_network(self.cluster)
        self.assertEqual(
            external_net['L3']['floating'],
            ['172.16.0.130:172.16.0.150', '172.16.0.200:172.16.0.254'],
        )

        external_net = self.serializer.generate_external_network(self.cluster)
        self.assertEqual(
            external_net['L3'],
            {'enable_dhcp': False,
             'floating': ['172.16.0.130:172.16.0.150',
                          '172.16.0.200:172.16.0.254'],
             'gateway': '172.16.0.1',
             'nameservers': [],
             'subnet': '172.16.0.0/24'
             }
        )
