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

import six

from nailgun.api.v1.validators.base import BasicValidator
from nailgun.api.v1.validators.json_schema import openstack_config as schema
from nailgun.errors import errors
from nailgun import objects


class OpenstackConfigValidator(BasicValidator):

    int_fields = frozenset(['cluster_id', 'node_id', 'is_active'])
    exclusive_fields = frozenset(['node_id', 'node_role'])

    supported_configs = frozenset([
        'nova_config', 'nova_paste_api_ini', 'neutron_config',
        'neutron_api_config', 'neutron_plugin_ml2', 'neutron_agent_ovs',
        'neutron_l3_agent_config', 'neutron_dhcp_agent_config',
        'neutron_metadata_agent_config', 'keystone_config'])

    @classmethod
    def validate(cls, data):
        data = cls._validate_data(data, schema.OPENSTACK_CONFIG)
        cls._check_supported_configs(data)
        return data

    @classmethod
    def validate_execute(cls, data):
        """Validate parameters for execute handler"""
        return cls._validate_data(data, schema.OPENSTACK_CONFIG_EXECUTE)

    @classmethod
    def _validate_data(cls, data, schema):
        data = super(OpenstackConfigValidator, cls).validate(data)
        cls.validate_schema(data, schema)
        cls._check_exclusive_fields(data)

        cluster = objects.Cluster.get_by_uid(data['cluster_id'],
                                             fail_if_not_found=True)
        if 'node_id' in data:
            node = objects.Node.get_by_uid(
                data['node_id'], fail_if_not_found=True)
            if node.cluster_id != cluster.id:
                raise errors.InvalidData(
                    "Node '{0}' is not assigned to cluster '{1}'".format(
                        data['node_id'], cluster.id))

        return data

    @classmethod
    def validate_query(cls, data):
        """Validate parameters to filter list of configurations"""
        cls._convert_query_fields(data)
        cls._check_exclusive_fields(data)
        cls.validate_schema(data, schema.OPENSTACK_CONFIG_QUERY)

        data['is_active'] = bool(data.get('is_active', True))
        return data

    @classmethod
    def validate_delete(cls, data, instance):
        pass

    @classmethod
    def _convert_query_fields(cls, data):
        """Converts parameters from URL query to appropriate types

        Parameters in URL query don't care any information about data types.
        Schema validation doesn't perform any type conversion, so
        it is required to convert them before schema validation.
        """
        for field in cls.int_fields:
            if field in data and data[field] is not None:
                data[field] = int(data[field])

    @classmethod
    def _check_exclusive_fields(cls, data):
        """Checks for conflicts between parameters

        Raises an exception if there are more than one mutually exclusive
        field in the request.
        """
        keys = []
        for key, value in six.iteritems(data):
            if value is None:
                continue
            if key in cls.exclusive_fields:
                keys.append(key)

        if len(keys) > 1:
            raise errors.InvalidData(
                "Parameter '{0}' conflicts with '{1}' ".format(
                    keys[0], ', '.join(keys[1:])))

    @classmethod
    def _check_supported_configs(cls, data):
        """Check that all provided configurations can be updated"""

        unsupported_configs = set(
            data['configuration']) - cls.supported_configs
        if unsupported_configs:
            raise errors.InvalidData(
                "Configurations '{0}' can not be updated".format(
                    ', '.join(unsupported_configs)))
