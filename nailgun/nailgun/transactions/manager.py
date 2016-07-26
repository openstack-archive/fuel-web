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

import itertools

import six

from nailgun import consts
from nailgun.db import db
from nailgun import errors
from nailgun import lcm
from nailgun.logger import logger
from nailgun import objects
from nailgun.orchestrator import deployment_serializers
from nailgun import rpc
from nailgun.settings import settings
from nailgun.task import helpers
from nailgun.task import legacy_tasks_adapter
from nailgun.utils import dict_update
from nailgun.utils import mule
from nailgun.utils.role_resolver import RoleResolver


if settings.FAKE_TASKS or settings.FAKE_TASKS_AMQP:
    from nailgun.task.task import fake_cast
    rpc.cast = fake_cast


class exception_handler(object):
    def __init__(self, transaction, suppress=False):
        self.transaction = transaction
        self.suppress = suppress

    def __enter__(self):
        logger.info("Transaction %s starts assembling.", self.transaction.id)
        self.log_item = helpers.TaskHelper.create_action_log(self.transaction)
        return self.transaction

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_val:
            logger.error(
                "Transaction %s failed",
                self.transaction.id, exc_info=(exc_type, exc_val, exc_tb)
            )

            data = {
                'status': consts.TASK_STATUSES.error,
                'progress': 100,
                'message': str(exc_val)
            }
            # update task entity with given data
            objects.Task.update(self.transaction, data)
            helpers.TaskHelper.update_action_log(
                self.transaction, self.log_item
            )
        else:
            logger.info(
                "Transaction %s finish assembling.", self.transaction.id
            )
        db().flush()
        return self.suppress


class TransactionsManager(object):
    task_name = consts.TASK_NAMES.deployment

    nonfunctional_types = {
        consts.ORCHESTRATOR_TASK_TYPES.skipped,
        consts.ORCHESTRATOR_TASK_TYPES.group,
        consts.ORCHESTRATOR_TASK_TYPES.stage,
    }

    def __init__(self, cluster_id=None):
        self.cluster_id = cluster_id

    def execute(self, nodes, graph_types=None, dry_run=False, **kwargs):
        """Execute the specified graphs in selected nodes."""

        logger.info(
            "Trying to start %s transaction at cluster '%s'",
            'noop' if dry_run else '', self.cluster_id
        )

        cluster = self._acquire_cluster()
        self._remove_obsolete_tasks(cluster)

        if not graph_types:
            graph_types = [consts.DEFAULT_DEPLOYMENT_GRAPH_TYPE]
        elif isinstance(graph_types, six.string_types):
            graph_types = graph_types.split(",")

        logger.info("graphs to execute: %s", ', '.join(graph_types))
        if 'task_names' in kwargs:
            logger.info("selected tasks: %s", ','.join(kwargs['task_names']))

        if nodes:
            logger.info("selected nodes: %s", ', '.join(n.uid for n in nodes))

        transaction = objects.Transaction.create({
            "name": self.task_name,
            "cluster_id": self.cluster_id,
            "status": consts.TASK_STATUSES.pending,
            "dry_run": dry_run
        })

        # need to commit, because asynchronous call might be executed
        # in separate process or thread
        db().commit()

        with exception_handler(transaction, suppress=True):
            mule.call_task_manager_async(
                self.__class__,
                '_execute_async_safe',
                self.cluster_id,
                transaction_id=transaction.id,
                node_ids=nodes and [n.id for n in nodes],
                graph_types=graph_types,
                dry_run=dry_run,
                **kwargs
            )
        return transaction

    def _execute_async_safe(self, transaction_id, **kwargs):
        transaction = objects.Transaction.get_by_uid(
            transaction_id, fail_if_not_found=True
        )
        with exception_handler(transaction, suppress=True):
            self._execute_async(transaction, **kwargs)

        # persistent state of task
        db().commit()

    def _execute_async(self, transaction, node_ids, graph_types, **kwargs):
        cluster = transaction.cluster
        nodes = objects.NodeCollection.filter_by(None, cluster_id=cluster.id)
        if node_ids:
            nodes = objects.NodeCollection.filter_by_list(
                nodes, 'id', node_ids
            )

        nodes = objects.NodeCollection.lock_for_update(
            objects.NodeCollection.order_by(nodes, 'id')
        ).all()

        for n in nodes:
            # bump progress to show that node in progress state
            n.progress = 1
            # reset node error
            n.error_msg = ""
            # TODO(bgaifullin) roles shall apply at end of transaction
            if n.pending_roles:
                n.roles = n.roles + n.pending_roles
                n.pending_roles = []

        db().flush()

        node_resolver = RoleResolver(nodes)
        task_names = kwargs.get('task_names')
        tasks_per_graph = {
            n: self._get_tasks(cluster, node_resolver, task_names, n)
            for n in graph_types
        }

        expected = self._get_expected_state(cluster, nodes)
        if kwargs.get('force'):
            current = {}
        else:
            current = self._get_current_state(
                cluster, nodes, itertools.chain(*tasks_per_graph.values())
            )

        self._dump_expected_state(transaction, expected)

        context = lcm.TransactionContext(expected, current)

        messages = []
        dry_run = kwargs.get('dry_run', False)
        for graph_type, tasks in tasks_per_graph.items():
            sub_transaction = transaction.create_subtask(
                self.task_name,
                status=consts.TASK_STATUSES.pending,
                dry_run=dry_run,
                graph_type=graph_type
            )
            with exception_handler(sub_transaction):
                objects.Transaction.attach_tasks_snapshot(
                    sub_transaction, tasks
                )
                msg = self._assemble_astute_message(
                    sub_transaction, context, tasks, node_resolver
                )
                msg['args']['dry_run'] = dry_run
                messages.append(msg)

        if messages:
            # persistent state in database before pass message into astute
            db().commit()
            rpc.cast('naily', messages)

    @classmethod
    def _is_node_for_redeploy(cls, node):
        """Should node's previous state be cleared.

        :param node: db Node object or None
        :returns: Bool
        """
        if node is None:
            return False
        return (
            node.pending_addition or
            node.status == consts.NODE_STATUSES.discover
        )

    def _acquire_cluster(self):
        cluster = objects.Cluster.get_by_uid(
            self.cluster_id, fail_if_not_found=True, lock_for_update=True
        )

        cluster_tasks = objects.TaskCollection.get_by_cluster_id(
            cluster_id=cluster.id
        )
        cluster_tasks = objects.TaskCollection.filter_by(
            cluster_tasks, name=self.task_name
        )
        cluster_tasks = objects.TaskCollection.filter_by_list(
            cluster_tasks,
            'status',
            [consts.TASK_STATUSES.pending, consts.TASK_STATUSES.running]
        )
        # TODO(bgaifullin) need new lock approach for cluster
        if objects.TaskCollection.count(cluster_tasks):
            raise errors.DeploymentAlreadyStarted()
        return cluster

    @classmethod
    def _remove_obsolete_tasks(cls, cluster):
        cluster_tasks = objects.TaskCollection.get_cluster_tasks(
            cluster_id=cluster.id
        )
        cluster_tasks = objects.TaskCollection.order_by(cluster_tasks, 'id')
        for task in cluster_tasks:
            if task.status in (consts.TASK_STATUSES.ready,
                               consts.TASK_STATUSES.error):
                objects.Task.delete(task)
        db().flush()

    @classmethod
    def _get_current_state(cls, cluster, nodes, tasks):
        """Current state for deployment.

        :param cluster: Cluster db object
        :param nodes: iterable of Node db objects
        :param tasks: list of tasks which state needed
        :returns: current state {task_name: {node_uid: <astute.yaml>, ...},}
        """

        nodes = {n.uid: n for n in nodes}
        nodes[consts.MASTER_NODE_UID] = None
        tasks_names = [
            t['id'] for t in tasks if t['type'] not in cls.nonfunctional_types
        ]

        transactions_obj = objects.TransactionCollection
        transaction_obj = objects.Transaction

        txs = transactions_obj.get_successful_transactions_per_task(
            cluster.id, tasks_names, nodes
        )
        state = {}
        for tx, data in itertools.groupby(txs, lambda x: x[0]):
            node_ids = []
            deferred_state = {}
            for _, node_id, task_name in data:
                t_state = state.setdefault(task_name, {})
                if cls._is_node_for_redeploy(nodes.get(node_id)):
                    t_state[node_id] = {}
                else:
                    t_state[node_id] = deferred_state.setdefault(node_id, {})
                    node_ids.append(node_id)

            dict_update(
                deferred_state,
                # we always attach deployment info to super transaction
                # to avoid duplication,
                # but history is attached to sub-transaction
                transaction_obj.get_deployment_info(
                    tx.parent, node_uids=node_ids
                ),
                level=2
            )
        return state

    @classmethod
    def _get_expected_state(cls, cluster, nodes):
        info = deployment_serializers.serialize_for_lcm(cluster, nodes)
        info = {n['uid']: n for n in info}
        # Added cluster state
        info[None] = {}
        return info

    @classmethod
    def _dump_expected_state(cls, transaction, state):
        transaction_db = objects.Transaction
        cluster_db = objects.Cluster
        cluster = transaction.cluster

        transaction_db.attach_deployment_info(transaction, state)
        transaction_db.attach_cluster_settings(
            transaction,
            {
                'editable': cluster_db.get_editable_attributes(cluster, True)
            }
        )
        transaction_db.attach_network_settings(
            transaction, cluster_db.get_network_attributes(cluster)
        )
        db().flush()

    @classmethod
    def _get_tasks(cls, cluster, node_resolver, names, graph_type):
        """Gets deployment tasks from graph."""
        tasks = objects.Cluster.get_deployment_tasks(cluster, graph_type)
        if objects.Cluster.is_propagate_task_deploy_enabled(cluster):
            # TODO(bgaifullin) move this code into Cluster.get_deployment_tasks
            # after dependency from role_resolver will be removed
            if graph_type == consts.DEFAULT_DEPLOYMENT_GRAPH_TYPE:
                plugin_tasks = objects.Cluster.get_legacy_plugin_tasks(cluster)
            else:
                plugin_tasks = None

            tasks = list(legacy_tasks_adapter.adapt_legacy_tasks(
                tasks, plugin_tasks, node_resolver
            ))
        if names:
            # filter task by names, mark all other task as skipped
            task_ids = set(names)
            for idx, task in enumerate(tasks):
                if (task['id'] not in task_ids and
                        task['type'] not in cls.nonfunctional_types):

                    task = task.copy()
                    task['type'] = consts.ORCHESTRATOR_TASK_TYPES.skipped
                    tasks[idx] = task

        return tasks

    @classmethod
    def _assemble_astute_message(cls, tx, context, tasks, node_resolver):
        directory, graph, metadata = lcm.TransactionSerializer.serialize(
            context, tasks, node_resolver
        )
        objects.DeploymentHistoryCollection.create(tx, graph)
        return {
            'api_version': settings.VERSION['api'],
            'method': 'task_deploy',
            'respond_to': 'transaction_resp',
            'args': {
                'task_uuid': tx.uuid,
                'tasks_directory': directory,
                'tasks_graph': graph,
                'tasks_metadata': metadata,
            }
        }
