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
from operator import attrgetter

from nailgun.api.v1.validators.base import BasicValidator
from nailgun.api.v1.validators.json_schema.assignment \
    import assignment_format_schema
from nailgun.api.v1.validators.json_schema.assignment \
    import unassignment_format_schema
from nailgun.db import db
from nailgun.db.sqlalchemy.models import Node
from nailgun.errors import errors
from nailgun.expression import Expression
from nailgun import objects


class AssignmentValidator(BasicValidator):

    predicate = None
    done_error_msg_template = None

    @staticmethod
    def check_all_nodes(nodes, node_ids):
        not_found_node_ids = set(node_ids) - set(n.id for n in nodes)
        if not_found_node_ids:
            raise errors.InvalidData(
                u"Nodes with ids {0} were not found."
                .format(
                    ",".join(map(str, not_found_node_ids))
                ), log_message=True
            )

    @classmethod
    def check_if_already_done(cls, nodes):
        already_done_nodes = filter(cls.predicate, nodes)
        if any(already_done_nodes):
            raise errors.InvalidData(
                cls.done_error_msg_template
                .format(",".join(map(str, already_done_nodes))),
                log_message=True
            )


class NodeAssignmentValidator(AssignmentValidator):

    predicate = attrgetter('cluster')
    done_error_msg_template = "Nodes with ids {0} already assigned to " \
                              "environments. Nodes must be unassigned " \
                              "before they can be assigned again."

    @classmethod
    def validate_collection_update(cls, data, cluster_id=None):
        data = cls.validate_json(data)
        cls.validate_schema(data, assignment_format_schema)
        dict_data = dict((d["id"], d["roles"]) for d in data)
        received_node_ids = dict_data.keys()
        nodes = db.query(Node).filter(Node.id.in_(received_node_ids))
        cls.check_all_nodes(nodes, received_node_ids)
        cls.check_if_already_done(nodes)
        cluster = objects.Cluster.get_by_uid(
            cluster_id, fail_if_not_found=True
        )

        for node_id in received_node_ids:
            cls.validate_roles(
                cluster,
                dict_data[node_id]
            )
        return dict_data

    @classmethod
    def validate_roles(cls, cluster, roles):
        release = cluster.release
        roles = set(roles)
        not_valid_roles = roles - set(release.roles)
        if not_valid_roles:
            raise errors.InvalidData(
                u"{0} are not valid roles for node in {1} release"
                .format(u", ".join(not_valid_roles), release.name),
                log_message=True
            )
        roles_metadata = release.roles_metadata
        if roles_metadata:
            cls.check_roles_for_conflicts(roles, roles_metadata)
            cls.check_roles_requirement(
                roles,
                roles_metadata,
                {
                    'settings': cluster.attributes.editable,
                    'cluster': cluster,
                })

    @classmethod
    def check_roles_for_conflicts(cls, roles, roles_metadata):
        for role in roles:
            if "conflicts" in roles_metadata[role]:
                other_roles = roles - set([role])
                conflicting_roles = set(roles_metadata[role]["conflicts"])
                conflicting_roles &= other_roles
                if conflicting_roles:
                    raise errors.InvalidData(
                        u'Role "{0}" in conflict with role {1}'
                        .format(role, ", ".join(conflicting_roles)),
                        log_message=True
                    )

    @classmethod
    def check_roles_requirement(cls, roles, roles_metadata, models):
        for role in roles:
            if "depends" in roles_metadata[role]:
                depends = roles_metadata[role]['depends']
                for condition in depends:
                    expression = condition['condition']

                    if not Expression(expression, models).evaluate():
                        raise errors.InvalidData(condition['warning'])


class NodeUnassignmentValidator(AssignmentValidator):

    done_error_msg_template = "Can't unassign nodes with ids {0} " \
                              "if they not assigned."

    @staticmethod
    def predicate(node):
        return not node.cluster or node.pending_deletion

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
        cls.check_if_already_done(nodes)
        return nodes
