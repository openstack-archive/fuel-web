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

from nailgun.plugins.classes import CustomRolesPlugin
from nailgun.plugins.classes import VolumesPlugin

from nailgun.volumes.manager import gb_to_mb


class CephRolePlugin(
    CustomRolesPlugin,
    VolumesPlugin
):

    role_names = [
        "lolceph-osd"
    ]

    release_roles_metadata = [
        (
            role_names[0],
            {
                "name": "Storage - LOLCeph OSD",
                "description": "LOLCeph storage role",
                "conflicts": "mongo"
            }
        )
    ]

    volumes_roles_mapping = [
        (
            role_names[0],
            [
                {"allocate_size": "min", "id": "os"},
                {"allocate_size": "min", "id": "lolcephjournal"},
                {"allocate_size": "full-disk", "id": "lolceph"},
            ]
        )
    ]

    volumes = [
        {
            'file_system': 'none',
            'id': 'lolceph',
            'label': 'LOLCeph',
            'min_size': {'generator': 'calc_min_lolceph_size'},
            'mount': 'none',
            'name': 'LOLCeph',
            'partition_guid': '4fbd7e29-9d25-41b8-afd0-062c0ceff05d',
            'type': 'partition'
        },
        {
            'file_system': 'none',
            'id': 'lolcephjournal',
            'label': 'LOLCeph Journal',
            'min_size': {'generator': 'calc_min_lolceph_journal_size'},
            'mount': 'none',
            'name': 'LOLCeph Journal',
            'partition_guid': '45b0969e-9b03-4f30-b4c6-b4b80ceff106',
            'type': 'partition'
        }
    ]

    generators = {
        'calc_min_lolceph_size': lambda: gb_to_mb(3),
        'calc_min_lolceph_journal_size': lambda: 0
    }
