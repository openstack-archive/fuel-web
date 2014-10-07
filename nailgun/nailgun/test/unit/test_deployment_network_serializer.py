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

from nailgun.test import base

from nailgun.orchestrator import deployment_serializers


CREDS = {'tenant': {'value': 'NONDEFAULT'}}


class TestNeutronDeploymentSerializer(base.BaseTestCase):

    def setUp(self):
        super(TestNeutronDeploymentSerializer, self).setUp()
        self.env.create(cluster_kwargs={'net_provider': 'neutron'})
        self.cluster = self.env.clusters[0]
        self.serializer = (deployment_serializers.
                           NeutronNetworkDeploymentSerializer)

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
        ext_network = self.serializer._generate_external_network(self.cluster)
        self.verify_network_tenant(ext_network)

    @patch(('nailgun.orchestrator.deployment_serializers.objects.'
            'Cluster.get_creds'), return_value=CREDS)
    def test_predefined_networks_tenant_name(self, creds):
        predefined_network = self.serializer.generate_predefined_networks(
            self.cluster)
        self.verify_network_tenant(predefined_network['net04'])
        self.verify_network_tenant(predefined_network['net04_ext'])
