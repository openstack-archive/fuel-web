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

from nailgun.extensions.cluster_upgrade.objects import adapters


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
        release = adapters.NailgunReleaseAdapter.get_by_uid(
            data["release_id"], fail_if_not_found=True)
        cls.validate_release_upgrade(cluster.release, release)
        return data

    @classmethod
    def validate_release_upgrade(cls, orig_release, new_release):
        if not objects.Release.is_deployable(new_release):
            raise errors.InvalidData(
                "Upgrade to the given release ({0}) is not possible because "
                "this release is deprecated and cannot be installed."
                .format(new_release.id),
                log_message=True)
        if orig_release >= new_release:
            raise errors.InvalidData(
                "Upgrade to the given release ({0}) is not possible because "
                "this release is equal or lower than the release of the "
                "original cluster.".format(new_release.id),
                log_message=True)

    @classmethod
    def validate_cluster_name(cls, cluster_name):
        clusters = objects.ClusterCollection.filter_by(None,
                                                       name=cluster_name)
        if clusters.first():
            raise errors.AlreadyExists(
                "Environment with this name '{0}' already exists."
                .format(cluster_name),
                log_message=True)

    @classmethod
    def validate_cluster_status(cls, cluster):
        from nailgun.extensions.cluster_upgrade.objects.relations \
            import UpgradeRelationObject

        if UpgradeRelationObject.is_cluster_in_upgrade(cluster.id):
            raise errors.InvalidData(
                "Upgrade is not possible because of the original cluster ({0})"
                " is already involved in the upgrade routine."
                .format(cluster.id),
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
        "required": ["node_id"],
    }

    @classmethod
    def validate(cls, data, cluster):
        data = super(NodeReassignValidator, cls).validate(data)
        cls.validate_schema(data, cls.schema)
        node = cls.validate_node(data['node_id'])
        cls.validate_node_cluster(node, cluster)
        return data

    @classmethod
    def validate_node(cls, node_id):
        node = adapters.NailgunNodeAdapter.get_by_uid(node_id)

        if not node:
            raise errors.ObjectNotFound("Node with id {0} was not found.".
                                        format(node_id), log_message=True)

        # node can go to error state while upgrade process
        allowed_statuses = (consts.NODE_STATUSES.ready,
                            consts.NODE_STATUSES.provisioned,
                            consts.NODE_STATUSES.error)
        if node.status not in allowed_statuses:
            raise errors.InvalidData("Node should be in one of statuses: {0}."
                                     " Currently node has {1} status.".
                                     format(allowed_statuses, node.status),
                                     log_message=True)
        if node.status == consts.NODE_STATUSES.error and\
           node.error_type != consts.NODE_ERRORS.deploy:
            raise errors.InvalidData("Node should be in error state only with"
                                     "deploy error type. Currently error type"
                                     " of node is {0}".format(node.error_type),
                                     log_message=True)
        return node

    @classmethod
    def validate_node_cluster(cls, node, cluster):
        if node.cluster_id == cluster.id:
            raise errors.InvalidData("Node {0} is already assigned to cluster"
                                     " {1}".format(node.id, cluster.id),
                                     log_message=True)
