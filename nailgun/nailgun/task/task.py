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

import netaddr

from sqlalchemy import func
from sqlalchemy import not_
from sqlalchemy.orm import ColumnProperty
from sqlalchemy.orm import joinedload
from sqlalchemy.orm import object_mapper

import nailgun.rpc as rpc

from nailgun import objects

from nailgun.db import db
from nailgun.db.sqlalchemy.models import CapacityLog
from nailgun.db.sqlalchemy.models import Cluster
from nailgun.db.sqlalchemy.models import Node
from nailgun.db.sqlalchemy.models import RedHatAccount
from nailgun.db.sqlalchemy.models import Release
from nailgun.errors import errors
from nailgun.logger import logger
from nailgun.network.checker import NetworkCheck
from nailgun.orchestrator import deployment_serializers
from nailgun.orchestrator import provisioning_serializers
from nailgun.settings import settings
from nailgun.task.fake import FAKE_THREADS
from nailgun.task.helpers import TaskHelper


def fake_cast(queue, messages, **kwargs):
    def make_thread(message, join_to=None):
        thread = FAKE_THREADS[message['method']](
            data=message,
            params=kwargs,
            join_to=join_to
        )
        logger.debug("Fake thread called: data: %s, params: %s",
                     message, kwargs)
        thread.start()
        thread.name = message['method'].upper()
        return thread

    if isinstance(messages, (list,)):
        thread = None
        for m in messages:
            thread = make_thread(m, join_to=thread)
    else:
        make_thread(messages)


if settings.FAKE_TASKS or settings.FAKE_TASKS_AMQP:
    rpc.cast = fake_cast


class DeploymentTask(object):
# LOGIC
# Use cases:
# 1. Cluster exists, node(s) added
#   If we add one node to existing OpenStack cluster, other nodes may require
#   updates (redeployment), but they don't require full system reinstallation.
#   How to: run deployment for all nodes which system type is target.
#   Run provisioning first and then deployment for nodes which are in
#   discover system type.
#   Q: Should we care about node status (provisioning, error, deploying)?
#   A: offline - when node doesn't respond (agent doesn't run, not
#                implemented); let's say user should remove this node from
#                cluster before deployment.
#      ready - target OS is loaded and node is Ok, we redeploy
#              ready nodes only if cluster has pending changes i.e.
#              network or cluster attrs were changed
#      discover - in discovery mode, provisioning is required
#      provisioning - at the time of task execution there should not be such
#                     case. If there is - previous provisioning has failed.
#                     Possible solution would be to try again to provision
#      deploying - the same as provisioning, but stucked in previous deploy,
#                  solution - try to deploy. May loose some data if reprovis.
#      error - recognized error in deployment or provisioning... We have to
#              know where the error was. If in deployment - reprovisioning may
#              not be a solution (can loose data). If in provisioning - can do
#              provisioning & deployment again
# 2. New cluster, just added nodes
#   Provision first, and run deploy as second
# 3. Remove some and add some another node
#   Deletion task will run first and will actually remove nodes, include
#   removal from DB.. however removal from DB happens when remove_nodes_resp
#   is ran. It means we have to filter nodes and not to run deployment on
#   those which are prepared for removal.

    @classmethod
    def message(cls, task, nodes):
        logger.debug("DeploymentTask.message(task=%s)" % task.uuid)

        nodes_ids = [n.id for n in nodes]
        for n in db().query(Node).filter_by(
                cluster=task.cluster).order_by(Node.id):

            if n.id in nodes_ids:
                if n.pending_roles:
                    n.roles += n.pending_roles
                    n.pending_roles = []

                # If reciever for some reasons didn't update
                # node's status to provisioned when deployment
                # started, we should do it in nailgun
                if n.status in ('deploying'):
                    n.status = 'provisioned'
                n.progress = 0
                db().add(n)
                db().commit()

        # here we replace provisioning data if user redefined them
        serialized_cluster = task.cluster.replaced_deployment_info or \
            deployment_serializers.serialize(task.cluster, nodes)

        # After searilization set pending_addition to False
        for node in nodes:
            node.pending_addition = False
        db().commit()

        return {
            'method': 'deploy',
            'respond_to': 'deploy_resp',
            'args': {
                'task_uuid': task.uuid,
                'deployment_info': serialized_cluster}}


class ProvisionTask(object):

    @classmethod
    def message(cls, task, nodes_to_provisioning):
        logger.debug("ProvisionTask.message(task=%s)" % task.uuid)

        serialized_cluster = task.cluster.replaced_provisioning_info or \
            provisioning_serializers.serialize(
                task.cluster, nodes_to_provisioning)

        for node in nodes_to_provisioning:
            if settings.FAKE_TASKS or settings.FAKE_TASKS_AMQP:
                continue

            TaskHelper.prepare_syslog_dir(node)

        message = {
            'method': 'provision',
            'respond_to': 'provision_resp',
            'args': {
                'task_uuid': task.uuid,
                'provisioning_info': serialized_cluster}}

        return message


class DeletionTask(object):

    @classmethod
    def execute(self, task, respond_to='remove_nodes_resp'):
        logger.debug("DeletionTask.execute(task=%s)" % task.uuid)
        task_uuid = task.uuid
        logger.debug("Nodes deletion task is running")
        nodes_to_delete = []
        nodes_to_delete_constant = []
        nodes_to_restore = []

        USE_FAKE = settings.FAKE_TASKS or settings.FAKE_TASKS_AMQP

        # no need to call astute if there are no nodes in cluster
        if respond_to == 'remove_cluster_resp' and \
                not list(task.cluster.nodes):
            rcvr = rpc.receiver.NailgunReceiver()
            rcvr.remove_cluster_resp(
                task_uuid=task_uuid,
                status='ready',
                progress=100
            )
            return

        for node in task.cluster.nodes:
            if node.pending_deletion:
                nodes_to_delete.append({
                    'id': node.id,
                    'uid': node.id,
                    'roles': node.roles,
                    'slave_name': TaskHelper.make_slave_name(node.id)
                })

                if USE_FAKE:
                    # only fake tasks
                    new_node = {}
                    keep_attrs = (
                        'id',
                        'cluster_id',
                        'roles',
                        'pending_deletion',
                        'pending_addition'
                    )
                    for prop in object_mapper(node).iterate_properties:
                        if isinstance(
                            prop, ColumnProperty
                        ) and prop.key not in keep_attrs:
                            new_node[prop.key] = getattr(node, prop.key)
                    nodes_to_restore.append(new_node)
                    # /only fake tasks

        # this variable is used to iterate over it
        # and be able to delete node from nodes_to_delete safely
        nodes_to_delete_constant = list(nodes_to_delete)

        for node in nodes_to_delete_constant:
            node_db = db().query(Node).get(node['id'])

            slave_name = TaskHelper.make_slave_name(node['id'])
            logger.debug("Removing node from database and pending it "
                         "to clean its MBR: %s", slave_name)
            if node_db.status == 'discover':
                logger.info(
                    "Node is not deployed yet,"
                    " can't clean MBR: %s", slave_name)
                db().delete(node_db)
                db().commit()

                nodes_to_delete.remove(node)

        msg_delete = {
            'method': 'remove_nodes',
            'respond_to': respond_to,
            'args': {
                'task_uuid': task.uuid,
                'nodes': nodes_to_delete,
                'engine': {
                    'url': settings.COBBLER_URL,
                    'username': settings.COBBLER_USER,
                    'password': settings.COBBLER_PASSWORD,
                }
            }
        }
        # only fake tasks
        if USE_FAKE and nodes_to_restore:
            msg_delete['args']['nodes_to_restore'] = nodes_to_restore
        # /only fake tasks
        logger.debug("Calling rpc remove_nodes method")
        rpc.cast('naily', msg_delete)


class StopDeploymentTask(object):

    @classmethod
    def message(cls, task, stop_task):
        nodes_to_stop = db().query(Node).filter(
            Node.cluster_id == task.cluster.id
        ).filter(
            not_(Node.status == 'ready')
        ).yield_per(100)
        return {
            "method": "stop_deploy_task",
            "respond_to": "stop_deployment_resp",
            "args": {
                "task_uuid": task.uuid,
                "stop_task_uuid": stop_task.uuid,
                "nodes": [
                    {
                        'uid': n.uid,
                        'roles': n.roles,
                        'slave_name': TaskHelper.make_slave_name(n.id)
                    } for n in nodes_to_stop
                ],
                "engine": {
                    "url": settings.COBBLER_URL,
                    "username": settings.COBBLER_USER,
                    "password": settings.COBBLER_PASSWORD,
                }
            }
        }

    @classmethod
    def execute(cls, task, deploy_task, provision_task):
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
        return {
            "method": "reset_environment",
            "respond_to": "reset_environment_resp",
            "args": {
                "task_uuid": task.uuid,
                "nodes": [
                    {
                        'uid': n.uid,
                        'roles': n.roles,
                        'slave_name': TaskHelper.make_slave_name(n.id)
                    } for n in nodes_to_reset
                ],
                "engine": {
                    "url": settings.COBBLER_URL,
                    "username": settings.COBBLER_USER,
                    "password": settings.COBBLER_PASSWORD,
                }
            }
        }

    @classmethod
    def execute(cls, task):
        rpc.cast('naily', cls.message(task))


class ClusterDeletionTask(object):

    @classmethod
    def execute(cls, task):
        logger.debug("Cluster deletion task is running")
        DeletionTask.execute(task, 'remove_cluster_resp')


class VerifyNetworksTask(object):

    @classmethod
    def _subtask_message(cls, task):
        for subtask in task.subtasks:
            yield subtask.name, {'respond_to': '{0}_resp'.format(subtask.name),
                                 'task_uuid': subtask.uuid}

    @classmethod
    def _message(cls, task, data):
        nodes = []
        for n in task.cluster.nodes:
            node_json = {'uid': n.id, 'networks': []}

            for nic in n.nic_interfaces:
                assigned_networks = nic.assigned_networks_list
                # in case of using bond interface - use networks assigned
                # to bond
                if nic.bond:
                    assigned_networks = nic.bond.assigned_networks_list
                vlans = []
                for ng in assigned_networks:
                    # Handle FuelWeb admin network first.
                    if not ng.cluster_id:
                        vlans.append(0)
                        continue
                    data_ng = filter(lambda i: i['name'] == ng.name, data)[0]
                    if data_ng['vlans']:
                        vlans.extend(data_ng['vlans'])
                    else:
                        # in case absence of vlans net_probe will
                        # send packages on untagged iface
                        vlans.append(0)
                if not vlans:
                    continue
                node_json['networks'].append(
                    {'iface': nic.name, 'vlans': vlans}
                )
            nodes.append(node_json)
        return {
            'method': task.name,
            'respond_to': '{0}_resp'.format(task.name),
            'args': {'task_uuid': task.uuid,
                     'nodes': nodes},
            'subtasks': dict(cls._subtask_message(task))}

    @classmethod
    def execute(cls, task, data):
        message = cls._message(task, data)
        logger.debug("%s method is called with: %s",
                     task.name, message)

        task.cache = message
        db().add(task)
        db().commit()
        rpc.cast('naily', message)


class CheckNetworksTask(object):

    @classmethod
    def execute(cls, task, data, check_admin_untagged=False):

        checker = NetworkCheck(task, data)
        checker.check_configuration()
        if check_admin_untagged:
            warn_msgs = checker.check_interface_mapping()
            if warn_msgs:
                task.result = {"warning": warn_msgs}
                db().commit()


class CheckBeforeDeploymentTask(object):

    @classmethod
    def execute(cls, task):
        cls._check_nodes_are_online(task)
        cls._check_controllers_count(task)
        cls._check_disks(task)
        cls._check_ceph(task)
        cls._check_volumes(task)
        cls._check_network(task)

    @classmethod
    def _check_nodes_are_online(cls, task):
        offline_nodes = db().query(Node).\
            filter(Node.cluster == task.cluster).\
            filter_by(online=False).\
            filter_by(pending_deletion=False).\
            filter(not_(Node.status.in_(['ready'])))

        if offline_nodes.count():
            node_names = ','.join(map(lambda n: n.full_name, offline_nodes))
            raise errors.NodeOffline(
                u'Nodes "{0}" are offline.'
                ' Remove them from environment '
                'and try again.'.format(node_names))

    @classmethod
    def _check_controllers_count(cls, task):
        controllers_count = len(filter(
            lambda node: 'controller' in node.all_roles,
            task.cluster.nodes)
        )
        cluster_mode = task.cluster.mode

        if cluster_mode == 'multinode' and controllers_count < 1:
            raise errors.NotEnoughControllers(
                "Not enough controllers, %s mode requires at least 1 "
                "controller" % (cluster_mode))
        elif cluster_mode == 'ha_compact' and controllers_count < 1:
            raise errors.NotEnoughControllers(
                "Not enough controllers, %s mode requires at least 1 "
                "controller" % (cluster_mode))

    @classmethod
    def _check_disks(cls, task):
        try:
            for node in task.cluster.nodes:
                if cls._is_disk_checking_required(node):
                    node.volume_manager.check_disk_space_for_deployment()
        except errors.NotEnoughFreeSpace:
            raise errors.NotEnoughFreeSpace(
                u"Node '{0}' has insufficient disk space".format(
                    node.human_readable_name
                )
            )

    @classmethod
    def _check_volumes(cls, task):
        try:
            for node in task.cluster.nodes:
                if cls._is_disk_checking_required(node):
                    node.volume_manager.check_volume_sizes_for_deployment()
        except errors.NotEnoughFreeSpace as e:
            raise errors.NotEnoughFreeSpace(
                u"Node '%s' has insufficient disk space\n%s" % (
                    node.human_readable_name, e.message))

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
    def _is_disk_checking_required(cls, node):
        """Disk checking required in case if node is not provisioned.
        """
        if node.status in ('ready', 'deploying') or \
           (node.status == 'error' and node.error_type != 'provision'):
            return False

        return True

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
    def _check_network(cls, task):
        nodes_count = len(task.cluster.nodes)

        public_network = filter(
            lambda ng: ng.name == 'public',
            task.cluster.network_groups)[0]
        public_network_size = cls.__network_size(public_network)

        if public_network_size < nodes_count:
            error_message = cls.__format_network_error(nodes_count)
            raise errors.NetworkCheckError(error_message)

    @classmethod
    def __network_size(cls, network):
        return sum(len(netaddr.IPRange(ip_range.first, ip_range.last))
                   for ip_range in network.ip_ranges)

    @classmethod
    def __format_network_error(cls, nodes_count):
        return 'Not enough IP addresses. Public network must have at least '\
            '{nodes_count} IP addresses '.format(nodes_count=nodes_count) + \
            'for the current environment.'


# Red Hat related tasks

class RedHatTask(object):

    @classmethod
    def message(cls, task, data):
        raise NotImplementedError()

    @classmethod
    def execute(cls, task, data):
        logger.debug(
            "%s(uuid=%s) is running" %
            (cls.__name__, task.uuid)
        )
        message = cls.message(task, data)
        task.cache = message
        task.result = {'release_info': data}
        db().add(task)
        db().commit()
        rpc.cast('naily', message)


class RedHatDownloadReleaseTask(RedHatTask):

    @classmethod
    def message(cls, task, data):
        # TODO(NAME): fix this ugly code
        cls.__update_release_state(
            data["release_id"]
        )
        return {
            'method': 'download_release',
            'respond_to': 'download_release_resp',
            'args': {
                'task_uuid': task.uuid,
                'release_info': data
            }
        }

    @classmethod
    def __update_release_state(cls, release_id):
        release = db().query(Release).get(release_id)
        release.state = 'downloading'
        db().commit()


class RedHatCheckCredentialsTask(RedHatTask):

    @classmethod
    def message(cls, task, data):
        return {
            "method": "check_redhat_credentials",
            "respond_to": "check_redhat_credentials_resp",
            "args": {
                "task_uuid": task.uuid,
                "release_info": data
            }
        }


class RedHatCheckLicensesTask(RedHatTask):

    @classmethod
    def message(cls, task, data, nodes=None):
        msg = {
            'method': 'check_redhat_licenses',
            'respond_to': 'redhat_check_licenses_resp',
            'args': {
                'task_uuid': task.uuid,
                'release_info': data
            }
        }
        if nodes:
            msg['args']['nodes'] = nodes
        return msg


class DumpTask(object):
    @classmethod
    def conf(cls):
        logger.debug("Preparing config for snapshot")
        nodes = db().query(Node).filter(
            Node.status.in_(['ready', 'provisioned', 'deploying', 'error'])
        ).all()

        dump_conf = settings.DUMP
        dump_conf['dump_roles']['slave'] = [n.fqdn for n in nodes]
        logger.debug("Dump slave nodes: %s",
                     ", ".join(dump_conf['dump_roles']['slave']))

        """
        here we try to filter out sensitive data from logs
        """
        rh_accounts = db().query(RedHatAccount).all()
        for num, obj in enumerate(dump_conf['dump_objects']['master']):
            if obj['type'] == 'subs' and obj['path'] == '/var/log/remote':
                for fieldname in ("username", "password"):
                    for fieldvalue in [getattr(acc, fieldname)
                                       for acc in rh_accounts]:
                        obj['subs'][fieldvalue] = ('substituted_{0}'
                                                   ''.format(fieldname))
        logger.debug("Dump conf: %s", str(dump_conf))
        return dump_conf

    @classmethod
    def execute(cls, task):
        logger.debug("DumpTask: task={0}".format(task.uuid))
        message = {
            'method': 'dump_environment',
            'respond_to': 'dump_environment_resp',
            'args': {
                'task_uuid': task.uuid,
                'settings': cls.conf()
            }
        }
        task.cache = message
        db().add(task)
        db().commit()
        rpc.cast('naily', message)


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

        nodes = db().query(Node).options(
            joinedload('role_list'))
        roles_stat = {}
        for node in nodes:
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
        db().commit()

        task.result = {'log_id': capacity_log.id}
        task.status = 'ready'
        task.progress = '100'
        db().add(task)
        db().commit()
