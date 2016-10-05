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
import sqlalchemy as sa

from nailgun.api.v1.validators.base import BasicValidator
from nailgun.api.v1.validators.json_schema.assignment \
    import assignment_format_schema
from nailgun.api.v1.validators.json_schema.assignment \
    import unassignment_format_schema
from nailgun.db import db
from nailgun.db.sqlalchemy.models import Node
from nailgun import errors
from nailgun import objects
from nailgun.settings import settings
from nailgun.utils.restrictions import RestrictionBase


class AssignmentValidator(BasicValidator):

    @staticmethod
    def check_all_nodes(nodes, node_ids):
        not_found_node_ids = set(node_ids) - set(n.id for n in nodes)
        if not_found_node_ids:
            raise errors.InvalidData(
                u"Nodes with ids {0} were not found."
                .format(
                    ", ".join(map(str, not_found_node_ids))
                ), log_message=True
            )

    @classmethod
    def check_unique_hostnames(cls, nodes, cluster_id):
        hostnames = [node.hostname for node in nodes]
        node_ids = [node.id for node in nodes]
        conflicting_hostnames = [
            x[0] for x in
            db.query(
                Node.hostname).filter(sa.and_(
                    ~Node.id.in_(node_ids),
                    Node.hostname.in_(hostnames),
                    Node.cluster_id == cluster_id,
                )
            ).all()
        ]
        if conflicting_hostnames:
            raise errors.AlreadyExists(
                "Nodes with hostnames [{0}] already exist in cluster {1}."
                .format(", ".join(conflicting_hostnames), cluster_id)
            )


class NodeAssignmentValidator(AssignmentValidator):

    @classmethod
    def validate_collection_update(cls, data, cluster_id=None):
        data = cls.validate_json(data)
        cls.validate_schema(data, assignment_format_schema)
        dict_data = dict((d["id"], d["roles"]) for d in data)
        received_node_ids = dict_data.keys()
        nodes = db.query(Node).filter(Node.id.in_(received_node_ids))
        cls.check_all_nodes(nodes, received_node_ids)
        cluster = objects.Cluster.get_by_uid(
            cluster_id, fail_if_not_found=True
        )
        cls.check_unique_hostnames(nodes, cluster_id)

        for node_id in received_node_ids:
            cls.validate_roles(
                cluster,
                dict_data[node_id]
            )
        return dict_data

    @classmethod
    def validate_roles(cls, cluster, roles):
        available_roles = objects.Cluster.get_roles(cluster)
        roles = set(roles)
        not_valid_roles = roles - set(available_roles)

        if not_valid_roles:
            raise errors.InvalidData(
                u"{0} are not valid roles for node in environment {1}"
                .format(u", ".join(not_valid_roles), cluster.id),
                log_message=True
            )

        cls.check_roles_for_conflicts(roles, available_roles)
        cls.check_roles_requirement(
            roles,
            available_roles,
            {
                'settings': objects.Cluster.get_editable_attributes(cluster),
                'cluster': cluster,
                'version': settings.VERSION,
            })

    @classmethod
    def check_roles_for_conflicts(cls, roles, roles_metadata):
        all_roles = set(roles_metadata.keys())
        for role in roles:
            if "conflicts" in roles_metadata[role]:
                other_roles = roles - set([role])
                conflicting_roles = roles_metadata[role]["conflicts"]
                if conflicting_roles == "*":
                    conflicting_roles = all_roles - set([role])
                else:
                    conflicting_roles = set(conflicting_roles)
                conflicting_roles &= other_roles
                if conflicting_roles:
                    raise errors.InvalidNodeRole(
                        "Role '{0}' in conflict with role '{1}'."
                        .format(role, ", ".join(conflicting_roles)),
                        log_message=True
                    )

    @classmethod
    def check_roles_requirement(cls, roles, roles_metadata, models):
        for role in roles:
            if "restrictions" in roles_metadata[role]:
                result = RestrictionBase.check_restrictions(
                    models, roles_metadata[role]['restrictions']
                )
                if result['result']:
                    raise errors.InvalidNodeRole(
                        "Role '{}' restrictions mismatch: {}"
                        .format(role, result['message'])
                    )


class NodeUnassignmentValidator(AssignmentValidator):

    @classmethod
    def validate_collection_update(cls, data, cluster_id=None):
        list_data = cls.validate_json(data)
        cls.validate_schema(list_data, unassignment_format_schema)
        node_ids_set = set(n['id'] for n in list_data)
        nodes = db.query(Node).filter(Node.id.in_(node_ids_set))
        node_id_cluster_map = dict(
            (n.id, n.cluster_id) for n in
            db.query(Node.id, Node.cluster_id).filter(
                Node.id.in_(node_ids_set)))
        other_cluster_ids_set = set(node_id_cluster_map.values()) - \
            set((int(cluster_id),))
        if other_cluster_ids_set:
            raise errors.InvalidData(
                u"Nodes [{0}] are not members of environment {1}."
                .format(
                    u", ".join(
                        str(n_id) for n_id, c_id in
                        node_id_cluster_map.iteritems()
                        if c_id in other_cluster_ids_set
                    ), cluster_id), log_message=True
            )
        cls.check_all_nodes(nodes, node_ids_set)
        return nodes
