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
from nailgun import errors
from nailgun import objects
from nailgun import utils


class OpenstackConfigValidator(BasicValidator):

    exclusive_fields = frozenset(['node_id', 'node_ids', 'node_role'])

    @staticmethod
    def _check_no_running_deploy_tasks(cluster):
        """Check that no deploy tasks are running at the moment

        If there are running deploy tasks in cluster, NotAllowed exception
        raises.
        """
        deploy_task_ids = [
            six.text_type(task.id)
            for task in objects.TaskCollection.get_by_name_and_cluster(
                cluster, (consts.TASK_NAMES.deployment,
                          consts.TASK_NAMES.dry_run_deployment,
                          consts.TASK_NAMES.noop_deployment))
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
            cluster, filters.get('node_ids'), filters.get('node_role'),
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

        # node_id is supported for backward compatibility
        node_id = data.pop('node_id', None)
        if node_id is not None:
            data['node_ids'] = [node_id]

        cluster = objects.Cluster.get_by_uid(
            data['cluster_id'], fail_if_not_found=True)

        node_ids = data.get('node_ids')
        if node_ids:
            nodes = objects.NodeCollection.get_by_ids(node_ids, cluster.id)
            invalid_node_ids = set(node_ids) - set(n.id for n in nodes)

            if invalid_node_ids:
                raise errors.InvalidData(
                    "Nodes '{0}' are not assigned to cluster '{1}'".format(
                        ', '.join(str(n) for n in sorted(invalid_node_ids)),
                        cluster.id))

        cls._check_no_running_deploy_tasks(cluster)
        return data

    @classmethod
    def validate(cls, data):
        """Validate data for new configuration

        Validation fails if there are running deployment tasks in cluster.
        """
        data = cls._validate_data(data, schema.OPENSTACK_CONFIG)
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
        cls._convert_query_fields(data)
        cls._check_exclusive_fields(data)
        cls.validate_schema(data, schema.OPENSTACK_CONFIG_QUERY)

        data.setdefault('is_active', True)
        return data

    @classmethod
    def validate_delete(cls, data, instance):
        """Validate parameters for delete handler

        Validation fails if there are running deployment tasks in cluster.
        """
        cluster = objects.Cluster.get_by_uid(instance.cluster_id)
        cls._check_no_running_deploy_tasks(cluster)

    @classmethod
    def _convert_query_fields(cls, data):
        """Converts parameters from URL query to appropriate types

        Parameters in URL query don't care any information about data types.
        Schema validation doesn't perform any type conversion, so
        it is required to convert them before schema validation.
        """
        for field in ['cluster_id', 'node_id']:
            value = data.get(field, None)
            if value is not None:
                try:
                    data[field] = int(value)
                except ValueError:
                    raise errors.InvalidData("Invalid '{0}' value: '{1}'"
                                             .format(field, value))

        node_ids = data.get('node_ids', None)
        if node_ids is not None:
            try:
                data['node_ids'] = [int(n) for n in node_ids.split(',')]
            except ValueError:
                raise errors.InvalidData("Invalid 'node_ids' value: '{0}'"
                                         .format(node_ids))

        if 'is_active' in data:
            try:
                data['is_active'] = utils.parse_bool(data['is_active'])
            except ValueError:
                raise errors.InvalidData("Invalid 'is_active' value: '{0}'"
                                         .format(data['is_active']))

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
