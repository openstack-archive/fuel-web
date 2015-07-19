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
from nailgun import consts
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
                "Upgrade to the given release is not possible because "
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


class NodeReassignValidator(base.BasicValidator):
    schema = {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "title": "Assign Node Parameters",
        "description": "Serialized parameters to assign node",
        "type": "object",
        "properties": {
            "node_id": {"type": "number"},
        },
    }

    @classmethod
    def validate(cls, data, cluster):
        data = super(NodeReassignValidator, cls).validate(data)
        cls.validate_schema(data, cls.schema)
        cls.validate_node(data['node_id'])
        return data

    @classmethod
    def validate_node(cls, node_id):
        node = adapters.NailgunNodeAdapter.get_by_uid(node_id)

        if not node.node:
            raise errors.ObjectNotFound("Node with id {0} was not found".
                                        format(node_id), log_message=True)

        # node can go to error state while upgrade process
        allowed_statuses = (consts.NODE_STATUSES.ready,
                            consts.NODE_STATUSES.provisioned,
                            consts.NODE_STATUSES.error)
        if node.status not in allowed_statuses:
            raise errors.InvalidData("Node should be in one of statuses: {0}".
                                     format(allowed_statuses),
                                     log_message=True)


class ClusterCloneIPsValidator(base.BasicValidator):

    @classmethod
    def validate(cls, data, orig_cluster_id):
        seed_cluster_id = cls.validate_orig_cluster(orig_cluster_id)
        cls.validate_controllers_amount(seed_cluster_id)

        return seed_cluster_id

    @classmethod
    def validate_orig_cluster(cls, orig_cluster_id):
        from .objects.relations import UpgradeRelationObject
        relation = UpgradeRelationObject.get_cluster_relation(
            orig_cluster_id)

        if not relation:
            raise errors.InvalidData(
                "Cluster with ID {0} is not in upgrade stage."
                .format(orig_cluster_id),
                log_message=True)

        if relation.orig_cluster_id != int(orig_cluster_id):
            raise errors.InvalidData(
                "There is no original cluster with ID {0}."
                .format(orig_cluster_id),
                log_message=True)

        return relation.seed_cluster_id

    @classmethod
    def validate_controllers_amount(cls, seed_cluster_id):
        seed_cluster = adapters.NailgunClusterAdapter.get_by_uid(
            seed_cluster_id)
        seed_controllers = adapters.NailgunClusterAdapter.get_nodes_by_role(
            seed_cluster, 'controller')

        if len(seed_controllers) == 0:
            raise errors.InvalidData("Seed cluster should has at least"
                                     " one controller", log_message=True)
