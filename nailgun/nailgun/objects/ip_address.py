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
from nailgun.errors import errors
from nailgun.objects import Cluster
from nailgun.objects import NailgunCollection
from nailgun.objects import NailgunObject
from nailgun.objects import NetworkGroup
from nailgun.objects.serializers.base import BasicSerializer


class IPAddr(NailgunObject):

    model = models.IPAddr
    serializer = BasicSerializer

    @classmethod
    def get_ips_except_admin(cls, node_id=None,
                             network_id=None, joined=False):
        """Get all non-admin IP addresses for node or network

        :param node_id: Node database ID.
        :type  node_id: int
        :param network_id: Network database ID.
        :type  network_id: int
        :returns: List of free IP addresses as SQLAlchemy objects.
        """
        ips = db().query(models.IPAddr).order_by(models.IPAddr.id)
        if joined:
            ips = ips.options(joinedload('network_data'))
        if node_id:
            ips = ips.filter_by(node=node_id)
        if network_id:
            ips = ips.filter_by(network=network_id)

        try:
            admin_net_id = NetworkGroup.get_admin_network_group(
                node_id=node_id).id
        except errors.AdminNetworkNotFound:
            admin_net_id = None
        if admin_net_id:
            ips = ips.filter(
                not_(models.IPAddr.network == admin_net_id)
            )

        return ips.all()

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
    def get_assigned_vips_for_net_groups(cls, cluster):
        """Get VIPs assigned in specified cluster's node group.

        :param cluster: Cluster object
        :type cluster: Cluster model
        :returns: VIPs for given cluster
        """
        node_group_id = Cluster.get_controllers_group_id(cluster)
        cluster_vips = db.query(models.IPAddr).join(
            models.IPAddr.network_data).filter(
                models.IPAddr.node.is_(None) &
                models.IPAddr.vip_type.isnot(None) &
                (models.NetworkGroup.group_id == node_group_id))
        return cluster_vips

    @classmethod
    def delete_by_network(cls, ip, network):
        db.query(models.IPAddr).filter(
            models.IPAddr.ip_addr == ip,
            models.IPAddr.network == network
        ).delete()
        db().flush()


class IPAddrRange(NailgunObject):
    model = models.IPAddrRange
    serializer = BasicSerializer


class IPAddrCollection(NailgunCollection):

    single = IPAddr
