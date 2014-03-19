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
            "release_id": {"type": "number"},
            "dns_nameservers": {"type": "array"},
            "replaced_deployment_info": {"type": "object"},
            "replaced_provisioning_info": {"type": "object"},
            "is_customized": {"type": "boolean"}
        }
    }

    @classmethod
    def create(cls, data):
        #TODO(enchantner): fix this temporary hack in clients
        if "release_id" not in data:
            release_id = data.pop("release", None)
            data["release_id"] = release_id

        assign_nodes = data.pop("nodes", [])

        with db().begin(subtransactions=True):
            new_cluster = super(Cluster, cls).create(data)

            attributes = models.Attributes(
                editable=new_cluster.release.attributes_metadata.get(
                    "editable"
                ),
                generated=new_cluster.release.attributes_metadata.get(
                    "generated"
                ),
                cluster=new_cluster
            )
            attributes.generate_fields()

            netmanager = new_cluster.network_manager

            try:
                netmanager.create_network_groups(new_cluster.id)
                if new_cluster.net_provider == 'neutron':
                    netmanager.create_neutron_config(new_cluster)

                new_cluster.add_pending_changes("attributes")
                new_cluster.add_pending_changes("networks")

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

        return new_cluster

    @classmethod
    def update(cls, instance, data):
        nodes = data.pop("nodes", None)
        super(Cluster, cls).update(instance, data)
        if nodes is not None:
            cls.update_nodes(instance, nodes)
        return instance

    @classmethod
    def update_nodes(cls, instance, nodes_ids):
        with db().begin(subtransactions=True):
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
            map(
                instance.network_manager.clear_assigned_networks,
                nodes_to_remove
            )
            map(
                instance.network_manager.assign_networks_by_default,
                nodes_to_add
            )


class ClusterCollection(NailgunCollection):

    single = Cluster
