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

"""
Node-related objects and collections
"""
import itertools
import operator
import traceback

from datetime import datetime

from netaddr import IPAddress
from netaddr import IPNetwork
from sqlalchemy.orm import joinedload
from sqlalchemy.orm import subqueryload_all

from nailgun import consts

from nailgun.objects.serializers.node import NodeSerializer

from nailgun.db import db
from nailgun.db.sqlalchemy import models
from nailgun.errors import errors
from nailgun.logger import logger

from nailgun.objects import Cluster
from nailgun.objects import NailgunCollection
from nailgun.objects import NailgunObject
from nailgun.objects import Notification

from nailgun.settings import settings


class Node(NailgunObject):
    """Node object
    """

    #: SQLAlchemy model for Node
    model = models.Node

    #: Serializer for Node
    serializer = NodeSerializer

    #: Node JSON schema
    schema = {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "title": "Node",
        "description": "Serialized Node object",
        "type": "object",
        "properties": {
            "id": {"type": "number"},
            "cluster_id": {"type": "number"},
            "name": {"type": "string"},
            "status": {
                "type": "string",
                "enum": list(consts.NODE_STATUSES)
            },
            "group_id": {"type": "number"},
            "meta": {"type": "object"},
            "mac": {"type": "string"},
            "fqdn": {"type": "string"},
            "manufacturer": {"type": "string"},
            "platform_name": {"type": "string"},
            "kernel_params": {"type": "string"},
            "progress": {"type": "number"},
            "os_platform": {"type": "string"},
            "pending_addition": {"type": "boolean"},
            "pending_deletion": {"type": "boolean"},
            "error_type": {
                "type": "string",
                "enum": list(consts.NODE_ERRORS)
            },
            "error_msg": {"type": "string"},
            "online": {"type": "boolean"},
            "roles": {"type": "array"},
            "pending_roles": {"type": "array"},
            "agent_checksum": {"type": "string"}
        }
    }

    @classmethod
    def get_by_mac_or_uid(cls, mac=None, node_uid=None):
        """Get Node instance by MAC or ID.

        :param mac: MAC address as string
        :param node_uid: Node ID
        :returns: Node instance
        """
        node = None
        if not mac and not node_uid:
            return node

        q = db().query(cls.model)
        if mac:
            node = q.filter_by(mac=mac.lower()).first()
        else:
            node = q.get(node_uid)
        return node

    @classmethod
    def get_by_hostname(cls, hostname, cluster_id=None):
        """Get Node instance by hostname.

        :param hostname: hostname as string
        :param cluster_id: Cluster ID. If it's not None -
         node will be searched only within the cluster with this ID.
        :returns: Node instance
        """

        if not hostname:
            return None

        q = db().query(cls.model).filter_by(hostname=hostname)
        if cluster_id:
            q = q.filter_by(cluster_id=cluster_id)
        return q.first()

    @classmethod
    def get_by_meta(cls, meta):
        """Search for instance using mac, node id or interfaces

        :param meta: dict with nodes metadata
        :returns: Node instance
        """
        node = cls.get_by_mac_or_uid(
            mac=meta.get('mac'), node_uid=meta.get('id'))

        if not node:
            can_search_by_ifaces = all([
                meta.get('meta'), meta['meta'].get('interfaces')])

            if can_search_by_ifaces:
                node = cls.search_by_interfaces(meta['meta']['interfaces'])

        return node

    @classmethod
    def search_by_interfaces(cls, interfaces):
        """Search for instance using MACs on interfaces

        :param interfaces: dict of Node interfaces
        :returns: Node instance
        """
        return db().query(cls.model).join(
            models.NodeNICInterface,
            cls.model.nic_interfaces
        ).filter(
            models.NodeNICInterface.mac.in_(
                [n["mac"].lower() for n in interfaces]
            )
        ).first()

    @classmethod
    def should_have_public(cls, instance):
        """Determine whether this node has Public network.

        :param instance: Node DB instance
        :returns: True when node has Public network
        """
        if Cluster.should_assign_public_to_all_nodes(instance.cluster):
            return True

        roles = itertools.chain(instance.roles, instance.pending_roles)
        for role in roles:
            roles_metadata = instance.cluster.release.roles_metadata
            if roles_metadata.get(role, {}).get('public_ip_required'):
                return True

        return False

    @classmethod
    def create(cls, data):
        """Create Node instance with specified parameters in DB.
        This includes:

        * generating its name by MAC (if name is not specified in data)
        * adding node to Cluster (if cluster_id is not None in data) \
        (see :func:`add_into_cluster`) with specified roles \
        (see :func:`update_roles` and :func:`update_pending_roles`)
        * creating interfaces for Node in DB (see :func:`update_interfaces`)
        * creating default Node attributes (see :func:`create_attributes`)
        * creating default volumes allocation for Node \
        (see :func:`update_volumes`)
        * creating Notification about newly discovered Node \
        (see :func:`create_discover_notification`)

        :param data: dictionary of key-value pairs as object fields
        :returns: Node instance
        """
        if "name" not in data:
            data["name"] = "Untitled ({0})".format(
                data['mac'][-5:].lower()
            )
        data["timestamp"] = datetime.now()
        data.pop("id", None)

        #TODO(enchantner): fix this temporary hack in clients
        if "cluster_id" not in data and "cluster" in data:
            cluster_id = data.pop("cluster", None)
            data["cluster_id"] = cluster_id

        roles = data.pop("roles", None)
        pending_roles = data.pop("pending_roles", None)
        primary_roles = data.pop("primary_roles", None)

        new_node_meta = data.pop("meta", {})
        new_node_cluster_id = data.pop("cluster_id", None)
        new_node = super(Node, cls).create(data)
        new_node.create_meta(new_node_meta)

        new_hostname = cls.make_slave_name(new_node)

        if not 'hostname' in data and \
                cls.get_by_hostname(new_hostname, new_node_cluster_id):
            # trying to create node with existing hostname
            logger.error("Trying to create node with existing hostname %s"
                         % new_hostname)
            cls.delete(new_node)
            message_correction = ""
            if new_node_cluster_id:
                message_correction = " in the cluster %s" %\
                                     new_node_cluster_id
            raise errors.CannotCreate(
                "Node with hostname '%s' already exists%s." %
                (new_hostname, message_correction))
        # all good. let's set new hostname
        new_node.hostname = new_hostname
        db().flush()

        # Add interfaces for node from 'meta'.
        if new_node.meta and new_node.meta.get('interfaces'):
            cls.update_interfaces(new_node)

        # adding node into cluster
        if new_node_cluster_id:
            cls.add_into_cluster(new_node, new_node_cluster_id)

        # updating roles
        if roles is not None:
            cls.update_roles(new_node, roles)
        if pending_roles is not None:
            cls.update_pending_roles(new_node, pending_roles)
        if primary_roles is not None:
            cls.update_primary_roles(new_node, primary_roles)

        # creating attributes
        cls.create_attributes(new_node)
        cls.update_volumes(new_node)

        cls.create_discover_notification(new_node)
        return new_node

    @classmethod
    def assign_group(cls, instance):
        if instance.group_id is None and instance.ip:
            admin_ngs = db().query(models.NetworkGroup).filter_by(
                name="fuelweb_admin")
            ip = IPAddress(instance.ip)

            for ng in admin_ngs:
                if ip in IPNetwork(ng.cidr):
                    instance.group_id = ng.group_id
                    break

        if not instance.group_id:
            instance.group_id = Cluster.get_default_group(instance.cluster).id

        db().add(instance)
        db().flush()

    @classmethod
    def create_attributes(cls, instance):
        """Create attributes for Node instance

        :param instance: Node instance
        :returns: NodeAttributes instance
        """
        new_attributes = models.NodeAttributes()
        instance.attributes = new_attributes
        db().add(new_attributes)
        db().add(instance)
        db().flush()
        return new_attributes

    @classmethod
    def hardware_info_locked(cls, instance):
        """Returns true if update of hardware information is not allowed.
        It is not allowed during provision/deployment, after
        successful provision/deployment and during node removal.
        """
        return instance.status not in (
            consts.NODE_STATUSES.discover,
            consts.NODE_STATUSES.error,
        )

    @classmethod
    def update_interfaces(cls, instance, update_by_agent=False):
        """Update interfaces for Node instance using Cluster
        network manager (see :func:`get_network_manager`)

        :param instance: Node instance
        :returns: None
        """
        try:
            network_manager = Cluster.get_network_manager(instance.cluster)
            network_manager.update_interfaces_info(instance, update_by_agent)

            db().refresh(instance)
        except errors.InvalidInterfacesInfo as exc:
            logger.warning(
                "Failed to update interfaces for node '%s' - invalid info "
                "in meta: %s", instance.human_readable_name, exc.message
            )
            logger.warning(traceback.format_exc())

    @classmethod
    def set_vms_conf(cls, instance, vms_conf):
        """Set vms_conf for Node instance from JSON data.

        :param instance: Node instance
        :param volumes_data: JSON with new vms_conf data
        :returns: None
        """
        db().query(models.NodeAttributes).filter_by(
            node_id=instance.id).update({'vms_conf': vms_conf})
        db().flush()
        db().refresh(instance)

    @classmethod
    def update_volumes(cls, instance):
        """Update volumes for Node instance.
        Adds pending "disks" changes for Cluster which Node belongs to

        :param instance: Node instance
        :returns: None
        """
        attrs = instance.attributes
        if not attrs:
            attrs = cls.create_attributes(instance)

        try:
            # TODO(eli): update volumes method should be moved
            # into an extension
            # Should be done as a part of blueprint:
            # https://blueprints.launchpad.net/fuel/+spec
            #                                 /volume-manager-refactoring
            from nailgun.extensions.volume_manager.extension \
                import VolumeManagerExtension
            VolumeManagerExtension.set_volumes(
                instance,
                instance.volume_manager.gen_volumes_info())
        except Exception as exc:
            msg = (
                u"Failed to generate volumes "
                u"info for node '{0}': '{1}'"
            ).format(
                instance.name or instance.mac or instance.id,
                str(exc) or "see logs for details"
            )
            logger.warning(traceback.format_exc())
            Notification.create({
                "topic": "error",
                "message": msg,
                "node_id": instance.id
            })

        if instance.cluster_id:
            Cluster.add_pending_changes(
                instance.cluster,
                "disks",
                node_id=instance.id
            )

        db().add(attrs)
        db().flush()

    @classmethod
    def create_discover_notification(cls, instance):
        """Create notification about discovering new Node

        :param instance: Node instance
        :returns: None
        """
        try:
            # we use multiplier of 1024 because there are no problems here
            # with unfair size calculation
            ram = str(round(float(
                instance.meta['memory']['total']) / 1073741824, 1)) + " GB RAM"
        except Exception:
            logger.warning(traceback.format_exc())
            ram = "unknown RAM"

        try:
            # we use multiplier of 1000 because disk vendors specify HDD size
            # in terms of decimal capacity. Sources:
            # http://knowledge.seagate.com/articles/en_US/FAQ/172191en
            # http://physics.nist.gov/cuu/Units/binary.html
            hd_size = round(
                float(
                    sum(
                        [d["size"] for d in instance.meta["disks"]]
                    ) / 1000000000
                ),
                1
            )
            # if HDD > 100 GB we show it's size in TB
            if hd_size > 100:
                hd_size = str(hd_size / 1000) + " TB HDD"
            else:
                hd_size = str(hd_size) + " GB HDD"
        except Exception:
            logger.warning(traceback.format_exc())
            hd_size = "unknown HDD"

        cores = str(instance.meta.get('cpu', {}).get('total', "unknown"))

        Notification.create({
            "topic": "discover",
            "message": u"New node is discovered: "
                       u"{0} CPUs / {1} / {2} ".format(cores, ram, hd_size),
            "node_id": instance.id
        })

    @classmethod
    def update(cls, instance, data):
        """Update Node instance with specified parameters in DB.
        This includes:

        * adding node to Cluster (if cluster_id is not None in data) \
        (see :func:`add_into_cluster`)
        * updating roles for Node if it belongs to Cluster \
        (see :func:`update_roles` and :func:`update_pending_roles`)
        * removing node from Cluster (if cluster_id is None in data) \
        (see :func:`remove_from_cluster`)
        * updating interfaces for Node in DB (see :func:`update_interfaces`)
        * creating default Node attributes (see :func:`create_attributes`)
        * updating volumes allocation for Node using Cluster's Release \
        metadata (see :func:`update_volumes`)

        :param data: dictionary of key-value pairs as object fields
        :returns: Node instance
        """
        data.pop("id", None)
        data.pop("network_data", None)

        roles = data.pop("roles", None)
        pending_roles = data.pop("pending_roles", None)
        new_meta = data.pop("meta", None)

        update_by_agent = data.pop("is_agent", False)

        disks_changed = None
        if new_meta and "disks" in new_meta and "disks" in instance.meta:
            key = operator.itemgetter("name")

            new_disks = sorted(new_meta["disks"], key=key)
            old_disks = sorted(instance.meta["disks"], key=key)

            disks_changed = (new_disks != old_disks)

        # TODO(enchantner): fix this temporary hack in clients
        if "cluster_id" not in data and "cluster" in data:
            cluster_id = data.pop("cluster", None)
            data["cluster_id"] = cluster_id

        if new_meta:
            instance.update_meta(new_meta)
            # The call to update_interfaces will execute a select query for
            # the current instance. This appears to overwrite the object in the
            # current session and we lose the meta changes.
            db().flush()
            if cls.hardware_info_locked(instance):
                logger.info("Interfaces are locked for update on node %s",
                            instance.human_readable_name)
            else:
                cls.update_interfaces(instance, update_by_agent)

        cluster_changed = False
        if "cluster_id" in data:
            new_cluster_id = data.pop("cluster_id")
            if instance.cluster_id:
                if new_cluster_id is None:
                    # removing node from cluster
                    cluster_changed = True
                    cls.remove_from_cluster(instance)
                elif new_cluster_id != instance.cluster_id:
                    # changing node cluster to another
                    # (is currently not allowed)
                    raise errors.CannotUpdate(
                        u"Changing cluster on the fly is not allowed"
                    )
            else:
                if new_cluster_id is not None:
                    # assigning node to cluster
                    cluster_changed = True
                    cls.add_into_cluster(instance, new_cluster_id)

        if "group_id" in data:
            new_group_id = data.pop("group_id")
            if instance.group_id != new_group_id:
                nm = Cluster.get_network_manager(instance.cluster)
                nm.clear_assigned_networks(instance)
                nm.clear_bond_configuration(instance)
            instance.group_id = new_group_id
            cls.add_into_cluster(instance, instance.cluster_id)

        # calculating flags
        roles_changed = (
            roles is not None and set(roles) != set(instance.roles)
        )
        pending_roles_changed = (
            pending_roles is not None and
            set(pending_roles) != set(instance.pending_roles)
        )

        super(Node, cls).update(instance, data)

        if roles_changed:
            cls.update_roles(instance, roles)
        if pending_roles_changed:
            cls.update_pending_roles(instance, pending_roles)

        if any((
            roles_changed,
            pending_roles_changed,
            cluster_changed,
            disks_changed,
        )) and instance.status not in (
            consts.NODE_STATUSES.provisioning,
            consts.NODE_STATUSES.deploying
        ):
            cls.update_volumes(instance)

        return instance

    @classmethod
    def reset_to_discover(cls, instance):
        """Flush database objects which is not consistent with actual node
           configuration in the event of resetting node to discover state

        :param instance: Node database object
        :returns: None
        """
        node_data = {
            "online": False,
            "status": consts.NODE_STATUSES.discover,
            "pending_addition": True,
            "pending_deletion": False,
        }
        cls.update_volumes(instance)
        cls.update(instance, node_data)
        cls.move_roles_to_pending_roles(instance)
        # when node reseted to discover:
        # - cobbler system is deleted
        # - mac to ip mapping from dnsmasq.conf is deleted
        # imho we need to revert node to original state, as it was
        # added to cluster (without any additonal state in database)
        netmanager = Cluster.get_network_manager()
        netmanager.clear_assigned_ips(instance)
        db().flush()

    @classmethod
    def update_by_agent(cls, instance, data):
        """Update Node instance with some specific cases for agent.

        * don't update provisioning or error state back to discover
        * don't update volume information if disks arrays is empty

        :param data: dictionary of key-value pairs as object fields
        :returns: Node instance
        """
        # don't update provisioning and error back to discover
        if instance.status in ('provisioning', 'error'):
            if data.get('status', 'discover') == 'discover':
                logger.debug(
                    u"Node {0} has provisioning or error status - "
                    u"status not updated by agent".format(
                        instance.human_readable_name
                    )
                )

                data['status'] = instance.status

        meta = data.get('meta', {})
        # don't update volume information, if agent has sent an empty array
        if len(meta.get('disks', [])) == 0 and instance.meta.get('disks'):

            logger.warning(
                u'Node {0} has received an empty disks array - '
                u'volume information will not be updated'.format(
                    instance.human_readable_name
                )
            )
            meta['disks'] = instance.meta['disks']

        # don't update volume information, if it is locked by node status
        if 'disks' in meta and cls.hardware_info_locked(instance):
            logger.info("Volume information is locked for update on node %s",
                        instance.human_readable_name)
            meta['disks'] = instance.meta['disks']

        #(dshulyak) change this verification to NODE_STATUSES.deploying
        # after we will reuse ips from dhcp range
        netmanager = Cluster.get_network_manager()
        admin_ng = netmanager.get_admin_network_group(instance.id)
        if data.get('ip') and not netmanager.is_same_network(data['ip'],
                                                             admin_ng.cidr):
            logger.debug(
                'Corrupted network data %s, skipping update',
                instance.id)
            return instance
        return cls.update(instance, data)

    @classmethod
    def update_roles(cls, instance, new_roles):
        """Update roles for Node instance.
        Logs an error if node doesn't belong to Cluster

        :param instance: Node instance
        :param new_roles: list of new role names
        :returns: None
        """
        if not instance.cluster_id:
            logger.warning(
                u"Attempting to assign roles to node "
                u"'{0}' which isn't added to cluster".format(
                    instance.full_name))
            return

        logger.debug(
            u"Updating roles for node {0}: {1}".format(
                instance.full_name,
                new_roles))

        instance.roles = new_roles
        db().flush()

    @classmethod
    def update_pending_roles(cls, instance, new_pending_roles):
        """Update pending_roles for Node instance.
        Logs an error if node doesn't belong to Cluster

        :param instance: Node instance
        :param new_pending_roles: list of new pending role names
        :returns: None
        """
        if not instance.cluster_id:
            logger.warning(
                u"Attempting to assign pending roles to node "
                u"'{0}' which isn't added to cluster".format(
                    instance.full_name))
            return

        logger.debug(
            u"Updating pending roles for node {0}: {1}".format(
                instance.full_name,
                new_pending_roles))

        if new_pending_roles == []:
            #TODO(enchantner): research why the hell we need this
            Cluster.clear_pending_changes(
                instance.cluster,
                node_id=instance.id
            )

        instance.pending_roles = new_pending_roles
        db().flush()

    @classmethod
    def update_primary_roles(cls, instance, new_primary_roles):
        """Update primary_roles for Node instance.
        Logs an error if node doesn't belong to Cluster

        :param instance: Node instance
        :param new_primary_roles: list of new pending role names
        :returns: None
        """
        if not instance.cluster_id:
            logger.warning(
                u"Attempting to assign pending roles to node "
                u"'{0}' which isn't added to cluster".format(
                    instance.full_name))
            return

        assigned_roles = set(instance.roles + instance.pending_roles)
        for role in new_primary_roles:
            if role not in assigned_roles:
                logger.warning(
                    u"Could not mark node {0} as primary for {1} role, "
                    u"because there's no assigned {1} role.".format(
                        instance.full_name, role)
                )
                return

        logger.debug(
            u"Updating primary roles for node {0}: {1}".format(
                instance.full_name,
                new_primary_roles))

        instance.primary_roles = new_primary_roles
        db().flush()

    @classmethod
    def add_into_cluster(cls, instance, cluster_id):
        """Adds Node to Cluster by its ID.
        Also assigns networks by default for Node.

        :param instance: Node instance
        :param cluster_id: Cluster ID
        :returns: None
        """
        instance.cluster_id = cluster_id
        db().flush()
        cls.assign_group(instance)
        network_manager = Cluster.get_network_manager(instance.cluster)
        network_manager.assign_networks_by_default(instance)
        cls.add_pending_change(instance, consts.CLUSTER_CHANGES.interfaces)

    @classmethod
    def add_pending_change(cls, instance, change):
        """Add pending change into Cluster.

        :param instance: Node instance
        :param change: string value of cluster change
        :returns: None
        """
        if instance.cluster:
            Cluster.add_pending_changes(
                instance.cluster, change, node_id=instance.id
            )

    @classmethod
    def get_admin_physical_iface(cls, instance):
        """Returns node's physical iface.
        In case if we have bonded admin iface, first
        of the bonded ifaces will be returned

        :param instance: Node instance
        :returns: interface instance
        """
        admin_iface = Cluster.get_network_manager(instance.cluster) \
            .get_admin_interface(instance)

        if admin_iface.type != consts.NETWORK_INTERFACE_TYPES.bond:
            return admin_iface

        iface = filter(lambda i: i.mac == instance.mac, admin_iface.slaves)
        return iface[0] if iface else admin_iface.slaves[-1]

    @classmethod
    def remove_from_cluster(cls, instance):
        """Remove Node from Cluster.
        Also drops networks assignment for Node and clears both
        roles and pending roles

        :param instance: Node instance
        :returns: None
        """
        if instance.cluster:
            Cluster.clear_pending_changes(
                instance.cluster,
                node_id=instance.id
            )
            netmanager = Cluster.get_network_manager(
                instance.cluster
            )
            netmanager.clear_assigned_networks(instance)
            netmanager.clear_bond_configuration(instance)
        cls.update_roles(instance, [])
        cls.update_pending_roles(instance, [])
        cls.remove_replaced_params(instance)
        instance.cluster_id = None
        instance.group_id = None
        instance.kernel_params = None
        instance.primary_roles = []
        instance.reset_name_to_default()
        db().flush()
        db().refresh(instance)

    @classmethod
    def move_roles_to_pending_roles(cls, instance):
        """Move roles to pending_roles
        """
        instance.pending_roles = instance.pending_roles + instance.roles
        instance.roles = []
        instance.primary_roles = []
        db().flush()

    @classmethod
    def make_slave_name(cls, instance):
        if not getattr(instance, 'hostname', None):
            return cls.default_slave_name(instance.id)
        return instance.hostname

    @classmethod
    def default_slave_name(cls, instance_id):
        return u"node-{node_id}".format(node_id=instance_id)

    @classmethod
    def make_slave_fqdn(cls, instance):
        return u"{instance_name}.{dns_domain}" \
            .format(instance_name=cls.make_slave_name(instance),
                    dns_domain=settings.DNS_DOMAIN)

    @classmethod
    def get_kernel_params(cls, instance):
        """Return cluster kernel_params if they wasnot replaced by
           custom params.
        """
        return (instance.kernel_params or
                Cluster.get_default_kernel_params(instance.cluster))

    @classmethod
    def remove_replaced_params(cls, instance):
        instance.replaced_deployment_info = []
        instance.replaced_provisioning_info = {}

    @classmethod
    def all_roles(cls, instance):
        roles = set(instance.roles + instance.pending_roles)
        roles -= set(instance.primary_roles)

        primary_roles = set([
            'primary-{0}'.format(role) for role in instance.primary_roles])

        return sorted(roles | primary_roles)


class NodeCollection(NailgunCollection):
    """Node collection
    """

    #: Single Node object class
    single = Node

    @classmethod
    def eager_nodes_handlers(cls, iterable):
        """Eager load objects instances that is used in nodes handler.

        :param iterable: iterable (SQLAlchemy query)
        :returns: iterable (SQLAlchemy query)
        """
        options = (
            joinedload('cluster'),
            subqueryload_all('nic_interfaces.assigned_networks_list'),
            subqueryload_all('bond_interfaces.assigned_networks_list'),
            subqueryload_all('ip_addrs.network_data')
        )
        return cls.eager_base(iterable, options)

    @classmethod
    def update_slave_nodes_fqdn(cls, instances):
        for n in instances:
            n.fqdn = cls.single.make_slave_fqdn(n)

        db().flush()

    @classmethod
    def prepare_for_lt_6_1_deployment(cls, instances):
        """Prepare environment for deployment,
        assign management, public, storage ips
        """
        cls.update_slave_nodes_fqdn(instances)

        # TODO(enchantner): check network manager instance for each node
        netmanager = Cluster.get_network_manager()
        if instances:
            netmanager.assign_ips(instances, 'management')
            netmanager.assign_ips(instances, 'public')
            netmanager.assign_ips(instances, 'storage')
            netmanager.assign_admin_ips(instances)

    @classmethod
    def prepare_for_deployment(cls, instances, nst=None):
        """Prepare environment for deployment,
        assign management, public, storage, private ips
        """
        cls.update_slave_nodes_fqdn(instances)

        # TODO(enchantner): check network manager instance for each node
        netmanager = Cluster.get_network_manager()
        if instances:
            netmanager.assign_ips(instances, 'management')
            netmanager.assign_ips(instances, 'public')
            netmanager.assign_ips(instances, 'storage')
            if nst == consts.NEUTRON_SEGMENT_TYPES.gre:
                netmanager.assign_ips(instances, 'private')
            netmanager.assign_admin_ips(instances)

    @classmethod
    def prepare_for_provisioning(cls, instances):
        """Prepare environment for provisioning,
        update fqdns, assign admin IPs
        """
        cls.update_slave_nodes_fqdn(instances)
        netmanager = Cluster.get_network_manager()
        netmanager.assign_admin_ips(instances)

    @classmethod
    def lock_nodes(cls, instances):
        """Locking nodes instances, fetched before, but required to be locked
        :param instances: list of nodes
        :return: list of locked nodes
        """
        instances_ids = [instance.id for instance in instances]
        q = cls.filter_by_list(None, 'id', instances_ids, order_by='id')
        return cls.lock_for_update(q).all()

    @classmethod
    def get_by_group_id(cls, group_id):
        return cls.filter_by(None, group_id=group_id)

    @classmethod
    def get_by_ids(cls, ids):
        return db.query(models.Node).filter(models.Node.id.in_(ids)).all()
