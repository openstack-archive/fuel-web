# -*- coding: utf-8 -*-
#    Copyright 2014 Mirantis, Inc.
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
from nailgun.errors import errors


class NodeGroupValidator(BasicValidator):

    @classmethod
    def validate_delete(cls, instance, force=False):
        if (instance.nodes or instance.networks) and not force:
            raise errors.CannotDelete(
                "You cannot delete a node group that contains "
                "nodes or networks"
            )

    @classmethod
    def validate_update(cls, data, **kwargs):
        return cls.validate_json(data)
