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

from nailgun.api.validators.base import BasicValidator
from nailgun.api.validators.json_schema.assignment \
    import assignment_format_schema
from nailgun.api.validators.json_schema.assignment \
    import unassignment_format_schema
from nailgun.db import db
from nailgun.db.sqlalchemy.models import Cluster
from nailgun.db.sqlalchemy.models import Node
from nailgun.errors import errors


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
                    ",".join(not_found_node_ids)
                ), log_message=True
            )

    @classmethod
    def check_if_already_done(cls, nodes):
        already_done_nodes = filter(cls.predicate, nodes)
        if any(already_done_nodes):
            raise errors.InvalidData(
                cls.done_error_msg_template
                .format(",".join(already_done_nodes)),
                log_message=True
            )


class NodeAssignmentValidator(AssignmentValidator):

    predicate = attrgetter('cluster')
    done_error_msg_template = "Nodes with ids {0} already assigned to " \
                              "environments. Nodes must be unassigned " \
                              "before they can be assigned again."

    @classmethod
    def validate_collection_update(cls, data, cluster_id=None):
        dict_data = cls.validate_json(data)
        cls.validate_schema(dict_data, assignment_format_schema)
        received_node_ids = map(int, dict_data.keys())
        nodes = db.query(Node).filter(Node.id.in_(received_node_ids))
        cls.check_all_nodes(nodes, received_node_ids)
        cls.check_if_already_done(nodes)
        release = db.query(Cluster).get(cluster_id).release
        for node_id in received_node_ids:
            cls.validate_roles(
                release,
                dict_data[str(node_id)]
            )
        return dict_data

    @classmethod
    def validate_roles(cls, release, roles):
        roles = set(roles)
        not_valid_roles = roles - set(release.roles)
        if not_valid_roles:
            raise errors.InvalidData(
                u"{0} are not valid roles for node in {1} release"
                .format(", ".join(not_valid_roles), release.name),
                log_message=True
            )
        roles_metadata = release.roles_metadata
        if roles_metadata:
            cls.check_roles_for_conflicts(roles, roles_metadata)

    @staticmethod
    def check_roles_for_conflicts(roles, roles_metadata):
        for role in roles:
            if "conflicts" in roles_metadata[role]:
                other_roles = roles - {role}
                conflicting_roles = set(roles_metadata[role]["conflicts"])
                conflicting_roles &= other_roles
                if conflicting_roles:
                    raise errors.InvalidData(
                        u'Role "{0}" in conflict with role {1}'
                        .format(role, ", ".join(conflicting_roles)),
                        log_message=True
                    )


class NodeUnassignmentValidator(AssignmentValidator):

    done_error_msg_template = "Can't unassign nodes with ids {0} " \
                              "if they not assigned."

    @staticmethod
    def predicate(node):
        return not node.cluster or node.pending_deletion

    @classmethod
    def validate_collection_update(cls, data):
        list_data = cls.validate_json(data)
        cls.validate_schema(list_data, unassignment_format_schema)
        node_ids = [n['id'] for n in list_data]
        nodes = db.query(Node).filter(Node.id.in_(node_ids))
        cls.check_all_nodes(nodes, node_ids)
        cls.check_if_already_done(nodes)
        return nodes
