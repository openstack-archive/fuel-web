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

from nailgun import consts
from nailgun.db.sqlalchemy.models import Node
from nailgun.orchestrator import provisioning_serializers as ps
from nailgun.settings import settings
from nailgun.test.base import BaseIntegrationTest


class TestGetSerializerForCluster(BaseIntegrationTest):

    def _get_cluster(self, version):
        """Returns cluster object of a given version."""
        release = self.env.create_release(api=False, version=version)
        cluster = self.env.create_cluster(api=False, release_id=release.id)
        return cluster

    def test_env_5_0(self):
        cluster = self._get_cluster('2014.1')
        serializer = ps.get_serializer_for_cluster(cluster)

        self.assertIs(serializer, ps.ProvisioningSerializer)

    def test_env_5_0_1(self):
        cluster = self._get_cluster('2014.1.1-5.0.1')
        serializer = ps.get_serializer_for_cluster(cluster)

        self.assertIs(serializer, ps.ProvisioningSerializer)

    def test_env_5_1(self):
        cluster = self._get_cluster('2014.1.1-5.1')
        serializer = ps.get_serializer_for_cluster(cluster)

        self.assertIs(serializer, ps.ProvisioningSerializer)

    def test_env_5_1_1(self):
        cluster = self._get_cluster('2014.1.1-5.1.1')
        serializer = ps.get_serializer_for_cluster(cluster)

        self.assertIs(serializer, ps.ProvisioningSerializer)

    def test_env_6_0(self):
        cluster = self._get_cluster('2014.2-6.0')
        serializer = ps.get_serializer_for_cluster(cluster)

        self.assertIs(serializer, ps.ProvisioningSerializer)

    def test_env_6_0_1(self):
        cluster = self._get_cluster('2014.2-6.0.1')
        serializer = ps.get_serializer_for_cluster(cluster)

        self.assertIs(serializer, ps.ProvisioningSerializer)

    def test_env_6_1(self):
        cluster = self._get_cluster('2014.2-6.1')
        serializer = ps.get_serializer_for_cluster(cluster)

        self.assertIs(serializer, ps.ProvisioningSerializer61)


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
        self.serialized_cluster = ps.serialize(
            self.cluster_db, self.cluster_db.nodes)

    def test_cluster_info_serialization(self):
        engine = self.serialized_cluster['engine']
        self.assertDictEqual(engine, {
            'url': settings.COBBLER_URL,
            'username': settings.COBBLER_USER,
            'password': settings.COBBLER_PASSWORD,
            'master_ip': settings.MASTER_IP
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

    def test_node_serialization_w_bonded_admin_iface(self):
        self.cluster_db = self.env.clusters[0]
        # create additional node to test bonding
        self.env.create_nodes_w_interfaces_count(
            1, 3,
            **{
                'roles': ['compute'],
                'pending_addition': True,
                'cluster_id': self.cluster_db.id
            }
        )
        node = self.cluster_db.nodes[-1]
        # identify admin nic
        self.admin_nic, self.other_nic = None, None
        for nic in node['interfaces']:
            net_names = [n["name"] for n in nic["assigned_networks"]]
            if "fuelweb_admin" in net_names:
                admin_nic = nic
            elif net_names:
                other_nic = nic
        # bond admin iface
        self.env.make_bond_via_api('lnx_bond',
                                   '',
                                   [admin_nic['name'], other_nic['name']],
                                   node['id'],
                                   bond_properties={
                                       'mode': consts.BOND_MODES.balance_rr
                                   })
        # check serialized data
        serialized_node = ps.serialize(self.cluster_db, node)['nodes'][0]
        self.assertDictEqual(serialized_node['kernel_options'], {
            'netcfg/choose_interface': admin_nic['mac'],
            'udevrules': '{0}_{1}'.format(admin_nic['name'], admin_nic['mac'])
        })


class TestProvisioningSerializer61(BaseIntegrationTest):

    serializer = ps.ProvisioningSerializer61

    def test_ubuntu_prov_task_for_images(self):
        release = self.env.create_release(
            api=False, operating_system=consts.RELEASE_OS.ubuntu)
        self.cluster = self.env.create_cluster(
            api=False, release_id=release.id)
        self.cluster.attributes.editable['provision']['method'] = \
            consts.PROVISION_METHODS.image

        serialized_info = self.serializer.serialize(self.cluster, [])

        self.assertIn('pre_provision', serialized_info)
        self.assertTrue(filter(
            lambda task: all([
                task['uids'] == ['master'],
                task['type'] == 'shell',
                task['parameters']['cmd'].startswith('fuel-image')
            ]),
            serialized_info['pre_provision']))
        self.assertFalse(filter(
            lambda task: all([
                task['uids'] == ['master'],
                task['type'] == 'shell',
                task['parameters']['cmd'].startswith(
                    'LOCAL_KERNEL_FILE')
            ]),
            serialized_info['pre_provision']))

    def test_ubuntu_prov_task_for_cobbler(self):
        release = self.env.create_release(
            api=False, operating_system=consts.RELEASE_OS.ubuntu)
        self.cluster = self.env.create_cluster(
            api=False, release_id=release.id)
        self.cluster.attributes.editable['provision']['method'] = \
            consts.PROVISION_METHODS.cobbler

        serialized_info = self.serializer.serialize(self.cluster, [])

        self.assertIn('pre_provision', serialized_info)
        self.assertTrue(filter(
            lambda task: all([
                task['uids'] == ['master'],
                task['type'] == 'shell',
                task['parameters']['cmd'].startswith(
                    'LOCAL_KERNEL_FILE')
            ]),
            serialized_info['pre_provision']))
        self.assertFalse(filter(
            lambda task: all([
                task['uids'] == ['master'],
                task['type'] == 'shell',
                task['parameters']['cmd'].startswith('fuel-image')
            ]),
            serialized_info['pre_provision']))

    def test_centos_prov_task_for_cobbler(self):
        release = self.env.create_release(
            api=False, operating_system=consts.RELEASE_OS.centos)
        self.cluster = self.env.create_cluster(
            api=False, release_id=release.id)
        self.cluster.attributes.editable['provision']['method'] = \
            consts.PROVISION_METHODS.cobbler

        serialized_info = self.serializer.serialize(self.cluster, [])

        self.assertIn('pre_provision', serialized_info)
        self.assertFalse(filter(
            lambda task: all([
                task['priority'] == 100,
                task['uids'] == ['master'],
                task['type'] == 'shell',
                task['parameters']['cmd'].startswith('fuel-image')
            ]),
            serialized_info['pre_provision']))
        self.assertIn('pre_provision', serialized_info)
        self.assertEquals([], serialized_info['pre_provision'])

    def test_centos_prov_task_for_images(self):
        release = self.env.create_release(
            api=False, operating_system=consts.RELEASE_OS.centos)
        self.cluster = self.env.create_cluster(
            api=False, release_id=release.id)
        self.cluster.attributes.editable['provision']['method'] = \
            consts.PROVISION_METHODS.image

        serialized_info = self.serializer.serialize(self.cluster, [])

        self.assertIn('pre_provision', serialized_info)
        self.assertFalse(filter(
            lambda task: all([
                task['priority'] == 100,
                task['uids'] == ['master'],
                task['type'] == 'shell',
                task['parameters']['cmd'].startswith('fuel-image')
            ]),
            serialized_info['pre_provision']))
        self.assertIn('pre_provision', serialized_info)
        self.assertEquals([], serialized_info['pre_provision'])

    def test_engine_does_not_contain_provisioning_method(self):
        self.cluster = self.env.create_cluster(api=False)
        serialized_info = self.serializer.serialize(self.cluster, [])

        self.assertNotIn('provision_method', serialized_info['engine'])
