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

from nailgun.test.integration import test_orchestrator_serializer_90


class TestDeploymentHASerializer100(
        test_orchestrator_serializer_90.TestDeploymentHASerializer90):

    env_version = 'newton-10.0'

    def test_remove_nodes_from_common_attrs(self):
        cluster_db = self.env.clusters[0]
        serializer = self.create_serializer(cluster_db)

        common_attrs = serializer.get_common_attrs(cluster_db)
        self.assertNotIn('nodes', common_attrs)
