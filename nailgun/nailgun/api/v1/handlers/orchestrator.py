# -*- coding: utf-8 -*-

#    Copyright 2013 Mirantis, Inc.
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

import six
import web

from nailgun.api.v1.handlers.base import BaseHandler
from nailgun.api.v1.handlers.base import content
from nailgun.api.v1.validators.cluster import ProvisionSelectedNodesValidator
from nailgun.api.v1.validators.graph import GraphVisualizationValidator
from nailgun.api.v1.validators.node import DeploySelectedNodesValidator
from nailgun.api.v1.validators.node import NodeDeploymentValidator
from nailgun.api.v1.validators.node import NodesFilterValidator

from nailgun.logger import logger

from nailgun.errors import errors
from nailgun import objects

from nailgun.orchestrator import deployment_graph
from nailgun.orchestrator import deployment_serializers
from nailgun.orchestrator import graph_visualization
from nailgun.orchestrator import provisioning_serializers
from nailgun.orchestrator.stages import post_deployment_serialize
from nailgun.orchestrator.stages import pre_deployment_serialize
from nailgun.orchestrator import task_based_deployment
from nailgun.task.helpers import TaskHelper
from nailgun.task import manager


class NodesFilterMixin(object):
    validator = NodesFilterValidator

    def get_default_nodes(self, cluster):
        """Method should be overriden and return list of nodes"""
        raise NotImplementedError('Please Implement this method')

    def get_nodes(self, cluster):
        """If nodes selected in filter then return them

        else return default nodes
        """
        nodes = web.input(nodes=None).nodes
        if nodes:
            node_ids = self.checked_data(data=nodes)
            return self.get_objects_list_or_404(
                objects.NodeCollection,
                node_ids
            )

        return self.get_default_nodes(cluster) or []


class DefaultOrchestratorInfo(NodesFilterMixin, BaseHandler):
    """Base class for default orchestrator data

    Need to redefine serializer variable
    """

    @content
    def GET(self, cluster_id):
        """:returns: JSONized default data which will be passed to orchestrator

        :http: * 200 (OK)
               * 404 (cluster not found in db)
        """
        cluster = self.get_object_or_404(objects.Cluster, cluster_id)
        nodes = self.get_nodes(cluster)

        return self._serialize(cluster, nodes)

    def _serialize(self, cluster, nodes):
        raise NotImplementedError('Override the method')


class OrchestratorInfo(BaseHandler):
    """Base class for replaced data."""

    def get_orchestrator_info(self, cluster):
        """Method should return data which will be passed to orchestrator"""
        raise NotImplementedError('Please Implement this method')

    def update_orchestrator_info(self, cluster, data):
        """Method should override data which will be passed to orchestrator"""
        raise NotImplementedError('Please Implement this method')

    @content
    def GET(self, cluster_id):
        """:returns: JSONized data which will be passed to orchestrator

        :http: * 200 (OK)
               * 404 (cluster not found in db)
        """
        cluster = self.get_object_or_404(objects.Cluster, cluster_id)
        return self.get_orchestrator_info(cluster)

    @content
    def PUT(self, cluster_id):
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

    @content
    def DELETE(self, cluster_id):
        """:returns: {}

        :http: * 202 (orchestrator data deletion process launched)
               * 400 (failed to execute orchestrator data deletion process)
               * 404 (cluster not found in db)
        """
        cluster = self.get_object_or_404(objects.Cluster, cluster_id)
        self.update_orchestrator_info(cluster, {})

        raise self.http(202, '{}')


class DefaultProvisioningInfo(DefaultOrchestratorInfo):

    def _serialize(self, cluster, nodes):
        return provisioning_serializers.serialize(
            cluster, nodes, ignore_customized=True)

    def get_default_nodes(self, cluster):
        return TaskHelper.nodes_to_provision(cluster)


class DefaultDeploymentInfo(DefaultOrchestratorInfo):

    def _serialize(self, cluster, nodes):
        graph = deployment_graph.AstuteGraph(cluster)
        return deployment_serializers.serialize(
            graph, cluster, nodes, ignore_customized=True)

    def get_default_nodes(self, cluster):
        return TaskHelper.nodes_to_deploy(cluster)


class DefaultPrePluginsHooksInfo(DefaultOrchestratorInfo):

    def _serialize(self, cluster, nodes):
        graph = deployment_graph.AstuteGraph(cluster)
        return pre_deployment_serialize(graph, cluster, nodes)

    def get_default_nodes(self, cluster):
        return TaskHelper.nodes_to_deploy(cluster)


class DefaultPostPluginsHooksInfo(DefaultOrchestratorInfo):

    def _serialize(self, cluster, nodes):
        graph = deployment_graph.AstuteGraph(cluster)
        return post_deployment_serialize(graph, cluster, nodes)

    def get_default_nodes(self, cluster):
        return TaskHelper.nodes_to_deploy(cluster)


class ProvisioningInfo(OrchestratorInfo):

    def get_orchestrator_info(self, cluster):
        return objects.Cluster.get_provisioning_info(cluster)

    def update_orchestrator_info(self, cluster, data):
        return objects.Cluster.replace_provisioning_info(cluster, data)


class DeploymentInfo(OrchestratorInfo):

    def get_orchestrator_info(self, cluster):
        return objects.Cluster.get_deployment_info(cluster)

    def update_orchestrator_info(self, cluster, data):
        return objects.Cluster.replace_deployment_info(cluster, data)


class SelectedNodesBase(NodesFilterMixin, BaseHandler):
    """Base class for running task manager on selected nodes."""

    def handle_task(self, cluster, **kwargs):

        nodes = self.get_nodes(cluster)

        try:
            task_manager = self.task_manager(cluster_id=cluster.id)
            task = task_manager.execute(nodes, **kwargs)
        except Exception as exc:
            logger.warn(
                u'Cannot execute %s task nodes: %s',
                task_manager.__class__.__name__, traceback.format_exc())
            raise self.http(400, message=six.text_type(exc))

        self.raise_task(task)

    @content
    def PUT(self, cluster_id):
        """:returns: JSONized Task object.

        :http: * 200 (task successfully executed)
               * 202 (task scheduled for execution)
               * 400 (data validation failed)
               * 404 (cluster or nodes not found in db)
        """
        cluster = self.get_object_or_404(objects.Cluster, cluster_id)
        return self.handle_task(cluster)


class ProvisionSelectedNodes(SelectedNodesBase):
    """Handler for provisioning selected nodes."""

    validator = ProvisionSelectedNodesValidator
    task_manager = manager.ProvisioningTaskManager

    def get_default_nodes(self, cluster):
        return TaskHelper.nodes_to_provision(cluster)

    @content
    def PUT(self, cluster_id):
        """:returns: JSONized Task object.

        :http: * 200 (task successfully executed)
               * 202 (task scheduled for execution)
               * 400 (data validation failed)
               * 404 (cluster or nodes not found in db)
        """
        cluster = self.get_object_or_404(objects.Cluster, cluster_id)

        # actually, there is no data in http body. the only reason why
        # we use it here is to follow dry rule and do not convert exceptions
        # into http status codes again.
        self.checked_data(self.validator.validate_provision, cluster=cluster)
        return self.handle_task(cluster)


class BaseDeploySelectedNodes(SelectedNodesBase):

    validator = DeploySelectedNodesValidator
    task_manager = manager.DeploymentTaskManager

    def get_default_nodes(self, cluster):
        return TaskHelper.nodes_to_deploy(cluster)

    def get_nodes(self, cluster):
        nodes_to_deploy = super(
            BaseDeploySelectedNodes, self).get_nodes(cluster)
        self.validate(cluster, nodes_to_deploy)
        return nodes_to_deploy

    def validate(self, cluster, nodes_to_deploy):
        self.checked_data(self.validator.validate_nodes_to_deploy,
                          nodes=nodes_to_deploy, cluster_id=cluster.id)

        self.checked_data(self.validator.validate_release, cluster=cluster)


class DeploySelectedNodes(BaseDeploySelectedNodes):
    """Handler for deployment selected nodes."""

    def get_nodes(self, cluster):
        nodes_to_deploy = super(
            DeploySelectedNodes, self).get_nodes(cluster)

        self.validate(cluster, nodes_to_deploy)

        return nodes_to_deploy

    @content
    def PUT(self, cluster_id):
        """:returns: JSONized Task object.

        :http: * 200 (task successfully executed)
               * 202 (task scheduled for execution)
               * 400 (data validation failed)
               * 404 (cluster or nodes not found in db)
        """
        cluster = self.get_object_or_404(objects.Cluster, cluster_id)
        return self.handle_task(cluster)


class DeploySelectedNodesWithTasks(BaseDeploySelectedNodes):

    validator = NodeDeploymentValidator

    @content
    def PUT(self, cluster_id):
        """:returns: JSONized Task object.

        :http: * 200 (task successfully executed)
               * 202 (task scheduled for execution)
               * 400 (data validation failed)
               * 404 (cluster or nodes not found in db)
        """
        cluster = self.get_object_or_404(objects.Cluster, cluster_id)
        data = self.checked_data(
            self.validator.validate_deployment,
            cluster=cluster)
        return self.handle_task(cluster, deployment_tasks=data)


class TaskDeployGraph(BaseHandler):

    validator = GraphVisualizationValidator

    def GET(self, cluster_id):
        """:returns: DOT representation of deployment graph.

        :http: * 200 (graph returned)
               * 404 (cluster not found in db)
               * 400 (failed to get graph)
        """
        web.header('Content-Type', 'text/vnd.graphviz', unique=True)

        cluster = self.get_object_or_404(objects.Cluster, cluster_id)
        tasks = objects.Cluster.get_deployment_tasks(cluster)
        graph = deployment_graph.DeploymentGraph(tasks)

        tasks = web.input(tasks=None).tasks
        parents_for = web.input(parents_for=None).parents_for
        remove = web.input(remove=None).remove

        if tasks:
            tasks = self.checked_data(
                self.validator.validate,
                data=tasks,
                cluster=cluster)
            logger.debug('Tasks used in dot graph %s', tasks)

        if parents_for:
            parents_for = self.checked_data(
                self.validator.validate_task_presence,
                data=parents_for,
                graph=graph)
            logger.debug('Graph with predecessors for %s', parents_for)

        if remove:
            remove = list(set(remove.split(',')))
            remove = self.checked_data(
                self.validator.validate_tasks_types,
                data=remove)
            logger.debug('Types to remove %s', remove)

        visualization = graph_visualization.GraphVisualization(graph)
        dotgraph = visualization.get_dotgraph(tasks=tasks,
                                              parents_for=parents_for,
                                              remove=remove)
        return dotgraph.to_string()


class SerializedTasksHandler(NodesFilterMixin, BaseHandler):

    def get_default_nodes(self, cluster):
        return TaskHelper.nodes_to_deploy(cluster)

    @content
    def GET(self, cluster_id):
        """:returns: serialized tasks in json format

        :http: * 200 (serialized tasks returned)
               * 400 (task based deployment is not allowed for cluster)
               * 400 (some nodes belong to different cluster)
               * 404 (cluster is not found)
               * 404 (nodes are not found)
        """
        cluster = self.get_object_or_404(objects.Cluster, cluster_id)
        nodes = self.get_nodes(cluster)
        self.checked_data(self.validator.validate_placement,
                          data=nodes, cluster=cluster)
        tasks = web.input(tasks=None).tasks
        task_ids = tasks.split(',') if tasks else None
        try:
            rst = task_based_deployment.TasksSerializer.serialize(
                cluster,
                nodes,
                objects.Cluster.get_deployment_tasks(cluster),
                task_ids=task_ids
            )
            return {'tasks_directory': rst[0], 'tasks_graph': rst[1]}
        except errors.TaskBaseDeploymentNotAllowed as exc:
            raise self.http(400, msg=six.text_type(exc))
