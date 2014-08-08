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

from nailgun.test.base import BaseIntegrationTest
from nailgun.utils.migration import upgrade_clusters_replaced_info


class TestReplacedDataMigration(BaseIntegrationTest):

    def setUp(self):
        super(TestReplacedDataMigration, self).setUp()
        self.env.create(
            nodes_kwargs=[
                {'roles': ['controller'], 'pending_addition': True},
                {'roles': ['controller', 'cinder'], 'pending_addition': True},
            ]
        )
        self.cluster = self.env.clusters[0]
        self.nodes = self.env.nodes
        self.deployment_info = []
        self.provisioning_info = {'nodes': [], 'engine': {'custom': 'type'}}
        for node in self.env.nodes:
            self.deployment_info.append({'uid': node.uid, 'type': 'deploy'})
            self.provisioning_info['nodes'].append(
                {'uid': node.uid, 'type': 'provision'})
        self.cluster.replaced_deployment_info = self.deployment_info
        self.cluster.replaced_provisioning_info = self.provisioning_info
        self.db.commit()
        self.provisioning_nodes = self.provisioning_info.pop('nodes')

    def test_migration_passed_successfully(self):
        connection = self.db.connection()
        upgrade_clusters_replaced_info(connection)

        self.assertEqual(self.provisioning_info,
                         self.cluster.replaced_provisioning_info)
        self.assertEqual(self.cluster.replaced_deployment_info, {})
        for node in self.nodes:
            self.assertEqual(
                node.replaced_deployment_info,
                [n for n in self.deployment_info if n['uid'] == node.uid]
            )
            self.assertEqual(
                node.replaced_provisioning_info,
                next(n for n in self.provisioning_nodes
                     if n['uid'] == node.uid)
            )
