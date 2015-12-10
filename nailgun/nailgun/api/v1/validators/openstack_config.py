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
from nailgun.errors import errors
from nailgun import objects


class OpenstackConfigValidator(BasicValidator):

    int_fields = frozenset(['cluster_id', 'node_id', 'is_active'])
    exclusive_fields = frozenset(['node_id', 'node_role'])

    @staticmethod
    def _check_no_running_deploy_tasks(cluster_id):
        """Check that no deploy tasks are running at the moment

        If there are running deploy tasks in cluster, NotAllowed exception
        raises.
        """
        deploy_task_ids = [
            six.text_type(task.id)
            for task in objects.TaskCollection.get_by_name_and_cluster_id(
                cluster_id, (consts.TASK_NAMES.deploy,))
            .filter_by(status=consts.TASK_STATUSES.running)
            .all()]

        if deploy_task_ids:
            raise errors.NotAllowed(
                "Cannot perform the action because there are "
                "running deployment tasks '{0}'"
                "".format(', '.join(deploy_task_ids)))

    @classmethod
    def _validate_nodes_before_execute(cls, filters):
        """Validate target nodes before execute configuration update"""
        # We can not pass cluster object here from handler because cluster_id
        # is passed in request data
        force = filters.get('force', False)
        cluster = objects.Cluster.get_by_uid(filters['cluster_id'],
                                             fail_if_not_found=True)
        target_nodes = objects.Cluster.get_nodes_to_update_config(
            cluster, filters.get('node_id'), filters.get('node_role'),
            only_ready_nodes=False)

        ready_target_nodes_uids = set(
            node.uid for node in target_nodes
            if node.status == consts.NODE_STATUSES.ready)

        if not ready_target_nodes_uids:
            raise errors.InvalidData("No nodes in status 'ready'")

        if force:
            return

        invalid_target_nodes_uids = set(
            node.uid for node in target_nodes
            if node.status != consts.NODE_STATUSES.ready)

        if invalid_target_nodes_uids:
            raise errors.InvalidData(
                "Nodes '{0}' are not in status 'ready' and can not be updated "
                "directly."
                "".format(', '.join(invalid_target_nodes_uids)))

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
    def validate(cls, data):
        """Validate data for new configuration

        Validation fails if there are running deployment tasks in cluster.
        """
        data = cls._validate_data(data, schema.OPENSTACK_CONFIG)
        cls._check_no_running_deploy_tasks(data['cluster_id'])
        return data

    @classmethod
    def validate_execute(cls, data):
        """Validate parameters for execute handler

        Validation fails if there are running deployment tasks in cluster.
        """
        filters = cls._validate_data(data, schema.OPENSTACK_CONFIG_EXECUTE)
        cls._check_no_running_deploy_tasks(filters['cluster_id'])
        cls._validate_nodes_before_execute(filters)
        return filters

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
        """Validate parameters for delete handler

        Validation fails if there are running deployment tasks in cluster.

        """
        cls._check_no_running_deploy_tasks(instance.cluster_id)

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
