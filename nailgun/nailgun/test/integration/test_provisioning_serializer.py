# -*- coding: utf-8 -*-

#    Copyright 2013 Mirantis, Inc.
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

from nailgun.db.sqlalchemy.models import Node
from nailgun.orchestrator.provisioning_serializers import serialize
from nailgun.settings import settings
from nailgun.test.base import BaseIntegrationTest


class TestProvisioningSerializer(BaseIntegrationTest):

    def setUp(self):
        super(TestProvisioningSerializer, self).setUp()
        self.env.create()
        self.cluster_db = self.env.clusters[0]
        self.env.create_nodes_w_interfaces_count(
            1, 1,
            **{
                'roles': ['controller'],
                'pending_addition': True,
                'cluster_id': self.cluster_db.id
            }
        )
        self.env.create_nodes_w_interfaces_count(
            1, 1,
            **{
                'roles': ['compute'],
                'pending_addition': True,
                'cluster_id': self.cluster_db.id
            }
        )
        self.attributes = self.cluster_db.attributes.editable
        self.serialized_cluster = serialize(
            self.cluster_db, self.cluster_db.nodes)

    def test_cluster_info_serialization(self):
        engine = self.serialized_cluster['engine']
        self.assertDictEqual(engine, {
            'url': settings.COBBLER_URL,
            'username': settings.COBBLER_USER,
            'password': settings.COBBLER_PASSWORD,
            'master_ip': settings.MASTER_IP,
            'provision_method': 'cobbler'
        })

    def test_node_serialization(self):
        for node in self.serialized_cluster['nodes']:
            node_db = self.db.query(Node).filter_by(
                fqdn=node['hostname']
            ).first()
            # Get interface (in our case we created only one for each node)
            intr_db = node_db.nic_interfaces[0]
            intr_name = intr_db.name
            intr_mac = intr_db.mac
            kernal_params = self.attributes.get('kernel_params', {}) \
                .get('kernel', {}).get('value')

            self.assertEqual(node['uid'], node_db.uid)
            self.assertEqual(node['power_address'], node_db.ip)
            self.assertEqual(node['name'], "node-{0}".format(node_db.id))
            self.assertEqual(node['hostname'], node_db.fqdn)
            self.assertEqual(
                node['power_pass'], settings.PATH_TO_BOOTSTRAP_SSH_KEY)

            self.assertDictEqual(node['kernel_options'], {
                'netcfg/choose_interface': node_db.admin_interface.mac,
                'udevrules': '{0}_{1}'.format(intr_mac, intr_name)
            })

            self.assertDictEqual(node['ks_meta']['pm_data'], {
                'ks_spaces': node_db.attributes.volumes,
                'kernel_params': kernal_params
            })
            # Check node interfaces section
            self.assertEqual(
                node['interfaces'][intr_name]['mac_address'], intr_mac)
            self.assertEqual(
                node['interfaces'][intr_name]['static'], '0')
            self.assertEqual(
                node['interfaces'][intr_name]['dns_name'], node_db.fqdn)
            # Check node interfaces extra section
            self.assertEqual(node['interfaces_extra'][intr_name], {
                'peerdns': 'no',
                'onboot': 'yes'
            })
