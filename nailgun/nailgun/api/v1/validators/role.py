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


from nailgun.api.v1.validators.base import BasicValidator
from nailgun.api.v1.validators.json_schema import role
from nailgun.errors import errors


class RoleValidator(BasicValidator):

    @classmethod
    def validate_delete(cls, instance):
        if instance.nodes or instance.pending_nodes:
            raise errors.CannotDelete(
                "Can't delete roles that is assigned to some node."
            )

    @classmethod
    def validate(cls, data, instance=None):
        parsed = super(RoleValidator, cls).validate(data)
        cls.validate_schema(parsed, role.SCHEMA)
        return parsed

    @classmethod
    def validate_update(cls, data, instance):
        return cls.validate(data, instance=instance)

    @classmethod
    def validate_create(cls, data):
        return cls.validate(data)
