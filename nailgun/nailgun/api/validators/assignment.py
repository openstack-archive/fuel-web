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

from nailgun.api.validators.base import BasicValidator
from nailgun.api.validators.json_schema.assignment \
    import assignment_format_schema
from nailgun.api.validators.json_schema.assignment \
    import unassignment_format_schema
from nailgun.db import db
from nailgun.db.sqlalchemy.models import Cluster
from nailgun.db.sqlalchemy.models import Node
from nailgun.errors import errors


class NodeAssignmentValidator(BasicValidator):
    @classmethod
    def validate_collection_update(cls, data):
        dict_data = cls.validate_json(data)
        cls.validate_schema(dict_data, assignment_format_schema)
        received_node_ids = dict_data["assignment"].keys()
        node_query_ids = set(n.id for n in db.query(Node).filter(
            Node.id.in_(received_node_ids)
        ))
        for node_id in received_node_ids:
            if int(node_id) not in node_query_ids:
                raise errors.InvalidData(
                    "Invalid ID specified",
                    log_message=True
                )
            cls.validate_roles(
                dict_data["cluster_id"],
                dict_data["assignment"][node_id]
            )
        return dict_data

    @classmethod
    def validate_roles(cls, cluster_id, roles):
        roles = set(roles)
        release = db.query(Cluster).get(cluster_id).release
        not_valid_roles = roles - set(release.roles)
        if not_valid_roles:
            raise errors.InvalidData(
                "{0} are not valid roles for environment with id={1}"
                .format(", ".join(not_valid_roles), cluster_id),
                log_message=True
            )
        roles_metadata = release.roles_metadata
        if roles_metadata:
            for role in roles:
                if "conflicts" in roles_metadata[role]:
                    other_roles = roles - {role}
                    conflicting_roles = set(roles_metadata[role]["conflicts"])
                    conflicting_roles &= other_roles
                    if conflicting_roles:
                        raise errors.InvalidData(
                            'Role "{0}" in conflict with role {1}'
                            .format(role, ", ".join(conflicting_roles)),
                            log_message=True
                        )


class NodeUnassignmentValidator(BasicValidator):
    @classmethod
    def validate_collection_update(cls, data):
        list_data = cls.validate_json(data)
        cls.validate_schema(list_data, unassignment_format_schema)
        return list_data
