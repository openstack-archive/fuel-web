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
from nailgun import consts
from nailgun.db.sqlalchemy import models
from nailgun.errors import errors
from nailgun import objects


class OpenstackConfigValidator(BasicValidator):

    exclusive_fields = frozenset(['node_id', 'node_role'])

    supported_configs = frozenset([
        'nova_config', 'nova_paste_api_ini', 'neutron_config',
        'neutron_api_config', 'neutron_plugin_ml2', 'neutron_agent_ovs',
        'neutron_l3_agent_config', 'neutron_dhcp_agent_config',
        'neutron_metadata_agent_config', 'keystone_config'])

    @staticmethod
    def _check_no_running_deploy_tasks(cluster):
        """Check that no deploy tasks are running at the moment

        If there are running deploy tasks in cluster, NotAllowed exception
        raises.
        """
        deploy_task_ids = [
            six.text_type(task.id)
            for task in objects.TaskCollection.get_by_name_and_cluster(
                cluster, (consts.TASK_NAMES.deployment,))
            .filter(models.Task.status.in_((consts.TASK_STATUSES.pending,
                                            consts.TASK_STATUSES.running)))
            .all()]

        if deploy_task_ids:
            raise errors.NotAllowed(
                "Cannot perform the action because there are "
                "running deployment tasks '{0}'"
                "".format(', '.join(deploy_task_ids)))

    @classmethod
    def _validate_env_before_execute(cls, filters):
        """Validate environment before execute configuration update"""

        # We can not pass cluster object here from handler because cluster_id
        # is passed in request data
        force = filters.get('force', False)
        cluster = objects.Cluster.get_by_uid(filters['cluster_id'],
                                             fail_if_not_found=True)
        if not force and cluster.status != consts.CLUSTER_STATUSES.operational:
            raise errors.InvalidData("Cluster should be in the status "
                                     "'operational'")

        target_nodes = objects.Cluster.get_nodes_to_update_config(
            cluster, filters.get('node_id'), filters.get('node_role'),
            only_ready_nodes=False)

        ready_target_nodes_uids = set(
            node.uid for node in target_nodes
            if node.status == consts.NODE_STATUSES.ready)

        if not ready_target_nodes_uids:
            raise errors.InvalidData("No nodes in status 'ready'")

        invalid_target_nodes_uids = set(
            node.uid for node in target_nodes
            if node.status != consts.NODE_STATUSES.ready)

        if not force and invalid_target_nodes_uids:
            raise errors.InvalidData(
                "Nodes '{0}' are not in status 'ready' and can not be updated "
                "directly."
                "".format(', '.join(invalid_target_nodes_uids)))

    @classmethod
    def _validate_data(cls, data, schema):
        """Common part of validation for creating and updating configuration

        Validation fails if there are running deployment tasks in cluster.
        """

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

        cls._check_no_running_deploy_tasks(cluster)
        return data

    @classmethod
    def validate(cls, data):
        """Validate data for new configuration

        Validation fails if there are running deployment tasks in cluster.
        """
        data = cls._validate_data(data, schema.OPENSTACK_CONFIG)
        cls._check_supported_configs(data)
        return data

    @classmethod
    def validate_execute(cls, data):
        """Validate parameters for execute handler"""
        filters = cls._validate_data(data, schema.OPENSTACK_CONFIG_EXECUTE)
        cls._validate_env_before_execute(filters)
        return filters

    @classmethod
    def validate_query(cls, data):
        """Validate parameters to filter list of configurations"""
        cls._check_exclusive_fields(data)
        cls.validate_schema(data, schema.OPENSTACK_CONFIG_QUERY)
        return data

    @classmethod
    def validate_delete(cls, data, instance):
        """Validate parameters for delete handler

        Validation fails if there are running deployment tasks in cluster.
        """
        cluster = objects.Cluster.get_by_uid(instance.cluster_id)
        cls._check_no_running_deploy_tasks(cluster)

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
