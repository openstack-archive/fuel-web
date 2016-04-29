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
    env_version = None
    serializer = None

    def setUp(self):
        super(BaseTestNeutronDeploymentSerializer, self).setUp()
        self.cluster = self.env.create(
            cluster_kwargs={'net_provider': 'neutron'},
            release_kwargs={'version': self.env_version}
        )

    def check_shared_attrs_of_external_network(self, external_net):
        self.assertEqual(
            external_net['L2'],
            {
                'network_type': 'local',
                'physnet': None,
                'router_ext': True,
                'segment_id': None
            },
        )
        self.assertFalse(external_net['shared'])
        self.assertEqual(external_net['tenant'], 'admin')


@patch('nailgun.orchestrator.deployment_serializers.objects.Cluster.get_creds',
       return_value=CREDS)
class NetworkTenantNameMixin(object):
    def verify_network_tenant(self, network):
        self.assertEqual(network['tenant'], CREDS['tenant']['value'])

    def test_internal_network_changes_tenant_name(self, creds):
        int_network = self.serializer._generate_internal_network(self.cluster)
        self.verify_network_tenant(int_network)

    def test_external_network_changes_tenant_name(self, creds):
        ext_network = self.serializer.generate_external_network(self.cluster)
        self.verify_network_tenant(ext_network)

    def test_predefined_networks_tenant_name(self, creds):
        predefined_network = self.serializer.generate_predefined_networks(
            self.cluster)
        self.verify_network_tenant(predefined_network['admin_internal_net'])
        self.verify_network_tenant(predefined_network['admin_floating_net'])


class TestNeutronDeploymentSerializer(BaseTestNeutronDeploymentSerializer,
                                      NetworkTenantNameMixin):
    env_version = '1111-5.1'
    serializer = ds.NeutronNetworkDeploymentSerializer


class TestNeutronDeploymentSerializer70(BaseTestNeutronDeploymentSerializer,
                                        NetworkTenantNameMixin):
    serializer = ds.NeutronNetworkDeploymentSerializer70
    env_version = '1111-7.0'

    def test_external_network(self):
        self.cluster.network_config.floating_ranges = [
            ["172.16.0.130", "172.16.0.150"]
        ]

        external_net = self.serializer.generate_external_network(self.cluster)
        self.check_shared_attrs_of_external_network(external_net)
        self.assertEqual(
            external_net['L3'],
            {'enable_dhcp': False,
             'floating': "172.16.0.130:172.16.0.150",
             'gateway': '172.16.0.1',
             'nameservers': [],
             'subnet': '172.16.0.0/24'
             }
        )


class TestNeutronDeploymentSerializer80(BaseTestNeutronDeploymentSerializer,
                                        NetworkTenantNameMixin):
    serializer = ds.NeutronNetworkDeploymentSerializer80
    env_version = '1111-8.0'

    def test_external_network(self):
        self.cluster.network_config.floating_ranges = [
            ["172.16.0.130", "172.16.0.150"],
            ["172.16.0.200", "172.16.0.254"]
        ]

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
        self.assertEqual(
            external_net["L2"],
            {
                'network_type': "flat",
                'physnet': 'physnet1',
                "segment_id": None,
                "router_ext": True,
            }
        )
        self.assertFalse(external_net['shared'])
        self.assertEqual(external_net['tenant'], 'admin')

    def test_generate_l2(self):
        phys_nets = self.serializer.generate_l2(self.cluster)["phys_nets"]
        self.assertIn("physnet1", phys_nets)
        self.assertEqual(
            phys_nets["physnet1"],
            {
                'bridge': 'br-floating',
                'vlan_range': None
            }
        )
