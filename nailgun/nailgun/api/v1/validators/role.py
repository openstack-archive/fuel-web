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
from nailgun.api.v1.validators.json_schema import role
from nailgun import errors


class RoleValidator(BasicValidator):

    @classmethod
    def validate_delete(cls, instance_cls, instance, role_name):
        node = instance_cls.get_node_by_role(instance, role_name)

        if node:
            raise errors.CannotDelete(
                "Can't delete role {} that is assigned "
                "to node {}.".format(role_name, node.id))

    @classmethod
    def validate(cls, data, instance=None):
        parsed = super(RoleValidator, cls).validate(data)
        cls.validate_schema(parsed, role.SCHEMA)
        return parsed

    @classmethod
    def validate_update(cls, data, instance_cls, instance):
        parsed = cls.validate(data, instance=instance)
        tags_meta = instance_cls.get_tags_metadata(instance)
        for tag in parsed.get('meta', {}).get('tags', []):
            if tag not in tags_meta:
                raise errors.InvalidData(
                    "Role {} contains non-existent tag {}".format(
                        parsed['name'], tag)
                )

        volumes_meta = instance_cls.get_volumes_metadata(instance)
        allowed_ids = [m['id'] for m in volumes_meta.get('volumes', [])]
        missing_volume_ids = []
        for volume in parsed['volumes_roles_mapping']:
            if volume['id'] not in allowed_ids:
                missing_volume_ids.append(volume['id'])

        if missing_volume_ids:
            raise errors.InvalidData(
                "Wrong data in volumes_roles_mapping. Volumes with ids {0} are"
                " not in the list of allowed volumes {1}".format(
                    missing_volume_ids, allowed_ids))
        return parsed

    @classmethod
    def validate_create(cls, data, instance_cls, instance):
        parsed = cls.validate_update(data, instance_cls, instance)
        tags_meta = instance_cls.get_tags_metadata(instance)
        for tag in parsed.get('meta', {}).get('tags', []):
            if tag not in tags_meta:
                raise errors.InvalidData(
                    "Role {} contains non-existent tag {}".format(
                        parsed['name'], tag)
                )
        role_name = parsed['name']
        if role_name in instance_cls.get_own_roles(instance):
            raise errors.AlreadyExists(
                "Role with name {} already "
                "exists for {} {}".format(
                    role_name, instance_cls.__name__.lower(), instance.id))

        return parsed
