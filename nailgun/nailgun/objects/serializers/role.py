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

from nailgun.objects.serializers.base import BasicSerializer


class RoleSerializer(BasicSerializer):

    @classmethod
    def serialize_from_obj(cls, obj_cls, obj, role_name):
        role_meta = obj_cls.get_roles(obj)[role_name]
        volumes_metadata = obj_cls.get_volumes_metadata(obj)
        role_mapping = volumes_metadata.get('volumes_roles_mapping').get(
            role_name, [])

        return {
            'name': role_name,
            'meta': role_meta,
            'volumes_roles_mapping': role_mapping}
