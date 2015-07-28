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

from nailgun.api.v1.validators import base
from nailgun.errors import errors
from nailgun import objects

from .objects import adapters


class ClusterUpgradeValidator(base.BasicValidator):
    schema = {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "title": "Start upgrade procedure for a cluster",
        "description": "Serialized parameters to upgrade a cluster.",
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "release_id": {"type": "number"},
        },
        "required": ["name", "release_id"],
    }

    @classmethod
    def validate(cls, data, cluster):
        cluster = adapters.NailgunClusterAdapter(cluster)
        data = super(ClusterUpgradeValidator, cls).validate(data)
        cls.validate_schema(data, cls.schema)
        cls.validate_cluster_status(cluster)
        cls.validate_cluster_name(data["name"])
        release = objects.Release.get_by_uid(data["release_id"],
                                             fail_if_not_found=True)
        release = adapters.NailgunReleaseAdapter(release)
        cls.validate_release_upgrade(cluster.release, release)
        return data

    @classmethod
    def validate_release_upgrade(cls, orig_release, new_release):
        if not new_release.is_deployable:
            raise errors.InvalidData(
                "Upgrade to the given release is not possible because this "
                "release is deprecated and cannot be installed.",
                log_message=True)
        if orig_release >= new_release:
            raise errors.InvalidData(
                "Upgrade to the given release it not possible because "
                "this release is equal or lower than the release of the "
                "original cluster.", log_message=True)

    @classmethod
    def validate_cluster_name(cls, cluster_name):
        clusters = objects.ClusterCollection.filter_by(None,
                                                       name=cluster_name)
        if clusters.first():
            raise errors.AlreadyExists(
                "Environment with this name already exists.",
                log_message=True)

    @classmethod
    def validate_cluster_status(cls, cluster):
        from .objects.relations import UpgradeRelationObject

        if UpgradeRelationObject.is_cluster_in_upgrade(cluster.id):
            raise errors.InvalidData(
                "Upgrade is not possible because of the original cluster is "
                "already involed in the upgrade routine.",
                log_message=True)
