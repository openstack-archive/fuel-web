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
from nailgun.orchestrator.deployment_serializers import\
    get_serializer_for_cluster
from nailgun.test.integration.test_orchestrator_serializer import \
    BaseDeploymentSerializer


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

    def test_metadata_attributes(self):

        for node in self.serialized_for_astute:
            quantum_settings = node['quantum_settings']['L2']
            self.assertFalse('segmentation_type' in quantum_settings)
            self.assertFalse('tunnel_id_ranges' in quantum_settings)
            self.assertFalse('predefined_networks' in quantum_settings)
