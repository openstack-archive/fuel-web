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


from nailgun.test.base import BaseTestCase
from nailgun.utils.migration import negate_condition
from nailgun.utils.migration import upgrade_release_attributes_50_to_51
from nailgun.utils.migration import upgrade_release_roles_50_to_51
from nailgun.utils.migration import upgrade_release_roles_51_to_60


class TestDataMigration(BaseTestCase):

    def test_release_attributes_metadata_upgrade_50_to_51(self):
        attributes_metadata_50 = {
            'editable': {
                'storage': {
                    'volumes_ceph': {
                        'value': False,
                        'label': "Ceph RBD for volumes (Cinder)",
                        'description': "Configures Cinder to store "
                                       "volumes in Ceph RBD images.",
                        'weight': 20,
                        'type': "checkbox",
                        'conflicts': [
                            {"settings:common.libvirt_type.value": "vcenter"},
                            {"settings:storage.volumes_lvm.value": True}
                        ]
                    },
                    'objects_ceph': {
                        'value': False,
                        'label': "Ceph RadosGW for objects(Swift API)",
                        'description': "Configures RadosGW front end "
                                       "for Ceph RBD.",
                        'weight': 40,
                        'type': "checkbox",
                        'depends': [
                            {"settings:storage.images_ceph.value": True}
                        ],
                        'conflicts': [
                            {"settings:common.libvirt_type.value": "vcenter"}
                        ]
                    }
                }
            }
        }

        attributes_metadata_51 = upgrade_release_attributes_50_to_51(
            attributes_metadata_50
        )

        storage_attrs = attributes_metadata_51["editable"]["storage"]
        self.assertEqual(
            storage_attrs['volumes_ceph'].get("restrictions"),
            [
                "settings:common.libvirt_type.value == 'vcenter'",
                "settings:storage.volumes_lvm.value == true"
            ]
        )
        self.assertEqual(
            storage_attrs['objects_ceph'].get("restrictions"),
            [
                "settings:storage.images_ceph.value != true",
                "settings:common.libvirt_type.value == 'vcenter'"
            ]
        )

    def test_release_roles_metadata_upgrade_50_to_51(self):
        roles_metadata_50 = {
            'mongo': {
            'name': "Telemetry - MongoDB",
            'description': "A feature-complete and recommended "
                           "database for storage of metering data "
                           "from OpenStack Telemetry (Ceilometer)",
            'conflicts': ['compute',
                          'ceph-osd',
                          'zabbix-server'],
            'depends': [
                {'condition':
                    {"settings:additional_components.ceilometer.value": True},
                 'warning': "Ceilometer should be enabled"}]

            }
        }

        roles_metadata_51 = upgrade_release_roles_50_to_51(
            roles_metadata_50
        )

        self.assertEqual(
            roles_metadata_51["mongo"]["depends"],
            [
                {'condition':
                    "settings:additional_components.ceilometer.value == true",
                 'warning': "Ceilometer should be enabled"}
            ]
        )

    def test_negate_condition(self):
        self.assertEqual(
            negate_condition('a == b'),
            'not (a == b)'
        )
        self.assertEqual(
            negate_condition('a != b'),
            'not (a != b)'
        )
        self.assertEqual(
            negate_condition('a in b'),
            'not (a in b)'
        )

    def test_release_roles_metadata_upgrade_51_to_60(self):
        operational_condition = {
            'condition': "cluster:status != 'operational'",
            'warning': "MongoDB node can not be added to an "
                       "operational environment."
        }
        ceilometer_condition = {
            'condition':
                'settings:additional_components.ceilometer.value == true',
            'warning': "Ceilometer should be enabled."
        }
        new_operational_condition = {
            'condition': negate_condition(operational_condition['condition']),
            'message': operational_condition['warning'],
        }
        new_ceilometer_condition = {
            'condition': negate_condition(ceilometer_condition['condition']),
            'message': ceilometer_condition['warning']
        }
        false_restriction = {
            'condition': "1 == 2",
            'message': "This is always false"
        }
        roles_metadata_51 = {
            'mongo': {
                'name': "Telemetry - MongoDB",
                'description': "A feature-complete and recommended "
                               "database for storage of metering data "
                               "from OpenStack Telemetry (Ceilometer)",
                'conflicts': ['compute',
                              'ceph-osd',
                              'zabbix-server'],
                'depends': [
                    operational_condition,
                    ceilometer_condition
                ],
            },
            'test': {
                'name': "Test restrictions extend",
                'description': "Testing restrictions list extend",
                'conflicts': [],
                'depends': [
                    operational_condition,
                    ceilometer_condition
                ],
                'restrictions': [
                    false_restriction
                ]
            }
        }

        roles_metadata_60 = upgrade_release_roles_51_to_60(
            roles_metadata_51
        )

        self.assertTrue('depends' not in roles_metadata_60["mongo"])
        self.assertTrue('depends' not in roles_metadata_60["test"])
        self.assertEqual(roles_metadata_60['mongo']['restrictions'],
            [
                new_operational_condition,
                new_ceilometer_condition
            ]
        )
        self.assertEqual(roles_metadata_60['test']['restrictions'],
             [
                 false_restriction,
                 new_operational_condition,
                 new_ceilometer_condition
             ]
        )
