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
import operator
import traceback

from datetime import datetime

from sqlalchemy.orm import joinedload
from sqlalchemy.orm import subqueryload_all

from nailgun import consts

from nailgun.api.serializers.node import NodeSerializer

from nailgun.db import db
from nailgun.db.sqlalchemy import models
from nailgun.errors import errors
from nailgun.logger import logger

from nailgun.objects import Cluster
from nailgun.objects import NailgunCollection
from nailgun.objects import NailgunObject
from nailgun.objects import Notification


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
            node = q.filter_by(mac=mac).first()
        else:
            node = q.get(node_uid)
        return node

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
                [n["mac"] for n in interfaces]
            )
        ).first()

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

        new_node_meta = data.pop("meta", {})
        new_node_cluster_id = data.pop("cluster_id", None)
        new_node = super(Node, cls).create(data)
        new_node.create_meta(new_node_meta)
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

        # creating attributes
        cls.create_attributes(new_node)
        cls.update_volumes(new_node)

        cls.create_discover_notification(new_node)
        return new_node

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
    def update_interfaces(cls, instance):
        """Update interfaces for Node instance using Cluster
        network manager (see :func:`get_network_manager`)

        :param instance: Node instance
        :returns: None
        """
        try:
            network_manager = Cluster.get_network_manager(instance.cluster)

            network_manager.check_interfaces_correctness(instance)
            network_manager.update_interfaces_info(instance)

            db().refresh(instance)
        except errors.InvalidInterfacesInfo as exc:
            logger.warning(
                "Failed to update interfaces for node '%s' - invalid info "
                "in meta: %s", instance.human_readable_name, exc.message
            )
            logger.warning(traceback.format_exc())

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
            attrs.volumes = instance.volume_manager.gen_volumes_info()
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

        roles = data.pop("roles", None)
        pending_roles = data.pop("pending_roles", None)
        new_meta = data.pop("meta", None)

        disks_changed = None
        if new_meta and "disks" in new_meta and "disks" in instance.meta:
            key = operator.itemgetter("name")

            new_disks = sorted(new_meta["disks"], key=key)
            old_disks = sorted(instance.meta["disks"], key=key)

            disks_changed = (new_disks != old_disks)

        #TODO(enchantner): fix this temporary hack in clients
        if "cluster_id" not in data and "cluster" in data:
            cluster_id = data.pop("cluster", None)
            data["cluster_id"] = cluster_id

        if new_meta:
            instance.update_meta(new_meta)
            # smarter check needed
            cls.update_interfaces(instance)

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

        # don't update volume information, if agent has sent an empty array
        meta = data.get('meta', {})
        if meta and len(meta.get('disks', [])) == 0 \
                and instance.meta.get('disks'):

            logger.warning(
                u'Node {0} has received an empty disks array - '
                u'volume information will not be updated'.format(
                    instance.human_readable_name
                )
            )
            meta['disks'] = instance.meta['disks']

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
                    instance.name or instance.id
                )
            )
            return

        if new_roles:
            instance.role_list = db().query(models.Role).filter_by(
                release_id=instance.cluster.release_id,
            ).filter(
                models.Role.name.in_(new_roles)
            ).all()
        else:
            instance.role_list = []
        db().flush()
        db().refresh(instance)

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
                    instance.name or instance.id
                )
            )
            return

        logger.debug(
            u"Updating pending roles for node {0}: {1}".format(
                instance.id,
                new_pending_roles
            )
        )

        if new_pending_roles == []:
            instance.pending_role_list = []
            # research why the hell we need this
            Cluster.clear_pending_changes(
                instance.cluster,
                node_id=instance.id
            )
        else:
            instance.pending_role_list = db().query(models.Role).filter_by(
                release_id=instance.cluster.release_id,
            ).filter(
                models.Role.name.in_(new_pending_roles)
            ).all()

        db().flush()
        db().refresh(instance)

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
        db().refresh(instance)
        instance.kernel_params = Cluster.get_default_kernel_params(
            instance.cluster
        )
        db().flush()
        network_manager = Cluster.get_network_manager(instance.cluster)
        network_manager.assign_networks_by_default(instance)

    @classmethod
    def get_network_manager(cls, instance=None):
        """Get network manager for Node instance.
        If instance is None then default NetworkManager is returned

        :param instance: Node instance
        :param cluster_id: Cluster ID
        :returns: None
        """
        if not instance.cluster:
            from nailgun.network.manager import NetworkManager
            return NetworkManager
        else:
            return Cluster.get_network_manager(instance.cluster)

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
            Cluster.get_network_manager(
                instance.cluster
            ).clear_assigned_networks(instance)
        cls.update_roles(instance, [])
        cls.update_pending_roles(instance, [])
        instance.cluster_id = None
        instance.kernel_params = None
        instance.reset_name_to_default()
        db().flush()
        db().refresh(instance)

    @classmethod
    def can_be_updated(cls, instance):
        return (instance.status in (consts.NODE_STATUSES.ready,
                                    consts.NODE_STATUSES.provisioned)) or \
               (instance.status == consts.NODE_STATUSES.error
                and instance.error_type == consts.NODE_ERRORS.deploy)

    @classmethod
    def move_roles_to_pending_roles(cls, instance):
        """Move roles to pending_roles
        """
        instance.pending_roles += instance.roles
        instance.roles = []
        db().flush()


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
            joinedload('role_list'),
            joinedload('pending_role_list'),
            subqueryload_all('nic_interfaces.assigned_networks_list'),
            subqueryload_all('bond_interfaces.assigned_networks_list'),
            subqueryload_all('ip_addrs.network_data')
        )
        return cls.eager_base(iterable, options)
