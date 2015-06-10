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

import mock

from nailgun.db.sqlalchemy.models import Cluster
from nailgun import objects
from nailgun.orchestrator.deployment_graph import AstuteGraph
from nailgun.orchestrator.deployment_serializers import \
    get_serializer_for_cluster
from nailgun.test.integration.test_orchestrator_serializer import \
    BaseDeploymentSerializer
from nailgun.test.integration.test_orchestrator_serializer import \
    TestDeploymentAttributesSerialization61


class TestDeploymentAttributesSerialization70(BaseDeploymentSerializer):
    @mock.patch('nailgun.utils.extract_env_version', return_value='7.0')
    def setUp(self, *args):
        super(TestDeploymentAttributesSerialization70, self).setUp()
        self.cluster = self.create_env('ha_compact')

        # NOTE: 'prepare_for_deployment' is going to be changed for 7.0
        objects.NodeCollection.prepare_for_deployment(self.env.nodes, 'gre')
        cluster_db = self.db.query(Cluster).get(self.cluster['id'])
        serializer = get_serializer_for_cluster(cluster_db)
        self.serialized_for_astute = serializer(
            AstuteGraph(cluster_db)).serialize(cluster_db, cluster_db.nodes)

    def test_provider_cluster_attrs(self):
        for node in self.serialized_for_astute:
            quantum_settings = node['quantum_settings']
            self.assertNotIn('L2', quantum_settings)
            self.assertNotIn('L3', quantum_settings)

            self.assertIsNot(quantum_settings['database']['passwd'], '')
            self.assertIsNot(quantum_settings['keystone']['admin_password'],
                             '')
            self.assertIsNot(
                quantum_settings['metadata']['metadata_proxy_shared_secret'],
                '')

    def test_network_scheme(self):
        for node in self.serialized_for_astute:
            roles = node['network_scheme']['roles']
            self.assertEqual(roles['neutron/mesh'], 'br-mgmt')

    def test_network_metadata(self):
        for node in self.serialized_for_astute:
            roles = node['network_metadata']['roles']

            # 'neutron/private' role test
            neutron_private_expected = {
                "tenant_networks": {
                    "enabled": True,
                    "type": "vlan",
                    "segm_range": [1000, 1030],
                    "networks": [
                        {
                            "name": "admin__vlan",
                            "segm_id": 1000,
                            "subnet": '192.168.111.0/24',
                            "gateway": '192.168.111.1',
                            "tenant_name": "admin",
                            "mtu": "0 (by default)"
                        }
                    ]
                }
            }
            self.assertEqual(roles['neutron/private'],
                             neutron_private_expected)

            # 'neutron/mesh' role test
            neutron_mesh_expected = {
                "tenant_networks": {
                    "enabled": True,
                    "type": "vxlan",
                    "segm_range": [
                        10000,
                        65535
                    ],
                    "networks": [
                        {
                            "name": "admin__vxlan",
                            "segm_id": 10000,
                            "subnet": "192.128.112.0/24",
                            "gateway": "192.128.112.1",
                            "tenant_name": "admin",
                            "mtu": 0
                        }
                    ]
                }
            }
            self.assertEqual(roles['neutron/mesh'], neutron_mesh_expected)

            # 'neutron/floating' role test
            neutron_floating_expected = {
                "floating_subnets": [
                    {
                        "name": "floating__sub_1",
                        "subnet": '172.16.0.0/24',
                        "range": {
                            "start": '172.16.0.130',
                            "end": '172.16.0.254'
                        },
                        "gw": '172.16.0.1'
                    },
                ]
            }
            self.assertEqual(roles['neutron/floating'],
                             neutron_floating_expected)
