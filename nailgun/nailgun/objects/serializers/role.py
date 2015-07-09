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

from nailgun import objects
from nailgun.objects.serializers.base import BasicSerializer


class RoleSerializer(BasicSerializer):

    @classmethod
    def serialize_for_release(cls, release, role_name):
        meta = release.roles_metadata[role_name]
        volumes = release.volumes_metadata['volumes_roles_mapping'][role_name]

        return {
            'name': role_name,
            'meta': meta,
            'volumes_roles_mapping': volumes}

    @classmethod
    def serialize_for_cluster(cls, cluster, role_name):
        meta = objects.Cluster.get_roles(cluster)[role_name]

        # TODO(ikalnitsky): Use volumes mapping from both release and plugins.
        # Currently, we try to retrieve them only from release and fallback
        # to empty list if nothing is found.
        volumes = cluster.release.volumes_metadata['volumes_roles_mapping']
        volumes = volumes.get(role_name, [])

        return {
            'name': role_name,
            'meta': meta,
            'volumes_roles_mapping': volumes}
