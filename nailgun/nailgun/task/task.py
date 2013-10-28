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

import shlex
import subprocess

import netaddr
from sqlalchemy import func
from sqlalchemy.orm import ColumnProperty
from sqlalchemy.orm import joinedload
from sqlalchemy.orm import object_mapper

from nailgun.api.models import Attributes
from nailgun.api.models import CapacityLog
from nailgun.api.models import Cluster
from nailgun.api.models import NetworkGroup
from nailgun.api.models import Node
from nailgun.api.models import RedHatAccount
from nailgun.api.models import Release
from nailgun.db import db
from nailgun.errors import errors
from nailgun.logger import logger
from nailgun.network.manager import NetworkManager
from nailgun.network.neutron import NeutronManager
from nailgun.orchestrator import deployment_serializers
from nailgun.orchestrator import provisioning_serializers
import nailgun.rpc as rpc
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
    def message(cls, task):
        logger.debug("DeploymentTask.message(task=%s)" % task.uuid)

        task.cluster.prepare_for_deployment()
        nodes = TaskHelper.nodes_to_deploy(task.cluster)
        nodes_ids = [n.id for n in nodes]
        for n in db().query(Node).filter_by(
                cluster=task.cluster).order_by(Node.id):
            # However, we must not pass nodes which are set to be deleted.
            if n.pending_deletion:
                continue

            if n.id in nodes_ids:
                if n.pending_roles:
                    n.roles += n.pending_roles
                    n.pending_roles = []
                if n.status in ('deploying'):
                    n.status = 'provisioned'
                n.progress = 0
                db().add(n)
                db().commit()

        # here we replace provisioning data if user redefined them
        serialized_cluster = task.cluster.replaced_deployment_info or \
            deployment_serializers.serialize(task.cluster)

        # After searilization set pending_addition to False
        for node in db().query(Node).filter(Node.id.in_(nodes_ids)):
            node.pending_addition = False
        db().commit()

        return {
            'method': 'deploy',
            'respond_to': 'deploy_resp',
            'args': {
                'task_uuid': task.uuid,
                'deployment_info': serialized_cluster}}

    @classmethod
    def execute(cls, task):
        logger.debug("DeploymentTask.execute(task=%s)" % task.uuid)
        message = cls.message(task)
        task.cache = message
        db().add(task)
        db().commit()
        rpc.cast('naily', message)


class ProvisionTask(object):

    @classmethod
    def message(cls, task):
        logger.debug("ProvisionTask.message(task=%s)" % task.uuid)
        nodes = TaskHelper.nodes_to_provision(task.cluster)
        USE_FAKE = settings.FAKE_TASKS or settings.FAKE_TASKS_AMQP

        # We need to assign admin ips
        # and only after that prepare syslog
        # directories
        task.cluster.prepare_for_provisioning()

        for node in nodes:
            if USE_FAKE:
                continue

            if node.offline:
                raise errors.NodeOffline(
                    u'Node "%s" is offline.'
                    ' Remove it from environment and try again.' %
                    node.full_name)

            TaskHelper.prepare_syslog_dir(node)

            node.status = 'provisioning'
            db().commit()

        serialized_cluster = task.cluster.replaced_provisioning_info or \
            provisioning_serializers.serialize(task.cluster)

        message = {
            'method': 'provision',
            'respond_to': 'provision_resp',
            'args': {
                'task_uuid': task.uuid,
                'provisioning_info': serialized_cluster}}

        return message

    @classmethod
    def execute(cls, task):
        logger.debug("ProvisionTask.execute(task=%s)" % task.uuid)
        message = cls.message(task)
        task.cache = message
        db().add(task)
        db().commit()
        rpc.cast('naily', message)


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

        # no need to call naily if there are no nodes in cluster
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
                    'roles': node.roles
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
            if not node_db.online or node_db.status == 'discover':
                logger.info(
                    "Node is offline or not deployed yet,"
                    " can't clean MBR: %s", slave_name)
                db().delete(node_db)
                db().commit()

                nodes_to_delete.remove(node)

        # only real tasks
        engine_nodes = []
        if not USE_FAKE:
            for node in nodes_to_delete_constant:
                slave_name = TaskHelper.make_slave_name(node['id'])
                logger.debug("Pending node to be removed from cobbler %s",
                             slave_name)
                engine_nodes.append(slave_name)
                try:
                    node_db = db().query(Node).get(node['id'])
                    if node_db and node_db.fqdn:
                        node_hostname = node_db.fqdn
                    else:
                        node_hostname = TaskHelper.make_slave_fqdn(node['id'])
                    logger.info("Removing node cert from puppet: %s",
                                node_hostname)
                    cmd = "puppet cert clean {0}".format(node_hostname)
                    proc = subprocess.Popen(
                        shlex.split(cmd),
                        shell=False,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE
                    )
                    p_stdout, p_stderr = proc.communicate()
                    logger.info(
                        "'{0}' executed, STDOUT: '{1}',"
                        " STDERR: '{2}'".format(
                            cmd,
                            p_stdout,
                            p_stderr
                        )
                    )
                except OSError:
                    logger.warning(
                        "'{0}' returned non-zero exit code".format(
                            cmd
                        )
                    )
                except Exception as e:
                    logger.warning("Exception occurred while trying to \
                            remove the system from Cobbler: '{0}'".format(
                        e.message))

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
                },
                'engine_nodes': engine_nodes
            }
        }
        # only fake tasks
        if USE_FAKE and nodes_to_restore:
            msg_delete['args']['nodes_to_restore'] = nodes_to_restore
        # /only fake tasks
        logger.debug("Calling rpc remove_nodes method")
        rpc.cast('naily', msg_delete)


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
            for nic in n.interfaces:
                vlans = []
                for ng in nic.assigned_networks:
                    # Handle FuelWeb admin network first.
                    if not ng.cluster_id:
                        vlans.append(0)
                        continue
                    data_ng = filter(
                        lambda i: i['name'] == ng.name,
                        data
                    )[0]
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
        if task.cluster.net_provider == 'neutron':
            cls.neutron_check_config(task, data)
            if check_admin_untagged:
                cls.neutron_check_interface_mapping(task, data)
        elif task.cluster.net_provider == 'nova_network':
            cls.nova_net_check(task, data, check_admin_untagged)

    @classmethod
    def nova_net_check(cls, task, data, check_admin_untagged):
        # If not set in data then fetch from db
        if 'net_manager' in data:
            netmanager = data['net_manager']
        else:
            netmanager = task.cluster.net_manager

        if 'networks' in data:
            networks = data['networks']
        else:
            networks = map(lambda x: x.__dict__, task.cluster.network_groups)

        result = []
        err_msgs = []

        # checking if there are untagged
        # networks on the same interface
        # (main) as admin network
        if check_admin_untagged:
            untagged_nets = set(
                n["id"] for n in filter(
                    lambda n: (n["vlan_start"] is None), networks))
            if untagged_nets:
                logger.info(
                    "Untagged networks found, "
                    "checking admin network intersection...")
                admin_interfaces = map(lambda node: node.admin_interface,
                                       task.cluster.nodes)
                found_intersection = []

                for iface in admin_interfaces:
                    nets = dict(
                        (n.id, n.name)
                        for n in iface.assigned_networks)

                    err_nets = set(nets.keys()) & untagged_nets
                    if err_nets:
                        err_net_names = [
                            '"{0}"'.format(nets[i]) for i in err_nets]
                        found_intersection.append(
                            [iface.node.name, err_net_names])

                if found_intersection:
                    nodes_with_errors = [
                        u'Node "{0}": {1}'.format(
                            name,
                            ", ".join(_networks)
                        ) for name, _networks in found_intersection]
                    err_msg = u"Some untagged networks are " \
                              "assigned to the same physical interface as " \
                              "admin (PXE) network. You can whether turn " \
                              "on tagging for these OpenStack " \
                              "networks or move them to another physical " \
                              "interface:\n{0}".format("\n".join(
                                  nodes_with_errors))
                    raise errors.NetworkCheckError(err_msg, add_client=False)

        net_man = NetworkManager()
        admin_ng = net_man.get_admin_network_group()
        admin_range = netaddr.IPNetwork(admin_ng.cidr)
        for ng in networks:
            net_errors = []
            sub_ranges = []
            ng_db = db().query(NetworkGroup).get(ng['id'])
            if not ng_db:
                net_errors.append("id")
                err_msgs.append(u"Invalid network ID: {0}".format(ng['id']))
            else:
                if ng.get('cidr'):
                    fnet = netaddr.IPNetwork(ng['cidr'])
                    if net_man.is_range_intersection(fnet, admin_range):
                        net_errors.append("cidr")
                        err_msgs.append(
                            u"Intersection with admin "
                            "network(s) '{0}' found".format(
                                admin_ng.cidr
                            )
                        )
                    if fnet.size < ng['network_size'] * ng['amount']:
                        net_errors.append("cidr")
                        err_msgs.append(
                            u"CIDR size for network '{0}' "
                            "is less than required".format(
                                ng.get('name') or ng_db.name or ng_db.id
                            )
                        )
                # Check for intersection with Admin network
                if 'ip_ranges' in ng:
                    for k, v in enumerate(ng['ip_ranges']):
                        ip_range = netaddr.IPRange(v[0], v[1])
                        if net_man.is_range_intersection(admin_range,
                                                         ip_range):
                            net_errors.append("cidr")
                            err_msgs.append(
                                u"IP range {0} - {1} in {2} network intersects"
                                " with admin range of {3}".format(
                                    v[0], v[1],
                                    ng.get('name') or ng_db.name or ng_db.id,
                                    admin_ng.cidr
                                )
                            )
                            sub_ranges.append(k)

                if ng.get('amount') > 1 and netmanager == 'FlatDHCPManager':
                    net_errors.append("amount")
                    err_msgs.append(
                        u"Network amount for '{0}' is more than 1 "
                        "while using FlatDHCP manager.".format(
                            ng.get('name') or ng_db.name or ng_db.id
                        )
                    )
            if net_errors:
                result.append({
                    "id": int(ng["id"]),
                    "range_errors": sub_ranges,
                    "errors": net_errors
                })
        if err_msgs:
            task.result = result
            db().add(task)
            db().commit()
            full_err_msg = "\n".join(err_msgs)
            raise errors.NetworkCheckError(full_err_msg, add_client=False)

    @classmethod
    def neutron_check_config(cls, task, data):

        if 'networks' in data:
            networks = data['networks']
        else:
            networks = map(lambda x: x.__dict__, task.cluster.network_groups)

        result = []

        # check: networks VLAN IDs should not be in
        # Neutron L2 private VLAN ID range (VLAN segmentation only)
        tagged_nets = dict((n["name"], n["vlan_start"]) for n in filter(
            lambda n: (n["vlan_start"] is not None), networks))

        if tagged_nets:
            if task.cluster.net_segment_type == 'vlan':
                if 'neutron_parameters' in data:
                    l2cfg = data['neutron_parameters']['L2']
                else:
                    l2cfg = task.cluster.neutron_config.L2
                for net, net_conf in l2cfg['phys_nets'].iteritems():
                    vrange = net_conf['vlan_range']
                    if vrange:
                        break
                else:
                    err_msg = u"Wrong VLAN range.\n"
                    raise errors.NetworkCheckError(err_msg, add_client=False)

                net_intersect = [name for name, vlan in tagged_nets.iteritems()
                                 if vrange[0] <= vlan <= vrange[1]]
                if net_intersect:
                    nets_with_errors = ", ".\
                        join(net_intersect)
                    err_msg = u"Networks VLAN tags are in " \
                              "ID range defined for Neutron L2. " \
                              "You should assign VLAN tags that are " \
                              "not in Neutron L2 VLAN ID range:\n{0}". \
                        format(nets_with_errors)
                    raise errors.NetworkCheckError(err_msg, add_client=False)

            # check: networks VLAN IDs should not intersect
            net_intersect = [name for name, vlan in tagged_nets.iteritems()
                             if tagged_nets.values().count(vlan) >= 2]
            if net_intersect:
                nets_with_errors = ", ". \
                    join(net_intersect)
                err_msg = u"Some networks use the same VLAN tags. " \
                          "You should assign different VLAN tag " \
                          "to every network:\n{0}". \
                    format(nets_with_errors)
                raise errors.NetworkCheckError(err_msg, add_client=False)

        def expose_error_messages():
            if err_msgs:
                task.result = result
                db().add(task)
                db().commit()
                full_err_msg = "\n".join(err_msgs)
                raise errors.NetworkCheckError(full_err_msg, add_client=False)

        # check intersection of address ranges
        # between admin networks and all other networks
        net_man = NeutronManager()
        admin_ng = net_man.get_admin_network_group()
        admin_range = netaddr.IPNetwork(admin_ng.cidr)
        err_msgs = []
        for ng in networks:
            net_errors = []
            sub_ranges = []
            ng_db = db().query(NetworkGroup).get(ng['id'])
            if not ng_db:
                net_errors.append("id")
                err_msgs.append("Invalid network ID: {0}".format(ng['id']))
            else:
                if ng.get('cidr'):
                    fnet = netaddr.IPNetwork(ng['cidr'])
                    if net_man.is_range_intersection(fnet, admin_range):
                        net_errors.append("cidr")
                        err_msgs.append(
                            u"Intersection with admin "
                            "network(s) '{0}' found".format(
                                admin_ng.cidr
                            )
                        )
                    # ng['amount'] is always equal 1 for Neutron
                    if fnet.size < ng['network_size']:  # * ng['amount']:
                        net_errors.append("cidr")
                        err_msgs.append(
                            u"CIDR size for network '{0}' "
                            "is less than required".format(
                                ng.get('name') or ng_db.name or ng_db.id
                            )
                        )
                # Check for intersection with Admin network
                if 'ip_ranges' in ng:
                    for k, v in enumerate(ng['ip_ranges']):
                        ip_range = netaddr.IPRange(v[0], v[1])
                        if net_man.is_range_intersection(admin_range,
                                                         ip_range):
                            net_errors.append("cidr")
                            err_msgs.append(
                                u"IP range {0} - {1} in {2} network intersects"
                                " with admin range of {3}".format(
                                    v[0], v[1],
                                    ng.get('name') or ng_db.name or ng_db.id,
                                    admin_ng.cidr
                                )
                            )
                            sub_ranges.append(k)
            if net_errors:
                result.append({
                    "id": int(ng["id"]),
                    "range_errors": sub_ranges,
                    "errors": net_errors
                })
        expose_error_messages()

        # check intersection of address ranges
        # between networks except admin network
        ng_names = dict((ng['id'], (ng.get('name')) or
                         db().query(NetworkGroup).get(ng['id']).name)
                        for ng in networks)
        ngs = list(networks)
        for ng1 in networks:
            net_errors = []
            ngs.remove(ng1)
            for ng2 in ngs:
                if ng1.get('cidr') and ng2.get('cidr'):
                    cidr1 = netaddr.IPNetwork(ng1['cidr'])
                    cidr2 = netaddr.IPNetwork(ng2['cidr'])
                    if net_man.is_cidr_intersection(cidr1, cidr2):
                        net_errors.append("cidr")
                        err_msgs.append(
                            u"Intersection between network address "
                            "spaces found:\n{0}".format(
                                ", ".join([ng_names[ng1['id']],
                                           ng_names[ng2['id']]])
                            )
                        )
            if net_errors:
                result.append({
                    "id": int(ng1["id"]),
                    "errors": net_errors
                })
        expose_error_messages()

        # check Public gateway, Floating Start and Stop IPs
        # belong to Public CIDR
        if 'neutron_parameters' in data:
            pre_net = data['neutron_parameters']['predefined_networks']
        else:
            pre_net = task.cluster.neutron_config.predefined_networks
        public = [n for n in networks if n['name'] == 'public'][0]
        net_errors = []
        fl_range = pre_net['net04_ext']['L3']['floating']
        if public.get('cidr') and public.get('gateway'):
            cidr = netaddr.IPNetwork(public['cidr'])
            if netaddr.IPAddress(public['gateway']) not in cidr:
                net_errors.append("gateway")
                err_msgs.append(
                    u"Public gateway {0} is not in Public "
                    "address space {1}.".format(
                        public['gateway'], public['cidr']
                    )
                )
            if netaddr.IPRange(fl_range[0], fl_range[1]) not in cidr:
                net_errors.append("float_range")
                err_msgs.append(
                    u"Floating address range {0}:{1} is not in Public "
                    "address space {2}.".format(
                        netaddr.IPAddress(fl_range[0]),
                        netaddr.IPAddress(fl_range[1]),
                        public['cidr']
                    )
                )
        else:
            net_errors.append("format")
            err_msgs.append(
                u"Public gateway or CIDR specification is invalid."
            )
        result = {"id": int(public["id"]), "errors": net_errors}
        expose_error_messages()

        # check internal Gateway is in Internal CIDR
        internal = pre_net['net04']['L3']
        if internal.get('cidr') and internal.get('gateway'):
            cidr = netaddr.IPNetwork(internal['cidr'])
            if netaddr.IPAddress(internal['gateway']) not in cidr:
                net_errors.append("gateway")
                err_msgs.append(
                    u"Internal gateway {0} is not in Internal "
                    "address space {1}.".format(
                        internal['gateway'], internal['cidr']
                    )
                )
            if net_man.is_range_intersection(
                    netaddr.IPRange(fl_range[0], fl_range[1]),
                    cidr):
                net_errors.append("cidr")
                err_msgs.append(
                    u"Intersection between Internal CIDR and Floating range."
                )
        else:
            net_errors.append("format")
            err_msgs.append(
                u"Internal gateway or CIDR specification is invalid."
            )
        result = {"name": "internal", "errors": net_errors}
        expose_error_messages()

    @classmethod
    def neutron_check_interface_mapping(cls, task, data):

        if 'networks' in data:
            networks = data['networks']
        else:
            networks = map(lambda x: x.__dict__, task.cluster.network_groups)

        # check if there any networks
        # on the same interface as admin network (main)
        admin_interfaces = map(lambda node: node.admin_interface,
                               task.cluster.nodes)
        found_intersection = []

        all_roles = set(n["id"] for n in networks)
        for iface in admin_interfaces:
            nets = dict(
                (n.id, n.name)
                for n in iface.assigned_networks)

            err_nets = set(nets.keys()) & all_roles
            if err_nets:
                err_net_names = [
                    '"{0}"'.format(nets[i]) for i in err_nets]
                found_intersection.append(
                    [iface.node.name, err_net_names])

        if found_intersection:
            nodes_with_errors = [
                u'Node "{0}": {1}'.format(
                    name,
                    ", ".join(_networks)
                ) for name, _networks in found_intersection]
            err_msg = u"Some networks are " \
                      "assigned to the same physical interface as " \
                      "admin (PXE) network. You should move them to " \
                      "another physical interfaces:\n{0}". \
                format("\n".join(nodes_with_errors))
            raise errors.NetworkCheckError(err_msg, add_client=False)

        # check if there any networks
        # on the same interface as private network (for vlan)
        if task.cluster.net_segment_type == 'vlan':
            private_interfaces = []
            # there should be shorter method to do this !
            for node in task.cluster.nodes:
                for iface in node.interfaces:
                    for anet in iface.assigned_networks:
                        if anet.name == 'private':
                            private_interfaces.append(iface)
            found_intersection = []

            all_roles = set(n["id"] for n in networks
                            if n["name"] != 'private')
            for iface in private_interfaces:
                nets = dict(
                    (n.id, n.name)
                    for n in iface.assigned_networks)

                err_nets = set(nets.keys()) & all_roles
                if err_nets:
                    err_net_names = [
                        '"{0}"'.format(nets[i]) for i in err_nets]
                    found_intersection.append(
                        [iface.node.name, err_net_names])

            if found_intersection:
                nodes_with_errors = [
                    u'Node "{0}": {1}'.format(
                        name,
                        ", ".join(_networks)
                    ) for name, _networks in found_intersection]
                err_msg = u"Some networks are " \
                          "assigned to the same physical interface as " \
                          "private network. You should move them to " \
                          "another physical interfaces:\n{0}". \
                    format("\n".join(nodes_with_errors))
                raise errors.NetworkCheckError(err_msg, add_client=False)

        # check untagged networks intersection
        untagged_nets = set(
            n["id"] for n in filter(
                lambda n: (n["vlan_start"] is None), networks))
        if untagged_nets:
            logger.info(
                "Untagged networks found, "
                "checking intersection between them...")
            interfaces = []
            for node in task.cluster.nodes:
                for iface in node.interfaces:
                    interfaces.append(iface)
            found_intersection = []

            for iface in interfaces:
                nets = dict(
                    (n.id, n.name)
                    for n in iface.assigned_networks)

                crossed_nets = set(nets.keys()) & untagged_nets
                if len(crossed_nets) > 1:
                    err_net_names = [
                        '"{0}"'.format(nets[i]) for i in crossed_nets]
                    found_intersection.append(
                        [iface.node.name, err_net_names])

            if found_intersection:
                nodes_with_errors = [
                    u'Node "{0}": {1}'.format(
                        name,
                        ", ".join(_networks)
                    ) for name, _networks in found_intersection]
                err_msg = u"Some untagged networks are " \
                          "assigned to the same physical interface. " \
                          "You should assign them to " \
                          "different physical interfaces:\n{0}". \
                    format("\n".join(nodes_with_errors))
                raise errors.NetworkCheckError(err_msg, add_client=False)


class CheckBeforeDeploymentTask(object):
    @classmethod
    def execute(cls, task):
        cls.__check_controllers_count(task)
        cls.__check_disks(task)
        cls.__check_ceph(task)
        cls.__check_network(task)

    @classmethod
    def __check_controllers_count(cls, task):
        controllers_count = len(filter(
            lambda node: 'controller' in node.all_roles,
            task.cluster.nodes)
        )
        cluster_mode = task.cluster.mode

        if cluster_mode == 'multinode' and controllers_count < 1:
            raise errors.NotEnoughControllers(
                "Not enough controllers, %s mode requires at least 1 "
                "controller" % (cluster_mode))
        elif cluster_mode == 'ha_compact' and controllers_count < 3:
            raise errors.NotEnoughControllers(
                "Not enough controllers, %s mode requires at least 3 "
                "controllers" % (cluster_mode))

    @classmethod
    def __check_disks(cls, task):
        try:
            for node in task.cluster.nodes:
                node.volume_manager.check_disk_space_for_deployment()
        except errors.NotEnoughFreeSpace:
            raise errors.NotEnoughFreeSpace(
                u"Node '%s' has insufficient disk space" %
                node.human_readable_name)

    @classmethod
    def __check_ceph(cls, task):
        storage = task.cluster.attributes.merged_attrs()['storage']
        for option in storage:
            if '_ceph' in option and\
               storage[option] and\
               storage[option]['value'] is True:
                cls.__check_ceph_osds(task)
                return

    @classmethod
    def __check_ceph_osds(cls, task):
        osd_count = len(filter(
            lambda node: 'ceph-osd' in node.all_roles,
            task.cluster.nodes))
        osd_pool_size = int(task.cluster.attributes.merged_attrs(
        )['storage']['osd_pool_size']['value'])
        if osd_count < osd_pool_size:
            raise errors.NotEnoughOsdNodes(
                'Number of OSD nodes (%s) cannot be less than '
                'the Ceph object replication factor (%s)' %
                (osd_count, osd_pool_size))

    @classmethod
    def __check_network(cls, task):
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
        logger.debug("Getting redhat parameters to filter them out")
        rh_accounts = db().query(RedHatAccount).all()
        for fieldname in ("username", "password"):
            for obscure in [getattr(acc, fieldname)
                            for acc in rh_accounts]:
                dump_conf['subs'].update({obscure: "OBSCURE_PARAMETER"})

        logger.debug("Getting obscure parameters to filter them out")
        for obscure in Attributes.obscure():
            dump_conf["subs"].update({obscure: "OBSCURE_PARAMETER"})

        logger.debug("Dump conf: %s", str(dump_conf))
        return dump_conf

    @classmethod
    def execute(cls, task):
        logger.debug("DumpTask: task=%s" % task.uuid)
        message = {
            'method': 'dump_environment',
            'respond_to': 'dump_environment_resp',
            'args': {
                'task_uuid': task.uuid,
                'lastdump': settings.DUMP["lastdump"]
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


def dump():
    """Entry point dump script."""
    from shotgun.config import Config as ShotgunConfig
    from shotgun.manager import Manager as ShotgunManager
    logger.debug("Starting snapshot procedure")
    conf = ShotgunConfig(DumpTask.conf())
    manager = ShotgunManager(conf)
    print(manager.snapshot())
