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

import collections
from itertools import groupby
import os

import netaddr
import six

from sqlalchemy import func
from sqlalchemy import not_
from sqlalchemy.orm import ColumnProperty
from sqlalchemy.orm import object_mapper

from nailgun.api.v1.validators import assignment
from nailgun import consts
from nailgun.db import db
from nailgun.db.sqlalchemy.models import CapacityLog
from nailgun.db.sqlalchemy.models import Cluster
from nailgun.db.sqlalchemy.models import Node
from nailgun.db.sqlalchemy.models import Task
from nailgun import errors
from nailgun.extensions import fire_callback_on_before_deployment_check
from nailgun.extensions.network_manager.checker import NetworkCheck
from nailgun.extensions.network_manager.manager import NetworkManager
from nailgun import lcm
from nailgun.logger import logger
from nailgun import objects
from nailgun.orchestrator import deployment_serializers
from nailgun.orchestrator import orchestrator_graph
from nailgun.orchestrator import provisioning_serializers
from nailgun.orchestrator import stages
from nailgun.orchestrator import task_based_deployment
from nailgun.orchestrator import tasks_serializer
from nailgun.orchestrator import tasks_templates
import nailgun.rpc as rpc
from nailgun.settings import settings
from nailgun.task.fake import FAKE_THREADS
from nailgun.task.helpers import TaskHelper
from nailgun.task.legacy_tasks_adapter import adapt_legacy_tasks
from nailgun.utils import logs as logs_utils
from nailgun.utils.restrictions import VmwareAttributesRestriction
from nailgun.utils.role_resolver import RoleResolver


def make_astute_message(task, method, respond_to, args):
    message = {
        'api_version': settings.VERSION['api'],
        'method': method,
        'respond_to': respond_to,
        'args': args
    }
    message['args']['task_uuid'] = task.uuid
    task.cache = message
    return message


def fake_cast(queue, messages, **kwargs):
    def make_thread(message, join_to=None):
        thread = FAKE_THREADS[message['method']](
            data=message,
            params=kwargs,
            join_to=join_to
        )
        tests = settings.TESTS_WITH_NO_THREADS
        if not tests:
            # Running real thread, if tests is not set or False
            logger.debug("Calling fake thread: data: %s, params: %s",
                         message, kwargs)
            thread.start()
            # thread.name can only be set after thread.start() here.
            # otherwise exception is raised: 'Thread.__init__() not called'
            thread.name = message['method'].upper()
            return thread
        else:
            # For testing purposes, we run the same code synchronously,
            # threading is mocked in test/base.py
            thread.run()

    def make_thread_task_in_orchestrator(message):
        task_in_orchestrator = {
            'args': {'task_uuid': message['args'].get('task_uuid')},
            'respond_to': 'task_in_orchestrator',
            'method': 'task_in_orchestrator'
        }
        make_thread(task_in_orchestrator)

    if isinstance(messages, (list,)):
        thread = None
        for m in messages:
            thread = make_thread(m, join_to=thread)
            make_thread_task_in_orchestrator(m)
    else:
        make_thread(messages)
        make_thread_task_in_orchestrator(messages)


class BaseDeploymentTask(object):
    @classmethod
    def get_deployment_methods(cls, cluster):
        """Get deployment method name based on cluster version

        :param cluster: Cluster db object
        :returns: list of available methods
        """
        methods = []
        if objects.Cluster.is_task_deploy_enabled(cluster):
            methods.append('task_deploy')
        if objects.Release.is_granular_enabled(cluster.release):
            methods.append('granular_deploy')
        else:
            methods.append('deploy')
        return methods

    @classmethod
    def call_deployment_method(cls, transaction, **kwargs):
        """Calls the deployment method with fallback.

        :param transaction: the transaction object
        :param kwargs: the keyword arguments
        """

        error_messages = []
        available_methods = cls.get_deployment_methods(transaction.cluster)
        for method in available_methods:
            try:
                args = getattr(cls, method)(transaction, **kwargs)
                # save tasks history
                if 'tasks_graph' in args:
                    logger.info("tasks history saving is started.")
                    objects.DeploymentHistoryCollection.create(
                        transaction, args['tasks_graph']
                    )
                    logger.info("tasks history saving is finished.")
                return method, args
            except errors.TaskBaseDeploymentNotAllowed as e:
                error_messages.append(six.text_type(e))
                logger.warning(
                    "%s is not allowed, fallback to next method.", method
                )

        raise errors.TaskBaseDeploymentNotAllowed(
            "The task deploy is not allowed because of {0}"
            .format(", ".join(error_messages))
        )

    @classmethod
    def _save_deployment_info(cls, transaction, deployment_info):
        # TODO(bgaifullin) need to rework serializers, it should return dict
        # instead of list
        normalized = {node['uid']: node for node in deployment_info}
        objects.Transaction.attach_deployment_info(transaction, normalized)
        return normalized


class DeploymentTask(BaseDeploymentTask):
    """Task for applying changes to cluster

    LOGIC
    Use cases:
    1. Cluster exists, node(s) added
      If we add one node to existing OpenStack cluster, other nodes may require
      updates (redeployment), but they don't require full system
      reinstallation.
      How to: run deployment for all nodes which system type is target.
      Run provisioning first and then deployment for nodes which are in
      discover system type.
      Q: Should we care about node status (provisioning, error, deploying)?
      A: offline - when node doesn't respond (agent doesn't run, not
                   implemented); let's say user should remove this node from
                   cluster before deployment.
         ready - target OS is loaded and node is Ok, we redeploy
                 ready nodes only if cluster has pending changes i.e.
                 network or cluster attrs were changed
         discover - in discovery mode, provisioning is required
         provisioning - at the time of task execution there should not be such
                        case. If there is - previous provisioning has failed.
                        Possible solution would be to try again to provision
         deploying - the same as provisioning, but stucked in previous deploy,
                     solution - try to deploy. May loose some data if reprovis.
         error - recognized error in deployment or provisioning... We have to
                 know where the error was. If in deployment - reprovisioning
                 may not be a solution (can loose data).
                 If in provisioning - can do provisioning & deployment again
    2. New cluster, just added nodes
      Provision first, and run deploy as second
    3. Remove some and add some another node
      Deletion task will run first and will actually remove nodes, include
      removal from DB.. however removal from DB happens when remove_nodes_resp
      is ran. It means we have to filter nodes and not to run deployment on
      those which are prepared for removal.
    """

    @classmethod
    def message(cls, task, nodes, affected_nodes=None, deployment_tasks=None,
                reexecutable_filter=None, graph_type=None,
                force=False, dry_run=False, **kwargs):
        """Builds RPC message for deployment task.

        :param task: the database task object instance
        :param nodes: the nodes for deployment
        :param affected_nodes: the list of nodes is affected by deployment
        :param deployment_tasks: the list of tasks_ids to execute,
                                 if None, all tasks will be executed
        :param reexecutable_filter: the list of events to find subscribed tasks
        :param force: force
        :param dry_run: dry run
        :param graph_type: deployment graph type
        """
        logger.debug("DeploymentTask.message(task=%s)" % task.uuid)

        task_ids = deployment_tasks or []

        objects.NodeCollection.lock_nodes(nodes)

        for n in nodes:
            if n.pending_roles:
                n.roles = n.roles + n.pending_roles
                n.pending_roles = []

                # If receiver for some reasons didn't update
                # node's status to provisioned when deployment
                # started, we should do it in nailgun
                if n.status in (consts.NODE_STATUSES.deploying,):
                    n.status = consts.NODE_STATUSES.provisioned
                n.progress = 0

        # database commit is required to release nodes lock before
        # serialization started otherwise concurrent nailgun API queries will
        # be locked at database level all the time it is running.
        db().commit()

        deployment_tasks = objects.Cluster.get_deployment_tasks(
            task.cluster, graph_type
        )
        objects.Transaction.attach_tasks_snapshot(
            task,
            deployment_tasks
        )

        # update all puppet tasks with puppet_debug value from settings
        cluster_settings = objects.Cluster.get_editable_attributes(
            task.cluster)
        puppet_debug = cluster_settings['common']['puppet_debug']['value']
        for deploy_task in deployment_tasks:
            if deploy_task['type'] == consts.ORCHESTRATOR_TASK_TYPES.puppet:
                logger.debug("Update puppet task: %s with debug=%s",
                             deploy_task['id'], puppet_debug)
                deploy_task['parameters']['debug'] = puppet_debug

        deployment_mode, message = cls.call_deployment_method(
            task, tasks=deployment_tasks, nodes=nodes,
            affected_nodes=affected_nodes, selected_task_ids=task_ids,
            events=reexecutable_filter, force=force,
            dry_run=dry_run, **kwargs
        )

        # After serialization set pending_addition to False
        for node in nodes:
            node.pending_addition = False

        objects.Transaction.attach_cluster_settings(
            task,
            {
                'editable': objects.Cluster.get_editable_attributes(
                    task.cluster, all_plugins_versions=True)
            }
        )
        objects.Transaction.attach_network_settings(
            task,
            objects.Cluster.get_network_attributes(task.cluster)
        )

        rpc_message = make_astute_message(
            task,
            deployment_mode,
            'deploy_resp',
            message
        )
        db().flush()
        return rpc_message

    @classmethod
    def granular_deploy(cls, transaction, tasks, nodes,
                        affected_nodes, selected_task_ids, events,
                        dry_run=False, **kwargs):
        """Builds parameters for granular deployment.

        :param transaction: the transaction object
        :param tasks: the list of deployment tasks to execute
        :param nodes: the nodes for deployment
        :param affected_nodes: the list of nodes is affected by deployment
        :param selected_task_ids: the list of tasks_ids to execute,
                                   if None, all tasks will be executed
        :param events: the list of events to find subscribed tasks
        :param dry_run: dry run
        :return: the arguments for RPC message
        """
        if dry_run:
            raise errors.DryRunSupportedOnlyByLCM()

        graph = orchestrator_graph.AstuteGraph(transaction.cluster, tasks)
        graph.check()
        graph.only_tasks(selected_task_ids)

        # NOTE(dshulyak) At this point parts of the orchestration can be empty,
        # it should not cause any issues with deployment/progress and was
        # done by design
        role_resolver = RoleResolver(nodes)
        serialized_cluster = deployment_serializers.serialize(
            graph, transaction.cluster, nodes)

        cls._save_deployment_info(transaction, serialized_cluster)

        if affected_nodes:
            graph.reexecutable_tasks(events)
            serialized_cluster.extend(deployment_serializers.serialize(
                graph, transaction.cluster, affected_nodes
            ))
            nodes = nodes + affected_nodes
        pre_deployment = stages.pre_deployment_serialize(
            graph, transaction.cluster, nodes,
            role_resolver=role_resolver)
        post_deployment = stages.post_deployment_serialize(
            graph, transaction.cluster, nodes,
            role_resolver=role_resolver)

        return {
            'deployment_info': serialized_cluster,
            'pre_deployment': pre_deployment,
            'post_deployment': post_deployment
        }

    deploy = granular_deploy

    @classmethod
    def task_deploy(cls, transaction, tasks, nodes, affected_nodes,
                    selected_task_ids, events, dry_run=False,
                    **kwargs):
        """Builds parameters for task based deployment.

        :param transaction: the transaction object
        :param tasks: the list of deployment tasks to execute
        :param nodes: the nodes for deployment
        :param affected_nodes: the list of nodes is affected by deployment
        :param selected_task_ids: the list of tasks_ids to execute,
                                  if None, all tasks will be executed
        :param events: the list of events to find subscribed tasks
        :param dry_run: dry run
        :return:  RPC method name, the arguments for RPC message
        """

        if dry_run:
            raise errors.DryRunSupportedOnlyByLCM()

        task_processor = task_based_deployment.TaskProcessor
        for task in tasks:
            task_processor.ensure_task_based_deploy_allowed(task)

        logger.info("cluster serialization is started.")
        serialized_cluster = deployment_serializers.serialize(
            None, transaction.cluster, nodes
        )
        cls._save_deployment_info(transaction, serialized_cluster)
        logger.info("cluster serialization is finished.")
        tasks_events = events and \
            task_based_deployment.TaskEvents('reexecute_on', events)

        logger.debug("tasks serialization is started.")
        directory, graph = task_based_deployment.TasksSerializer.serialize(
            transaction.cluster, nodes, tasks, affected_nodes,
            selected_task_ids, tasks_events
        )
        logger.info("tasks serialization is finished.")

        return {
            "deployment_info": serialized_cluster,
            "tasks_directory": directory,
            "tasks_graph": graph
        }


class ClusterTransaction(DeploymentTask):

    ignored_types = {
        consts.ORCHESTRATOR_TASK_TYPES.skipped,
        consts.ORCHESTRATOR_TASK_TYPES.group,
        consts.ORCHESTRATOR_TASK_TYPES.stage,
    }

    node_statuses_for_redeploy = {
        consts.NODE_STATUSES.discover,
        consts.NODE_STATUSES.error,
        consts.NODE_STATUSES.provisioned,
        consts.NODE_STATUSES.stopped,
    }

    @classmethod
    def get_deployment_methods(cls, cluster):
        return ['task_deploy']

    @classmethod
    def mark_skipped(cls, tasks, ids_not_to_skip):
        """Change tasks type which ids not present in ids_not_to_skip to skipped

        :param tasks: the list of deployment tasks to execute
        :param ids_not_to_skip: the list of task ids that will be not skipped
        """
        task_ids = set(ids_not_to_skip)

        for task in tasks:
            if (task['id'] not in task_ids and
                    task['type'] not in cls.ignored_types):
                task = task.copy()
                task['type'] = consts.ORCHESTRATOR_TASK_TYPES.skipped

            yield task

    @classmethod
    def is_node_for_redeploy(cls, node):
        """Should node's previous state be cleared.

        :param node: db Node object or None
        :returns: Bool
        """
        if node is None:
            return False

        return node.status in cls.node_statuses_for_redeploy

    @classmethod
    def get_current_state(cls, cluster, nodes, tasks):
        """Current state for deployment.

        :param cluster: Cluster db object
        :param nodes: iterable of Node db objects
        :param tasks: list of tasks which state needed
        :returns: current state {task_name: {node_uid: <astute.yaml>, ...},}

        """
        nodes = {n.uid: n for n in nodes}
        nodes[consts.MASTER_NODE_UID] = None
        tasks_names = [t['id'] for t in tasks
                       if t['type'] not in cls.ignored_types]

        transactions = list(
            objects.TransactionCollection.get_successful_transactions_per_task(
                cluster.id, tasks_names, nodes)
        )

        # sort by transaction.id
        transactions.sort(key=lambda x: x[0].id)

        state = {}
        for transaction, data in groupby(transactions, lambda x: x[0]):
            data = list(data)
            transaction_nodes = [d[1] for d in data]

            deployment_info = objects.Transaction.get_deployment_info(
                transaction, node_uids=transaction_nodes)

            for _, node_uid, task_name in data:
                task_state = state.setdefault(task_name, {})
                task_state.setdefault(node_uid, {})

                if cls.is_node_for_redeploy(nodes.get(node_uid)):
                    task_state[node_uid] = {}
                else:
                    task_state[node_uid] = deployment_info.get(node_uid, {})

        return state

    @classmethod
    def task_deploy(cls, transaction, tasks, nodes, force=False,
                    selected_task_ids=None, dry_run=False, **kwargs):
        logger.info("The cluster transaction is initiated.")
        logger.info("cluster serialization is started.")
        # we should update information for all nodes except deleted
        # TODO(bgaifullin) pass role resolver to serializers

        deployment_info = deployment_serializers.serialize_for_lcm(
            transaction.cluster, nodes
        )
        logger.info("cluster serialization is finished.")

        if selected_task_ids:
            tasks = list(cls.mark_skipped(tasks, selected_task_ids))

        if force:
            current_state = {}
        else:
            current_state = cls.get_current_state(
                transaction.cluster, nodes, tasks)

        expected_state = cls._save_deployment_info(
            transaction, deployment_info
        )
        # Added cluster state
        expected_state[None] = {}

        context = lcm.TransactionContext(expected_state, current_state)
        logger.debug("tasks serialization is started.")
        # TODO(bgaifullin) Primary roles applied in deployment_serializers
        # need to move this code from deployment serializer
        # also role resolver should be created after serialization completed
        role_resolver = RoleResolver(nodes)
        cluster = transaction.cluster

        if objects.Cluster.is_propagate_task_deploy_enabled(cluster):
            logger.info("The legacy tasks adaptation is used.")
            tasks = adapt_legacy_tasks(
                tasks,
                objects.Cluster.get_legacy_plugin_tasks(cluster),
                role_resolver,
            )

        directory, graph, metadata = lcm.TransactionSerializer.serialize(
            context,
            tasks,
            role_resolver,
        )
        logger.info("tasks serialization is finished.")
        return {
            "tasks_directory": directory,
            "tasks_graph": graph,
            "tasks_metadata": metadata,
            "dry_run": dry_run,
        }


class UpdateNodesInfoTask(object):
    """Task for updating nodes.yaml and /etc/hosts on all slaves

    The task is intended to be used in order to update both nodes.yaml and
    /etc/hosts on all slaves. This task aren't going to manage node or cluster
    statuses, and should be used only in one case - when we remove some node
    and don't add anything new (if some new node is added, these tasks will
    be executed without any additional help).
    """

    # the following post deployment tasks are used to update nodes
    # information on all slaves
    _tasks = [
        tasks_serializer.UploadNodesInfo.identity,
        tasks_serializer.UpdateHosts.identity,
    ]

    @classmethod
    def message(cls, task):
        graph = orchestrator_graph.AstuteGraph(task.cluster)
        graph.only_tasks(cls._tasks)

        rpc_message = make_astute_message(
            task,
            'execute_tasks',
            'deploy_resp',
            {
                'tasks': graph.post_tasks_serialize([])
            }
        )
        db().flush()
        return rpc_message


class ProvisionTask(object):

    @classmethod
    def _get_provision_method(cls, cluster):
        """Get provision method name based on cluster attributes

        :param cluster: Cluster db object
        :returns: string - an Astute callable
        """
        cluster_attrs = objects.Attributes.merged_attrs_values(
            cluster.attributes)
        provision_method = cluster_attrs.get('provision', {}).get(
            'method', consts.PROVISION_METHODS.cobbler)

        # NOTE(kozhukalov):
        #
        # Map provisioning method to Astute callable.
        if provision_method == consts.PROVISION_METHODS.cobbler:
            return 'native_provision'
        return 'image_provision'

    @classmethod
    def message(cls, task, nodes_to_provisioning):
        logger.debug("ProvisionTask.message(task=%s)" % task.uuid)
        task = objects.Task.get_by_uid(
            task.id,
            fail_if_not_found=True,
            lock_for_update=True
        )
        objects.NodeCollection.lock_nodes(nodes_to_provisioning)
        serialized_cluster = provisioning_serializers.serialize(
            task.cluster, nodes_to_provisioning)

        for node in nodes_to_provisioning:
            if settings.FAKE_TASKS or settings.FAKE_TASKS_AMQP:
                continue
            logs_utils.prepare_syslog_dir(node)

        rpc_message = make_astute_message(
            task,
            cls._get_provision_method(task.cluster),
            'provision_resp',
            {
                'provisioning_info': serialized_cluster
            }
        )
        db().commit()
        return rpc_message


class DeletionTask(object):

    @classmethod
    def format_node_to_delete(cls, node, mclient_remove=True):
        """Convert node to dict for deletion.

        :param node: Node object
        :param mclient_remove: Boolean flag telling Astute whether to also
            remove node from mclient (True by default). For offline nodes this
            can be set to False to avoid long retrying unsuccessful deletes.
        :return: Dictionary in format accepted by Astute.
        """
        return {
            'id': node.id,
            'uid': node.id,
            'roles': node.roles,
            'slave_name': objects.Node.get_slave_name(node),
            'mclient_remove': mclient_remove,
        }

    # TODO(ikalnitsky): Get rid of this, maybe move to fake handlers?
    @classmethod
    def format_node_to_restore(cls, node):
        """Convert node to dict for restoring, works only in fake mode.

        Fake mode can optionally restore the removed node (this simulates
        the node being rediscovered). This method creates the appropriate
        input for that procedure.
        :param node:
        :return: dict
        """
        # only fake tasks
        if cls.use_fake():
            new_node = {}
            reset_attrs = (
                'id',
                'cluster_id',
                'roles',
                'pending_deletion',
                'pending_addition',
                'group_id',
                'hostname',
            )
            for prop in object_mapper(node).iterate_properties:
                if isinstance(
                    prop, ColumnProperty
                ) and prop.key not in reset_attrs:
                    new_node[prop.key] = getattr(node, prop.key)
            return new_node
        # /only fake tasks

    @classmethod
    def prepare_nodes_for_task(cls, nodes, mclient_remove=True):
        """Format all specified nodes for the deletion task.

        :param nodes:
        :param mclient_remove:
        :return: dict
        """
        nodes_to_delete = []
        nodes_to_restore = []

        for node in nodes:
            nodes_to_delete.append(
                cls.format_node_to_delete(node, mclient_remove=mclient_remove)
            )

            if not node.pending_deletion:
                objects.Node.update(node, {'pending_deletion': True})
                db().flush()

            node_to_restore = cls.format_node_to_restore(node)
            if node_to_restore:
                nodes_to_restore.append(node_to_restore)

        return {
            'nodes_to_delete': nodes_to_delete,
            'nodes_to_restore': nodes_to_restore,
        }

    @classmethod
    def get_task_nodes_for_cluster(cls, cluster):
        return cls.prepare_nodes_for_task(TaskHelper.nodes_to_delete(cluster))

    @classmethod
    def remove_undeployed_nodes_from_db(cls, nodes_to_delete):
        """Removes undeployed nodes from the given list from the DB.

        :param List nodes_to_delete: List of nodes as returned by
            :meth:`DeletionTask.format_node_to_delete`
        :returns: Remaining (deployed) nodes to delete.
        """

        node_names_dict = dict(
            (node['id'], node['slave_name']) for node in nodes_to_delete)

        node_ids = [n['id'] for n in nodes_to_delete]
        discovery_ids = objects.NodeCollection.discovery_node_ids()

        objects.NodeCollection.delete_by_ids(
            set(discovery_ids) & set(node_ids))
        db.commit()

        remaining_nodes_db = db().query(
            Node.id).filter(Node.id.in_(node_names_dict.keys()))

        remaining_nodes_ids = set([
            row[0] for row
            in remaining_nodes_db
        ])

        remaining_nodes = filter(
            lambda node: node['id'] in remaining_nodes_ids,
            nodes_to_delete
        )

        deleted_nodes_ids = set(node_names_dict).difference(
            remaining_nodes_ids)

        slave_names_joined = ', '.join([slave_name
                                        for id, slave_name
                                        in six.iteritems(node_names_dict)
                                        if id in deleted_nodes_ids])
        if len(slave_names_joined):
            logger.info("Nodes are not deployed yet, can't clean MBR: %s",
                        slave_names_joined)

        return remaining_nodes

    @classmethod
    def execute(cls, task, nodes=None, respond_to='remove_nodes_resp',
                check_ceph=False):
        """Call remote Astute method to remove nodes from a cluster

        :param task: Task object
        :param nodes: List of nodes to delete
        :param respond_to: RPC method which receives data from remote method
        :param check_ceph: Boolean flag to tell Astute to run (or not run)
            checks to prevent deletion of OSD nodes. If True this task will
            fail if a node to be deleted has Ceph data on it. This flag must
            be False if deleting all nodes.
        """
        logger.debug("DeletionTask.execute(task=%s, nodes=%s)",
                     task.uuid, nodes)
        task_uuid = task.uuid
        logger.debug("Nodes deletion task is running")

        # TODO(ikalnitsky): remove this, let the flow always go through Astute
        # No need to call Astute if no nodes are specified
        if task.name == consts.TASK_NAMES.cluster_deletion and \
                not (nodes and nodes['nodes_to_delete']):
            logger.debug("No nodes specified, exiting")
            rcvr = rpc.receiver.NailgunReceiver()
            rcvr.remove_cluster_resp(
                task_uuid=task_uuid,
                status=consts.TASK_STATUSES.ready,
                progress=100
            )
            return

        nodes_to_delete = nodes['nodes_to_delete']
        nodes_to_restore = nodes['nodes_to_restore']

        nodes_to_delete = cls.remove_undeployed_nodes_from_db(nodes_to_delete)

        logger.debug(
            "Removing nodes from database and pending them to clean their "
            "MBR: %s",
            ', '.join(node['slave_name'] for node in nodes_to_delete)
        )

        msg_delete = make_astute_message(
            task,
            'remove_nodes',
            respond_to,
            {
                'nodes': nodes_to_delete,
                'check_ceph': check_ceph,
                'engine': {
                    'url': settings.COBBLER_URL,
                    'username': settings.COBBLER_USER,
                    'password': settings.COBBLER_PASSWORD,
                    'master_ip': settings.MASTER_IP,
                }
            }
        )
        db().flush()

        # only fake tasks
        if cls.use_fake() and nodes_to_restore:
            msg_delete['args']['nodes_to_restore'] = nodes_to_restore
        # /only fake tasks

        logger.debug("Calling rpc remove_nodes method with nodes %s",
                     nodes_to_delete)
        rpc.cast('naily', msg_delete)

    @classmethod
    def use_fake(cls):
        return settings.FAKE_TASKS or settings.FAKE_TASKS_AMQP


class DeleteIBPImagesTask(object):

    @classmethod
    def message(cls, task, images_data):
        files = []
        for image_path, image_data in six.iteritems(images_data):
            file_name = os.path.basename(
                six.moves.urllib.parse.urlsplit(image_data['uri']).path)
            files.append(os.path.join(
                settings.PROVISIONING_IMAGES_PATH, file_name)
            )
            if image_path == '/':
                yaml_name = '{0}.{1}'.format(file_name.split('.')[0], 'yaml')
                files.append(os.path.join(
                    settings.PROVISIONING_IMAGES_PATH, yaml_name))

        task_params = {
            'parameters': {
                'cmd': 'rm -f {0}'.format(' '.join(files)),
                'timeout': settings.REMOVE_IMAGES_TIMEOUT,
            }
        }
        rpc_message = make_astute_message(
            task,
            'execute_tasks',
            'remove_images_resp',
            {
                'tasks': [tasks_templates.make_shell_task(
                    [consts.MASTER_NODE_UID], task_params
                )]
            }
        )
        return rpc_message

    @classmethod
    def execute(cls, cluster, image_data):
        task = Task(name=consts.TASK_NAMES.remove_images, cluster=cluster)
        db().add(task)
        db().flush()
        rpc.cast('naily', cls.message(task, image_data))


class StopDeploymentTask(object):

    @classmethod
    def message(cls, task, stop_task):
        nodes_to_stop = db().query(Node).filter(
            Node.cluster_id == task.cluster.id
        ).filter(
            not_(Node.status == 'ready')
        ).yield_per(100)
        rpc_message = make_astute_message(
            task,
            "stop_deploy_task",
            "stop_deployment_resp",
            {
                "stop_task_uuid": stop_task.uuid,
                "nodes": [
                    {
                        'uid': n.uid,
                        'roles': n.roles,
                        'slave_name': objects.Node.get_slave_name(n),
                        'admin_ip': objects.Cluster.get_network_manager(
                            n.cluster
                        ).get_admin_ip_for_node(n)
                    } for n in nodes_to_stop
                ],
                "engine": {
                    "url": settings.COBBLER_URL,
                    "username": settings.COBBLER_USER,
                    "password": settings.COBBLER_PASSWORD,
                    "master_ip": settings.MASTER_IP,
                }
            }
        )
        db().commit()
        return rpc_message

    @classmethod
    def execute(cls, task, deploy_task=None, provision_task=None):
        if provision_task:
            rpc.cast(
                'naily',
                cls.message(task, provision_task),
                service=True
            )
        if deploy_task:
            rpc.cast(
                'naily',
                cls.message(task, deploy_task),
                service=True
            )


class ResetEnvironmentTask(object):

    @classmethod
    def message(cls, task):
        nodes_to_reset = db().query(Node).filter(
            Node.cluster_id == task.cluster.id
        ).yield_per(100)
        rpc_message = make_astute_message(
            task,
            "reset_environment",
            "reset_environment_resp",
            {
                "nodes": [
                    {
                        'uid': n.uid,
                        'roles': n.roles,
                        'slave_name': objects.Node.get_slave_name(n)
                    } for n in nodes_to_reset
                ],
                "engine": {
                    "url": settings.COBBLER_URL,
                    "username": settings.COBBLER_USER,
                    "password": settings.COBBLER_PASSWORD,
                    "master_ip": settings.MASTER_IP,
                }
            }
        )
        db().commit()
        return rpc_message


class RemoveClusterKeys(object):
    """Task that deletes all ssh and ssl data for deployed environment

    Meant to be run after environment reset to make sure that new keys will be
    generated.
    """

    @classmethod
    def message(cls, task):
        rpc_message = make_astute_message(
            task,
            "execute_tasks",
            "reset_environment_resp",
            {
                "tasks": [
                    tasks_templates.make_shell_task(
                        [consts.MASTER_NODE_UID],
                        {
                            "parameters": {
                                "cmd": "rm -rf /var/lib/fuel/keys/{0}".format(
                                    task.cluster.id),
                                "timeout": 30
                            }
                        }
                    )
                ]
            }
        )
        return rpc_message


class RemoveIronicBootstrap(object):
    """Task that deletes Ironic's bootstrap images

    Meant to be run after environment reset to make sure that new images will
    be generated.
    """

    @classmethod
    def message(cls, task):
        rpc_message = make_astute_message(
            task,
            "execute_tasks",
            "reset_environment_resp",
            {
                "tasks": [
                    tasks_templates.make_shell_task(
                        [consts.MASTER_NODE_UID],
                        {
                            "parameters": {
                                "cmd": "rm -rf /var/www/nailgun/bootstrap/"
                                       "ironic/{0}".format(task.cluster.id),
                                "timeout": 30
                            }
                        }
                    )
                ]
            }
        )
        return rpc_message


class ClusterDeletionTask(object):

    @classmethod
    def execute(cls, task):
        logger.debug("Cluster deletion task is running")
        attrs = objects.Attributes.merged_attrs_values(task.cluster.attributes)
        if attrs.get('provision'):
            if (task.cluster.release.operating_system ==
                    consts.RELEASE_OS.ubuntu and
                    attrs['provision']['method'] ==
                    consts.PROVISION_METHODS.image):
                logger.debug("Delete IBP images task is running")
                DeleteIBPImagesTask.execute(
                    task.cluster, attrs['provision']['image_data'])
        else:
            logger.debug("Skipping IBP images deletion task")
        DeletionTask.execute(
            task,
            nodes=DeletionTask.get_task_nodes_for_cluster(task.cluster),
            respond_to='remove_cluster_resp'
        )


class BaseNetworkVerification(object):

    def __init__(self, task, config):
        self.task = task
        self.config = config

    def get_ifaces_on_undeployed_node(self, node, node_json, networks_to_skip):
        """Get list of interfaces and their VLANs to be checked for the node

        :param node: Node object
        :param node_json: dictionary for saving result
        :param networks_to_skip: list of networks, which should be skipped
        :return:
        """
        # Save bonds info to be able to check net-probe results w/o
        # need to access nodes in DB (node can be deleted before the test is
        # completed). This info is needed for non-deployed nodes only.
        bonds = {}
        for bond in node.bond_interfaces:
            bonds[bond.name] = sorted(s.name for s in bond.slaves)
        if bonds:
            node_json['bonds'] = bonds

        for iface in node.nic_interfaces:
            assigned_networks = iface.assigned_networks_list
            # In case of present bond interfaces - collect assigned networks
            # against bonds slave NICs. We should skip bonds with LACP and
            # Round-robin (balance-rr) modes as Fuel do not setup them for
            # network_checker now.
            if iface.bond:
                assigned_networks = iface.bond.assigned_networks_list

            vlans = []
            for ng in assigned_networks:
                # Handle FuelWeb admin network first.
                if ng.group_id is None:
                    vlans.append(0)
                    continue
                if ng.name in networks_to_skip:
                    continue

                data_ng = filter(lambda i: i['name'] == ng.name,
                                 self.config)[0]
                if data_ng['vlans']:
                    vlans.extend(data_ng['vlans'])
                else:
                    # in case absence of vlans net_probe will
                    # send packages on untagged iface
                    vlans.append(0)

            if not vlans:
                continue

            modes_to_skip = (consts.BOND_MODES.l_802_3ad,
                             consts.BOND_MODES.balance_rr)
            if iface.bond and iface.bond.mode in modes_to_skip:
                node_json['excluded_networks'].append(
                    {'iface': iface.name})
            else:
                node_json['networks'].append(
                    {'iface': iface.name, 'vlans': vlans})

    def get_ifaces_on_deployed_node(self, node, node_json, networks_to_skip):
        """Get list of interfaces and their VLANs to be checked for the node

        :param node: Node object
        :param node_json: dictionary for saving result
        :param networks_to_skip: list of networks, which should be skipped
        :return:
        """
        for iface in node.interfaces:
            # In case of present bond interfaces - collect assigned networks
            # against bonds themselves. We can check bonds as they are up on
            # deployed nodes.
            vlans = []
            for ng in iface.assigned_networks_list:
                # Handle FuelWeb admin network first.
                if ng.group_id is None:
                    vlans.append(0)
                    continue
                if ng.name in networks_to_skip:
                    continue

                data_ng = filter(lambda i: i['name'] == ng.name,
                                 self.config)[0]
                if data_ng['vlans']:
                    vlans.extend(data_ng['vlans'])
                else:
                    # in case absence of vlans net_probe will
                    # send packages on untagged iface
                    vlans.append(0)

            if vlans:
                node_json['networks'].append(
                    {'iface': iface.name, 'vlans': vlans})

    def get_message_body(self):
        nodes = []
        offline_nodes = 0
        nodes_w_public = set()
        nodes_wo_dpdk = set()
        for node in self.task.cluster.nodes:
            if node.offline:
                continue
            if objects.Node.should_have_public_with_ip(node):
                nodes_w_public.add(node.id)
            # it's ok to check private networks on non deployed dpdk nodes
            if not (objects.Node.dpdk_enabled(node) and
                    node.status == consts.NODE_STATUSES.ready):
                nodes_wo_dpdk.add(node.id)
        if len(nodes_w_public) == 1:
            # don't check public VLANs if there is the only node with public
            nodes_w_public = set()
        if len(nodes_wo_dpdk) == 1:
            # We cannot check private VLANs if there is the
            # only node without DPDK
            nodes_wo_dpdk = set()
        for node in self.task.cluster.nodes:
            if node.offline:
                offline_nodes += 1
                continue

            node_json = {
                'uid': node.id,
                'name': node.name,
                'status': node.status,
                'networks': [],
                'excluded_networks': [],
            }

            networks_to_skip = []
            if node.id not in nodes_w_public:
                networks_to_skip.append(consts.NETWORKS.public)
            if node.id not in nodes_wo_dpdk:
                # After deployment we can't check traffic on DPDK enabled
                # interface since it's no longer visible in the system. So we
                # should skip "Private" network from network verification
                # after deployment.
                networks_to_skip.append(consts.NETWORKS.private)
            # Check bonds on deployed nodes and check bonds slave NICs on
            # undeployed ones.
            if node.status == consts.NODE_STATUSES.ready:
                self.get_ifaces_on_deployed_node(node, node_json,
                                                 networks_to_skip)
            else:
                self.get_ifaces_on_undeployed_node(node, node_json,
                                                   networks_to_skip)

            nodes.append(node_json)

        return {
            'nodes': nodes,
            'offline': offline_nodes
        }

    def get_message(self):
        msg_body = self.get_message_body()
        message = make_astute_message(
            self.task,
            self.task.name,
            '{0}_resp'.format(self.task.name),
            msg_body
        )
        return message

    def execute(self, task=None):
        # task is there for prev compatibility
        message = self.get_message()

        logger.debug("%s method is called with: %s",
                     self.task.name, message)

        db().commit()
        rpc.cast('naily', message)

    @classmethod
    def enabled(cls, cluster):
        """Verify that subtask is enabled based on cluster configuration."""
        return True


class VerifyNetworksForTemplateMixin(object):

    @staticmethod
    def _get_private_vlan_range(cluster, template):
        if cluster.network_config.segmentation_type == \
                consts.NEUTRON_SEGMENT_TYPES.vlan and \
                'neutron/private' in template['roles']:
            vlan_range = cluster.network_config.vlan_range
            return range(vlan_range[0], vlan_range[1] + 1)
        return None

    @classmethod
    def _add_interface(cls, ifaces, ifname, vlan_ids, bond_name=None):
        ifname, vlan = cls._parse_template_iface(ifname)
        bond_name = bond_name or ifname
        ifaces[bond_name].add(int(vlan))
        if vlan_ids:
            ifaces[bond_name].update(vlan_ids)

        return ifname

    @classmethod
    def _get_transformations(cls, node):
        templates_for_node_mapping = \
            node.network_template['templates_for_node_role']
        cluster = node.cluster

        counter_by_network_template = collections.defaultdict(int)
        for n in cluster.nodes:
            seen_templates = set()
            for r in n.all_roles:
                for net_template in templates_for_node_mapping[r]:
                    # same template can be used for multiple node roles
                    # therefore ensure that they counted only once
                    if net_template not in seen_templates:
                        counter_by_network_template[net_template] += 1
                        seen_templates.add(net_template)

        node_templates = set()
        for role_name in node.all_roles:
            node_templates.update(templates_for_node_mapping[role_name])

        templates = node.network_template['templates']
        for template_name in node_templates:
            if counter_by_network_template[template_name] < 2:
                logger.warning(
                    'We have only one node in cluster with '
                    'network template %s.'
                    ' Verification for this network template will be skipped.',
                    template_name)
                continue

            template = templates[template_name]
            transformations = template['transformations']

            vlan_ids = cls._get_private_vlan_range(cluster, template)
            private_endpoint = template['roles'].get('neutron/private')

            for transformation in transformations:
                if transformation['action'] in ['add-port', 'add-bond']:
                    # After deployment we can't check traffic on DPDK enabled
                    # interface since it's not visible in the system. So we
                    # should skip "Private" network from network verification.
                    if (transformation.get('provider', '') == 'dpdkovs' and
                            node.status == consts.NODE_STATUSES.ready and
                            transformation.get('bridge', '') ==
                            private_endpoint):
                        continue
                yield transformation, vlan_ids

    @staticmethod
    def _parse_template_iface(ifname):
        vlan = 0
        chunks = ifname.rsplit('.', 1)
        if len(chunks) == 2:
            ifname, vlan = chunks

        return ifname, vlan

    @classmethod
    def get_ifaces_from_template_on_undeployed_node(cls, node, node_json):
        """Retrieves list of network interfaces on the undeployed node

        List is retrieved from the network template.
        """
        bonds = collections.defaultdict(list)
        ifaces = collections.defaultdict(set)

        for transformation, vlan_ids in cls._get_transformations(node):
            if transformation['action'] == 'add-port':
                cls._add_interface(ifaces, transformation['name'], vlan_ids)
            elif transformation['action'] == 'add-bond':
                if transformation.get('mode') == consts.BOND_MODES.l_802_3ad:
                    node_json['excluded_networks'].append(
                        transformation['name'])
                else:
                    for ifname in sorted(transformation['interfaces']):
                        ifname = cls._add_interface(ifaces, ifname, vlan_ids)
                        bond_name = transformation['name']
                        bonds[bond_name].append(ifname)

        for if_name, vlans in six.iteritems(ifaces):
            node_json['networks'].append({
                'iface': if_name,
                'vlans': sorted(vlans)
            })

        if bonds:
            node_json['bonds'] = bonds

    @classmethod
    def get_ifaces_from_template_on_deployed_node(cls, node, node_json,
                                                  skip_private):
        """Retrieves list of network interfaces on the deployed node

        List is retrieved from the network template.
        """
        ifaces = collections.defaultdict(set)
        net_manager = objects.Cluster.get_network_manager(node.cluster)
        private_endpoint = \
            net_manager.get_node_endpoint_by_network_role(node,
                                                          'neutron/private')
        for transformation, vlan_ids in cls._get_transformations(node):
            if (skip_private and transformation.get('bridge', '') ==
                    private_endpoint):
                continue
            if transformation['action'] == 'add-port':
                cls._add_interface(ifaces, transformation['name'], vlan_ids)
            elif transformation['action'] == 'add-bond':
                bond_name = transformation['name']
                for ifname in transformation['interfaces']:
                    cls._add_interface(ifaces, ifname, vlan_ids, bond_name)

        for if_name, vlans in six.iteritems(ifaces):
            node_json['networks'].append({
                'iface': if_name,
                'vlans': sorted(vlans)
            })

    def get_ifaces_on_undeployed_node(self, node, node_json, networks_to_skip):
        """Retrieves list of network interfaces on the undeployed node.

        By default list of network interfaces is based on the information
        recieved from the fuel agent unless cluster has network template
        attached. In this case, list of interfaces retrieved from the
        network template.
        """
        if node.network_template:
            self.get_ifaces_from_template_on_undeployed_node(node, node_json)
            return

        super(VerifyNetworksForTemplateMixin, self
              ).get_ifaces_on_undeployed_node(node, node_json,
                                              networks_to_skip)

    def get_ifaces_on_deployed_node(self, node, node_json, networks_to_skip):
        """Retrieves list of network interfaces on the deployed node."""
        if node.network_template:
            self.get_ifaces_from_template_on_deployed_node(
                node, node_json,
                skip_private=consts.NETWORKS.private in networks_to_skip)
            return

        super(VerifyNetworksForTemplateMixin, self
              ).get_ifaces_on_deployed_node(node, node_json, networks_to_skip)


class VerifyNetworksTask(VerifyNetworksForTemplateMixin,
                         BaseNetworkVerification):

    def __init__(self, *args):
        super(VerifyNetworksTask, self).__init__(*args)
        self.subtasks = []

    def add_subtask(self, subtask):
        self.subtasks.append(subtask.get_message())

    def get_message(self):
        message = super(VerifyNetworksTask, self).get_message()
        message['subtasks'] = self.subtasks
        return message


class CheckDhcpTask(VerifyNetworksForTemplateMixin,
                    BaseNetworkVerification):
    """Task for dhcp verification."""


class MulticastVerificationTask(BaseNetworkVerification):

    def __init__(self, task):
        corosync = task.cluster.attributes['editable']['corosync']
        group = corosync['group']['value']
        port = corosync['port']['value']
        conf = {'group': group, 'port': port}
        super(MulticastVerificationTask, self).__init__(task, conf)

    def get_message_body(self):
        # multicast verification should be done only for network which
        # corosync uses for communication - management in our case
        all_nics = objects.cluster.Cluster.get_ifaces_for_network_in_cluster(
            self.task.cluster, 'management')
        return {
            'nodes': [dict(self.config, iface=nic[1], uid=str(nic[0]))
                      for nic in all_nics]
        }

    @classmethod
    def enabled(cls, cluster):
        """Checks whether task is enabled

        Multicast should be enabled only in case 'corosync' section
        is present in editable attributes, which is not the case if cluster
        was upgraded from 5.0
        """
        # TODO(dshulyak) enable it, when it will be possible to upgrade
        # mcagent and network checker for old envs
        return False


class CheckNetworksTask(object):

    @classmethod
    def execute(cls, task, data, check_all_parameters=False):
        """Execute NetworkCheck task

        :param task: Task instance
        :param data: task data
        :param check_all_parameters: bool flag to specify that all network
        checks should be run. Without this flag only check for network
        configuration parameters will be run. For now, check_all_parameters
        is set to True only if task is executed from VerifyNetworks or
        CheckBeforeDeployment tasks.
        """

        checker = NetworkCheck(task, data)
        checker.check_configuration()
        if check_all_parameters:
            checker.check_network_template()
            warn_msgs = checker.check_interface_mapping()
            if warn_msgs:
                task.result = {"warning": warn_msgs}
        db().commit()


class CheckBeforeDeploymentTask(object):

    @classmethod
    def execute(cls, task):
        fire_callback_on_before_deployment_check(task.cluster)

        cls._check_nodes_are_online(task)
        cls._check_nodes_roles(task)
        cls._check_ceph(task)
        cls._check_public_network(task)
        cls._check_vmware_consistency(task)
        cls._validate_network_template(task)

        # TODO(asvechnikov): Make an appropriate versioning of tasks
        if objects.Release.is_nfv_supported(task.cluster.release):
            cls._check_sriov_properties(task)
            cls._check_dpdk_properties(task)

        if objects.Release.is_external_mongo_enabled(task.cluster.release):
            cls._check_mongo_nodes(task)

    @classmethod
    def _check_nodes_are_online(cls, task):
        offline_nodes = db().query(Node).\
            filter(Node.cluster == task.cluster).\
            filter_by(online=False).\
            filter_by(pending_deletion=False)

        offline_nodes_not_ready = [n for n in offline_nodes
                                   if n.status != consts.NODE_STATUSES.ready]
        nodes_to_deploy = TaskHelper.nodes_to_deploy(task.cluster)
        offline_nodes_to_redeploy = [
            n for n in offline_nodes
            if n.status == consts.NODE_STATUSES.ready and n in nodes_to_deploy]

        if offline_nodes_not_ready or offline_nodes_to_redeploy:
            node_names = ','.join(
                map(lambda n: n.full_name,
                    offline_nodes_not_ready + offline_nodes_to_redeploy))
            raise errors.NodeOffline(
                u'Nodes "{0}" are offline.'
                ' Remove them from environment '
                'and try again.'.format(node_names))

    @classmethod
    def _check_nodes_roles(cls, task):
        cluster = task.cluster

        models = objects.Cluster.get_restrictions_models(cluster)

        nodes = TaskHelper.nodes_to_deploy(cluster)
        roles_metadata = objects.Cluster.get_roles(cluster)

        for node in nodes:
            roles = node.all_roles
            # TODO(asvechnikov): move these methods out from validator
            assignment.NodeAssignmentValidator.check_roles_for_conflicts(
                roles, roles_metadata)
            assignment.NodeAssignmentValidator.check_roles_requirement(
                roles, roles_metadata, models)

    @classmethod
    def _check_ceph(cls, task):
        storage = objects.Attributes.merged_attrs(
            task.cluster.attributes
        )['storage']
        for option in storage:
            if '_ceph' in option and\
               storage[option] and\
               storage[option]['value'] is True:
                cls._check_ceph_osds(task)
                return

    @classmethod
    def _check_ceph_osds(cls, task):
        osd_count = len(filter(
            lambda node: 'ceph-osd' in node.all_roles,
            task.cluster.nodes))
        osd_pool_size = int(objects.Attributes.merged_attrs(
            task.cluster.attributes
        )['storage']['osd_pool_size']['value'])
        if osd_count < osd_pool_size:
            raise errors.NotEnoughOsdNodes(
                'Number of OSD nodes (%s) cannot be less than '
                'the Ceph object replication factor (%s). '
                'Please either assign ceph-osd role to more nodes, '
                'or reduce Ceph replication factor in the Settings tab.' %
                (osd_count, osd_pool_size))

    @classmethod
    def _check_public_network(cls, task):
        all_public = \
            objects.Cluster.should_assign_public_to_all_nodes(task.cluster)

        public_networks = filter(
            lambda ng: ng.name == 'public',
            task.cluster.network_groups)

        for public in public_networks:
            nodes = objects.NodeCollection.get_by_group_id(public.group_id)
            if all_public:
                nodes_count = nodes.count()
            else:
                nodes_count = sum(
                    int(objects.Node.should_have_public_with_ip(node)) for
                    node in nodes)
            vip_count = 0
            if task.cluster.is_ha_mode and (
                any('controller' in node.all_roles
                    for node in nodes)
            ):
                # 2 IPs are required for VIPs (1 for haproxy + 1 for vrouter)
                vip_count = 2
            if cls.__network_size(public) < nodes_count + vip_count:
                error_message = cls.__format_network_error(public, nodes_count)
                raise errors.NetworkCheckError(error_message)

    @classmethod
    def __network_size(cls, network):
        return sum(len(netaddr.IPRange(ip_range.first, ip_range.last))
                   for ip_range in network.ip_ranges)

    @classmethod
    def __format_network_error(cls, public, nodes_count):
        return 'Not enough IP addresses. Public network {0} must have ' \
            'at least {1} IP addresses '.format(public.cidr, nodes_count) + \
            'for the current environment.'

    @classmethod
    def _check_mongo_nodes(cls, task):
        """Check for mongo nodes presence in env with external mongo."""
        components = objects.Attributes.merged_attrs(
            task.cluster.attributes).get("additional_components", None)

        if (components and components["ceilometer"]["value"] and
                components["mongo"]["value"] and
                len(objects.Cluster.get_nodes_by_role(
                    task.cluster, 'mongo')) > 0):

                    raise errors.ExtMongoCheckerError

        if (components and components["ceilometer"]["value"] and not
                components["mongo"]["value"] and
                len(objects.Cluster.get_nodes_by_role(
                    task.cluster, 'mongo')) == 0):

                    raise errors.MongoNodesCheckError

    @classmethod
    def _check_vmware_consistency(cls, task):
        """Checks vmware attributes consistency and proper values."""
        attributes = objects.Cluster.get_editable_attributes(task.cluster)
        vmware_attributes = task.cluster.vmware_attributes
        # Old(< 6.1) clusters haven't vmware support
        if vmware_attributes:
            cinder_nodes = [node for node in task.cluster.nodes if
                            'cinder' in node.all_roles]

            if not cinder_nodes:
                logger.info('There is no any node with "cinder" role provided')

            compute_vmware_nodes = [node for node in task.cluster.nodes if
                                    'compute-vmware' in node.all_roles]
            if compute_vmware_nodes:
                cls._check_vmware_nova_computes(compute_vmware_nodes,
                                                vmware_attributes)

            models = {
                'settings': attributes,
                'default': vmware_attributes.editable,
                'cluster': task.cluster,
                'version': settings.VERSION,
                'networking_parameters': task.cluster.network_config
            }

            errors_msg = VmwareAttributesRestriction.check_data(
                models=models,
                metadata=vmware_attributes.editable['metadata'],
                data=vmware_attributes.editable['value'])

            if errors_msg:
                raise errors.CheckBeforeDeploymentError('\n'.join(errors_msg))

    @classmethod
    def _check_vmware_nova_computes(cls, compute_vmware_nodes, attributes):
        """Check that nova computes settings is correct for cluster nodes

        :param compute_vmware_nodes: all node with role compute-vmware that
                                     belongs to cluster
        :type compute_vmware_nodes: list of nailgun.db.sqlalchemy.models.Node
                                    instances
        :param attributes: cluster vmware_attributes
        :type attributes: nailgun.db.sqlalchemy.models.VmwareAttributes
        :raises: errors.CheckBeforeDeploymentError
        """
        compute_nodes_targets = \
            objects.VmwareAttributes.get_nova_computes_target_nodes(attributes)
        compute_nodes_hostnames = set([t['id'] for t in compute_nodes_targets])

        errors_msg = []
        cluster_nodes_hostname = set()
        not_deleted_nodes_from_computes = set()
        not_assigned_nodes_to_computes = set()
        for node in compute_vmware_nodes:
            node_hostname = node.hostname
            if node.pending_deletion:
                if node_hostname in compute_nodes_hostnames:
                    not_deleted_nodes_from_computes.add(node.name)
            elif node_hostname not in compute_nodes_hostnames:
                not_assigned_nodes_to_computes.add(node.name)

            cluster_nodes_hostname.add(node_hostname)

        if not_assigned_nodes_to_computes:
            errors_msg.append(
                "The following compute-vmware nodes are not assigned to "
                "any vCenter cluster: {0}".format(
                    ', '.join(sorted(not_assigned_nodes_to_computes))
                )
            )
        if not_deleted_nodes_from_computes:
            errors_msg.append(
                "The following nodes are prepared for deletion and "
                "couldn't be assigned to any vCenter cluster: {0}".format(
                    ', '.join(sorted(not_deleted_nodes_from_computes))
                ),
            )

        alien_nodes_names = [t['label'] for t in compute_nodes_targets if
                             t['id'] not in cluster_nodes_hostname]
        if alien_nodes_names:
            errors_msg.append(
                "The following nodes don't belong to compute-vmware nodes of "
                "environment and couldn't be assigned to any vSphere cluster: "
                "{0}".format(', '.join(sorted(alien_nodes_names)))
            )

        if errors_msg:
            raise errors.CheckBeforeDeploymentError('\n'.join(errors_msg))

    @classmethod
    def _validate_network_template(cls, task):
        cluster = task.cluster

        if not cluster.network_config.configuration_template:
            return

        template = (cluster.network_config.configuration_template
                    ['adv_net_template'])

        # following loop does two things: checking that networks of each
        # network group from the template belongs to those of particular
        # node group of the cluster and cumulating node roles from the template
        # for further check

        template_node_roles = set()

        for node_group in cluster.node_groups:
            template_for_node_group = (
                template[node_group.name] if node_group.name in template
                else template['default']
            )
            required_nets = set(template_for_node_group['network_assignments'])

            ng_nets = set(ng.name for ng in node_group.networks)
            # Admin net doesn't have a nodegroup so must be added to
            # the default group
            if node_group.is_default:
                ng_nets.add(consts.NETWORKS.fuelweb_admin)

            missing_nets = required_nets - ng_nets
            if missing_nets:
                error_msg = ('The following network groups are missing: {0} '
                             'from node group {1} and are required by the '
                             'current network '
                             'template.'.format(
                                 ','.join(missing_nets),
                                 node_group.name)
                             )
                raise errors.NetworkTemplateMissingNetworkGroup(error_msg)

            template_node_roles.update(
                template_for_node_group['templates_for_node_role'])

            cls._check_dpdk_network_scheme(
                template_for_node_group['network_scheme'], node_group)

        cluster_roles = objects.Cluster.get_assigned_roles(cluster)

        missing_roles = cluster_roles - template_node_roles
        if missing_roles:
            error_roles = ', '.join(missing_roles)
            error_msg = ('Node roles {0} are missing from '
                         'network configuration template').format(error_roles)
            raise errors.NetworkTemplateMissingRoles(error_msg)

        # TODO(akostrikov) https://bugs.launchpad.net/fuel/+bug/1561485

    @classmethod
    def _check_sriov_properties(self, task):
        # check hypervisor type
        h_type = objects.Cluster.get_editable_attributes(
            task.cluster)['common']['libvirt_type']['value']

        for node in task.cluster.nodes:
            if not objects.Node.sriov_enabled(node):
                continue

            if h_type != consts.HYPERVISORS.kvm:
                raise errors.InvalidData(
                    'Only KVM hypervisor works with SRIOV.')

    @classmethod
    def _check_dpdk_network_scheme(cls, network_scheme, node_group):
        """DPDK endpoint provider check

        Check that endpoint with dpdk provider mapped only to neutron/private
        """

        for net_template in network_scheme.values():
            roles = net_template['roles']

            endpoints = set()
            for transformation in net_template['transformations']:
                if (
                        transformation.get('provider') ==
                        consts.NEUTRON_L23_PROVIDERS.dpdkovs
                ):
                    endpoints.add(transformation['bridge'])

            if not endpoints:
                continue

            if len(endpoints) > 1:
                raise errors.NetworkCheckError(
                    'dpdkovs provider can be assigned only for one endpoint.'
                    ' You trying for {}: {}'.format(len(endpoints),
                                                    ', '.join(endpoints))
                )

            endpoint_roles = collections.defaultdict(set)
            for role_name, endpoint in roles.items():
                endpoint_roles[endpoint].add(role_name)

            endpoint = endpoints.pop()
            if endpoint_roles[endpoint] != {'neutron/private'}:
                raise errors.NetworkCheckError(
                    "Only neutron/private network role could be assigned to"
                    " node group '{}' with DPDK".format(
                        node_group.name)
                )

    @classmethod
    def _check_dpdk_properties(self, task):
        dpdk_enabled = False
        for node in task.cluster.nodes:
            if node.pending_deletion:
                continue

            try:
                objects.NodeAttributes.distribute_node_cpus(node)
            except ValueError as e:
                raise errors.InvalidData(
                    "Node '{}': {}".format(node.id, e.message))

            if not objects.Node.dpdk_enabled(node):
                continue

            dpdk_enabled = True

            if not objects.NodeAttributes.is_dpdk_hugepages_enabled(node):
                raise errors.InvalidData(
                    "Hugepages for DPDK are not configured"
                    " for node '{}'".format(node.id))

            if not objects.NodeAttributes.is_nova_hugepages_enabled(node):
                raise errors.InvalidData(
                    "Hugepages for Nova are not configured"
                    " for node '{}'".format(node.id))

        if dpdk_enabled:
            # check hypervisor type
            h_type = objects.Cluster.get_editable_attributes(
                task.cluster)['common']['libvirt_type']['value']

            if h_type != consts.HYPERVISORS.kvm:
                raise errors.InvalidData(
                    'Only KVM hypervisor works with DPDK.')


class GenerateCapacityLogTask(object):
    @classmethod
    def execute(cls, task):
        logger.debug("GenerateCapacityLogTask: task=%s" % task.uuid)
        unallocated_nodes = db().query(Node).filter_by(cluster_id=None).count()
        # Use Node.cluster_id != (None) for PEP-8 accordance.
        allocated_nodes = db().query(Node).\
            filter(Node.cluster_id != (None)).count()
        node_allocation = db().query(Cluster, func.count(Node.id)).\
            outerjoin(Node).group_by(Cluster)
        env_stats = []
        for allocation in node_allocation:
            env_stats.append({'cluster': allocation[0].name,
                              'nodes': allocation[1]})
        allocation_stats = {'allocated': allocated_nodes,
                            'unallocated': unallocated_nodes}

        fuel_data = {
            "release": settings.VERSION['release'],
            "uuid": settings.FUEL_KEY
        }

        roles_stat = {}
        for node in db().query(Node):
            if node.roles:
                roles_list = '+'.join(sorted(node.roles))
                if roles_list in roles_stat:
                    roles_stat[roles_list] += 1
                else:
                    roles_stat[roles_list] = 1

        capacity_data = {'environment_stats': env_stats,
                         'allocation_stats': allocation_stats,
                         'fuel_data': fuel_data,
                         'roles_stat': roles_stat}

        capacity_log = CapacityLog()
        capacity_log.report = capacity_data
        db().add(capacity_log)
        db().flush()

        task.result = {'log_id': capacity_log.id}
        task.status = 'ready'
        task.progress = '100'
        db().commit()


class CheckRepoAvailability(BaseNetworkVerification):

    def get_message(self):
        rpc_message = make_astute_message(
            self.task,
            "check_repositories",
            "check_repositories_resp",
            {
                "nodes": self._get_nodes_to_check(),
                "urls": objects.Cluster.get_repo_urls(self.task.cluster),
            }
        )
        return rpc_message

    def execute(self):
        rpc.cast('naily', self.get_message())

    def _get_nodes_to_check(self):
        nodes = [{'uid': consts.MASTER_NODE_UID}]
        for n in objects.Cluster.get_nodes_not_for_deletion(self.task.cluster):
            if n.online:
                nodes.append({'uid': n.id})
        return nodes


class CheckRepoAvailabilityWithSetup(object):

    def __init__(self, task, config):
        self.task = task
        self.config = config

    @classmethod
    def get_config(cls, cluster):
        urls = objects.Cluster.get_repo_urls(cluster)
        nodes = []
        errors = []
        # if there is nothing to verify - just skip this task
        if not urls:
            return

        all_public = \
            objects.Cluster.should_assign_public_to_all_nodes(cluster)

        public_networks = filter(
            lambda ng: ng.name == 'public', cluster.network_groups)

        for public in public_networks:
            # we are not running this verification for nodes not in discover
            # state
            nodes_with_public_ip = []
            required_ips = 0
            group_nodes = objects.NodeCollection.filter_by(
                None, group_id=public.group_id,
                status=consts.NODE_STATUSES.discover).all()

            for node in group_nodes:

                if not (all_public or
                        objects.Node.should_have_public_with_ip(node)):
                    continue

                ip = NetworkManager.get_ip_by_network_name(node, public.name)
                nodes_with_public_ip.append((node, ip))
                if ip is None:
                    required_ips += 1

            if not nodes_with_public_ip:
                continue

            # we are not doing any allocations during verification
            # just ask for free ips and use them
            free_ips = iter(NetworkManager.get_free_ips(public, required_ips))
            mask = public.cidr.split('/')[1]

            lacp_modes = (
                consts.BOND_MODES.lacp_balance_tcp,
                consts.BOND_MODES.l_802_3ad)

            for node, ip in nodes_with_public_ip:
                if not node.online:
                    continue

                iface = NetworkManager.find_nic_assoc_with_ng(
                    node, public)

                if iface.bond and iface.bond.mode in lacp_modes:
                    errors.append(
                        'Iface {0} on node {1} configured to use '
                        'lacp-balance-tcp mode as part of {2}. Repo '
                        'availability verification for this node '
                        'will be skipped.'.format(
                            iface.name, node.name, iface.bond.name))
                    continue

                ip = ip or next(free_ips)
                node_config = {
                    'addr': '{0}/{1}'.format(ip, mask),
                    'gateway': public.gateway,
                    'vlan': public.vlan_start or 0,
                    'iface': iface.name,
                    'urls': urls,
                    'uid': node.uid}
                nodes.append(node_config)
        # if no nodes will be present - we will skip this task
        return nodes, errors

    def get_message(self):
        return make_astute_message(
            self.task,
            "check_repositories_with_setup",
            "check_repositories_with_setup_resp",
            {
                "nodes": self.config
            }
        )


class CreateStatsUserTask(object):

    @classmethod
    def message(cls, task, primary_controller):
        rpc_message = make_astute_message(
            task,
            'execute_tasks',
            'stats_user_resp',
            {
                'tasks': [{
                    'type': consts.ORCHESTRATOR_TASK_TYPES.puppet,
                    'uids': [primary_controller.id],
                    'parameters': {
                        'puppet_modules': '/etc/puppet/modules',
                        'puppet_manifest': '/etc/puppet/modules/osnailyfacter'
                                           '/modular/keystone'
                                           '/workloads_collector_add.pp',
                        'cwd': '/',
                    }
                }]
            }
        )
        return rpc_message

    @classmethod
    def execute(cls, task, primary_controller):
        rpc.cast(
            'naily',
            cls.message(task, primary_controller)
        )


class RemoveStatsUserTask(object):

    @classmethod
    def message(cls, task, primary_controller):
        rpc_message = make_astute_message(
            task,
            'execute_tasks',
            'stats_user_resp',
            {
                'tasks': [{
                    'type': consts.ORCHESTRATOR_TASK_TYPES.puppet,
                    'uids': [primary_controller.id],
                    'parameters': {
                        'puppet_modules': '/etc/puppet/modules',
                        'puppet_manifest': '/etc/puppet/modules/osnailyfacter'
                                           '/modular/keystone'
                                           '/workloads_collector_remove.pp',
                        'cwd': '/',
                    }
                }]
            }
        )
        return rpc_message

    @classmethod
    def execute(cls, task, primary_controller):
        rpc.cast(
            'naily',
            cls.message(task, primary_controller)
        )


class UpdateOpenstackConfigTask(BaseDeploymentTask):

    @staticmethod
    def task_deploy(transaction, nodes, tasks, task_ids):
        # TODO(akostrikov) https://bugs.launchpad.net/fuel/+bug/1561485
        directory, graph = task_based_deployment.TasksSerializer.serialize(
            transaction.cluster, nodes, tasks, task_ids=task_ids
        )
        return make_astute_message(
            transaction, "task_deploy", "update_config_resp", {
                "tasks_directory": directory,
                "tasks_graph": graph
            }
        )

    @staticmethod
    def granular_deploy(transaction, nodes, tasks, task_ids):
        graph = orchestrator_graph.AstuteGraph(transaction.cluster, tasks)
        graph.only_tasks(task_ids)
        deployment_tasks = graph.stage_tasks_serialize(
            graph.graph.topology, nodes
        )
        return make_astute_message(
            transaction, 'execute_tasks', 'update_config_resp', {
                'tasks': deployment_tasks,
            })

    @classmethod
    def message(cls, task, nodes, graph_type, **kwargs):
        configs = objects.OpenstackConfigCollection.find_configs_for_nodes(
            task.cluster, nodes)
        updated_configs = set()
        for config in configs:
            updated_configs.update(config.configuration)

        if updated_configs:
            updated_configs.add('*')  # '*' means any config
        else:
            raise errors.NoChanges()

        refreshable_tasks = objects.Cluster.get_refreshable_tasks(
            task.cluster, updated_configs, graph_type
        )
        task_ids = {t['id'] for t in refreshable_tasks}
        deployment_tasks = objects.Cluster.get_deployment_tasks(
            task.cluster, graph_type)
        return cls.call_deployment_method(
            task, tasks=deployment_tasks, nodes=nodes, task_ids=task_ids
        )[1]


if settings.FAKE_TASKS or settings.FAKE_TASKS_AMQP:
    rpc.cast = fake_cast
