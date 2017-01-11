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

    def test_cluster_name_length(self):
        cluster_data = {
            'name': u'ю' * 2048,
            'fuel_version': '',
            'release_id': self.env.create_release(api=False).id
        }
        cluster = Cluster(**cluster_data)
        self.db.add(cluster)
        self.db.commit()


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
        'attributes': {'test_property': 'test_value'},
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

    def test_interface_attributes_str_type_failure(self):
        nic_data = copy.deepcopy(self.sample_nic_interface_data)
        nic_data['attributes'] = jsonutils.dumps(
            nic_data['attributes'])   # str type cause ValueError
        self.assertRaises(ValueError, NodeNICInterface, **nic_data)

    def test_bond_attributes_str_type_failure(self):
        sample_bond_data = {
            'node_id': 1,
            'name': 'test_bond_interface',
            'mode': 'active-backup',
            'attributes': jsonutils.dumps(
                {'test_property': 'test_value'})    # str type cause ValueError
        }
        self.assertRaises(ValueError, NodeBondInterface, **sample_bond_data)
