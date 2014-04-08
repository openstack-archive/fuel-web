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

from nailgun import consts

from nailgun.api.serializers.cluster import ClusterSerializer

from nailgun.db import db

from nailgun.db.sqlalchemy import models

from nailgun.errors import errors

from nailgun.objects import NailgunCollection
from nailgun.objects import NailgunObject

from nailgun.utils import AttributesGenerator
from nailgun.utils import dict_merge
from nailgun.utils import traverse


class Attributes(NailgunObject):

    model = models.Attributes

    @classmethod
    def generate_fields(cls, instance):
        instance.generated = traverse(
            instance.generated,
            AttributesGenerator
        )
        db().add(instance)
        db().flush()

    @classmethod
    def merged_attrs(cls, instance):
        return dict_merge(
            instance.generated,
            instance.editable
        )

    @classmethod
    def merged_attrs_values(cls, instance):
        attrs = cls.merged_attrs(instance)
        for group_attrs in attrs.itervalues():
            for attr, value in group_attrs.iteritems():
                if isinstance(value, dict) and 'value' in value:
                    group_attrs[attr] = value['value']
        if 'common' in attrs:
            attrs.update(attrs.pop('common'))
        if 'additional_components' in attrs:
            for comp, enabled in attrs['additional_components'].iteritems():
                if isinstance(enabled, bool):
                    attrs.setdefault(comp, {}).update({
                        "enabled": enabled
                    })

            attrs.pop('additional_components')
        return attrs


class Cluster(NailgunObject):

    model = models.Cluster
    serializer = ClusterSerializer

    schema = {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "title": "Cluster",
        "description": "Serialized Cluster object",
        "type": "object",
        "properties": {
            "id": {"type": "number"},
            "name": {"type": "string"},
            "mode": {
                "type": "string",
                "enum": list(consts.CLUSTER_MODES)
            },
            "status": {
                "type": "string",
                "enum": list(consts.CLUSTER_STATUSES)
            },
            "net_provider": {
                "type": "string",
                "enum": list(consts.CLUSTER_NET_PROVIDERS)
            },
            "net_l23_provider": {
                "type": "string",
                "enum": list(consts.CLUSTER_NET_L23_PROVIDERS)
            },
            "net_segment_type": {
                "type": "string",
                "enum": list(consts.CLUSTER_NET_SEGMENT_TYPES)
            },
            "net_manager": {
                "type": "string",
                "enum": list(consts.CLUSTER_NET_MANAGERS)
            },
            "grouping": {
                "type": "string",
                "enum": list(consts.CLUSTER_GROUPING)
            },
            "current_release_id": {"type": "number"},
            # "pending_release_id": {"type": "number"},
            "dns_nameservers": {"type": "array"},
            "replaced_deployment_info": {"type": "object"},
            "replaced_provisioning_info": {"type": "object"},
            "is_customized": {"type": "boolean"}
        }
    }

    @classmethod
    def create(cls, data):
        #TODO(enchantner): fix this temporary hack in clients
        if "current_release_id" not in data:
            release_id = data.pop("release", None)
            data["current_release_id"] = release_id

        assign_nodes = data.pop("nodes", [])

        new_cluster = super(Cluster, cls).create(data)

        cls.create_attributes(new_cluster)

        netmanager = cls.get_network_manager(new_cluster)

        try:
            netmanager.create_network_groups(new_cluster.id)
            if new_cluster.net_provider == 'neutron':
                netmanager.create_neutron_config(new_cluster)

            cls.add_pending_changes(new_cluster, "attributes")
            cls.add_pending_changes(new_cluster, "networks")

            if assign_nodes:
                cls.update_nodes(new_cluster, assign_nodes)

        except (
            errors.OutOfVLANs,
            errors.OutOfIPs,
            errors.NoSuitableCIDR,
            errors.InvalidNetworkPool
        ) as exc:
            db().delete(new_cluster)
            raise errors.CannotCreate(exc.message)

        db().flush()

        return new_cluster

    @classmethod
    def create_attributes(cls, instance):
        attributes = Attributes.create(
            {
                "editable": instance.release.attributes_metadata.get(
                    "editable"
                ),
                "generated": instance.release.attributes_metadata.get(
                    "generated"
                ),
                "cluster_id": instance.id
            }
        )
        Attributes.generate_fields(attributes)

    @classmethod
    def get_attributes(cls, instance):
        return db().query(models.Attributes).filter(
            models.Attributes.cluster_id == instance.id
        ).first()

    @classmethod
    def get_network_manager(cls, instance=None):
        if not instance:
            from nailgun.network.manager import NetworkManager
            return NetworkManager

        if instance.net_provider == 'neutron':
            from nailgun.network.neutron import NeutronManager
            return NeutronManager
        else:
            from nailgun.network.nova_network import NovaNetworkManager
            return NovaNetworkManager

    @classmethod
    def add_pending_changes(cls, instance, changes_type, node_id=None):
        ex_chs = db().query(models.ClusterChanges).filter_by(
            cluster=instance,
            name=changes_type
        )
        if not node_id:
            ex_chs = ex_chs.first()
        else:
            ex_chs = ex_chs.filter_by(node_id=node_id).first()
        # do nothing if changes with the same name already pending
        if ex_chs:
            return
        ch = models.ClusterChanges(
            cluster_id=instance.id,
            name=changes_type
        )
        if node_id:
            ch.node_id = node_id
        db().add(ch)
        db().flush()

    @classmethod
    def clear_pending_changes(cls, instance, node_id=None):
        chs = db().query(models.ClusterChanges).filter_by(
            cluster_id=instance.id
        )
        if node_id:
            chs = chs.filter_by(node_id=node_id)
        map(db().delete, chs.all())
        db().flush()

    @classmethod
    def update(cls, instance, data):
        nodes = data.pop("nodes", None)
        super(Cluster, cls).update(instance, data)
        if nodes is not None:
            cls.update_nodes(instance, nodes)
        return instance

    @classmethod
    def update_nodes(cls, instance, nodes_ids):
        # TODO(NAME): sepatate nodes
        #for deletion and addition by set().
        new_nodes = []
        if nodes_ids:
            new_nodes = db().query(models.Node).filter(
                models.Node.id.in_(nodes_ids)
            )

        nodes_to_remove = [n for n in instance.nodes
                           if n not in new_nodes]
        nodes_to_add = [n for n in new_nodes
                        if n not in instance.nodes]

        for node in nodes_to_add:
            if not node.online:
                raise errors.NodeOffline(
                    u"Cannot add offline node "
                    u"'{0}' to environment".format(node.id)
                )

        map(instance.nodes.remove, nodes_to_remove)
        map(instance.nodes.append, nodes_to_add)

        net_manager = cls.get_network_manager(instance)
        map(
            net_manager.clear_assigned_networks,
            nodes_to_remove
        )
        map(
            net_manager.assign_networks_by_default,
            nodes_to_add
        )
        db().flush()


class ClusterCollection(NailgunCollection):

    single = Cluster
