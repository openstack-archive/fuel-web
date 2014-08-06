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
import itertools
import os
import traceback

from sqlalchemy import or_

from nailgun import consts
from nailgun import notifier
from nailgun import objects
from nailgun.settings import settings

from nailgun.consts import TASK_STATUSES
from nailgun.db import db
from nailgun.db.sqlalchemy.models import IPAddr
from nailgun.db.sqlalchemy.models import Node
from nailgun.db.sqlalchemy.models import Release
from nailgun.logger import logger
from nailgun.openstack.common import jsonutils
from nailgun.task.helpers import TaskHelper


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

        # locking tasks on cluster
        task = objects.Task.get_by_uuid(task_uuid, fail_if_not_found=True)
        objects.TaskCollection.lock_cluster_tasks(task.cluster_id)
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
        locked_nodes = objects.NodeCollection.filter_by_list(
            None,
            'id',
            all_nodes_ids,
            order_by='id'
        )
        objects.NodeCollection.lock_for_update(locked_nodes).all()

        for node in nodes:
            node_db = objects.Node.get_by_uid(node['uid'])
            if not node_db:
                logger.error(
                    u"Failed to delete node '%s': node doesn't exist",
                    str(node)
                )
                break
            db().delete(node_db)

        for node in inaccessible_nodes:
            # Nodes which not answered by rpc just removed from db
            node_db = objects.Node.get_by_uid(node['uid'])
            if node_db:
                logger.warn(
                    u'Node %s not answered by RPC, removing from db',
                    node_db.human_readable_name)
                db().delete(node_db)

        for node in error_nodes:
            node_db = objects.Node.get_by_uid(node['uid'])
            if not node_db:
                logger.error(
                    u"Failed to delete node '%s' marked as error from Astute:"
                    " node doesn't exist", str(node)
                )
                break
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
        data = {'status': status, 'progress': progress, 'message': error_msg}
        objects.Task.update(task, data)

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

            db().delete(cluster)
            db().flush()

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
            fail_if_not_found=True,
        )

        # locking all cluster tasks
        objects.TaskCollection.lock_cluster_tasks(task.cluster_id)

        # lock cluster
        objects.Cluster.get_by_uid(
            task.cluster_id,
            fail_if_not_found=True,
            lock_for_update=True
        )

        if not status:
            status = task.status

        # lock nodes for updating so they can't be deleted
        q_nodes = objects.NodeCollection.filter_by_id_list(
            None,
            [n['uid'] for n in nodes],
        )
        q_nodes = objects.NodeCollection.order_by(q_nodes, 'id')
        objects.NodeCollection.lock_for_update(q_nodes).all()

        # First of all, let's update nodes in database
        for node in nodes:
            node_db = objects.Node.get_by_uid(node['uid'])
            if not node_db:
                logger.warning(
                    u"No node found with uid '{0}' - nothing changed".format(
                        node['uid']
                    )
                )
                continue

            update_fields = (
                'error_msg',
                'error_type',
                'status',
                'progress',
                'online'
            )
            for param in update_fields:
                if param in node:
                    logger.debug(
                        u"Updating node {0} - set {1} to {2}".format(
                            node['uid'],
                            param,
                            node[param]
                        )
                    )
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
                            "error",
                            u"Failed to deploy node '{0}': {1}".format(
                                node_db.name,
                                node_db.error_msg or "Unknown error"
                            ),
                            cluster_id=task.cluster_id,
                            node_id=node['uid'],
                            task_uuid=task_uuid
                        )
        db().flush()
        if nodes and not progress:
            progress = TaskHelper.recalculate_deployment_task_progress(task)

        # Let's check the whole task status
        if status in ('error',):
            cls._error_action(task, status, progress, message)
        elif status in ('ready',):
            cls._success_action(task, status, progress)
        else:
            data = {'status': status, 'progress': progress, 'message': message}
            objects.Task.update(task, data)

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

        # lock nodes for updating
        q_nodes = objects.NodeCollection.filter_by_id_list(
            None,
            [n['uid'] for n in nodes],
        )
        q_nodes = objects.NodeCollection.order_by(q_nodes, 'id')
        objects.NodeCollection.lock_for_update(q_nodes).all()

        for node in nodes:
            uid = node.get('uid')
            node_db = objects.Node.get_by_uid(node['uid'])

            if not node_db:
                logger.warn('Node with uid "{0}" not found'.format(uid))
                continue

            if node.get('status') == 'error':
                node_db.status = 'error'
                node_db.progress = 100
                node_db.error_type = 'provision'
                node_db.error_msg = node.get('error_msg', 'Unknown error')
            else:
                node_db.status = node.get('status')
                node_db.progress = node.get('progress')

        db().flush()
        if nodes and not progress:
            progress = TaskHelper.recalculate_provisioning_task_progress(task)

        data = {'status': status, 'progress': progress, 'message': message}
        objects.Task.update(task, data)

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
            message = u"Unknown error"
        return message

    @classmethod
    def _error_action(cls, task, status, progress, message=None):
        task_name = task.name.title()
        if message:
            message = u"{0} has failed. {1}".format(task_name, message)
        else:
            message = u"{0} has failed. Check these nodes:\n{1}".format(
                task_name,
                cls._generate_error_message(
                    task,
                    error_types=('deploy', 'provision'),
                    names_only=True
                )
            )
        notifier.notify(
            "error",
            message,
            task.cluster_id
        )
        data = {'status': status, 'progress': progress, 'message': message}
        objects.Task.update(task, data)

    @classmethod
    def _success_action(cls, task, status, progress):
        # check if all nodes are ready
        if any(map(lambda n: n.status == 'error',
                   task.cluster.nodes)):
            cls._error_action(task, 'error', 100)
            return

        task_name = task.name.title()
        if task.cluster.mode in ('singlenode', 'multinode'):
            # determining horizon url - it's an IP
            # of a first cluster controller
            controller = db().query(Node).filter_by(
                cluster_id=task.cluster_id
            ).filter(Node.role_list.any(name='controller')).first()
            if controller:
                logger.debug(
                    u"Controller is found, node_id=%s, "
                    "getting it's IP addresses",
                    controller.id
                )
                public_net = filter(
                    lambda n: n['name'] == 'public' and 'ip' in n,
                    objects.Node.get_network_manager(
                        controller
                    ).get_node_networks(controller)
                )
                if public_net:
                    horizon_ip = public_net[0]['ip'].split('/')[0]
                    message = (
                        u"{0} of environment '{1}' is done. "
                        "Access the OpenStack dashboard (Horizon) at "
                        "http://{2}/ or via internal network at http://{3}/"
                    ).format(
                        task_name,
                        task.cluster.name,
                        horizon_ip,
                        controller.ip
                    )
                else:
                    message = u"{0} of environment '{1}' is done".format(
                        task_name,
                        task.cluster.name
                    )
                    logger.warning(
                        u"Public ip for controller node "
                        "not found in '{0}'".format(task.cluster.name)
                    )
            else:
                message = u"{0} of environment '{1}' is done".format(
                    task_name,
                    task.cluster.name
                )
                logger.warning(u"Controller node not found in '{0}'".format(
                    task.cluster.name
                ))
        elif task.cluster.is_ha_mode:
            # determining horizon url in HA mode - it's vip
            # from a public network saved in task cache
            try:
                message = (
                    u"{0} of environment '{1}' is done. "
                    "Access the OpenStack dashboard (Horizon) at {2}"
                ).format(
                    task_name,
                    task.cluster.name,
                    objects.Cluster.get_network_manager(
                        task.cluster
                    ).get_horizon_url(task.cluster.id)
                )
            except Exception as exc:
                logger.error(": ".join([
                    str(exc),
                    traceback.format_exc()
                ]))
                message = u"{0} of environment '{1}' is done".format(
                    task_name,
                    task.cluster.name
                )
                logger.warning(
                    u"Cannot find virtual IP for '{0}'".format(
                        task.cluster.name
                    )
                )

        zabbix_url = objects.Cluster.get_network_manager(
            task.cluster
        ).get_zabbix_url(task.cluster)

        if zabbix_url:
            zabbix_suffix = " Access Zabbix dashboard at {0}".format(
                zabbix_url
            )
            message += zabbix_suffix

        notifier.notify(
            "done",
            message,
            task.cluster_id
        )
        data = {'status': status, 'progress': progress, 'message': message}
        objects.Task.update(task, data)

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

        # locking all cluster tasks
        objects.TaskCollection.lock_cluster_tasks(task.cluster_id)

        stopping_task_names = [
            consts.TASK_NAMES.deploy,
            consts.TASK_NAMES.deployment,
            consts.TASK_NAMES.provision
        ]

        # Locking other tasks for stopping
        q_stop_tasks = objects.TaskCollection.filter_by_list(
            None,
            'name',
            stopping_task_names
        )
        q_stop_tasks = objects.TaskCollection.filter_by(
            q_stop_tasks,
            cluster_id=task.cluster_id
        )
        q_stop_tasks = objects.TaskCollection.order_by(
            q_stop_tasks,
            'id'
        )
        stop_tasks = objects.TaskCollection.lock_for_update(q_stop_tasks).all()

        # Locking cluster
        objects.Cluster.get_by_uid(
            task.cluster_id,
            fail_if_not_found=True,
            lock_for_update=True
        )

        if not stop_tasks:
            logger.warning("stop_deployment_resp: deployment tasks \
                            not found for environment '%s'!", task.cluster_id)

        if status == "ready":
            task.cluster.status = "stopped"

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
            node_data = {
                'online': False,
                'status': consts.NODE_STATUSES.discover,
                'pending_addition': True,
            }

            for n in update_nodes:
                objects.Node.update(n, node_data)
                objects.Node.move_roles_to_pending_roles(n)

            if ia_nodes:
                cls._notify_inaccessible(
                    task.cluster_id,
                    [n["uid"] for n in ia_nodes],
                    u"deployment stopping"
                )

            message = (
                u"Deployment of environment '{0}' "
                u"was successfully stopped".format(
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

        task = objects.Task.get_by_uuid(task_uuid)

        if status == "ready":

            # restoring pending changes
            task.cluster.status = "new"
            objects.Cluster.add_pending_changes(task.cluster, "attributes")
            objects.Cluster.add_pending_changes(task.cluster, "networks")

            for node in task.cluster.nodes:
                objects.Cluster.add_pending_changes(
                    task.cluster,
                    "disks",
                    node_id=node.id
                )

            update_nodes = db().query(Node).filter(
                Node.id.in_([
                    n["uid"] for n in itertools.chain(
                        nodes,
                        ia_nodes
                    )
                ]),
                Node.cluster_id == task.cluster_id
            ).yield_per(100)

            update_nodes.update(
                {
                    "online": False,
                    "status": "discover",
                    "pending_addition": True,
                    "pending_deletion": False,
                },
                synchronize_session='fetch'
            )

            # Use nailgun.objects.Node.move_roles_to_pending_roles after
            # reset_environment_resp refactoring to nailgun objects
            for n in update_nodes:
                n.roles, n.pending_roles = n.pending_roles, n.roles

            db().flush()

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

                    for cached_network in cached_node['networks']:
                        received_networks_filtered = filter(
                            lambda n: n['iface'] == cached_network['iface'],
                            node.get('networks', [])
                        )

                        if received_networks_filtered:
                            received_network = received_networks_filtered[0]
                            absent_vlans = list(
                                set(cached_network['vlans']) -
                                set(received_network['vlans'])
                            )
                        else:
                            logger.warning(
                                "verify_networks_resp: arguments don't contain"
                                " data for interface: uid=%s iface=%s",
                                node['uid'], cached_network['iface']
                            )
                            absent_vlans = cached_network['vlans']

                        if absent_vlans:
                            data = {'uid': node['uid'],
                                    'interface': cached_network['iface'],
                                    'absent_vlans': absent_vlans}
                            node_db = db().query(Node).get(node['uid'])
                            if node_db:
                                data['name'] = node_db.name
                                db_nics = filter(
                                    lambda i:
                                    i.name == cached_network['iface'],
                                    node_db.interfaces
                                )
                                if db_nics:
                                    data['mac'] = db_nics[0].mac
                                else:
                                    logger.warning(
                                        "verify_networks_resp: can't find "
                                        "interface %r for node %r in DB",
                                        cached_network['iface'], node_db.id
                                    )
                                    data['mac'] = 'unknown'
                            else:
                                logger.warning(
                                    "verify_networks_resp: can't find node "
                                    "%r in DB",
                                    node['uid']
                                )

                            error_nodes.append(data)

                if error_nodes:
                    result = error_nodes
                    status = 'error'
        else:
            error_msg = (error_msg or
                         'verify_networks_resp: argument "nodes"'
                         ' have incorrect type')
            status = 'error'
            logger.error(error_msg)
        if status not in ('ready', 'error'):
            data = {'status': status, 'progress': progress,
                    'message': error_msg, 'result': result}
            objects.Task.update(task, data)
        else:
            objects.Task.update_verify_networks(task, status, progress,
                                                error_msg, result)

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
                    if row['mac'] != master_network_mac:
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
    def _update_release_state(cls, release_id, state):
        release = db().query(Release).get(release_id)
        release.state = state
        db.add(release)
        db.flush()

    @classmethod
    def _download_release_completed(cls, release_id):
        release = db().query(Release).get(release_id)
        release.state = 'available'
        db().flush()
        success_msg = u"Successfully downloaded {0}".format(
            release.name
        )
        notifier.notify("done", success_msg)

    @classmethod
    def _download_release_error(
        cls,
        release_id,
        error_message
    ):
        release = db().query(Release).get(release_id)
        release.state = 'error'
        db().flush()
        # TODO(NAME): remove this ugly checks
        if error_message != 'Task aborted':
            notifier.notify('error', error_message)

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
            data = {'status': status, 'progress': progress,
                    'message': '/dump/{0}'.format(dumpfile)}
            objects.Task.update(task, data)
