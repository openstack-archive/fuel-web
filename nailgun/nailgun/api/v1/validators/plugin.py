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


from nailgun.api.v1.validators.base import BasicValidator
from nailgun.errors import errors

from nailgun.api.v1.validators.json_schema import plugin


class PluginValidator(BasicValidator):

    @classmethod
    def validate_delete(cls, instance):
        if instance.clusters:
            raise errors.CannotDelete(
                "Can't delete plugin which is enabled"
                "for some environment."
            )

    @classmethod
    def validate(cls, data):
        parsed = super(PluginValidator, cls).validate(data)
        cls.validate_schema(parsed, plugin.PLUGIN_SCHEMA)
        return parsed

    @classmethod
    def validate_update(cls, data, instance):
        return cls.validate(data)

    @classmethod
    def validate_create(cls, data):
        return cls.validate(data)
