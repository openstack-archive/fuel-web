# -*- coding: utf-8 -*-

#    Copyright 2015 Mirantis, Inc.
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

from sqlalchemy.orm import joinedload
from sqlalchemy.sql import not_

from nailgun.db import db
from nailgun.db.sqlalchemy import models
from nailgun import errors
from nailgun.extensions.network_manager.objects.serializers.ip_addr import \
    IPAddrSerializer
from nailgun.objects import Cluster
from nailgun.objects import NailgunCollection
from nailgun.objects import NailgunObject
from nailgun.objects import NetworkGroup
from nailgun.objects.serializers.base import BasicSerializer


class IPAddr(NailgunObject):

    model = models.IPAddr
    serializer = IPAddrSerializer

    @classmethod
    def bulk_create(cls, data):
        db().execute(cls.model.__table__.insert(), data)

    @classmethod
    def get_ips_except_admin(cls, node=None, network_id=None,
                             include_network_data=False,
                             default_admin_net=None):
        """Get all non-admin IP addresses for node or network.

        This method will not return VIPs.

        :param node: nailgun.db.sqlalchemy.models.Node. If it already
         contains related data we will have performance boost.
        :type node: nailgun.db.sqlalchemy.models.Node
        :param network_id: Network database ID.
        :type  network_id: int
        :param include_network_data: Include related network data.
        :type include_network_data: bool
        :param default_admin_net: Default admin network
        :param nailgun.db.sqlalchemy.models.NetworkGroup
        :returns: List of free IP addresses as SQLAlchemy objects.
        """
        ips = db().query(models.IPAddr).filter(
            models.IPAddr.vip_name == None  # noqa
        ).order_by(
            models.IPAddr.id
        )

        if include_network_data:
            ips = ips.options(joinedload('network_data'))
        if node is not None:
            ips = ips.filter_by(node=node.id)
        if network_id:
            ips = ips.filter_by(network=network_id)

        try:
            admin_net_id = NetworkGroup.get_admin_network_group(
                node, default_admin_net).id
        except errors.AdminNetworkNotFound:
            admin_net_id = None
        if admin_net_id:
            ips = ips.filter(
                not_(models.IPAddr.network == admin_net_id)
            )

        return ips.all()

    @classmethod
    def get_by_node_for_network(cls, network_id):
        """Get IPs assigned to node from specified network.

        :param node_id: Node ID
        :type node_id: int
        :param network_id: NetworkGroup ID
        :type network_id: int
        :returns: query
        """
        return db().query(
            models.IPAddr.ip_addr,
            models.IPAddr.node
        ).filter_by(
            network=network_id
        )

    @classmethod
    def delete_by_node(cls, node_id):
        """Delete all IPs allocated to specified node.

        :param node_id: Node ID
        :type node_id: int
        :returns: None
        """
        db().query(models.IPAddr).filter_by(node=node_id).delete()

    @classmethod
    def get_distinct_in_list(cls, ip_list):
        """Find IPs from ip_list which exist in database.

        :param ip_list: List of IP adresses
        :type ip_list: list
        :returns: set of IPs in ip_list that exist in database
        """
        return db().query(
            models.IPAddr.ip_addr.distinct()
        ).filter(
            models.IPAddr.ip_addr.in_(ip_list)
        )

    @classmethod
    def get_assigned_vips_for_controller_group(cls, cluster):
        """Get VIPs assigned in specified cluster's controller node group

        :param cluster: Cluster object
        :type cluster: Cluster model
        :returns: VIPs for given cluster
        """
        node_group_id = Cluster.get_controllers_group_id(cluster)
        cluster_vips = db.query(models.IPAddr).join(
            models.IPAddr.network_data).filter(
                models.IPAddr.vip_name.isnot(None) &
                (models.NetworkGroup.group_id == node_group_id))
        return cluster_vips

    @classmethod
    def delete_by_network(cls, ip, network):
        db.query(models.IPAddr).filter(
            models.IPAddr.ip_addr == ip,
            models.IPAddr.network == network
        ).delete(synchronize_session='fetch')

    @classmethod
    def get_networks_ips(cls, node):
        """Get IPs assigned to node grouped by network group.

        :param node: Node instance
        :returns: query
        """
        return db().query(
            models.NetworkGroup, models.IPAddr.ip_addr
        ).filter(
            models.NetworkGroup.group_id == node.group_id,
            models.IPAddr.network == models.NetworkGroup.id,
            models.IPAddr.node == node.id
        )

    @classmethod
    def get_networks_ips_dict(cls, node):
        """Get IPs assigned to node grouped by network group.

        :param node: Node instance
        :returns: dict mapping network group name to IP addresses
        """
        return {ng.name: ip for ng, ip in cls.get_networks_ips(node)}

    @classmethod
    def get_network_ips_count(cls, node_id, network_id):
        """Get number of IPs from specified network assigned to node.

        :param node_id: Node ID
        :param network_id: NetworkGroup ID
        :returns: count of IP addresses
        """
        return db().query(models.IPAddr).filter_by(
            node=node_id, network=network_id).count()

    @classmethod
    def set_networks_ips(cls, node, ips_by_network_name):
        """Set IPs by provided network-to-IP mapping.

        :param instance: Node instance
        :param ips_by_network_name: dict
        :returns: None
        """
        ngs = db().query(
            models.NetworkGroup.name, models.IPAddr
        ).filter(
            models.NetworkGroup.group_id == node.group_id,
            models.IPAddr.network == models.NetworkGroup.id,
            models.IPAddr.node == node.id,
            models.NetworkGroup.name.in_(ips_by_network_name)
        )
        for ng_name, ip_addr in ngs:
            ip_addr.ip_addr = ips_by_network_name[ng_name]
        db().flush()


class IPAddrRange(NailgunObject):
    model = models.IPAddrRange
    serializer = BasicSerializer

    @classmethod
    def get_by_cluster(cls, cluster_id):
        """Get IP Address ranges for all node groups in cluster

        :param cluster: Cluster ID
        :type cluster_id: int
        :returns: VIPs for given cluster
        """
        return db().query(
            models.IPAddrRange.first,
            models.IPAddrRange.last,
        ).join(
            models.NetworkGroup.ip_ranges,
            models.NetworkGroup.nodegroup
        ).filter(
            models.NodeGroup.cluster_id == cluster_id
        )


class IPAddrCollection(NailgunCollection):

    single = IPAddr

    @classmethod
    def get_all_by_addr(cls, ip_addr):
        """Get all IPs with given ip address."""
        return cls.all().filter(cls.single.model.ip_addr == ip_addr)

    @classmethod
    def get_by_cluster_id(cls, cluster_id):
        """Get records filtered by cluster identifier.

        Or returns all records if no cluster_id is provided.

        :param cluster_id: cluster identifier or None to get all records
        :type cluster_id: int|None
        :return: vips query
        :rtype: SQLAlchemy Query
        """
        query = cls.all()
        if cluster_id is not None:
            query = query.join(models.NetworkGroup)\
                .join(models.NodeGroup)\
                .filter(models.NodeGroup.cluster_id == cluster_id)
        return query

    @classmethod
    def get_vips_by_cluster_id(cls, cluster_id,
                               network_id=None, network_role=None):
        """Get VIP filtered by cluster ID.

        VIP is determined by not NULL vip_name field of IPAddr model.

        :param cluster_id: cluster identifier or None to get all records
        :type cluster_id: int|None
        :param network_id: network identifier
        :type network_id: int
        :param network_role: network role
        :type network_role: str
        :return: vips query
        :rtype: SQLAlchemy Query
        """
        query = cls.get_by_cluster_id(cluster_id)\
            .filter(models.IPAddr.vip_name.isnot(None))

        if network_id:
            query = query.filter(models.IPAddr.network == network_id)

        if network_role:
            # Get all network_roles for cluster and gain vip names from it,
            # then bound query to this names.
            # See network_roles.yaml in plugin examples for the details of
            # input structure.
            cluster_obj = Cluster.get_by_uid(cluster_id)
            vips = []

            for cluster_network_role in Cluster.get_network_roles(cluster_obj):
                if cluster_network_role.get('id') == network_role:
                    vips.extend(
                        cluster_network_role
                        .get('properties', {})
                        .get('vip', [])
                    )

            vip_names = (vip['name'] for vip in vips)
            unique_vip_names = list(set(vip_names))
            query = query.filter(models.IPAddr.vip_name.in_(unique_vip_names))

        return query

    @classmethod
    def update_vips(cls, new_data_list):
        """Perform batch update of VIP data.

        :param new_data_list:
        :type new_data_list: list(dict)
        :return: vips query
        :rtype: SQLAlchemy Query
        """
        # create dictionary where key is id
        data_by_ids = {item['id']: item for item in new_data_list}

        # get db instances
        query = cls.filter_by_list(None, 'id', list(data_by_ids))

        cls.lock_for_update(query).all()
        for existing_instance in query:
            cls.single.update(
                existing_instance,
                data_by_ids[existing_instance.id]
            )
        return query
