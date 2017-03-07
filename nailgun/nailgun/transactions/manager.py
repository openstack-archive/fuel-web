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
from nailgun import notifier
from nailgun import objects
from nailgun.objects.serializers import node as node_serializers
from nailgun.orchestrator import deployment_serializers
from nailgun import rpc
from nailgun.settings import settings
from nailgun.task import helpers
from nailgun.task import legacy_tasks_adapter
from nailgun.utils import dict_update
from nailgun.utils import get_in
from nailgun.utils import mule
from nailgun.utils import resolvers
from nailgun import yaql_ext


_DEFAULT_NODE_ATTRIBUTES = {
    'on_success': {'status': consts.NODE_STATUSES.ready},
    'on_error': {'status': consts.NODE_STATUSES.error},
    'on_stop': {'status': consts.NODE_STATUSES.stopped},
}

_DEFAULT_NODE_FILTER = (
    "not $.pending_addition and not $.pending_deletion and "
    "($.status in [ready, provisioned, stopped] or $.error_type = 'deploy')"
)


def _get_node_attributes(graph, kind):
    r = get_in(graph, kind, 'node_attributes')
    if r is None:
        r = _DEFAULT_NODE_ATTRIBUTES[kind]
    return r


def make_astute_message(transaction, context, graph, node_resolver):
    directory, tasks, metadata = lcm.TransactionSerializer.serialize(
        context, graph['tasks'], node_resolver
    )

    metadata['node_statuses_transitions'] = {
        'successful': _get_node_attributes(graph, 'on_success'),
        'failed': _get_node_attributes(graph, 'on_error'),
        'stopped': _get_node_attributes(graph, 'on_stop')
    }
    subgraphs = transaction.cache.get('subgraphs')
    if subgraphs:
        metadata['subgraphs'] = subgraphs
    objects.DeploymentHistoryCollection.create(transaction, tasks)

    return {
        'api_version': settings.VERSION['api'],
        'method': 'task_deploy',
        'respond_to': 'transaction_resp',
        'args': {
            'task_uuid': transaction.uuid,
            'tasks_directory': directory,
            'tasks_graph': tasks,
            'tasks_metadata': metadata,
            'dry_run': transaction.cache.get('dry_run'),
            'noop_run': transaction.cache.get('noop_run'),
            'debug': transaction.cache.get('debug'),
        }
    }


class try_transaction(object):
    """Wraps transaction in some sort of pre-/post- actions.

    So far it includes the following actions:

      * mark transaction as failed if exception has been raised;
      * create an action log record on start/finish;

    :param transaction: a transaction instance to be wrapped
    """

    def __init__(self, transaction, on_error):
        self._transaction = transaction
        self._on_error = on_error

    def __enter__(self):
        logger.debug("Transaction %s starts assembling.", self._transaction.id)
        return self._transaction

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_val:
            logger.error(
                "Transaction %s failed.",
                self._transaction.id, exc_info=(exc_type, exc_val, exc_tb)
            )
            return self._on_error(self._transaction, six.text_type(exc_val))
        else:
            logger.debug(
                "Transaction %s finish assembling.", self._transaction.id
            )
        return False


class TransactionsManager(object):

    # We're moving towards everything-is-a-graph approach where there's
    # no place for transaction names. From now on we're going to use
    # transaction's attributes (e.g. graph_type, dry_run) to find out
    # what this transaction about. Still, we need to specify transaction
    # name until we move everything to graphs.
    task_name = consts.TASK_NAMES.deployment

    def __init__(self, cluster_id):
        self.cluster_id = cluster_id

    def execute(self, graphs, dry_run=False, noop_run=False, force=False,
                debug=False, subgraphs=None):
        """Start a new transaction with a given parameters.

        Under the hood starting a new transaction means serialize a lot of
        stuff and assemble an Astute message. So at the end of method we
        either send an Astute message with execution flow or mark transaction
        as failed.

        :param graphs: a list of graph type to be run on a given nodes
        :param dry_run: run a new transaction in dry run mode
        :param noop_run: run a new transaction in noop run mode
        :param force: re-evaluate tasks's conditions as it's a first run
        :param debug: enable debug mode for tasks executor
        """
        logger.info(
            'Start new transaction: '
            'cluster=%d graphs=%s dry_run=%d noop_run=%s force=%d ',
            self.cluster_id, graphs, dry_run, noop_run, force
        )

        # So far we don't support parallel execution of transactions within
        # one cluster. So we need to fail quickly in there's transaction
        # in-progress.
        cluster = self._acquire_cluster()

        # Unfortunately, by historical reasons UI polls 'deployment' tasks
        # for cluster and expects there's only one. That one is considered
        # as latest and is used for tracking progress and showing error
        # message. So we have came up with the following workaround:
        #
        #  * each new transaction we mark previous ones as deleted
        #  * /tasks endpoint doesn't return "deleted" transactions in response
        #  * /transactions endpoint does return "deleted" transactions
        #
        # FIXME: We must provide a way to get latest transaction with its
        #        sub-transactions via API. Once it's done, and UI uses it -
        #        we can safely remove this workaround.
        _remove_obsolete_tasks(cluster)

        transaction = objects.Transaction.create({
            'name': consts.TASK_NAMES.deploy,
            'cluster_id': self.cluster_id,
            'status': consts.TASK_STATUSES.running,
            'dry_run': dry_run or noop_run,
        })
        objects.Transaction.on_start(transaction)
        helpers.TaskHelper.create_action_log(transaction)

        for graph in graphs:
            # 'dry_run' flag is a part of transaction, so we can restore its
            # value anywhere. That doesn't apply to 'force' flag, because it
            # affects only context calculation. However we need somehow to
            # pass it down in order to build context once first graph
            # is executed (much much latter, when we call continue_ in RPC
            # receiver).
            cache = graph.copy()
            cache['force'] = force
            cache['noop_run'] = noop_run
            cache['dry_run'] = dry_run
            cache['debug'] = debug
            cache['subgraphs'] = subgraphs

            transaction.create_subtask(
                self.task_name,
                status=consts.TASK_STATUSES.pending,
                dry_run=dry_run or noop_run,
                graph_type=graph['type'],
                # We need to save input parameters in cache, so RPC receiver
                # can use them to do further serialization.
                #
                # FIXME: Consider to use a separate set of columns.
                cache=cache,
            )

        # We need to commit transaction because asynchronous call below might
        # be executed in separate process or thread.
        db().commit()

        self.continue_(transaction)
        return transaction

    def continue_(self, transaction):
        """Pick next pending task and send it to execution.

        Transaction may consist of a number of sub-transactions. We should
        execute them one-by-one. This method allows to pick first pending
        transaction and send it to execution.

        :param transaction: a top-level transaction to continue
        :return: True if sub transaction will be started, otherwise False
        """
        sub_transaction = next((
            sub_transaction
            for sub_transaction in transaction.subtasks
            if sub_transaction.status == consts.TASK_STATUSES.pending), None)

        if sub_transaction is None:
            # there is no sub-transaction, so we can close this transaction
            self.success(transaction)
            return False

        with try_transaction(transaction, self.fail):
            # uWSGI mule is a separate process, and that means it won't share
            # our DB session. Hence, we can't pass fetched DB instances to the
            # function we want to be executed in mule, so let's proceed with
            # unique identifiers.
            mule.call_task_manager_async(
                self.__class__,
                '_execute_async',
                self.cluster_id,
                sub_transaction.id,
            )
        return True

    def process(self, transaction, report):
        """Process feedback from executor (Astute).

        :param transaction: a transaction to handle (sibling, not top level)
        :param report: a report to process
        """
        nodes = report.get('nodes', [])
        error = report.get('error')
        status = report.get('status')
        progress = report.get('progress')

        # Report may contain two virtual nodes: master and cluster ('None').
        # Since we don't have them in database we should ensure we ain't
        # going to update them.
        nodes_params = {
            str(node['uid']): node for node in nodes
            if node['uid'] not in (consts.MASTER_NODE_UID, None)
        }
        nodes_instances = objects.NodeCollection.lock_for_update(
            objects.NodeCollection.filter_by_list(
                None, 'id', nodes_params.keys(), order_by=('id', )
            )
        ).all()

        _update_nodes(transaction, nodes_instances, nodes_params)
        _update_history(transaction, nodes)
        _update_transaction(transaction, status, progress, error)

        if status in (consts.TASK_STATUSES.error, consts.TASK_STATUSES.ready):
            objects.Transaction.on_finish(transaction, status)
            helpers.TaskHelper.update_action_log(transaction)
            if transaction.parent:
                # if transaction is completed successfully,
                #  we've got to initiate the next one in the chain
                if status == consts.TASK_STATUSES.ready:
                    self.continue_(transaction.parent)
                else:
                    self.fail(transaction.parent, error)

    def success(self, transaction):
        objects.Transaction.on_finish(transaction, consts.TASK_STATUSES.ready)
        helpers.TaskHelper.update_action_log(transaction)
        _update_cluster_status(transaction)
        notifier.notify(
            consts.NOTIFICATION_TOPICS.done,
            "Graph execution has been successfully completed."
            "You can check deployment history for detailed information.",
            transaction.cluster_id,
            None,
            task_uuid=transaction.uuid
        )

    def fail(self, transaction, reason):
        objects.Transaction.on_finish(
            transaction, consts.TASK_STATUSES.error, message=reason
        )
        helpers.TaskHelper.update_action_log(transaction)
        for sub_transaction in transaction.subtasks:
            if sub_transaction.status == consts.TASK_STATUSES.pending:
                # on_start and on_finish called to properly handle
                # status transition
                objects.Transaction.on_start(sub_transaction)
                objects.Transaction.on_finish(
                    sub_transaction, consts.TASK_STATUSES.error, "Aborted"
                )

        _update_cluster_status(transaction)
        notifier.notify(
            consts.NOTIFICATION_TOPICS.error,
            "Graph execution failed with error: '{0}'."
            "Please check deployment history for more details."
            .format(reason),
            transaction.cluster_id,
            None,
            task_uuid=transaction.uuid
        )
        return True

    def _execute_async(self, sub_transaction_id):
        sub_transaction = objects.Transaction.get_by_uid(sub_transaction_id)

        with try_transaction(sub_transaction.parent, self.fail):
            self._execute_sync(sub_transaction)

        # Since the whole function is executed in separate process, we must
        # commit all changes in order to do not lost them.
        db().commit()

    def _execute_sync(self, sub_transaction):
        cluster = sub_transaction.cluster
        graph = objects.Cluster.get_deployment_graph(
            cluster, sub_transaction.graph_type
        )
        nodes = _get_nodes_to_run(
            cluster,
            graph.get('node_filter'),
            sub_transaction.cache.get('nodes')
        )
        logger.debug(
            "execute graph %s on nodes %s",
            sub_transaction.graph_type, [n.id for n in nodes]
        )
        # we should initialize primary roles for cluster before
        # role resolve has been created
        objects.Cluster.set_primary_tags(cluster, nodes)
        resolver = resolvers.TagResolver(nodes)
        _adjust_graph_tasks(
            graph,
            cluster,
            resolver,
            sub_transaction.cache.get('tasks'))

        context = lcm.TransactionContext(
            _get_expected_state(cluster, nodes),
            _get_current_state(
                cluster, nodes, graph['tasks'],
                sub_transaction.cache.get('force')
            ))

        _prepare_nodes(nodes, sub_transaction.dry_run, context.new['nodes'])

        # Attach desired state to the sub transaction, so when we continue
        # our top-level transaction, the new state will be calculated on
        # top of this.
        _dump_expected_state(sub_transaction, context.new, graph['tasks'])

        message = make_astute_message(
            sub_transaction, context, graph, resolver
        )
        objects.Transaction.on_start(sub_transaction)
        helpers.TaskHelper.create_action_log(sub_transaction)

        # Once rpc.cast() is called, the message is sent to Astute. By
        # that moment all transaction instanced must exist in database,
        # otherwise we may get wrong result due to RPC receiver won't
        # found entry to update.
        db().commit()
        rpc.cast('naily', [message])

    def _acquire_cluster(self):
        cluster = objects.Cluster.get_by_uid(
            self.cluster_id, fail_if_not_found=True, lock_for_update=True
        )
        running_tasks = objects.TaskCollection.all_in_progress(
            cluster_id=cluster.id
        )
        # TODO(bgaifullin) need new lock approach for cluster
        if objects.TaskCollection.count(running_tasks):
            raise errors.DeploymentAlreadyStarted()
        return cluster


def _remove_obsolete_tasks(cluster):
    all_tasks = objects.TaskCollection.all_not_deleted()
    cluster_tasks = objects.TaskCollection.filter_by(
        all_tasks, cluster_id=cluster.id
    )
    finished_tasks = objects.TaskCollection.filter_by_list(
        cluster_tasks, 'status',
        [consts.TASK_STATUSES.ready, consts.TASK_STATUSES.error]
    )
    finished_tasks = objects.TaskCollection.order_by(finished_tasks, 'id')

    for task in finished_tasks:
        objects.Task.delete(task)

    db().flush()


def _get_nodes_to_run(cluster, node_filter, ids=None):
    # Trying to run tasks on offline nodes will lead to error, since most
    # probably MCollective is unreachable. In order to avoid that, we need
    # to select only online nodes.
    nodes = objects.NodeCollection.filter_by(
        None, cluster_id=cluster.id, online=True)

    if node_filter is None:
        node_filter = _DEFAULT_NODE_FILTER

    if ids is None and node_filter:
        logger.debug("applying nodes filter: %s", node_filter)
        # TODO(bgaifullin) Need to implement adapter for YAQL
        # to direct query data from DB instead of query all data from DB
        yaql_exp = yaql_ext.get_default_engine()(
            '$.where({0}).select($.id)'.format(node_filter)
        )
        ids = yaql_exp.evaluate(
            data=objects.NodeCollection.to_list(
                nodes,
                # TODO(bgaifullin) remove hard-coded list of fields
                # the field network_data causes fail of following
                # cluster serialization because it modifies attributes of
                # node and this update will be stored in DB.
                serializer=node_serializers.NodeSerializerForDeployment
            ),
            context=yaql_ext.create_context(
                add_extensions=True, yaqlized=False
            )
        )

    if ids is not None:
        logger.debug("filter by node_ids: %s", ids)
        nodes = objects.NodeCollection.filter_by_list(nodes, 'id', ids)

    return objects.NodeCollection.lock_for_update(
        objects.NodeCollection.order_by(nodes, 'id')
    ).all()


def _adjust_graph_tasks(graph, cluster, node_resolver, names=None):
    if objects.Cluster.is_propagate_task_deploy_enabled(cluster):
        # TODO(bgaifullin) move this code into Cluster.get_deployment_tasks
        # after dependency from role_resolver will be removed
        if graph['type'] == consts.DEFAULT_DEPLOYMENT_GRAPH_TYPE:
            plugin_tasks = objects.Cluster.get_legacy_plugin_tasks(cluster)
        else:
            plugin_tasks = None

        graph['tasks'] = list(legacy_tasks_adapter.adapt_legacy_tasks(
            graph['tasks'], plugin_tasks, node_resolver
        ))

    if names:
        # filter task by names, mark all other task as skipped
        task_ids = set(names)
        tasks = graph['tasks']
        for idx, task in enumerate(tasks):
            if (task['id'] not in task_ids and
                    task['type'] not in consts.INTERNAL_TASKS):

                task = task.copy()
                task['type'] = consts.ORCHESTRATOR_TASK_TYPES.skipped
                tasks[idx] = task


def _is_node_for_redeploy(node):
    if node is None:
        return False
    if node.pending_addition:
        return True

    return node.error_type or node.status in (
        consts.NODE_STATUSES.discover,
        consts.NODE_STATUSES.error,
        consts.NODE_STATUSES.provisioned,
        consts.NODE_STATUSES.stopped,
    )


def _get_current_state(cluster, nodes, tasks, force=False):
    # In case of force=True, the current state is {} which means: behave like
    # an intial deployment.
    if force:
        return {}

    nodes = {n.uid: n for n in nodes}
    nodes[consts.MASTER_NODE_UID] = None
    tasks_names = [
        t['id'] for t in tasks if t['type'] not in consts.INTERNAL_TASKS
    ]

    txs = objects.TransactionCollection.get_successful_transactions_per_task(
        cluster.id, tasks_names, nodes
    )
    state = {}
    for tx, data in itertools.groupby(txs, lambda x: x[0]):
        node_ids = []
        common_attrs = {}
        deferred_state = {}
        for _, node_id, task_name in data:
            t_state = state.setdefault(task_name, {
                'nodes': {}, 'common': common_attrs
            })
            if _is_node_for_redeploy(nodes.get(node_id)):
                t_state['nodes'][node_id] = {}
            else:
                t_state['nodes'][node_id] = deferred_state.setdefault(
                    node_id, {}
                )
                node_ids.append(node_id)

        deployment_info = objects.Transaction.get_deployment_info(
            tx, node_uids=node_ids)

        common_attrs.update(deployment_info['common'])
        dict_update(deferred_state, deployment_info['nodes'], level=2)

    return state


def _get_expected_state(cluster, nodes):
    info = deployment_serializers.serialize_for_lcm(cluster, nodes)
    info['nodes'] = {n['uid']: n for n in info['nodes']}
    # Added cluster state
    info['nodes'][None] = {}
    return info


def _dump_expected_state(transaction, state, tasks):
    cluster = transaction.cluster

    objects.Transaction.attach_deployment_info(transaction, state)
    objects.Transaction.attach_tasks_snapshot(transaction, tasks)
    objects.Transaction.attach_cluster_settings(
        transaction,
        {
            'editable': objects.Cluster.get_editable_attributes(cluster, True)
        })
    objects.Transaction.attach_network_settings(
        transaction, objects.Cluster.get_network_attributes(cluster))

    db().flush()


def _prepare_nodes(nodes, dry_run, involved_node_ids):
    for node in (node for node in nodes if node.uid in involved_node_ids):
        # set progress to show that node is in progress state
        node.progress = 1
        if not dry_run:
            node.error_type = None
            node.error_msg = None


def _update_nodes(transaction, nodes_instances, nodes_params):
    allow_update = {
        'name',
        'status',
        'hostname',
        'kernel_params',
        'pending_addition',
        'pending_deletion',
        'error_msg',
        'online',
        'progress',
    }

    # dry-run transactions must not update nodes except progress column
    if transaction.dry_run:
        allow_update = {'progress'}

    for node in nodes_instances:
        node_params = nodes_params.pop(node.uid)

        for param in allow_update.intersection(node_params):
            if param == 'status':
                new_status = node_params['status']
                if new_status == 'deleted':
                    # the deleted is special status which causes
                    # to delete node from cluster
                    objects.Node.remove_from_cluster(node)
                elif new_status == 'error':
                    # TODO(bgaifullin) do not persist status in DB
                    node.status = new_status
                    node.error_type = node_params.get(
                        'error_type', consts.NODE_ERRORS.deploy
                    )
                    node.progress = 100
                    # Notification on particular node failure
                    notifier.notify(
                        consts.NOTIFICATION_TOPICS.error,
                        u"Node '{0}' failed: {1}".format(
                            node.name,
                            node_params.get('error_msg', "Unknown error")
                        ),
                        cluster_id=transaction.cluster_id,
                        node_id=node.uid,
                        task_uuid=transaction.uuid
                    )
                elif new_status == 'ready':
                    # TODO(bgaifullin) need to remove pengind roles concept
                    node.roles = list(set(node.roles + node.pending_roles))
                    node.pending_roles = []
                    node.progress = 100
                    node.status = new_status
                else:
                    node.status = new_status
            else:
                setattr(node, param, node_params[param])
    db.flush()

    if nodes_params:
        logger.warning(
            "The following nodes are not found: %s",
            ",".join(sorted(nodes_params.keys()))
        )


def _update_history(transaction, nodes):
    for node in nodes:
        if {'deployment_graph_task_name', 'task_status'}.issubset(node.keys()):
            objects.DeploymentHistory.update_if_exist(
                transaction.id,
                node['uid'],
                node['deployment_graph_task_name'],
                node['task_status'],
                node.get('summary'),
                node.get('custom'),
            )
    db.flush()


def _update_transaction(transaction, status, progress, message):
    data = {}
    if status:
        data['status'] = status
    if message:
        data['message'] = message
    data['progress'] = _calculate_progress(transaction, progress)
    if data:
        objects.Transaction.update(transaction, data)

    if transaction.parent and data['progress']:
        logger.debug("Updating parent task: %s.", transaction.parent.uuid)
        siblings = transaction.parent.subtasks
        total_progress = sum(x.progress for x in siblings)
        objects.Transaction.update(transaction.parent, {
            'progress': total_progress // len(siblings)
        })


def _calculate_progress(transaction, progress):
    if progress is not None:
        return progress
    else:
        return helpers.TaskHelper.recalculate_deployment_task_progress(
            transaction)


def _update_cluster_status(transaction):
    if transaction.dry_run:
        return

    nodes = objects.NodeCollection.filter_by(
        None, cluster_id=transaction.cluster_id
    )
    failed_nodes = objects.NodeCollection.filter_by_not(nodes, error_type=None)
    not_ready_nodes = objects.NodeCollection.filter_by_not(
        nodes, status=consts.NODE_STATUSES.ready
    )
    # if all nodes are ready - cluster has operational status
    # otherwise cluster has partially deployed status
    if (objects.NodeCollection.count(failed_nodes) or
            objects.NodeCollection.count(not_ready_nodes)):
        status = consts.CLUSTER_STATUSES.partially_deployed
    else:
        status = consts.CLUSTER_STATUSES.operational

    objects.Cluster.update(transaction.cluster, {'status': status})
