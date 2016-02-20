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
from nailgun.errors import errors as nailgun_errors
from nailgun import notifier
from nailgun import objects
from nailgun.settings import settings

from nailgun.consts import TASK_STATUSES
from nailgun.db import db
from nailgun.db.sqlalchemy.models import IPAddr
from nailgun.db.sqlalchemy.models import Node
from nailgun.db.sqlalchemy.models import Release
from nailgun.network import connectivity_check
from nailgun.network import utils as net_utils
from nailgun.objects.plugin import ClusterPlugins
from nailgun.task.helpers import TaskHelper
from nailgun.utils import logs as logs_utils
from nailgun.utils import reverse


logger = logging.getLogger('receiverd')


class NailgunReceiver(object):

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
        task = objects.Task.get_by_uuid(
            task_uuid,
            fail_if_not_found=True,
            lock_for_update=True
        )

        # locking cluster
        if task.cluster_id is not None:
            objects.Cluster.get_by_uid(
                task.cluster_id,
                fail_if_not_found=True,
                lock_for_update=True
            )

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
        if nodes:
            success_msg = u"Successfully removed {0} node(s)".format(
                len(nodes)
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
            map(db().delete, ips)
            db().flush()

            nm = objects.Cluster.get_network_manager(cluster)
            admin_nets = nm.get_admin_networks()
            objects.Cluster.delete(cluster)
            if admin_nets != nm.get_admin_networks():
                # import it here due to cyclic dependencies problem
                from nailgun.task.manager import UpdateDnsmasqTaskManager
                UpdateDnsmasqTaskManager().execute()

            notifier.notify(
                "done",
                u"Environment '%s' and all its nodes are deleted" % (
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
        task = objects.Task.get_by_uuid(task_uuid)

        if status == consts.TASK_STATUSES.ready:
            logger.info("IBP images from deleted cluster have been removed")
        elif status == consts.TASK_STATUSES.error:
            logger.error("Removing IBP images failed: task_uuid %s", task_uuid)

        objects.Task.update(task, {'status': status})

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

        task = objects.Task.get_by_uuid(
            task_uuid,
            fail_if_not_found=True
        )

        # lock cluster
        objects.Cluster.get_by_uid(
            task.cluster_id,
            fail_if_not_found=True,
            lock_for_update=True
        )

        if not status:
            status = task.status

        # for deployment we need just to pop
        # if there no node except master - then just skip updating
        # nodes status, for the task itself astute will send
        # message with descriptive error
        nodes_by_id = {str(n['uid']): n for n in nodes}
        master = nodes_by_id.pop(consts.MASTER_NODE_UID, {})

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

                    if param == 'progress' and node.get('status') == 'error' \
                            or node.get('online') is False:
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
        db().flush()
        if nodes_by_id:
            logger.warning("The following nodes is not found: %s",
                           ",".join(sorted(nodes_by_id)))

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

        task = objects.Task.get_by_uuid(
            task_uuid,
            fail_if_not_found=True,
            lock_for_update=True
        )

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
            node = nodes_by_id[node_db.uid]
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

        task = objects.Task.get_by_uuid(
            task_uuid,
            fail_if_not_found=True,
            lock_for_update=True
        )

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
    def _update_task_status(cls, task, status, progress, message, nodes):
        """Do update task status actions.

        :param task: objects.Task object
        :param status: consts.TASK_STATUSES value
        :param progress: progress number value
        :param message: message text
        :param nodes: the modified nodes list
        """
        # Let's check the whole task status
        if status == consts.TASK_STATUSES.error:
            cls._error_action(task, status, progress, message)
        elif status == consts.TASK_STATUSES.ready:
            cls._success_action(task, status, progress, nodes)
        else:
            data = {'status': status, 'progress': progress, 'message': message}
            objects.Task.update(task, data)

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
        data = {'status': status, 'progress': progress, 'message': message}
        objects.Task.update(task, data)

    @classmethod
    def _success_action(cls, task, status, progress, nodes):
        # check if all nodes are ready
        if any(n.status == consts.NODE_STATUSES.error for n in nodes):
            cls._error_action(task, 'error', 100)
            return

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

        zabbix_url = objects.Cluster.get_network_manager(
            task.cluster
        ).get_zabbix_url(task.cluster)

        if zabbix_url:
            message = "{0} Access Zabbix dashboard at {1}".format(
                message, zabbix_url)

        plugins_msg = cls._make_plugins_success_message(
            ClusterPlugins.get_enabled(task.cluster.id))
        if plugins_msg:
            message = '{0}\n\n{1}'.format(message, plugins_msg)

        cls._notify(task, consts.NOTIFICATION_TOPICS.done, message)
        data = {'status': status, 'progress': progress, 'message': message}
        objects.Task.update(task, data)

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

        task = objects.Task.get_by_uuid(
            task_uuid,
            fail_if_not_found=True,
        )

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
            cluster_id=task.cluster_id
        )
        stop_tasks = objects.TaskCollection.order_by(
            q_stop_tasks,
            'id'
        ).all()

        # Locking cluster
        objects.Cluster.get_by_uid(
            task.cluster_id,
            fail_if_not_found=True,
            lock_for_update=True
        )

        if not stop_tasks:
            logger.warning("stop_deployment_resp: deployment tasks \
                            not found for environment '%s'!", task.cluster_id)

        if status == consts.TASK_STATUSES.ready:
            task.cluster.status = consts.CLUSTER_STATUSES.stopped

            if stop_tasks:
                map(db().delete, stop_tasks)

            node_uids = [n['uid'] for n in itertools.chain(nodes, ia_nodes)]
            q_nodes = objects.NodeCollection.filter_by_id_list(None, node_uids)
            q_nodes = objects.NodeCollection.filter_by(
                q_nodes,
                cluster_id=task.cluster_id
            )
            q_nodes = objects.NodeCollection.order_by(q_nodes, 'id')
            q_nodes = objects.NodeCollection.lock_for_update(q_nodes)

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

            message = (
                u"Deployment of environment '{0}' was successfully stopped. "
                u"Please make changes."
                .format(task.cluster.name or task.cluster_id)
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
        task_uuid = kwargs.get('task_uuid')
        nodes = kwargs.get('nodes', [])
        ia_nodes = kwargs.get('inaccessible_nodes', [])
        message = kwargs.get('error')
        status = kwargs.get('status')
        progress = kwargs.get('progress')

        task = objects.Task.get_by_uuid(
            task_uuid,
            fail_if_not_found=True,
            lock_for_update=True
        )

        # Locking cluster
        objects.Cluster.get_by_uid(
            task.cluster_id,
            fail_if_not_found=True,
            lock_for_update=True
        )

        if status == consts.TASK_STATUSES.ready:
            # restoring pending changes
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

            if ia_nodes:
                cls._notify_inaccessible(
                    task.cluster_id,
                    [n["uid"] for n in ia_nodes],
                    u"environment resetting"
                )

            message = (
                u"Environment '{0}' "
                u"was successfully reset".format(
                    task.cluster.name or task.cluster_id
                )
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

        # We simply check that each node received all vlans for cluster
        task = objects.Task.get_by_uuid(task_uuid, fail_if_not_found=True)

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

                    # Check if we have excluded interfaces for LACP bonds
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
                            'Fuel cannot establish LACP on Bootstrap nodes. '
                            'Only interfaces of successfully deployed nodes '
                            'may be checked with LACP enabled. The list of '
                            'skipped interfaces: {0}.'.format(interfaces_list)
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
        task = objects.task.Task.get_by_uuid(uuid=task_uuid)
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
            for node_id, received_ids in response.iteritems():
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

        nodes_uids = [node['uid'] for node in nodes]
        nodes_db = db().query(Node).filter(Node.id.in_(nodes_uids)).all()
        nodes_map = dict((str(node.id), node) for node in nodes_db)

        master_network_mac = settings.ADMIN_NETWORK['mac']
        logger.debug('Mac addr on master node %s', master_network_mac)

        for node in nodes:
            if node['status'] == 'ready':
                for row in node.get('data', []):
                    if not net_utils.is_same_mac(row['mac'],
                                                 master_network_mac):
                        node_db = nodes_map.get(node['uid'])
                        if node_db:
                            row['node_name'] = node_db.name
                            message = message_template.format(**row)
                            messages.append(message)
                            result[node['uid']].append(row)
                        else:
                            logger.warning(
                                'Received message from nonexistent node. '
                                'Message %s', row)
        status = status if not messages else "error"
        error_msg = '\n'.join(messages) if messages else error_msg
        logger.debug('Check dhcp message %s', error_msg)

        task = objects.Task.get_by_uuid(task_uuid, fail_if_not_found=True)
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

        task = objects.Task.get_by_uuid(task_uuid, fail_if_not_found=True)

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

        task = objects.Task.get_by_uuid(task_uuid, fail_if_not_found=True)

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

        task = objects.Task.get_by_uuid(
            task_uuid, fail_if_not_found=True, lock_for_update=True)

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

        task = objects.Task.get_by_uuid(
            task_uuid, fail_if_not_found=True)

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
    def task_in_orchestrator(cls, **kwargs):
        logger.info("RPC method task_in_orchestrator received: %s",
                    jsonutils.dumps(kwargs))

        task_uuid = kwargs.get('task_uuid')

        try:
            task = objects.Task.get_by_uuid(task_uuid, fail_if_not_found=True,
                                            lock_for_update=True)
            if task.status == consts.TASK_STATUSES.pending:
                objects.Task.update(
                    task, {'status': consts.TASK_STATUSES.running})
                logger.debug("Task '%s' is acknowledged as running",
                             task_uuid)
            else:
                logger.debug("Task '%s' in status '%s' can not "
                             "be acknowledged as running", task_uuid,
                             task.status)
        except nailgun_errors.ObjectNotFound:
            logger.warning("Task '%s' acknowledgement as running failed "
                           "due to task doesn't exist in DB", task_uuid)

    @classmethod
    def update_dnsmasq_resp(cls, **kwargs):
        logger.info("RPC method update_dnsmasq_resp received: %s",
                    jsonutils.dumps(kwargs))

        task_uuid = kwargs.get('task_uuid')
        status = kwargs.get('status')
        error = kwargs.get('error', '')
        message = kwargs.get('msg', '')

        task = objects.Task.get_by_uuid(
            task_uuid, fail_if_not_found=True, lock_for_update=True)

        data = {'status': status, 'progress': 100, 'message': message}
        if status == consts.TASK_STATUSES.error:
            logger.error("Task %s, id: %s failed: %s",
                         task.name, task.id, error)
            data['message'] = error

        objects.Task.update(task, data)
        cls._update_action_log_entry(status, task.name, task_uuid, [])
