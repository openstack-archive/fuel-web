# -*- coding: utf-8 -*-
#    Copyright 2016 Mirantis, Inc.
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
from nailgun.api.v1.validators.json_schema import deployment_sequence as schema

from nailgun import errors
from nailgun import objects


class SequenceValidator(BasicValidator):
    single_schema = schema.SEQUENCE_SCHEMA

    @classmethod
    def validate(cls, data):
        parsed = cls.validate_json(data)
        cls.validate_schema(
            parsed,
            cls.single_schema
        )

        if objects.DeploymentSequence.get_by_name(parsed['name']):
            raise errors.AlreadyExists(
                'Sequence with name "{0}" already exist.'
                .format(parsed['name'])
            )
        return parsed

    @classmethod
    def validate_update(cls, data, instance):
        parsed = cls.validate_json(data)
        serialized = objects.DeploymentSequence.to_dict(
            instance, fields=('name', 'graphs')
        )
        serialized.update(parsed)
        cls.validate_schema(serialized, cls.single_schema)
        return parsed

    @classmethod
    def validate_delete(cls, *args, **kwargs):
        pass


class SequenceExecutorValidator(BasicValidator):
    single_schema = schema.SEQUENCE_EXECUTION_PARAMS

    @classmethod
    def validate(cls, data):
        parsed = cls.validate_json(data)
        cls.validate_schema(parsed, cls.single_schema)
        sequence = objects.DeploymentSequence.get_by_name(
            parsed.pop('name'), fail_if_not_found=True
        )
        parsed['graphs'] = sequence.graphs
        return parsed
