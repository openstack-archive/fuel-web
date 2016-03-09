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

from nailgun.api.v1.validators.base import BasicValidator
from nailgun.errors import errors
from nailgun.extensions.volume_manager.objects.adapters \
    import NailgunNodeAdapter
from nailgun.extensions.volume_manager.validators.json_schema.disks \
    import disks_simple_format_schema


class NodeDisksValidator(BasicValidator):

    @classmethod
    def validate(cls, data, node=None):
        dict_data = cls.validate_json(data)
        cls.validate_schema(dict_data, disks_simple_format_schema)
        cls.at_least_one_disk_exists(dict_data)
        cls.sum_of_volumes_not_greater_than_disk_size(dict_data)
        cls.check_keep_data_flag_for_volumes_with_same_role(dict_data)
        # in case of Ubuntu we should allocate OS on one disk only
        # https://bugs.launchpad.net/fuel/+bug/1308592
        if NailgunNodeAdapter(node).is_ubuntu:
            cls.os_vg_single_disk(dict_data)
        return dict_data

    @classmethod
    def os_vg_single_disk(cls, data):
        os_vg_count = 0
        for disk in data:
            for vol in disk["volumes"]:
                if vol["name"] == "os" and vol["size"] > 0:
                    os_vg_count += 1
        if os_vg_count > 1:
            raise errors.InvalidData(
                u'Base system should be allocated on one disk only'
            )

    @classmethod
    def at_least_one_disk_exists(cls, data):
        if len(data) < 1:
            raise errors.InvalidData(u'Node seems not to have disks')

    @classmethod
    def sum_of_volumes_not_greater_than_disk_size(cls, data):
        for disk in data:
            volumes_size = sum([volume['size'] for volume in disk['volumes']])

            if volumes_size > disk['size']:
                raise errors.InvalidData(
                    u'Not enough free space on disk: %s' % disk)

    @classmethod
    def check_keep_data_flag_for_volumes_with_same_role(cls, data):
        names_with_keep_data = set()
        for disk in data:
            for volume in disk['volumes']:
                if volume.get('keep_data', False):
                    names_with_keep_data.add(volume['name'])
        incorrect_names = set()
        for disk in data:
            for volume in disk['volumes']:
                if volume['name'] in names_with_keep_data and \
                        not volume.get('keep_data', False):
                    incorrect_names.add(volume['name'])

        if len(incorrect_names) > 0:
            s = ', '.join(incorrect_names)
            raise errors.InvalidData(u'All volumes with the same name should'
                                     u' have the same value for `keep_data` '
                                     u'flag, incorrect volumes: {0}'.format(s))
