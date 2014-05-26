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

import traceback

import pecan

from nailgun.api.v2.controllers.base import BaseController

from nailgun.api.v1.validators.cluster import ProvisionSelectedNodesValidator
from nailgun.api.v1.validators.node import NodesFilterValidator

from nailgun.logger import logger

from nailgun import objects

from nailgun.orchestrator import deployment_serializers
from nailgun.orchestrator import provisioning_serializers
from nailgun.task.helpers import TaskHelper
from nailgun.task.manager import DeploymentTaskManager
from nailgun.task.manager import ProvisioningTaskManager


class NodesFilterMixin(object):
    validator = NodesFilterValidator

    def get_default_nodes(self, cluster):
        """Method should be overriden and
        return list of nodes
        """
        raise NotImplementedError('Please Implement this method')

    def get_nodes(self, cluster):
        """If nodes selected in filter
        then returns them, else returns
        default nodes.
        """
        request = pecan.request
        nodes = request.params.get("nodes", None)

        if nodes:
            node_ids = self.checked_data(data=nodes)
            return self.get_objects_list_or_404(
                objects.Node,
                node_ids
            )

        return self.get_default_nodes(cluster)


class DefaultOrchestratorInfo(NodesFilterMixin, BaseController):
    """Base class for default orchestrator data.
    Need to redefine serializer variable
    """

    # Override this attribute
    _serializer = None

    @pecan.expose(template='json:', content_type='application/json')
    def get_all(self, cluster_id):
        """:returns: JSONized default data which will be passed to orchestrator
        :http: * 200 (OK)
               * 404 (cluster not found in db)
        """
        cluster = self.get_object_or_404(objects.Cluster, cluster_id)
        nodes = self.get_nodes(cluster)
        return self._serializer.serialize(cluster, nodes)


class OrchestratorInfo(BaseController):
    """Base class for replaced data."""

    def get_orchestrator_info(self, cluster):
        """Method should return data
        which will be passed to orchestrator
        """
        raise NotImplementedError('Please Implement this method')

    def update_orchestrator_info(self, cluster, data):
        """Method should override data which
        will be passed to orchestrator
        """
        raise NotImplementedError('Please Implement this method')

    @pecan.expose(template='json:', content_type='application/json')
    def get_all(self, cluster_id):
        """:returns: JSONized data which will be passed to orchestrator
        :http: * 200 (OK)
               * 404 (cluster not found in db)
        """
        cluster = self.get_object_or_404(objects.Cluster, cluster_id)
        return self.get_orchestrator_info(cluster)

    @pecan.expose(template='json:', content_type='application/json')
    def put(self, cluster_id):
        """:returns: JSONized data which will be passed to orchestrator
        :http: * 200 (OK)
               * 400 (wrong data specified)
               * 404 (cluster not found in db)
        """
        cluster = self.get_object_or_404(objects.Cluster, cluster_id)
        data = self.checked_data()
        self.update_orchestrator_info(cluster, data)
        logger.debug('OrchestratorInfo:'
                     ' facts for cluster_id {0} were uploaded'
                     .format(cluster_id))
        return data

    @pecan.expose(template='json:', content_type='application/json')
    def delete(self, cluster_id):
        """:returns: {}
        :http: * 202 (orchestrator data deletion process launched)
               * 400 (failed to execute orchestrator data deletion process)
               * 404 (cluster not found in db)
        """
        cluster = self.get_object_or_404(objects.Cluster, cluster_id)
        self.update_orchestrator_info(cluster, {})

        raise self.http(202, '{}')


class DefaultProvisioningInfo(DefaultOrchestratorInfo):

    _serializer = provisioning_serializers

    def get_default_nodes(self, cluster):
        return TaskHelper.nodes_to_provision(cluster)


class DefaultDeploymentInfo(DefaultOrchestratorInfo):

    _serializer = deployment_serializers

    def get_default_nodes(self, cluster):
        return TaskHelper.nodes_to_deploy(cluster)


class ProvisioningInfo(OrchestratorInfo):

    defaults = DefaultProvisioningInfo()

    def get_orchestrator_info(self, cluster):
        return cluster.replaced_provisioning_info

    def update_orchestrator_info(self, cluster, data):
        cluster.replace_provisioning_info(data)
        return cluster.replaced_provisioning_info


class DeploymentInfo(OrchestratorInfo):

    defaults = DefaultDeploymentInfo()

    def get_orchestrator_info(self, cluster):
        return cluster.replaced_deployment_info

    def update_orchestrator_info(self, cluster, data):
        cluster.replace_deployment_info(data)
        return cluster.replaced_deployment_info


class SelectedNodesBase(NodesFilterMixin, BaseController):
    """Base class for running task manager on selected nodes."""

    @pecan.expose(template='json:', content_type='application/json')
    def put(self, cluster_id):
        """:returns: JSONized Task object.
        :http: * 200 (task successfully executed)
               * 404 (cluster or nodes not found in db)
               * 400 (failed to execute task)
        """
        cluster = self.get_object_or_404(objects.Cluster, cluster_id)
        nodes = self.get_nodes(cluster)

        try:
            task_manager = self.task_manager(cluster_id=cluster.id)
            task = task_manager.execute(nodes)
        except Exception as exc:
            logger.warn(u'Cannot execute {0} task nodes: {1}'.format(
                task_manager.__class__.__name__, traceback.format_exc()))
            raise self.http(400, message=str(exc))

        self.raise_task(task)


class ProvisionSelectedNodes(SelectedNodesBase):
    """Controller for provisioning selected nodes."""

    validator = ProvisionSelectedNodesValidator
    task_manager = ProvisioningTaskManager

    def get_default_nodes(self, cluster):
        TaskHelper.nodes_to_provision(cluster)


class DeploySelectedNodes(SelectedNodesBase):
    """Controller for deployment selected nodes."""

    task_manager = DeploymentTaskManager

    def get_default_nodes(self, cluster):
        TaskHelper.nodes_to_deploy(cluster)


class OrchestratorController(BaseController):

    deployment = DeploymentInfo()
    provisioning = ProvisioningInfo()
