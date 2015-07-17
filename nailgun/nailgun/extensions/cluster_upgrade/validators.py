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


class ClusterUpgradeValidator(base.BasicValidator):
    single_schema = {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "title": "Start upgrade procedure for a cluster",
        "description": "Serialized parameters to upgrade a cluster.",
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "release_id": {"type": "number"},
        },
    }

    @classmethod
    def validate_release_upgrade(cls, orig_release, new_release):
        if not new_release.is_deployable:
            raise errors.InvalidDate(
                "Upgrade to the given release is not possible because this "
                "release is not deployable.", log_message=True)
        if orig_release <= new_release:
            raise errors.InvalidDate(
                "Upgrade to the given release it not possible because "
                "this release is equal or lower than the release of the "
                "original cluster", log_message=True)

    @classmethod
    def validate_cluster_name(cls, new_cluster_name):
        clusters = objects.ClusterCollection.filter_by(None,
                                                       name=new_cluster_name)
        if clusters.first():
            raise errors.AlreadyExists(
                "Environment with this name already exists",
                log_message=True)

    @classmethod
    def validate_cluster_status(cls, cluster):
        from . import upgrade

        if upgrade.is_cluster_in_upgrade(cluster):
            raise errors.InvalidData(
                "Upgrade is not possible because of the original cluster is "
                "already involed in the upgrade routine.",
                log_message=True)
