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

import six
import web

from nailgun.api.v1.handlers.base import BaseHandler
from nailgun.api.v1.handlers.base import handle_errors
from nailgun.api.v1.handlers.base import serialize
from nailgun.api.v1.handlers.base import TransactionExecutorHandler
from nailgun.api.v1.handlers.base import validate
from nailgun.api.v1.validators.cluster import ProvisionSelectedNodesValidator
from nailgun.api.v1.validators.node import DeploySelectedNodesValidator
from nailgun.api.v1.validators.node import NodeDeploymentValidator
from nailgun.api.v1.validators.node import NodesFilterValidator
from nailgun.api.v1.validators.orchestrator_graph import \
    GraphSolverVisualizationValidator

from nailgun.logger import logger

from nailgun import consts
from nailgun import errors
from nailgun import objects
from nailgun import utils

from nailgun.orchestrator import deployment_serializers
from nailgun.orchestrator import graph_visualization
from nailgun.orchestrator import orchestrator_graph
from nailgun.orchestrator import provisioning_serializers
from nailgun.orchestrator.stages import post_deployment_serialize
from nailgun.orchestrator.stages import pre_deployment_serialize
from nailgun.orchestrator import task_based_deployment
from nailgun.task.helpers import TaskHelper
from nailgun.task import manager
from nailgun.task import task


class NodesFilterMixin(object):
    validator = NodesFilterValidator

    def get_default_nodes(self, cluster):
        """Method should be overriden and return list of nodes"""
        raise NotImplementedError('Please Implement this method')

    def get_nodes(self, cluster):
        """If nodes selected in filter then return them

        else return default nodes
        """
        nodes = self.get_param_as_set('nodes', default=[])
        if not nodes:
            return self.get_default_nodes(cluster) or []

        node_ids = self.checked_data(data=nodes)
        nodes_obj = self.get_objects_list_or_404(
            objects.NodeCollection,
            node_ids
        )
        self.checked_data(self.validator.validate_placement,
                          data=nodes_obj, cluster=cluster)
        return nodes_obj


class DefaultOrchestratorInfo(NodesFilterMixin, BaseHandler):
    """Base class for default orchestrator data

    Need to redefine serializer variable
    """

    @handle_errors
    @validate
    @serialize
    def GET(self, cluster_id):
        """:returns: JSONized default data which will be passed to orchestrator

        :http: * 200 (OK)
               * 400 (some nodes belong to different cluster or not assigned)
               * 404 (cluster not found in db)
        """
        cluster = self.get_object_or_404(objects.Cluster, cluster_id)
        nodes = self.get_nodes(cluster)

        return self._serialize(cluster, nodes)

    def _serialize(self, cluster, nodes):
        raise NotImplementedError('Override the method')

    def get_default_nodes(self, cluster):
        return objects.Cluster.get_nodes_not_for_deletion(cluster)


class OrchestratorInfo(BaseHandler):
    """Base class for replaced data."""

    def get_orchestrator_info(self, cluster):
        """Method should return data which will be passed to orchestrator"""
        raise NotImplementedError('Please Implement this method')

    def update_orchestrator_info(self, cluster, data):
        """Method should override data which will be passed to orchestrator"""
        raise NotImplementedError('Please Implement this method')

    @handle_errors
    @validate
    @serialize
    def GET(self, cluster_id):
        """:returns: JSONized data which will be passed to orchestrator

        :http: * 200 (OK)
               * 404 (cluster not found in db)
        """
        cluster = self.get_object_or_404(objects.Cluster, cluster_id)
        return self.get_orchestrator_info(cluster)

    @handle_errors
    @validate
    @serialize
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

    @handle_errors
    @validate
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


class DefaultDeploymentInfo(DefaultOrchestratorInfo):

    def _serialize(self, cluster, nodes):
        if objects.Release.is_lcm_supported(cluster.release):
            serialized = deployment_serializers.serialize_for_lcm(
                cluster, nodes, ignore_customized=True
            )
        else:
            graph = orchestrator_graph.AstuteGraph(cluster)
            serialized = deployment_serializers.serialize(
                graph, cluster, nodes, ignore_customized=True)

        return _deployment_info_in_compatible_format(
            serialized, utils.parse_bool(web.input(split='0').split)
        )


class DefaultPrePluginsHooksInfo(DefaultOrchestratorInfo):

    def _serialize(self, cluster, nodes):
        if objects.Release.is_lcm_supported(cluster.release):
            raise self.http(
                405, msg="The plugin hooks are not supported anymore."
            )
        graph = orchestrator_graph.AstuteGraph(cluster)
        return pre_deployment_serialize(graph, cluster, nodes)


class DefaultPostPluginsHooksInfo(DefaultOrchestratorInfo):

    def _serialize(self, cluster, nodes):
        if objects.Release.is_lcm_supported(cluster.release):
            raise self.http(
                405, msg="The plugin hooks are not supported anymore."
            )
        graph = orchestrator_graph.AstuteGraph(cluster)
        return post_deployment_serialize(graph, cluster, nodes)


class ProvisioningInfo(OrchestratorInfo):

    def get_orchestrator_info(self, cluster):
        return objects.Cluster.get_provisioning_info(cluster)

    def update_orchestrator_info(self, cluster, data):
        return objects.Cluster.replace_provisioning_info(cluster, data)


class DeploymentInfo(OrchestratorInfo):

    def get_orchestrator_info(self, cluster):
        return _deployment_info_in_compatible_format(
            objects.Cluster.get_deployment_info(cluster),
            utils.parse_bool(web.input(split='0').split)
        )

    def update_orchestrator_info(self, cluster, data):
        if isinstance(data, list):
            # FIXME(bgaifullin) need to update fuelclient
            # use uid common to determine cluster attributes
            nodes = {n['uid']: n for n in data if 'uid' in n}
            custom_info = {
                'common': nodes.pop('common', {}),
                'nodes': nodes
            }
            new_format = False
        else:
            custom_info = data
            new_format = True

        return _deployment_info_in_compatible_format(
            objects.Cluster.replace_deployment_info(cluster, custom_info),
            new_format
        )


class RunMixin(object):
    """Provides dry_run or noop_run parameters."""

    def get_dry_run(self):
        return utils.parse_bool(web.input(dry_run='0').dry_run)

    def get_noop_run(self):
        return utils.parse_bool(web.input(noop_run='0').noop_run)


class SelectedNodesBase(NodesFilterMixin, TransactionExecutorHandler):
    """Base class for running task manager on selected nodes."""

    graph_type = None

    def get_transaction_options(self, cluster, options):
        if not objects.Release.is_lcm_supported(cluster.release):
            # this code is actual only for lcm
            return

        graph_type = options.get('graph_type') or self.graph_type
        graph = graph_type and objects.Cluster.get_deployment_graph(
            cluster, graph_type
        )

        if not graph or not graph['tasks']:
            return

        nodes_ids = self.get_param_as_set('nodes', default=None)
        if nodes_ids is not None:
            nodes = self.get_objects_list_or_404(
                objects.NodeCollection, nodes_ids
            )
            nodes_ids = [n.id for n in nodes]

        if graph:
            return {
                'noop_run': options.get('noop_run'),
                'dry_run': options.get('dry_run'),
                'force': options.get('force'),
                'graphs': [{
                    'type': graph['type'],
                    'nodes': nodes_ids,
                    'tasks': options.get('deployment_tasks')
                }]
            }

    def handle_task(self, cluster, **kwargs):
        if objects.Release.is_lcm_supported(cluster.release):
            # this code is actual only if cluster is LCM ready
            try:
                transaction_options = self.get_transaction_options(
                    cluster, kwargs
                )
            except errors.NailgunException as e:
                logger.exception("Failed to get transaction options.")
                raise self.http(400, six.text_type(e))

            if transaction_options:
                return self.start_transaction(cluster, transaction_options)

        nodes = self.get_nodes(cluster)
        try:
            task_manager = self.task_manager(cluster_id=cluster.id)
            task = task_manager.execute(nodes, **kwargs)
        except Exception as exc:
            logger.exception(
                u'Cannot execute %s task nodes: %s',
                self.task_manager.__name__, ','.join(n.uid for n in nodes)
            )
            raise self.http(400, msg=six.text_type(exc))

        self.raise_task(task)

    @handle_errors
    @validate
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

    graph_type = 'provision'

    def get_default_nodes(self, cluster):
        return TaskHelper.nodes_to_provision(cluster)

    @handle_errors
    @validate
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

    graph_type = consts.DEFAULT_DEPLOYMENT_GRAPH_TYPE

    def get_default_nodes(self, cluster):
        return TaskHelper.nodes_to_deploy(cluster)

    def get_graph_type(self):
        return web.input(graph_type=None).graph_type or None

    def get_force(self):
        return utils.parse_bool(web.input(force='0').force)

    def get_nodes(self, cluster):
        nodes_to_deploy = super(
            BaseDeploySelectedNodes, self).get_nodes(cluster)
        self.validate(cluster, nodes_to_deploy, self.get_graph_type())
        return nodes_to_deploy

    def validate(self, cluster, nodes_to_deploy, graph_type=None):
        self.checked_data(self.validator.validate_nodes_to_deploy,
                          nodes=nodes_to_deploy, cluster_id=cluster.id)

        self.checked_data(self.validator.validate_release, cluster=cluster,
                          graph_type=graph_type)


class DeploySelectedNodes(BaseDeploySelectedNodes, RunMixin):
    """Handler for deployment selected nodes."""

    @handle_errors
    @validate
    def PUT(self, cluster_id):
        """:returns: JSONized Task object.

        :http: * 200 (task successfully executed)
               * 202 (task scheduled for execution)
               * 400 (data validation failed)
               * 404 (cluster or nodes not found in db)
        """
        cluster = self.get_object_or_404(objects.Cluster, cluster_id)
        return self.handle_task(
            cluster=cluster,
            graph_type=self.get_graph_type(),
            dry_run=self.get_dry_run(),
            noop_run=self.get_noop_run(),
            force=self.get_force()
        )


class DeploySelectedNodesWithTasks(BaseDeploySelectedNodes, RunMixin):

    validator = NodeDeploymentValidator

    @handle_errors
    @validate
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
            cluster=cluster,
            graph_type=self.get_graph_type())
        return self.handle_task(
            cluster,
            deployment_tasks=data,
            graph_type=self.get_graph_type(),
            dry_run=self.get_dry_run(),
            noop_run=self.get_noop_run(),
            force=self.get_force()
        )


class TaskDeployGraph(BaseHandler):

    validator = GraphSolverVisualizationValidator

    @handle_errors
    @validate
    def GET(self, cluster_id):
        """:returns: DOT representation of deployment graph.

        :http: * 200 (graph returned)
               * 404 (cluster not found in db)
               * 400 (failed to get graph)
        """
        web.header('Content-Type', 'text/vnd.graphviz', unique=True)
        graph_type = web.input(graph_type=None).graph_type or None

        cluster = self.get_object_or_404(objects.Cluster, cluster_id)
        tasks = objects.Cluster.get_deployment_tasks(cluster, graph_type)
        graph = orchestrator_graph.GraphSolver(tasks)

        tasks = self.get_param_as_set('tasks', default=[])
        parents_for = web.input(parents_for=None).parents_for
        remove = self.get_param_as_set('remove')

        if tasks:
            tasks = self.checked_data(
                self.validator.validate,
                data=list(tasks),
                cluster=cluster,
                graph_type=graph_type)
            logger.debug('Tasks used in dot graph %s', tasks)

        if parents_for:
            parents_for = self.checked_data(
                self.validator.validate_task_presence,
                data=parents_for,
                graph=graph)
            logger.debug('Graph with predecessors for %s', parents_for)

        if remove:
            remove = list(remove)
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
        if objects.Release.is_lcm_supported(cluster.release):
            return objects.Cluster.get_nodes_not_for_deletion(cluster).all()
        return TaskHelper.nodes_to_deploy(cluster)

    @handle_errors
    @validate
    @serialize
    def GET(self, cluster_id):
        """:returns: serialized tasks in json format

        :http: * 200 (serialized tasks returned)
               * 400 (task based deployment is not allowed for cluster)
               * 400 (some nodes belong to different cluster or not assigned)
               * 404 (cluster is not found)
               * 404 (nodes are not found)
        """
        cluster = self.get_object_or_404(objects.Cluster, cluster_id)
        nodes = self.get_nodes(cluster)
        graph_type = web.input(graph_type=None).graph_type or None
        task_ids = self.get_param_as_set('tasks')

        try:
            if objects.Release.is_lcm_supported(cluster.release):
                # in order to do not repeat quite complex logic, we create
                # a temporary task (transaction) instance and pass it to
                # task_deploy serializer.
                transaction = objects.Transaction.model(
                    name=consts.TASK_NAMES.deployment, cluster=cluster)
                rv = task.ClusterTransaction.task_deploy(
                    transaction,
                    objects.Cluster.get_deployment_tasks(cluster, graph_type),
                    nodes,
                    selected_task_ids=task_ids)

                objects.Transaction.delete(transaction)
                return rv

            # for old clusters we have to fallback to old serializers
            serialized_tasks = task_based_deployment.TasksSerializer.serialize(
                cluster,
                nodes,
                objects.Cluster.get_deployment_tasks(cluster, graph_type),
                task_ids=task_ids
            )
            return {'tasks_directory': serialized_tasks[0],
                    'tasks_graph': serialized_tasks[1]}

        except errors.TaskBaseDeploymentNotAllowed as exc:
            raise self.http(400, msg=six.text_type(exc))


def _deployment_info_in_compatible_format(depoyment_info, separate):
    # FIXME(bgaifullin) need to update fuelclient
    # uid 'common' because fuelclient expects list of dicts, where
    # each dict contains field 'uid', which will be used as name of file
    data = depoyment_info.get('nodes', [])
    common = depoyment_info.get('common')
    if common:
        if separate:
            data.append(dict(common, uid='common'))
        else:
            for i, node_info in enumerate(data):
                data[i] = utils.dict_merge(common, node_info)
    return data
