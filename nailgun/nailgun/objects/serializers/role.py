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

from nailgun.objects.serializers.base import BasicSerializer


class RoleSerializer(BasicSerializer):

    @classmethod
    def serialize(cls, role, fields=None):
        release = role.release
        meta = release.roles_metadata[role.name]
        volumes = release.volumes_metadata['volumes_roles_mapping'][role.name]

        return {
            'id': role.id,
            'name': role.name,
            'release_id': role.release_id,
            'meta': meta,
            'volumes': volumes}
