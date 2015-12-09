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


from nailgun.db import db
from nailgun.db.sqlalchemy import models
from nailgun.errors import errors
from nailgun.network.proxy import IPAddrProxy
from nailgun.network.proxy import IPAddrRangeProxy
from nailgun.objects import Cluster
from nailgun.objects import NetworkGroup
from nailgun.objects import ProxiedNailgunCollection
from nailgun.objects import ProxiedNailgunObject
from nailgun.objects.serializers.base import BasicSerializer


class IPAddr(ProxiedNailgunObject):

    model = models.IPAddr
    serializer = BasicSerializer
    proxy = IPAddrProxy()

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

        filters = []
        params = {}
        if node_id:
            filters.append({'name': 'node', 'op': 'eq', 'val': node_id})
        if network_id:
            filters.append({'name': 'network', 'op': 'eq', 'val': network_id})
        if joined:
            params['options'] = {
                'joinedload': 'network_data'
            }

        try:
            admin_net_id = NetworkGroup.get_admin_network_group(
                node_id=node_id).id
        except errors.AdminNetworkNotFound:
            admin_net_id = None

        if admin_net_id:
            filters.append({
                'not': {
                    'name': 'network',
                    'op': 'eq',
                    'val': admin_net_id
                }
            })

        params['filters'] = filters
        return cls.proxy.filter(params).all()

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
        params = {'filters': [{'name': 'node', 'op': 'eq', 'val': node_id}]}
        all_ips = cls.proxy.filter(params)
        cls.proxy.bulk_delete([i.id for i in all_ips])

    @classmethod
    def get_distinct_in_list(cls, ip_list):
        """Find IPs from ip_list which exist in database.

        :param ip_list: List of IP adresses
        :type ip_list: list
        :returns: set of IPs in ip_list that exist in database
        """
        params = {
            'options': {'distinct': ['ip_addr']},
            'filters': [{'name': 'ip_addr', 'op': 'in', 'val': ip_list}]
        }
        return cls.proxy.filter(params)

    @classmethod
    def get_assigned_vips_for_controller_group(cls, cluster):
        """Get VIPs assigned in specified cluster's controller node group

        :param cluster: Cluster object
        :type cluster: Cluster model
        :returns: VIPs for given cluster
        """
        node_group_id = Cluster.get_controllers_group_id(cluster)
        params = {
            'filters': [
                {'name': 'vip_type', 'op': 'isnot', 'val': None},
                {
                    'name': 'network_data__group_id',
                    'op': 'eq',
                    'val': node_group_id
                }
            ]
        }
        cluster_vips = cls.proxy.filter(params)
        return cluster_vips

    @classmethod
    def delete_by_network(cls, ip, network):
        params = {
            'filters': [
                {'name': 'ip_addr', 'op': 'eq', 'val': ip},
                {'name': 'network', 'op': 'eq', 'val': network}
            ]
        }
        cls.proxy.filter_delete(params)


class IPAddrRange(ProxiedNailgunObject):
    model = models.IPAddrRange
    serializer = BasicSerializer
    proxy = IPAddrRangeProxy()

    @classmethod
    def get_by_network(cls, cluster_id):
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


class IPAddrCollection(ProxiedNailgunCollection):

    single = IPAddr
