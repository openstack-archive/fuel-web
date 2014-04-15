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


import json

from nailgun.orchestrator.deployment_serializers import serialize
from nailgun.test import base


class TestDeploymentSerializer(base.BaseIntegrationTest):

    def test_vlan_splinters_serialization(self):
        self.env.create(
            cluster_kwargs={
                'net_provider': 'neutron',
                'net_segment_type': 'gre'
            },
            nodes_kwargs=[
                {'roles': ['controller'], 'pending_addition': True},
                {'roles': ['compute'], 'pending_addition': True}]
        )

        cluster = self.env.clusters[0]
        vlan_splinters = {
            'vswitch': {
                'value': 'hard'
            }
        }
        cluster_attrs = cluster.attributes.editable
        cluster_attrs['vlan_splinters'] = vlan_splinters

        self.app.put(
            base.reverse('ClusterAttributesHandler',
                         kwargs={'cluster_id': self.env.clusters[0].id}),
            json.dumps({'editable': cluster_attrs}),
            headers=self.default_headers
        )

        serialized_cluster = serialize(cluster, cluster.nodes)
        interfaces = serialized_cluster[0]['network_scheme']['interfaces']

        L2_info = dict()
        for iface in interfaces:
            L2_info.update(interfaces[iface]['L2'])

        # if all L2 dicts are empty then there is a bug
        self.assertTrue(L2_info)

        for iface in interfaces:
            self.assertEqual(
                interfaces[iface]['L2']['vlan_splinters'], 'auto'
            )
