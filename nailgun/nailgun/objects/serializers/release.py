# -*- coding: utf-8 -*-

#    Copyright 2013 Mirantis, Inc.
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


class ReleaseSerializer(BasicSerializer):

    fields = (
        "id",
        "name",
        "version",
        "can_update_from_versions",
        "description",
        "operating_system",
        "modes_metadata",
        "roles_metadata",
        "wizard_metadata",
        "state",
        "attributes_metadata",
        "vmware_attributes_metadata",
    )

    @classmethod
    def serialize(cls, instance, fields=None):
        from nailgun.objects.release import Release

        release_dict = \
            super(ReleaseSerializer, cls).serialize(instance, fields)
        release_dict["is_deployable"] = Release.is_deployable(instance)

        return release_dict
