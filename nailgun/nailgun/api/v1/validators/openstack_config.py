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

from nailgun.errors import errors

from nailgun.api.v1.validators.base import BasicValidator

from nailgun.api.v1.validators.json_schema import openstack_config as schema


class OpenstackConfigValidator(BasicValidator):

    int_fields = frozenset(['cluster_id', 'node_id', 'is_active'])
    exclusive_fields = frozenset(['node_id', 'node_role'])

    @classmethod
    def validate(cls, data, instance=None):
        return cls._validate_data(data, schema.OPENSTACK_CONFIG)

    @classmethod
    def validate_execute(cls, data):
        return cls._validate_data(data, schema.OPENSTACK_CONFIG_EXECUTE)

    @classmethod
    def _validate_data(cls, data, schema):
        data = super(OpenstackConfigValidator, cls).validate(data)
        cls.validate_schema(data, schema)
        cls._check_exclusive_fields(data)
        return data

    @classmethod
    def validate_query(cls, data):
        for field in cls.int_fields:
            if field in data:
                data[field] = int(data[field])
        cls._check_exclusive_fields(data)
        cls.validate_schema(data, schema.OPENSTACK_CONFIG_QUERY)

        data['is_active'] = bool(data.get('is_active', True))
        return data

    @classmethod
    def validate_delete(cls, data, instance):
        pass

    @classmethod
    def _check_exclusive_fields(cls, data):
        keys = [k for k in data if k in cls.exclusive_fields]
        if len(keys) > 1:
            raise errors.InvalidData(
                "Parameter '{0}' conflicts with '{1}' ".format(
                    keys[0], ', '.join(keys[1:])))
