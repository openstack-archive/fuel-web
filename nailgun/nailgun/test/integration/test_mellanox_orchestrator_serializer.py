# -*- coding: utf-8 -*-

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

from random import randint

from nailgun import objects

from nailgun.db.sqlalchemy.models import NetworkGroup
from nailgun.orchestrator.provisioning_serializers \
    import serialize as prov_serializer
from nailgun.test.integration.test_orchestrator_serializer \
    import OrchestratorSerializerTestBase


class TestMellanox(OrchestratorSerializerTestBase):

    def setUp(self):
        super(TestMellanox, self).setUp()
        self.iser_interface_name = 'eth_iser0'
        self.vlan_splinters_off = {'L2': {'vlan_splinters': 'off'}}
        self.segment_type = 'vlan'

    def create_env(self, mode, mellanox=False, iser=False, iser_vlan=None):
        # Create env
        cluster = self.env.create(
            cluster_kwargs={
                'mode': mode,
                'net_provider': 'neutron',
                'net_segment_type': self.segment_type
            },
            nodes_kwargs=[
                {'roles': ['controller'], 'pending_addition': True},
                {'roles': ['compute'], 'pending_addition': True},
                {'roles': ['cinder'], 'pending_addition': True},
            ]
        )
        self.cluster_id = cluster['id']
        cluster_db = objects.Cluster.get_by_uid(self.cluster_id)
        editable_attrs = self._make_data_copy(cluster_db.attributes.editable)

        # Set Mellanox params
        if mellanox:
            mellanox_attrs = editable_attrs.setdefault('neutron_mellanox', {})
            mellanox_attrs.setdefault('plugin', {})['value'] = 'ethernet'
        if iser:
            iser_sttr = editable_attrs.setdefault('storage', {})
            iser_sttr.setdefault('iser', {})['value'] = True
            network_group = self.db().query(NetworkGroup)
            storage = network_group.filter_by(name="storage")
            if iser_vlan:
                storage.update(
                    {"vlan_start": iser_vlan}, synchronize_session="fetch")
            else:
                storage.update(
                    {"vlan_start": None}, synchronize_session="fetch")

        # Commit changes
        cluster_db.attributes.editable = editable_attrs
        self.db.commit()
        cluster_db = objects.Cluster.get_by_uid(self.cluster_id)
        objects.NodeCollection.prepare_for_deployment(cluster_db.nodes)
        return cluster_db

    def test_serialize_mellanox_plugin_enabled(self):
        # Serialize cluster
        self.cluster = self.create_env('ha_compact', mellanox=True)
        serialized_data = self.serializer.serialize(self.cluster,
                                                    self.cluster.nodes)
        for data in serialized_data:
            # Check plugin parameters
            self.assertIn('physical_port', data['neutron_mellanox'])
            self.assertIn('ml2_eswitch', data['neutron_mellanox'])

            # Check eswitch settings
            eswitch_dict = data['neutron_mellanox']['ml2_eswitch']
            self.assertIn('vnic_type', eswitch_dict)
            self.assertEqual('hostdev', eswitch_dict['vnic_type'])
            self.assertIn('apply_profile_patch', eswitch_dict)
            self.assertEqual(True, eswitch_dict['apply_profile_patch'])

            # Check L2 settings
            quantum_settings_l2 = data['quantum_settings']['L2']
            self.assertIn('mechanism_drivers', quantum_settings_l2)
            self.assertIn('mlnx', quantum_settings_l2['mechanism_drivers'])
            self.assertIn('type_drivers', quantum_settings_l2)
            seg_type = self.cluster.network_config.segmentation_type
            self.assertEquals(
                quantum_settings_l2['type_drivers'],
                '{0},flat,local'.format(seg_type)
            )
            self.assertIn(self.segment_type,
                          quantum_settings_l2['type_drivers'])
            self.assertIn('tenant_network_types', quantum_settings_l2)
            self.assertIn(self.segment_type,
                          quantum_settings_l2['tenant_network_types'])

    def test_serialize_mellanox_iser_enabled_untagged(self):
        # Serialize cluster
        self.cluster = \
            self.create_env('ha_compact', mellanox=True, iser=True,
                            iser_vlan=None)
        serialized_data = self.serializer.serialize(self.cluster,
                                                    self.cluster.nodes)

        for data in serialized_data:
            # Check Mellanox iSER values
            self.assertIn('storage_parent', data['neutron_mellanox'])
            self.assertIn('iser_interface_name', data['neutron_mellanox'])

            # Check network scheme changes
            network_scheme = data['network_scheme']
            self.assertEqual(
                self.iser_interface_name, network_scheme['roles']['storage'])
            self.assertIn(
                self.iser_interface_name, network_scheme['interfaces'])
            self.assertEqual(self.vlan_splinters_off,
                             network_scheme['interfaces']
                             [self.iser_interface_name])
            self.assertIn(
                self.iser_interface_name, network_scheme['endpoints'])
            self.assertNotIn('br-storage', network_scheme['endpoints'])

    def test_serialize_mellanox_iser_enabled_vlan(self):
        # set VLAN params
        vlan = randint(1, 4095)
        vlan_name = 'vlan{0}'.format(vlan)

        # Serialize cluster
        self.cluster = \
            self.create_env('ha_compact', mellanox=True, iser=True,
                            iser_vlan=vlan)
        serialized_data = self.serializer.serialize(self.cluster,
                                                    self.cluster.nodes)

        for data in serialized_data:
            # Check Mellanox iSER values
            self.assertIn('storage_parent', data['neutron_mellanox'])
            self.assertIn('iser_interface_name', data['neutron_mellanox'])

            # Check network scheme changes
            network_scheme = data['network_scheme']
            self.assertEqual(vlan_name, network_scheme['roles']['storage'])
            self.assertIn(vlan_name, network_scheme['interfaces'])
            self.assertEqual(
                self.vlan_splinters_off,
                network_scheme['interfaces'][vlan_name])
            self.assertIn(vlan_name, network_scheme['endpoints'])
            self.assertIn('vlandev', network_scheme['endpoints'][vlan_name])
            self.assertEqual(
                self.iser_interface_name,
                network_scheme['endpoints'][vlan_name]['vlandev'])
            self.assertNotIn('br-storage', network_scheme['endpoints'])

    def check_mellanox_kernel_params(self, mode, mellanox, iser):
        self.cluster = self.create_env(
            mode=mode,
            mellanox=mellanox,
            iser=iser,
        )
        serialized_cluster = prov_serializer(
            self.cluster,
            self.cluster.nodes
        )
        # The kernel param should exist if the user chooses Mellanox plugin,
        # or iSER protocol for volumes, or both
        assert_method = (
            self.assertIn if (mellanox or iser) else self.assertNotIn
        )
        for node in serialized_cluster['nodes']:
            assert_method(
                'intel_iommu=on',
                node['ks_meta']['pm_data']['kernel_params'].split()
            )

    def test_serialize_kernel_params_using_mellanox_sriov_plugin(self):
        self.check_mellanox_kernel_params(
            mode='multinode',
            mellanox=True,
            iser=False,
        )

    def test_serialize_kernel_params_using_mellanox_iser(self):
        self.check_mellanox_kernel_params(
            mode='ha_compact',
            mellanox=True,
            iser=True,
        )

    def test_serialize_kernel_params_not_using_mellanox(self):
        self.check_mellanox_kernel_params(
            mode='ha_compact',
            mellanox=False,
            iser=False,
        )
