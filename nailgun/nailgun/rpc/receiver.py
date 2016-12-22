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
import copy
import datetime
import itertools
import logging
import os
import six

from oslo_serialization import jsonutils
from sqlalchemy import or_

from nailgun import consts
from nailgun import notifier
from nailgun import objects
from nailgun.settings import settings
from nailgun import transactions

from nailgun.consts import TASK_STATUSES
from nailgun.db import db
from nailgun.db.sqlalchemy.models import IPAddr
from nailgun.db.sqlalchemy.models import Node
from nailgun.db.sqlalchemy.models import Release
from nailgun.extensions.network_manager import connectivity_check
from nailgun.extensions.network_manager import utils as net_utils
from nailgun.objects.plugin import ClusterPlugin
from nailgun.task.helpers import TaskHelper
from nailgun.utils import logs as logs_utils
from nailgun.utils import reverse


logger = logging.getLogger('receiverd')


class NailgunReceiver(object):

    @classmethod
    def acquire_lock(cls, transaction_uuid):
        """Get transaction and acquire exclusive access.

        :param transaction_uuid: the unique identifier of transaction
        :return: transaction object or None if there is no task with such uid
        """
        # use transaction object to get removed by UI tasks
        transaction = objects.Transaction.get_by_uuid(transaction_uuid)
        if not transaction:
            logger.error("Task '%s' was removed.", transaction_uuid)
            return

        # the lock order is following: cluster, task
        if transaction.cluster:
            objects.Cluster.get_by_uid(
                transaction.cluster_id,
                fail_if_not_found=True, lock_for_update=True
            )

        # read transaction again to ensure
        # that it was not removed in other session
        transaction = objects.Transaction.get_by_uuid(
            transaction_uuid, lock_for_update=True)
        if not transaction:
            logger.error(
                "Race condition detected, task '%s' was removed.",
                transaction_uuid
            )
        return transaction

    @classmethod
    def remove_nodes_resp(cls, **kwargs):
        logger.info(
            "RPC method remove_nodes_resp received: %s" %
            jsonutils.dumps(kwargs)
        )
        task_uuid = kwargs.get('task_uuid')
        nodes = kwargs.get('nodes') or []
        error_nodes = kwargs.get('error_nodes') or []
        inaccessible_nodes = kwargs.get('inaccessible_nodes') or []
        error_msg = kwargs.get('error')
        status = kwargs.get('status')
        progress = kwargs.get('progress')
        if status in [consts.TASK_STATUSES.ready, consts.TASK_STATUSES.error]:
            progress = 100

        # locking task
        task = cls.acquire_lock(task_uuid)
        if not task:
            return False

        # locking nodes
        all_nodes = itertools.chain(nodes, error_nodes, inaccessible_nodes)
        all_nodes_ids = [
            node['id'] if 'id' in node else node['uid']
            for node in all_nodes
        ]
        locked_nodes = objects.NodeCollection.order_by(
            objects.NodeCollection.filter_by_list(
                None,
                'id',
                all_nodes_ids,
            ),
            'id'
        )
        objects.NodeCollection.lock_for_update(locked_nodes).all()

        def get_node_id(n):
            return n.get('id', int(n.get('uid')))

        nodes_to_delete_ids = [get_node_id(n) for n in nodes]

        if len(inaccessible_nodes) > 0:
            inaccessible_node_ids = [
                get_node_id(n) for n in inaccessible_nodes]

            logger.warn(u'Nodes %s not answered by RPC, removing from db',
                        inaccessible_nodes)

            nodes_to_delete_ids.extend(inaccessible_node_ids)

        for node in objects.NodeCollection.filter_by_id_list(
                None, nodes_to_delete_ids):
            logs_utils.delete_node_logs(node)

        objects.NodeCollection.delete_by_ids(nodes_to_delete_ids)

        for node in error_nodes:
            node_db = objects.Node.get_by_uid(node['uid'])
            if not node_db:
                logger.error(
                    u"Failed to delete node '%s' marked as error from Astute:"
                    " node doesn't exist", str(node)
                )
            else:
                node_db.pending_deletion = False
                node_db.status = 'error'
                db().add(node_db)
                node['name'] = node_db.name
        db().flush()

        success_msg = u"No nodes were removed"
        err_msg = u"No errors occurred"
        if nodes_to_delete_ids:
            success_msg = u"Successfully removed {0} node(s)".format(
                len(nodes_to_delete_ids)
            )
            notifier.notify("done", success_msg)
        if error_nodes:
            err_msg = u"Failed to remove {0} node(s): {1}".format(
                len(error_nodes),
                ', '.join(
                    [n.get('name') or "ID: {0}".format(n['uid'])
                        for n in error_nodes])
            )
            notifier.notify("error", err_msg)
        if not error_msg:
            error_msg = ". ".join([success_msg, err_msg])
        data = {
            'status': status,
            'progress': progress,
            'message': error_msg,
        }
        objects.Task.update(task, data)

        cls._update_action_log_entry(status, task.name, task_uuid, nodes)

    @classmethod
    def remove_cluster_resp(cls, **kwargs):
        logger.info(
            "RPC method remove_cluster_resp received: %s" %
            jsonutils.dumps(kwargs)
        )
        task_uuid = kwargs.get('task_uuid')

        # in remove_nodes_resp method all objects are already locked
        cls.remove_nodes_resp(**kwargs)

        task = objects.Task.get_by_uuid(task_uuid, fail_if_not_found=True)
        cluster = task.cluster

        if task.status in ('ready',):
            logger.debug("Removing environment itself")
            cluster_name = cluster.name

            ips = db().query(IPAddr).filter(
                IPAddr.network.in_([n.id for n in cluster.network_groups])
            )
            for ip in ips:
                db().delete(ip)
            db().flush()

            objects.Task.delete(task)
            for task_ in cluster.tasks:
                if task_ != task:
                    objects.Transaction.delete(task_)

            objects.Cluster.delete(cluster)

            notifier.notify(
                "done",
                u"Environment '{0}' is deleted".format(
                    cluster_name
                )
            )

        elif task.status in ('error',):
            cluster.status = 'error'
            db().add(cluster)
            db().flush()
            if not task.message:
                task.message = "Failed to delete nodes:\n{0}".format(
                    cls._generate_error_message(
                        task,
                        error_types=('deletion',)
                    )
                )
            notifier.notify(
                "error",
                task.message,
                cluster.id
            )

    @classmethod
    def remove_images_resp(cls, **kwargs):
        logger.info(
            "RPC method remove_images_resp received: %s",
            jsonutils.dumps(kwargs)
        )
        status = kwargs.get('status')
        task_uuid = kwargs['task_uuid']
        task = cls.acquire_lock(task_uuid)
        if not task:
            return

        if status == consts.TASK_STATUSES.ready:
            logger.info("IBP images from deleted cluster have been removed")
        elif status == consts.TASK_STATUSES.error:
            logger.error("Removing IBP images failed: task_uuid %s", task_uuid)

        objects.Task.update(task, {'status': status})

    @classmethod
    def transaction_resp(cls, **kwargs):
        logger.info(
            "RPC method transaction_resp received: %s", jsonutils.dumps(kwargs)
        )

        # TODO(bgaifullin) move lock to transaction manager
        transaction = cls.acquire_lock(kwargs.pop('task_uuid', None))
        if not transaction:
            return
        manager = transactions.TransactionsManager(transaction.cluster.id)
        manager.process(transaction, kwargs)

    @classmethod
    def deploy_resp(cls, **kwargs):
        logger.info(
            "RPC method deploy_resp received: %s" %
            jsonutils.dumps(kwargs)
        )
        task_uuid = kwargs.get('task_uuid')
        nodes = kwargs.get('nodes') or []
        message = kwargs.get('error')
        status = kwargs.get('status')
        progress = kwargs.get('progress')

        task = cls.acquire_lock(task_uuid)
        if not task:
            return

        if not status:
            status = task.status

        # for deployment we need just to pop
        # if there no node except master - then just skip updating
        # nodes status, for the task itself astute will send
        # message with descriptive error
        nodes_by_id = {str(n['uid']): n for n in nodes}
        master = nodes_by_id.pop(consts.MASTER_NODE_UID, {})
        nodes_by_id.pop('None', {})

        if nodes_by_id:
            # lock nodes for updating so they can't be deleted
            q_nodes = objects.NodeCollection.filter_by_id_list(
                None,
                nodes_by_id,
            )
            q_nodes = objects.NodeCollection.order_by(q_nodes, 'id')
            db_nodes = objects.NodeCollection.lock_for_update(q_nodes).all()
        else:
            db_nodes = []

        # Dry run deployments should not actually lead to update of
        # nodes' statuses
        if task.name != consts.TASK_NAMES.dry_run_deployment and \
                not task.get('dry_run'):

            # First of all, let's update nodes in database
            for node_db in db_nodes:
                node = nodes_by_id.pop(node_db.uid)
                update_fields = (
                    'error_msg',
                    'error_type',
                    'status',
                    'progress',
                    'online'
                )
                for param in update_fields:
                    if param in node:
                        logger.debug("Updating node %s - set %s to %s",
                                     node['uid'], param, node[param])
                        setattr(node_db, param, node[param])

                        if param == 'progress' and node.get('status') == \
                                'error' or node.get('online') is False:
                            # If failure occurred with node
                            # it's progress should be 100
                            node_db.progress = 100
                            # Setting node error_msg for offline nodes
                            if node.get('online') is False \
                                    and not node_db.error_msg:
                                node_db.error_msg = u"Node is offline"
                            # Notification on particular node failure
                            notifier.notify(
                                consts.NOTIFICATION_TOPICS.error,
                                u"Failed to {0} node '{1}': {2}".format(
                                    consts.TASK_NAMES.deploy,
                                    node_db.name,
                                    node_db.error_msg or "Unknown error"
                                ),
                                cluster_id=task.cluster_id,
                                node_id=node['uid'],
                                task_uuid=task_uuid
                            )
            if nodes_by_id:
                logger.warning("The following nodes are not found: %s",
                               ",".join(sorted(nodes_by_id)))

        for node in nodes:
            if node.get('deployment_graph_task_name') \
                    and node.get('task_status'):
                objects.DeploymentHistory.update_if_exist(
                    task.id,
                    node['uid'],
                    node['deployment_graph_task_name'],
                    node['task_status'],
                    node.get('summary', {}),
                    node.get('custom', {})
                )
        db().flush()

        if nodes and not progress:
            progress = TaskHelper.recalculate_deployment_task_progress(task)

        # full error will be provided in next astute message
        if master.get('status') == consts.TASK_STATUSES.error:
            status = consts.TASK_STATUSES.error

        cls._update_task_status(task, status, progress, message, db_nodes)
        cls._update_action_log_entry(status, task.name, task_uuid, nodes)

    @classmethod
    def provision_resp(cls, **kwargs):
        logger.info(
            "RPC method provision_resp received: %s" %
            jsonutils.dumps(kwargs))

        task_uuid = kwargs.get('task_uuid')
        message = kwargs.get('error')
        status = kwargs.get('status')
        progress = kwargs.get('progress')
        nodes = kwargs.get('nodes', [])

        task = cls.acquire_lock(task_uuid)
        if not task:
            return

        # we should remove master node from the nodes since it requires
        # special handling and won't work with old code
        # lock nodes for updating
        nodes_by_id = {str(n['uid']): n for n in nodes}
        master = nodes_by_id.pop(consts.MASTER_NODE_UID, {})
        if master.get('status') == consts.TASK_STATUSES.error:
            status = consts.TASK_STATUSES.error
            progress = 100

        q_nodes = objects.NodeCollection.filter_by_id_list(
            None, nodes_by_id
        )
        q_nodes = objects.NodeCollection.order_by(q_nodes, 'id')
        db_nodes = objects.NodeCollection.lock_for_update(q_nodes).all()

        for node_db in db_nodes:
            node = nodes_by_id.pop(node_db.uid)
            if node.get('status') == consts.TASK_STATUSES.error:
                node_db.status = consts.TASK_STATUSES.error
                node_db.progress = 100
                node_db.error_type = consts.TASK_NAMES.provision
                node_db.error_msg = node.get('error_msg', 'Unknown error')
            else:
                node_db.status = node.get('status')
                node_db.progress = node.get('progress')

        db().flush()
        if nodes_by_id:
            logger.warning("The following nodes is not found: %s",
                           ",".join(sorted(six.moves.map(str, nodes_by_id))))

        if nodes and not progress:
            progress = TaskHelper.recalculate_provisioning_task_progress(task)

        cls._update_task_status(task, status, progress, message, db_nodes)
        cls._update_action_log_entry(status, task.name, task_uuid, nodes)

    @classmethod
    def update_config_resp(cls, **kwargs):
        """Updates task and nodes states at the end of upload config task"""
        logger.info(
            "RPC method update_config_resp received: %s" %
            jsonutils.dumps(kwargs))

        task_uuid = kwargs['task_uuid']
        message = kwargs.get('error')
        status = kwargs.get('status')
        progress = kwargs.get('progress')

        task = cls.acquire_lock(task_uuid)
        if not task:
            return

        q_nodes = objects.NodeCollection.filter_by_id_list(
            None, task.cache['nodes'])
        # lock nodes for updating
        nodes = objects.NodeCollection.lock_for_update(q_nodes).all()

        if status in (consts.TASK_STATUSES.ready, consts.TASK_STATUSES.error):
            for node in nodes:
                node.status = consts.NODE_STATUSES.ready
                node.progress = 100

        if status == consts.TASK_STATUSES.error:
            message = (u"Failed to update configuration on nodes:"
                       u" {0}.").format(', '.join(node.name for node in nodes))
            logger.error(message)
            notifier.notify("error", message)

        db().flush()

        data = {'status': status, 'progress': progress, 'message': message}
        objects.Task.update(task, data)

        cls._update_action_log_entry(status, task.name, task_uuid, nodes)

    @classmethod
    def _notify(cls, task, topic, message, node_id=None, task_uuid=None):
        """Send notification.

        :param task: objects.Task object
        :param topic: consts.NOTIFICATION_TOPICS value
        :param message: message text
        :param node_id: node identifier
        :param task_uuid: task uuid. specify task_uuid if necessary to pass it
        """
        # Due to design of UI, that shows all notifications,
        # we should notify provision task only then the task is top-level task
        if (task.name == consts.TASK_NAMES.provision
                and task.parent_id is not None) or message is None:
            return

        notifier.notify(
            topic,
            message,
            task.cluster_id,
            node_id=node_id,
            task_uuid=task_uuid
        )

    @classmethod
    def _assemble_task_update(cls, task, status, progress, message, nodes):
        """Assemble arguments to update task.

        :param task: objects.Task object
        :param status: consts.TASK_STATUSES value
        :param progress: progress number value
        :param message: message text
        :param nodes: the modified nodes list
        """

        if status == consts.TASK_STATUSES.error:
            data = cls._error_action(task, status, progress, message)
        elif status == consts.TASK_STATUSES.ready:
            data = cls._success_action(task, status, progress, nodes)
        else:
            data = {}
            if status:
                data['status'] = status
            if progress:
                data['progress'] = progress
            if message:
                data['message'] = message
        return data

    @classmethod
    def _update_task_status(cls, task, status, progress, message, nodes):
        """Do update task status actions.

        :param task: objects.Task object
        :param status: consts.TASK_STATUSES value
        :param progress: progress number value
        :param message: message text
        :param nodes: the modified nodes list
        """
        objects.Task.update(
            task,
            cls._assemble_task_update(task, status, progress, message, nodes)
        )

    @classmethod
    def _update_action_log_entry(cls, task_status, task_name, task_uuid,
                                 nodes_from_resp):
        try:
            if task_status in (consts.TASK_STATUSES.ready,
                               consts.TASK_STATUSES.error):
                al = objects.ActionLog.get_by_kwargs(task_uuid=task_uuid,
                                                     action_name=task_name)

                if al:
                    data = {
                        'end_timestamp': datetime.datetime.utcnow(),
                        'additional_info': {
                            'nodes_from_resp': cls.sanitize_nodes_from_resp(
                                nodes_from_resp),
                            'ended_with_status': task_status
                        }
                    }
                    objects.ActionLog.update(al, data)
        except Exception as e:
            logger.error("_update_action_log_entry failed: %s",
                         six.text_type(e))

    @classmethod
    def sanitize_nodes_from_resp(cls, nodes):
        resp = []
        if isinstance(nodes, list):
            for n in nodes:
                if isinstance(n, dict) and 'uid' in n:
                    resp.append(n['uid'])
        return resp

    @classmethod
    def _generate_error_message(cls, task, error_types, names_only=False):
        nodes_info = []
        error_nodes = db().query(Node).filter_by(
            cluster_id=task.cluster_id
        ).filter(
            or_(
                Node.status == 'error',
                Node.online == (False)
            )
        ).filter(
            Node.error_type.in_(error_types)
        ).all()
        for n in error_nodes:
            if names_only:
                nodes_info.append(u"'{0}'".format(n.name))
            else:
                nodes_info.append(u"'{0}': {1}".format(n.name, n.error_msg))
        if nodes_info:
            if names_only:
                message = u", ".join(nodes_info)
            else:
                message = u"\n".join(nodes_info)
        else:
            message = None
        return message

    @classmethod
    def _error_action(cls, task, status, progress, message=None):
        task_name = task.name.title()
        if message:
            message = u"{0} has failed. {1}".format(task_name, message)
            # in case we are sending faild task message from astute
            # we should not create a notification with it, because its add
            # a lot of clutter for user
            notify_message = message.split('\n\n')[0]
        else:
            error_message = cls._generate_error_message(
                task,
                error_types=('deploy', 'provision'),
                names_only=True
            )
            message = u"{0} has failed. Check these nodes:\n{1}".format(
                task_name, error_message
            )
            notify_message = message if error_message is not None else None

        cls._notify(task, consts.NOTIFICATION_TOPICS.error, notify_message)
        return {'status': status, 'progress': progress, 'message': message}

    @classmethod
    def _success_action(cls, task, status, progress, nodes):
        # we shouldn't report success if there's at least one node in
        # error state
        if any(n.status == consts.NODE_STATUSES.error for n in nodes):
            return cls._error_action(task, 'error', 100)

        task_name = task.name.title()
        if nodes:
            # check that all nodes in same state
            remaining = objects.Cluster.get_nodes_count_unmet_status(
                nodes[0].cluster, nodes[0].status
            )
            if remaining > 0:
                message = u"{0} of {1} environment node(s) is done.".format(
                    task_name, len(nodes)
                )
            else:
                message = u"{0} of environment '{1}' is done.".format(
                    task_name, task.cluster.name
                )
        else:
            message = u"{0} is done. No changes.".format(task_name)

        if task.name != consts.TASK_NAMES.provision:
            plugins_msg = cls._make_plugins_success_message(
                ClusterPlugin.get_enabled(task.cluster.id))
            if plugins_msg:
                message = '{0}\n\n{1}'.format(message, plugins_msg)

        cls._notify(task, consts.NOTIFICATION_TOPICS.done, message)
        return {'status': status, 'progress': progress, 'message': message}

    @classmethod
    def _make_plugins_success_message(cls, plugins):
        """Makes plugins installation message"""
        msg = 'Plugin {0} is deployed. {1}'
        return '\n'.join(
            map(lambda p: msg.format(p.name, p.description), plugins))

    @classmethod
    def stop_deployment_resp(cls, **kwargs):
        logger.info(
            "RPC method stop_deployment_resp received: %s" %
            jsonutils.dumps(kwargs)
        )
        task_uuid = kwargs.get('task_uuid')
        nodes = kwargs.get('nodes', [])
        ia_nodes = kwargs.get('inaccessible_nodes', [])
        message = kwargs.get('error')
        status = kwargs.get('status')
        progress = kwargs.get('progress')

        task = cls.acquire_lock(task_uuid)
        if not task:
            return

        stopping_task_names = [
            consts.TASK_NAMES.deploy,
            consts.TASK_NAMES.deployment,
            consts.TASK_NAMES.provision
        ]

        q_stop_tasks = objects.TaskCollection.filter_by_list(
            None,
            'name',
            stopping_task_names
        )
        q_stop_tasks = objects.TaskCollection.filter_by(
            q_stop_tasks,
            cluster_id=task.cluster_id,
            deleted_at=None
        )
        stop_tasks = objects.TaskCollection.order_by(
            q_stop_tasks,
            'id'
        ).all()

        if not stop_tasks:
            logger.warning("stop_deployment_resp: deployment tasks \
                            not found for environment '%s'!", task.cluster_id)

        if status == consts.TASK_STATUSES.ready:
            task.cluster.status = consts.CLUSTER_STATUSES.stopped

            if stop_tasks:
                objects.Task.bulk_delete(x.id for x in stop_tasks)

            node_uids = [n['uid'] for n in itertools.chain(nodes, ia_nodes)]
            q_nodes = objects.NodeCollection.filter_by_id_list(None, node_uids)
            q_nodes = objects.NodeCollection.filter_by(
                q_nodes,
                cluster_id=task.cluster_id
            )
            q_nodes = objects.NodeCollection.order_by(q_nodes, 'id')

            # locking Nodes for update
            update_nodes = objects.NodeCollection.lock_for_update(
                q_nodes
            ).all()

            for node in update_nodes:
                objects.Node.reset_to_discover(node)

            if ia_nodes:
                cls._notify_inaccessible(
                    task.cluster_id,
                    [n["uid"] for n in ia_nodes],
                    u"deployment stopping"
                )

            message = cls._make_stop_deployment_message(
                task, status, stop_tasks, update_nodes, message)

            notifier.notify(
                "done",
                message,
                task.cluster_id
            )
        elif status == consts.TASK_STATUSES.error:
            task.cluster.status = consts.CLUSTER_STATUSES.error

            if stop_tasks:
                objects.Task.bulk_delete(x.id for x in stop_tasks)

            q_nodes = objects.NodeCollection.filter_by(
                None,
                cluster_id=task.cluster_id
            )
            q_nodes = objects.NodeCollection.filter_by(
                q_nodes,
                status=consts.NODE_STATUSES.deploying
            )
            q_nodes = objects.NodeCollection.order_by(q_nodes, 'id')

            update_nodes = objects.NodeCollection.lock_for_update(
                q_nodes
            ).all()

            for node_db in update_nodes:
                node_db.status = consts.NODE_STATUSES.error
                node_db.progress = 100
                node_db.error_type = consts.NODE_ERRORS.stop_deployment

            db().flush()
            message = cls._make_stop_deployment_message(
                task, status, stop_tasks, update_nodes, message)

            notifier.notify(
                "error",
                message,
                task.cluster_id
            )

        data = {'status': status, 'progress': progress, 'message': message}
        objects.Task.update(task, data)

        cls._update_action_log_entry(status, task.name, task_uuid, nodes)

    @classmethod
    def _make_stop_deployment_message(cls, task, status, stop_tasks, nodes,
                                      message):
        messages_by_status = {
            consts.TASK_STATUSES.ready: [
                u"Deployment of environment '{0}' was successfully stopped. ",
                u"{0} of {1} environment node(s) was successfully stopped. "
            ],
            consts.TASK_STATUSES.error: [
                u"Deployment of environment '{0}' was failed to stop: {1}. "
                u"Please check logs for details.",
                u"{0} of {1} environment node(s) was failed to stop: {2}. "
                u"Please check logs for details."
            ]
        }
        stop_task_names = [t.name for t in stop_tasks]

        if consts.TASK_NAMES.deploy in stop_task_names:
            return messages_by_status[status][0].format(
                task.cluster.name or task.cluster_id, message)
        process = u"Deployment"
        if consts.TASK_NAMES.deployment not in stop_task_names:
            process = u"Provisioning"
        return messages_by_status[status][1].format(
            process, len(nodes), message)

    @classmethod
    def _restore_pending_changes(cls, nodes, task, ia_nodes):
        task.cluster.status = consts.CLUSTER_STATUSES.new
        objects.Cluster.add_pending_changes(
            task.cluster,
            consts.CLUSTER_CHANGES.attributes
        )
        objects.Cluster.add_pending_changes(
            task.cluster,
            consts.CLUSTER_CHANGES.networks
        )
        node_uids = [n["uid"] for n in itertools.chain(nodes, ia_nodes)]
        q_nodes = objects.NodeCollection.filter_by_id_list(None, node_uids)
        q_nodes = objects.NodeCollection.filter_by(
            q_nodes,
            cluster_id=task.cluster_id
        )
        q_nodes = objects.NodeCollection.order_by(q_nodes, 'id')
        # locking Nodes for update
        update_nodes = objects.NodeCollection.lock_for_update(
            q_nodes
        ).all()

        for node in update_nodes:
            logs_utils.delete_node_logs(node)
            objects.Node.reset_to_discover(node)

    @classmethod
    def _reset_resp(cls, successful_message, restore_pending_changes=False,
                    **kwargs):
        task_uuid = kwargs.get('task_uuid')
        nodes = kwargs.get('nodes', [])
        ia_nodes = kwargs.get('inaccessible_nodes', [])
        message = kwargs.get('error')
        status = kwargs.get('status')
        progress = kwargs.get('progress')

        task = cls.acquire_lock(task_uuid)
        if not task:
            return

        if status == consts.TASK_STATUSES.ready:
            if restore_pending_changes:
                cls._restore_pending_changes(nodes, task, ia_nodes)
            if ia_nodes:
                cls._notify_inaccessible(
                    task.cluster_id,
                    [n["uid"] for n in ia_nodes],
                    u"environment resetting"
                )
            message = successful_message.format(
                task.cluster.name or task.cluster_id
            )
            notifier.notify(
                "done",
                message,
                task.cluster_id
            )
        data = {'status': status, 'progress': progress, 'message': message}
        objects.Task.update(task, data)
        cls._update_action_log_entry(status, task.name, task_uuid, nodes)

    @classmethod
    def reset_environment_resp(cls, **kwargs):
        logger.info(
            "RPC method reset_environment_resp received: %s",
            jsonutils.dumps(kwargs)
        )
        message = u"Environment '{0}' was successfully reset"
        cls._reset_resp(message, restore_pending_changes=True, **kwargs)

    @classmethod
    def remove_keys_resp(cls, **kwargs):
        logger.info(
            "RPC method remove_keys_resp received: %s",
            jsonutils.dumps(kwargs)
        )
        message = u"Keys were removed from environment '{0}'"
        cls._reset_resp(message, **kwargs)

    @classmethod
    def remove_ironic_bootstrap_resp(cls, **kwargs):
        logger.info(
            "RPC method remove_ironic_bootstrap_resp received: %s",
            jsonutils.dumps(kwargs)
        )
        message = u"Ironic bootstrap was removed from environment '{0}'"
        cls._reset_resp(message, **kwargs)

    @classmethod
    def _notify_inaccessible(cls, cluster_id, nodes_uids, action):
        ia_nodes_db = db().query(Node.name).filter(
            Node.id.in_(nodes_uids),
            Node.cluster_id == cluster_id
        ).order_by(Node.id).yield_per(100)
        ia_message = (
            u"Fuel couldn't reach these nodes during "
            u"{0}: {1}. Manual check may be needed.".format(
                action,
                u", ".join([
                    u"'{0}'".format(n.name)
                    for n in ia_nodes_db
                ])
            )
        )
        notifier.notify(
            "warning",
            ia_message,
            cluster_id
        )

    @classmethod
    def verify_networks_resp(cls, **kwargs):
        logger.info(
            "RPC method verify_networks_resp received: %s" %
            jsonutils.dumps(kwargs)
        )
        task_uuid = kwargs.get('task_uuid')
        nodes = kwargs.get('nodes')
        error_msg = kwargs.get('error')
        status = kwargs.get('status')
        progress = kwargs.get('progress')

        task = cls.acquire_lock(task_uuid)
        if not task:
            return

        result = []
        #  We expect that 'nodes' contains all nodes which we test.
        #  Situation when some nodes not answered must be processed
        #  in orchestrator early.
        if nodes is None:
            # If no nodes in kwargs then we update progress or status only.
            pass
        elif isinstance(nodes, list):
            cached_nodes = task.cache['args']['nodes']
            node_uids = [str(n['uid']) for n in nodes]
            cached_node_uids = [str(n['uid']) for n in cached_nodes]
            forgotten_uids = set(cached_node_uids) - set(node_uids)

            if forgotten_uids:
                absent_nodes = db().query(Node).filter(
                    Node.id.in_(forgotten_uids)
                ).all()
                absent_node_names = []
                for n in absent_nodes:
                    if n.name:
                        absent_node_names.append(n.name)
                    else:
                        absent_node_names.append('id: %s' % n.id)
                if not error_msg:
                    error_msg = 'Node(s) {0} didn\'t return data.'.format(
                        ', '.join(absent_node_names)
                    )
                status = 'error'
            else:
                error_nodes = []
                node_excluded_networks = []

                for node in nodes:
                    cached_nodes_filtered = filter(
                        lambda n: str(n['uid']) == str(node['uid']),
                        cached_nodes
                    )

                    if not cached_nodes_filtered:
                        logger.warning(
                            "verify_networks_resp: arguments contain node "
                            "data which is not in the task cache: %r",
                            node
                        )
                        continue

                    cached_node = cached_nodes_filtered[0]

                    # Check if we have excluded bonded interfaces
                    # (in particular modes as LACP, Round-robin, etc.)
                    # that cannot be checked at the moment
                    excluded_networks = cached_node.get(
                        'excluded_networks', [])
                    if excluded_networks:
                        interfaces = ', '.join(
                            [net.get('iface') for net in excluded_networks])

                        node_excluded_networks.append({
                            'node_name': cached_node['name'],
                            'interfaces': interfaces
                        })

                    errors = connectivity_check.check_received_data(
                        cached_node, node)

                    error_nodes.extend(errors)

                if error_nodes:
                    result = error_nodes
                    status = 'error'
                else:
                    # notices must not rewrite error messages
                    if node_excluded_networks:
                        interfaces_list = ', '.join(
                            ['node {0} [{1}]'.format(
                                item['node_name'], item['interfaces'])
                             for item in node_excluded_networks])
                        error_msg = connectivity_check.append_message(
                            error_msg,
                            'Notice: some interfaces were skipped from '
                            'connectivity checking because this version of '
                            'Fuel cannot establish following bonding modes '
                            'on Bootstrap nodes: LACP, Round-robin '
                            '(balance-rr). Only interfaces of '
                            'successfully deployed nodes may be checked '
                            'with mentioned modes enabled. The list of '
                            'skipped interfaces: {0}.'.format(interfaces_list),
                        )
                    if task.cache['args']['offline'] > 0:
                        error_msg = connectivity_check.append_message(
                            error_msg,
                            'Notice: {0} node(s) were offline during '
                            'connectivity check so they were skipped from the '
                            'check.'.format(task.cache['args']['offline'])
                        )

        else:
            error_msg = (error_msg or
                         'verify_networks_resp: argument "nodes"'
                         ' have incorrect type')
            status = 'error'
            logger.error(error_msg)

        if status not in ('ready', 'error'):
            data = {
                'status': status,
                'progress': progress,
                'message': error_msg,
                'result': result
            }
            objects.Task.update(task, data)
        else:
            objects.Task.update_verify_networks(
                task, status, progress, error_msg, result)

        cls._update_action_log_entry(status, task.name, task_uuid, nodes)

    @classmethod
    def multicast_verification_resp(cls, **kwargs):
        """Receiver for verification of multicast packages

        data - {1: response, 2: response}
        """
        logger.info(
            u"RPC method multicast_resp received: {0}".format(
                jsonutils.dumps(kwargs))
        )
        task_uuid = kwargs.get('task_uuid')
        task = cls.acquire_lock(task_uuid)
        if not task:
            return

        if kwargs.get('status'):
            task.status = kwargs['status']
        task.progress = kwargs.get('progress', 0)

        response = kwargs.get('nodes', {})
        error_msg = kwargs.get('error')

        if task.status == TASK_STATUSES.error:
            task.message = error_msg
        elif task.status == TASK_STATUSES.ready:
            errors = []
            results = []
            node_ids = set(config['uid'] for config
                           in task.cache['args']['nodes'])
            not_received_nodes = node_ids - set(response.keys())
            if not_received_nodes:
                msg = (u'No answer from nodes: {0}').format(
                    list(not_received_nodes))
                errors.append(msg)
            for node_id, received_ids in six.iteritems(response):
                result = {}
                not_received_ids = node_ids - set(received_ids or [])
                result = {'node_id': node_id,
                          'not_received': list(not_received_ids)}
                results.append(result)
                if not_received_ids:
                    msg = (u'Not received ids {0}'
                           u' for node {1}.').format(not_received_ids, node_id)
                    errors.append(msg)

            task.message = '\n'.join(errors)
            if errors:
                task.status = TASK_STATUSES.error
            task.result = results
        if task.status == TASK_STATUSES.ready:
            editable = copy.deepcopy(task.cluster.attributes.editable)
            editable['corosync']['verified']['value'] = True
            task.cluster.attributes.editable = editable
        logger.debug(u'Multicast verification message %s', task.message)
        objects.Task.update_verify_networks(
            task, task.status,
            task.progress, task.message, task.result)

    @classmethod
    def check_dhcp_resp(cls, **kwargs):
        """Receiver method for check_dhcp task

        For example of kwargs check FakeCheckingDhcpThread
        """
        logger.info(
            "RPC method check_dhcp_resp received: %s",
            jsonutils.dumps(kwargs)
        )
        messages = []

        result = collections.defaultdict(list)
        message_template = (
            u"Node {node_name} discovered DHCP server "
            u"via {iface} with following parameters: IP: {server_id}, "
            u"MAC: {mac}. This server will conflict with the installation.")
        task_uuid = kwargs.get('task_uuid')
        nodes = kwargs.get('nodes', [])
        error_msg = kwargs.get('error')
        status = kwargs.get('status')
        progress = kwargs.get('progress')

        task = cls.acquire_lock(task_uuid)
        if not task:
            return

        nodes_uids = [node['uid'] for node in nodes]
        nodes_db = db().query(Node).filter(Node.id.in_(nodes_uids)).all()
        nodes_map = dict((str(node.id), node) for node in nodes_db)

        master_network_mac = settings.ADMIN_NETWORK['mac']
        logger.debug('Mac addr on master node %s', master_network_mac)

        for node in nodes:
            node_db = nodes_map.get(node['uid'])
            if not node_db:
                logger.warning(
                    "Received message from nonexistent node. "
                    "Node's UID {0}. Node's data {1}"
                    .format(node['uid'], node.get('data', []))
                )
                continue

            if node['status'] == consts.NODE_STATUSES.error:
                messages.append(
                    "DHCP discover check failed on node with ID={}. "
                    "Check logs for details."
                    .format(node['uid'])
                )
                result[node['uid']] = node.get('data')

            elif node['status'] == consts.NODE_STATUSES.ready:
                # (vvalyavskiy): dhcp_check util produces one record with
                # empty fields if no dhcp server is present, so, we can
                # safely skip checking such kind of responses
                response = node.get('data', [])
                if (len(response) == 1 and isinstance(response[0], dict)
                        and not any(response[0].values())):
                    logger.warning(
                        "No DHCP servers were found! "
                        "Node's UID {0}. Node's data {1}"
                        .format(node['uid'], response)
                    )
                    continue

                incorrect_input = False
                for row in response:
                    try:
                        if not net_utils.is_same_mac(row['mac'],
                                                     master_network_mac):
                            row['node_name'] = node_db.name
                            message = message_template.format(**row)
                            messages.append(message)
                    # NOTE(aroma): for example when mac's value
                    # is an empty string
                    except ValueError as e:
                        logger.warning(
                            "Failed to compare mac address "
                            "from response data (row = {0}) "
                            "from node with id={1}. "
                            "Original error:\n {2}"
                            .format(row, node['uid'], six.text_type(e)))
                        incorrect_input = True
                    finally:
                        result[node['uid']].append(row)

                if incorrect_input:
                    messages.append(
                        "Something is wrong with response data from node with "
                        "id={}. Check logs for details."
                        .format(node['uid'])
                    )

        status = status if not messages else consts.TASK_STATUSES.error
        error_msg = '\n'.join(messages) if messages else error_msg
        logger.debug('Check dhcp message %s', error_msg)

        objects.Task.update_verify_networks(task, status, progress,
                                            error_msg, result)

    @classmethod
    def download_release_resp(cls, **kwargs):
        logger.info(
            "RPC method download_release_resp received: %s" %
            jsonutils.dumps(kwargs)
        )
        task_uuid = kwargs.get('task_uuid')
        error_msg = kwargs.get('error')
        status = kwargs.get('status')
        progress = kwargs.get('progress')

        task = cls.acquire_lock(task_uuid)
        if not task:
            return

        release_info = task.cache['args']['release_info']
        release_id = release_info['release_id']
        release = db().query(Release).get(release_id)
        if not release:
            logger.error("download_release_resp: Release"
                         " with ID %s not found", release_id)
            return

        if error_msg:
            status = 'error'
            error_msg = "{0} download and preparation " \
                        "has failed.".format(release.name)
            cls._download_release_error(
                release_id,
                error_msg
            )
        elif progress == 100 and status == 'ready':
            cls._download_release_completed(release_id)

        result = {
            "release_info": {
                "release_id": release_id
            }
        }

        data = {'status': status, 'progress': progress, 'message': error_msg,
                'result': result}
        objects.Task.update(task, data)

    @classmethod
    def dump_environment_resp(cls, **kwargs):
        logger.info(
            "RPC method dump_environment_resp received: %s" %
            jsonutils.dumps(kwargs)
        )
        task_uuid = kwargs.get('task_uuid')
        status = kwargs.get('status')
        progress = kwargs.get('progress')
        error = kwargs.get('error')
        msg = kwargs.get('msg')

        task = cls.acquire_lock(task_uuid)
        if not task:
            return

        if status == 'error':
            notifier.notify('error', error)

            data = {'status': status, 'progress': 100, 'message': error}
            objects.Task.update(task, data)

        elif status == 'ready':
            dumpfile = os.path.basename(msg)
            notifier.notify('done', 'Snapshot is ready. '
                            'Visit Support page to download')
            dumpfile_url = reverse('SnapshotDownloadHandler',
                                   kwargs={'snapshot_name': dumpfile})
            data = {'status': status, 'progress': progress,
                    'message': dumpfile_url}
            objects.Task.update(task, data)

    @classmethod
    def stats_user_resp(cls, **kwargs):
        logger.info("RPC method stats_user_resp received: %s",
                    jsonutils.dumps(kwargs))

        task_uuid = kwargs.get('task_uuid')
        nodes = kwargs.get('nodes', [])
        status = kwargs.get('status')
        error = kwargs.get('error')
        message = kwargs.get('msg')

        task = cls.acquire_lock(task_uuid)
        if not task:
            return

        if status not in (consts.TASK_STATUSES.ready,
                          consts.TASK_STATUSES.error):
            logger.debug("Task %s, id: %s in status: %s",
                         task.name, task.id, task.status)
            return

        data = {'status': status, 'progress': 100, 'message': message}
        if status == consts.TASK_STATUSES.error:
            logger.error("Task %s, id: %s failed: %s",
                         task.name, task.id, error)
            data['message'] = error

        objects.Task.update(task, data)
        cls._update_action_log_entry(status, task.name, task_uuid, nodes)
        logger.info("RPC method stats_user_resp processed")

    @classmethod
    def _get_failed_repos(cls, node):
        """Get failed repositories from failed node.

        :param node: master or slave
        :type node: dict
        :return: list of failed repositories
        """
        return node['out'].get('failed_urls', [])

    @classmethod
    def _check_repos_connectivity(cls, resp_kwargs, failed_nodes_msg,
                                  suggestion_msg=''):
        """Analyze response data to check repo connectivity from nodes

        :param resp_kwargs: task response data
        :type resp_kwargs: dict
        :param failed_nodes_msg: error message part if the task has not
            due to underlying command execution error; is formatted by
            node name
        :type failed_nodes_msg: str
        :param failed_repos_msg: error message part if connection to the
            repositories cannot be established; is formatted by list of names
            of the repositories
        :type failed_repos_msg: str
        :param err_msg: general error message part
        :type err_msg: str
        """
        task_uuid = resp_kwargs.get('task_uuid')
        response = resp_kwargs.get('nodes', [])
        status = consts.TASK_STATUSES.ready
        progress = 100

        task = cls.acquire_lock(task_uuid)
        if not task:
            return

        failed_response_nodes = {
            n['uid']: n for n in response if n['status'] != 0
        }

        failed_nodes = []
        failed_repos = set()

        master = failed_response_nodes.pop(consts.MASTER_NODE_UID, None)
        if master is not None:
            failed_repos.update(cls._get_failed_repos(master))
            failed_nodes.append(consts.MASTER_NODE_NAME)

        nodes = objects.NodeCollection.filter_by_list(
            None, 'id', failed_response_nodes, order_by='id')

        for node in nodes:
            failed_repos.update(cls._get_failed_repos(
                failed_response_nodes[node.uid]))
            failed_nodes.append(node.name)

        err_msg = ''

        failed_repos_msg = (
            'Following repos are not available - {0}.\n '
        )

        if failed_nodes:
            err_msg = failed_nodes_msg.format(', '.join(failed_nodes))
        if failed_repos:
            err_msg += failed_repos_msg.format(', '.join(failed_repos))
        if err_msg and suggestion_msg:
            err_msg += suggestion_msg

        if err_msg:
            status = consts.TASK_STATUSES.error

        objects.Task.update_verify_networks(
            task, status, progress, err_msg, {})

    @classmethod
    def check_repositories_resp(cls, **kwargs):
        logger.info(
            "RPC method check_repositories_resp received: %s",
            jsonutils.dumps(kwargs)
        )

        failed_nodes_msg = (
            'Repo availability verification'
            ' failed on following nodes {0}.\n '
        )

        cls._check_repos_connectivity(kwargs, failed_nodes_msg)

    @classmethod
    def check_repositories_with_setup_resp(cls, **kwargs):
        logger.info(
            "RPC method check_repositories_with_setup received: %s",
            jsonutils.dumps(kwargs)
        )

        failed_nodes_msg = (
            'Repo availability verification using public network'
            ' failed on following nodes {0}.\n '
        )
        suggestion_msg = (
            'Check your public network settings and '
            'availability of the repositories from public network. '
            'Please examine nailgun and astute'
            ' logs for additional details.'
        )

        cls._check_repos_connectivity(kwargs, failed_nodes_msg,
                                      suggestion_msg)

    @classmethod
    def base_resp(cls, **kwargs):
        logger.info("RPC method base_resp received: %s",
                    jsonutils.dumps(kwargs))

        task_uuid = kwargs.get('task_uuid')
        status = kwargs.get('status')
        error = kwargs.get('error', '')
        message = kwargs.get('msg', '')

        task = cls.acquire_lock(task_uuid)
        if not task:
            return

        data = {'status': status, 'progress': 100, 'message': message}
        if status == consts.TASK_STATUSES.error:
            logger.error("Task %s, id: %s failed: %s",
                         task.name, task.id, error)
            data['message'] = error

        objects.Task.update(task, data)
        cls._update_action_log_entry(status, task.name, task_uuid, [])
