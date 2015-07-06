# -*- coding: utf-8 -*-

# Copyright 2014 Mirantis, Inc.
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
import copy
from random import randint

from nailgun.db.sqlalchemy.models import Cluster
from nailgun.db.sqlalchemy.models import NodeBondInterface
from nailgun.db.sqlalchemy.models import NodeNICInterface
from nailgun.db.sqlalchemy.models import Release

from nailgun.test.base import BaseTestCase
from oslo_serialization import jsonutils


class TestDbModels(BaseTestCase):

    def test_cluster_fuel_version_length(self):
        fuel_version = 'a' * 1024
        cluster_data = {
            'name': 'cluster-api-' + str(randint(0, 1000000)),
            'fuel_version': fuel_version,
            'release_id': self.env.create_release(api=False).id
        }

        cluster = Cluster(**cluster_data)
        self.db.add(cluster)
        self.db.commit()

    def test_release_environment_version(self):
        test_cases = (
            ('2014.1', '5.0'),
            ('2014.1-5.0', '5.0'),
            ('2014.1.1-5.0.1', '5.0.1'),
            ('2014.1.1-5.0.1-X', '5.0.1'),
            ('2014.1.1-5.1', '5.1'),
        )

        for version, enviroment_version in test_cases:
            self.assertEqual(
                Release(version=version).environment_version,
                enviroment_version)


class TestNodeInterfacesDbModels(BaseTestCase):
    sample_nic_interface_data = {
        'node_id': 1,
        'name': 'test_interface',
        'mac': '00:00:00:00:00:01',
        'max_speed': 200,
        'current_speed': 100,
        'ip_addr': '10.20.0.2',
        'netmask': '255.255.255.0',
        'state': 'test_state',
        'interface_properties': jsonutils.dumps(
            {'test_property': 'test_value'}),
        'parent_id': 1,
        'driver': 'test_driver',
        'bus_info': 'some_test_info'
    }

    unchanged_modes = [
        {
            'name': 'mode_1',
            'state': None,
            'sub': [
                {
                    'name': 'sub_mode_1',
                    'state': None,
                    'sub': []
                }
            ]
        },
        {
            'name': 'mode_2',
            'state': None,
            'sub': [
                {
                    'name': 'sub_mode_2',
                    'state': None,
                    'sub': []
                }
            ]
        }
    ]

    changed_modes = [
        {
            'name': 'mode_1',
            'state': True,
            'sub': [
                {
                    'name': 'sub_mode_1',
                    'state': None,
                    'sub': []
                }
            ]
        },
        {
            'name': 'mode_2',
            'state': None,
            'sub': [
                {
                    'name': 'sub_mode_2',
                    'state': False,
                    'sub': []
                }
            ]
        }
    ]

    expected_result = {
        'mode_1': True,
        'sub_mode_1': None,
        'mode_2': None,
        'sub_mode_2': False
    }

    def test_offloading_modes_as_flat_dict(self):
        self.assertDictEqual(
            self.expected_result,
            NodeNICInterface.offloading_modes_as_flat_dict(
                self.changed_modes))

    def test_update_offloading_modes_for_bond_interface(self):
        nics = []
        for i in xrange(2):
            nic_data = copy.deepcopy(self.sample_nic_interface_data)
            nic_data['offloading_modes'] = \
                copy.deepcopy(self.unchanged_modes)
            nics.append(NodeNICInterface(**nic_data))

        sample_bond_data = {
            'node_id': 1,
            'name': 'test_bond_interface',
            'mode': 'active-backup',
            'bond_properties': jsonutils.dumps(
                {'test_property': 'test_value'})
        }

        bond = NodeBondInterface(**sample_bond_data)
        bond.slaves = nics

        bond_modes = bond.offloading_modes
        self.assertListEqual(self.unchanged_modes, bond_modes)

        bond.offloading_modes = self.changed_modes

        bond_modes = bond.offloading_modes
        self.assertListEqual(self.changed_modes, bond_modes)

        for nic in nics:
            self.assertListEqual(self.changed_modes,
                                 nic.offloading_modes)
