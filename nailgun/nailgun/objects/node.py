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

import traceback

from datetime import datetime

from netaddr import IPAddress
from netaddr import IPNetwork

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

    model = models.Node
    serializer = NodeSerializer

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
            "api": {"type": "string"},
            "fqdn": {"type": "string"},
            "manufacturer": {"type": "string"},
            "platform_name": {"type": "string"},
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
    def search_by_interfaces(cls, interfaces):
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

        # Assign node group
        cls.assign_group(new_node)

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
    def assign_group(cls, instance):
        if instance.group_id is None and instance.ip:
            admin_ngs = db().query(models.NetworkGroup).filter_by(
                name="fuelweb_admin")
            ip = IPAddress(instance.ip)
            for ng in admin_ngs:
                if ip in IPNetwork(ng.cidr):
                    instance.group_id = ng.group_id
                    break
            if instance.group_id is None and instance.error_type is None:
                msg = (
                    u"Failed to match node '{0}' with group_id. Add "
                    "fuelweb_admin NetworkGroup to match '{1}'"
                ).format(
                    instance.name or instance.mac,
                    instance.ip
                )
                logger.warning(msg)
            db().add(instance)
            db().flush()

    @classmethod
    def create_attributes(cls, instance):
        new_attributes = models.NodeAttributes()
        instance.attributes = new_attributes
        db().add(new_attributes)
        db().add(instance)
        db().flush()
        return new_attributes

    @classmethod
    def update_interfaces(cls, instance):
        Cluster.get_network_manager(
            instance.cluster
        ).update_interfaces_info(instance)

    @classmethod
    def update_volumes(cls, instance):
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
        data.pop("id", None)

        roles = data.pop("roles", None)
        pending_roles = data.pop("pending_roles", None)
        new_meta = data.pop("meta", None)

        #TODO(enchantner): fix this temporary hack in clients
        if "cluster_id" not in data and "cluster" in data:
            cluster_id = data.pop("cluster", None)
            data["cluster_id"] = cluster_id

        if new_meta:
            instance.update_meta(new_meta)
            # smarter check needed
            cls.update_interfaces(instance)

        new_cluster_id = instance.cluster_id
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
            cluster_changed
        )) and instance.status not in (
            consts.NODE_STATUSES.provisioning,
            consts.NODE_STATUSES.deploying
        ):
            cls.update_volumes(instance)

        return instance

    @classmethod
    def update_roles(cls, instance, new_roles):
        if not instance.cluster_id:
            logger.warning(
                u"Attempting to assign roles to node "
                u"'{0}' which isn't added to cluster".format(
                    instance.name or instance.id
                )
            )
            return

        instance.role_list = db().query(models.Role).filter_by(
            release_id=instance.cluster.release_id,
        ).filter(
            models.Role.name.in_(new_roles)
        ).all()
        db().flush()
        db().refresh(instance)

    @classmethod
    def update_pending_roles(cls, instance, new_pending_roles):
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
        instance.cluster_id = cluster_id
        db().flush()
        db().refresh(instance)
        network_manager = Cluster.get_network_manager(instance.cluster)
        network_manager.assign_networks_by_default(instance)

    @classmethod
    def get_network_manager(cls, instance=None):
        if not instance.cluster:
            from nailgun.network.manager import NetworkManager
            return NetworkManager
        else:
            return Cluster.get_network_manager(instance.cluster)

    @classmethod
    def remove_from_cluster(cls, instance):
        Cluster.clear_pending_changes(
            instance.cluster,
            node_id=instance.id
        )
        Cluster.get_network_manager(
            instance.cluster
        ).clear_assigned_networks(instance)
        instance.cluster_id = None
        instance.roles = instance.pending_roles = []
        instance.reset_name_to_default()
        db().flush()
        db().refresh(instance)

    @classmethod
    def to_dict(cls, instance, fields=None):
        node_dict = super(Node, cls).to_dict(instance, fields=fields)
        net_manager = Cluster.get_network_manager(instance.cluster)
        ips_mapped = net_manager.get_grouped_ips_by_node()
        networks_grouped = net_manager.get_networks_grouped_by_node_group()
        group_id = instance.group_id
        if not group_id:
            group_id = getattr(instance.cluster, 'default_group', None)

        node_dict['network_data'] = net_manager.get_node_networks_optimized(
            instance,
            ips_mapped.get(instance.id, []),
            networks_grouped.get(group_id, [])
        )
        return node_dict


class NodeCollection(NailgunCollection):

    single = Node
