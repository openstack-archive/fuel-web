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
from nailgun.api.v1.validators.json_schema import tag
from nailgun import errors


class TagValidator(BasicValidator):

    @classmethod
    def validate(cls, data, instance=None):
        parsed = super(TagValidator, cls).validate(data)
        cls.validate_schema(parsed, tag.SCHEMA)
        return parsed

    @classmethod
    def validate_update(cls, data, instance_cls, instance):
        parsed = cls.validate(data, instance=instance)
        return parsed

    @classmethod
    def validate_create(cls, data, instance_cls, instance):
        parsed = cls.validate(data, instance=instance)

        tag_name = parsed['name']
        if tag_name in instance_cls.get_own_tags(instance):
            raise errors.AlreadyExists(
                "Tag with name '{}' already "
                "exists for {} {}".format(
                    tag_name, instance_cls.__name__.lower(), instance.id))

        return parsed
