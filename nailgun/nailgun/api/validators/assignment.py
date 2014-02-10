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
from nailgun.db import db
from nailgun.db.sqlalchemy.models import Node
from nailgun.errors import errors


class NodeAssignmentValidator(BasicValidator):
    @classmethod
    def validate_collection_update(cls, data):
        d = cls.validate_json(data)
        if not isinstance(d, list):
            raise errors.InvalidData(
                "Invalid json list",
                log_message=True
            )
        q = db().query(Node)
        for nd in d:
            if not nd.get("id"):
                raise errors.InvalidData(
                    "ID is not specified",
                    log_message=True
                )
            else:
                existent_node = q.get(nd["id"])
                if not existent_node:
                    raise errors.InvalidData(
                        "Invalid ID specified",
                        log_message=True
                    )
                if 'roles' in nd:
                    cls.validate_roles(nd)
        return d

    @classmethod
    def validate_roles(cls, data):
        if 'roles' in data:
            if not isinstance(data['roles'], list) or \
                    any(not isinstance(role, (
                        str, unicode)) for role in data['roles']):
                raise errors.InvalidData(
                    "Role list must be list of strings",
                    log_message=True
                )
