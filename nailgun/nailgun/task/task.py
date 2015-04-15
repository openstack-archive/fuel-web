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

from copy import deepcopy
from distutils.version import StrictVersion

import netaddr
import six

from sqlalchemy import func
from sqlalchemy import not_
from sqlalchemy.orm import ColumnProperty
from sqlalchemy.orm import joinedload
from sqlalchemy.orm import object_mapper

import nailgun.rpc as rpc

from nailgun import objects

from nailgun import consts
from nailgun.db import db
from nailgun.db.sqlalchemy.models import CapacityLog
from nailgun.db.sqlalchemy.models import Cluster
from nailgun.db.sqlalchemy.models import Node
from nailgun.errors import errors
from nailgun.logger import logger
from nailgun.network.checker import NetworkCheck
from nailgun.orchestrator import deployment_graph
from nailgun.orchestrator import deployment_serializers
from nailgun.orchestrator import provisioning_serializers
from nailgun.orchestrator import stages
from nailgun.settings import settings
from nailgun.task.fake import FAKE_THREADS
from nailgun.task.helpers import TaskHelper
from nailgun.utils.restrictions import VmwareAttributesRestriction
from nailgun.utils.zabbix import ZabbixManager


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
    def _get_deployment_method(cls, cluster):
        """Get deployment method name based on cluster version

        :param cluster: Cluster db object
        :returns: string - deploy/granular_deploy
        """
        if (StrictVersion(cluster.release.fuel_version) <
                StrictVersion(consts.FUEL_GRANULAR_DEPLOY)):
            return 'deploy'
        return 'granular_deploy'

    @classmethod
    def message(cls, task, nodes, deployment_tasks=None):
        logger.debug("DeploymentTask.message(task=%s)" % task.uuid)
        deployment_tasks = deployment_tasks or []

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
                if n.status in (consts.NODE_STATUSES.deploying,):
                    n.status = consts.NODE_STATUSES.provisioned
                n.progress = 0
                db().add(n)
        db().flush()

        orchestrator_graph = deployment_graph.AstuteGraph(task.cluster)
        orchestrator_graph.only_tasks(deployment_tasks)

        #NOTE(dshulyak) At this point parts of the orchestration can be empty,
        # it should not cause any issues with deployment/progress and was
        # done by design
        serialized_cluster = deployment_serializers.serialize(
            orchestrator_graph, task.cluster, nodes)
        pre_deployment = stages.pre_deployment_serialize(
            orchestrator_graph, task.cluster, nodes)
        post_deployment = stages.post_deployment_serialize(
            orchestrator_graph, task.cluster, nodes)

        # After serialization set pending_addition to False
        for node in nodes:
            node.pending_addition = False

        rpc_message = make_astute_message(
            task,
            cls._get_deployment_method(task.cluster),
            'deploy_resp',
            {
                'deployment_info': serialized_cluster,
                'pre_deployment': pre_deployment,
                'post_deployment': post_deployment
            }
        )
        db().flush()
        return rpc_message


class UpdateTask(object):

    @classmethod
    def message(cls, task, nodes):
        logger.debug("%s.message(task=%s)", cls.__class__.__name__, task.uuid)

        for n in nodes:
            if n.pending_roles:
                n.roles += n.pending_roles
                n.pending_roles = []
            n.status = 'provisioned'
            n.progress = 0

        orchestrator_graph = deployment_graph.AstuteGraph(task.cluster)

        serialized_cluster = deployment_serializers.serialize(
            orchestrator_graph, task.cluster, nodes)

        # After serialization set pending_addition to False
        for node in nodes:
            node.pending_addition = False

        rpc_message = make_astute_message(
            task,
            'deploy',
            'deploy_resp',
            {
                'deployment_info': serialized_cluster
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

            admin_net_id = objects.Node.get_network_manager(
                node
            ).get_admin_network_group_id(node.id)

            TaskHelper.prepare_syslog_dir(node, admin_net_id)

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
            'slave_name': objects.Node.make_slave_name(node),
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
        :returns: Remaining (non-undeployed) nodes to delete.
        """

        node_names_dict = dict(
            (node['id'], node['slave_name']) for node in nodes_to_delete)

        objects.NodeCollection \
            .filter_by_list(None, 'id', six.iterkeys(node_names_dict)) \
            .filter(
                objects.Node.model.status == consts.NODE_STATUSES.discover
            ) \
            .delete(synchronize_session=False)
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
    def execute(cls, task, nodes=None, respond_to='remove_nodes_resp'):
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

        # check if there's a Zabbix server in an environment
        # and if there is, remove hosts
        if (task.name != consts.TASK_NAMES.cluster_deletion
                and ZabbixManager.get_zabbix_node(task.cluster)):
            zabbix_credentials = ZabbixManager.get_zabbix_credentials(
                task.cluster
            )
            logger.debug("Removing nodes %s from zabbix", nodes_to_delete)
            try:
                ZabbixManager.remove_from_zabbix(
                    zabbix_credentials, nodes_to_delete
                )
            except (errors.CannotMakeZabbixRequest,
                    errors.ZabbixRequestError) as e:
                logger.warning("%s, skipping removing nodes from Zabbix", e)

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
                        'slave_name': objects.Node.make_slave_name(n),
                        'admin_ip': objects.Node.get_network_manager(
                            n
                        ).get_admin_ip_for_node(n.id)
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
                        'slave_name': objects.Node.make_slave_name(n)
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

    @classmethod
    def execute(cls, task):
        rpc.cast('naily', cls.message(task))


class ClusterDeletionTask(object):

    @classmethod
    def execute(cls, task):
        logger.debug("Cluster deletion task is running")
        DeletionTask.execute(
            task,
            nodes=DeletionTask.get_task_nodes_for_cluster(task.cluster),
            respond_to='remove_cluster_resp')


class BaseNetworkVerification(object):

    def __init__(self, task, config):
        self.task = task
        self.config = config

    def get_message_body(self):
        nodes = []
        for n in self.task.cluster.nodes:
            node_json = {'uid': n.id, 'networks': []}

            for iface in n.interfaces:
                vlans = []
                for ng in iface.assigned_networks_list:
                    # Handle FuelWeb admin network first.
                    if ng.group_id is None:
                        vlans.append(0)
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
                        {'iface': iface.name, 'vlans': vlans}
                    )
            nodes.append(node_json)

        return nodes

    def get_message(self):
        nodes = self.get_message_body()
        message = make_astute_message(
            self.task,
            self.task.name,
            '{0}_resp'.format(self.task.name),
            {
                'nodes': nodes
            }
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
        """Should be used to verify that subtask is enabled based on
        cluster configuration
        """
        return True


class VerifyNetworksTask(BaseNetworkVerification):

    def __init__(self, *args):
        super(VerifyNetworksTask, self).__init__(*args)
        self.subtasks = []

    def add_subtask(self, subtask):
        self.subtasks.append(subtask.get_message())

    def get_message(self):
        message = super(VerifyNetworksTask, self).get_message()
        message['subtasks'] = self.subtasks
        return message


class CheckDhcpTask(BaseNetworkVerification):
    """Task for dhcp verification
    """


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
        return [dict(self.config, iface=nic[1], uid=str(nic[0]))
                for nic in all_nics]

    @classmethod
    def enabled(cls, cluster):
        """Multicast should be enabled only in case 'corosync' section
        is present in editable attributes, which is not the case if cluster
        was upgraded from 5.0
        """
        #TODO(dshulyak) enable it, when it will be possible to upgrade
        # mcagent and network checker for old envs
        return False


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
        cls._check_public_network(task)
        cls._check_mongo_nodes(task)
        cls._check_vmware_consistency(task)

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
        cluster = task.cluster
        controllers = objects.Cluster.get_nodes_by_role(
            task.cluster, 'controller')
        # we should make sure that cluster has at least one controller
        if len(controllers) < 1:
            raise errors.NotEnoughControllers(
                "Not enough controllers, %s mode requires at least 1 "
                "controller" % (cluster.mode))

        if cluster.status in (
                consts.CLUSTER_STATUSES.operational,
                consts.CLUSTER_STATUSES.error,
                consts.CLUSTER_STATUSES.update_error):
            # get a list of deployed controllers - which are going
            # don't to be changed
            deployed_controllers = filter(
                lambda node: all([
                    node.pending_addition is False,
                    node.pending_deletion is False]),
                controllers)

            # we should fail in case of user remove all controllers and add
            # new in one task, since that's affect cluster's availability
            if not deployed_controllers:
                raise errors.NotEnoughControllers(
                    "Not enough deployed controllers - deployed cluster "
                    "requires at least 1 deployed controller.")

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
        if node.status in ('ready', 'deploying', 'provisioned') or \
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
                nodes_count = sum(int(objects.Node.should_have_public(node))
                                  for node in nodes)
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
        """Mongo nodes shouldn't be present in environment
        if external mongo is chosen.
        """
        components = objects.Attributes.merged_attrs(
            task.cluster.attributes).get("additional_components", None)
        if (components and components["ceilometer"]["value"]
            and components["mongo"]["value"]
                and len(objects.Cluster.get_nodes_by_role(
                        task.cluster, 'mongo')) > 0):
                    raise errors.ExtMongoCheckerError
        if (components and components["ceilometer"]["value"]
            and not components["mongo"]["value"]
                and len(objects.Cluster.get_nodes_by_role(
                        task.cluster, 'mongo')) == 0):
                    raise errors.MongoNodesCheckError

    @classmethod
    def _check_vmware_consistency(cls, task):
        attributes = task.cluster.attributes.editable
        vmware_attributes = task.cluster.vmware_attributes.editable
        cinder_nodes = filter(
            lambda node: 'cinder' in node.all_roles,
            task.cluster.nodes)

        if not cinder_nodes:
            logger.info('There is no any node with "cinder" role provided')

        models = {
            'settings': attributes,
            'default': vmware_attributes,
            'cluster': task.cluster,
            'version': settings.VERSION,
            'networking_parameters': task.cluster.network_config
        }

        errors_msg = VmwareAttributesRestriction.check_data(
            models=models,
            metadata=vmware_attributes['metadata'],
            data=vmware_attributes['value'])

        if errors_msg:
            raise errors.CheckBeforeDeploymentError('\n'.join(errors_msg))


class DumpTask(object):
    @classmethod
    def conf(cls):
        logger.debug("Preparing config for snapshot")
        nodes = db().query(Node).filter(
            Node.status.in_(['ready', 'provisioned', 'deploying', 'error'])
        ).all()

        dump_conf = deepcopy(settings.DUMP)
        for node in nodes:
            host = {
                'address': node.fqdn,
                'ssh-key': settings.SHOTGUN_SSH_KEY,
            }

            # save controllers
            if 'controller' in node.roles:
                dump_conf['dump']['controller']['hosts'].append(host)
            # save slaves
            dump_conf['dump']['slave']['hosts'].append(host)

        # render postgres connection data in dump settings
        dump_conf['dump']['local']['objects'].append({
            'type': 'postgres',
            'dbhost': settings.DATABASE['host'],
            'dbname': settings.DATABASE['name'],
            'username': settings.DATABASE['user'],
            'password': settings.DATABASE['passwd'],
        })

        # render cobbler coonection data in dump settings
        # NOTE: we no need user/password for cobbler
        dump_conf['dump']['local']['objects'].append({
            'type': 'xmlrpc',
            'server': settings.COBBLER_URL,
            'methods': [
                'get_distros',
                'get_profiles',
                'get_systems',
            ],
            'to_file': 'cobbler.txt',
        })

        # inject master host
        dump_conf['dump']['master']['hosts'] = [{
            'address': settings.MASTER_IP,
            'ssh-key': settings.SHOTGUN_SSH_KEY,
        }]

        logger.debug("Dump conf: %s", str(dump_conf))
        return dump_conf

    @classmethod
    def execute(cls, task, conf=None):
        logger.debug("DumpTask: task={0}".format(task.uuid))
        message = make_astute_message(
            task,
            'dump_environment',
            'dump_environment_resp',
            {
                'settings': conf or cls.conf()
            }
        )
        db().flush()
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
        db().flush()

        task.result = {'log_id': capacity_log.id}
        task.status = 'ready'
        task.progress = '100'
        db().commit()
