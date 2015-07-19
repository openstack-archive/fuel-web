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
from nailgun.db import db
from nailgun.db.sqlalchemy import models
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
        "required": ["name", "release_id"],
    }

    @classmethod
    def validate(cls, data, cluster):
        data = super(ClusterUpgradeValidator, cls).validate(data)
        cls.validate_cluster_status(cluster)
        cls.validate_cluster_name(data["name"])
        release = objects.Release.get_by_uid(data["release_id"],
                                             fail_if_not_found=True)
        cls.validate_release_upgrade(cluster.release, release)
        return data

    @classmethod
    def validate_release_upgrade(cls, orig_release, new_release):
        if not new_release.is_deployable:
            raise errors.InvalidDate(
                "Upgrade to the given release is not possible because this "
                "release is deprecated and cannot be installed.",
                log_message=True)
        if orig_release >= new_release:
            raise errors.InvalidDate(
                "Upgrade to the given release it not possible because "
                "this release is equal or lower than the release of the "
                "original cluster", log_message=True)

    @classmethod
    def validate_cluster_name(cls, cluster_name):
        clusters = objects.ClusterCollection.filter_by(None,
                                                       name=cluster_name)
        if clusters.first():
            raise errors.AlreadyExists(
                "Environment with this name already exists",
                log_message=True)

    @classmethod
    def validate_cluster_status(cls, cluster):
        from .objects.relations import UpgradeRelationObject

        if UpgradeRelationObject.is_cluster_in_upgrade(cluster):
            raise errors.InvalidData(
                "Upgrade is not possible because of the original cluster is "
                "already involed in the upgrade routine.",
                log_message=True)


class ClusterCloneIPsValidator(base.BasicValidator):

    @classmethod
    def validate(cls, data, cluster):
        seed_cluster_id = cls.validate_orig_cluster(cluster)
        cls.validate_controllers_amount(cluster, seed_cluster_id)

        return seed_cluster_id

    @classmethod
    def validate_orig_cluster(cls, cluster_id):
        seed_cluster_id = db.query(models.UpgradeRelation).filter(
            (models.UpgradeRelation.orig_cluster_id == cluster_id) |
            (models.UpgradeRelation.seed_cluster_id == cluster_id))

        if not seed_cluster_id:
            raise errors.IvalidData(
                "Cluster with ID {0} is not in upgrade stage"
                .format(cluster_id),
                log_message=True)

        seed_cluster_id = db.query(models.UpgradeRelation).filter(
            (models.UpgradeRelation.orig_cluster_id == cluster_id))

        if not seed_cluster_id:
            raise errors.InvalidData(
                "Need original cluster ID [{0}] instead of seed"
                " ID[{1}]".format(seed_cluster_id, cluster_id))

    @classmethod
    def validate_controllers_amount(cls, orig_cluster_id, seed_cluster_id):
        seed_cluster = objects.Cluster.get_by_uid(seed_cluster_id)
        orig_cluster = objects.cluster.get_by_uid(orig_cluster_id)

        seed_controllers = objects.Cluster.get_nodes_by_role(seed_cluster,
                                                             'controllers')
        orig_controllers = objects.Cluster.get_nodes_by_role(orig_cluster,
                                                             'controllers')
        if len(seed_controllers) > len(orig_controllers):
            raise errors.InvalidData("Original cluster has less"
                                     " controllers than seed cluster")
