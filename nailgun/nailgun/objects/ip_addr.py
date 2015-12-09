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

from nailgun.db.sqlalchemy import models
from nailgun.errors import errors
from nailgun.network.proxy import IPAddrProxy
from nailgun.network.proxy import IPAddrRangeProxy
from nailgun.objects import Cluster
from nailgun.objects import NailgunCollection
from nailgun.objects import NailgunObject
from nailgun.objects import NetworkGroup
from nailgun.objects.serializers.base import BasicSerializer
from nailgun.objects.serializers.ip_addr import IPAddrSerializer


class IPAddr(NailgunObject):

    model = models.IPAddr
    serializer = IPAddrSerializer
    proxy = IPAddrProxy()

    @classmethod
    def get_intersecting_ip(cls, instance, addr):
        """Get ip that intersects by ip_addr with given."""
        params = {
            'options': {
                'single': True
            },
            'filters': [
                {'name': 'ip_addr', 'op': 'eq', 'val': addr},
                {'name': 'id', 'op': 'ne', 'val': instance.id},
            ]
        }

        return cls.proxy.filter(params)

    @classmethod
    def get_ips_except_admin(cls, node_id=None,
                             network_id=None, include_network_data=False):
        """Get all non-admin IP addresses for node or network.

        This method will not return VIPs.

        :param node_id: Node database ID.
        :type  node_id: int
        :param network_id: Network database ID.
        :type  network_id: int
        :param include_network_data: Include related network data.
        :type include_network_data: bool
        :returns: List of free IP addresses as SQLAlchemy objects.
        """
        filters = [
            {'name': 'vip_name', 'op': 'eq', 'val': None}
        ]
        params = {}
        if node_id:
            filters.append({'name': 'node', 'op': 'eq', 'val': node_id})
        if network_id:
            filters.append({'name': 'network', 'op': 'eq', 'val': network_id})
        if include_network_data:
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
        params = {
            'options': {
                'fields': ['ip_addr', 'node']
            },
            'filters': [
                {'name': 'network', 'op': 'eq', 'val': network_id}
            ]
        }
        return cls.proxy.filter(params)

    @classmethod
    def delete_by_node(cls, node_id):
        """Delete all IPs allocated to specified node.

        :param node_id: Node ID
        :type node_id: int
        :returns: None
        """
        params = {
            'filters': [
                {'name': 'node', 'op': 'eq', 'val': node_id}
            ]
        }
        cls.proxy.filter_delete(params)

    @classmethod
    def get_distinct_in_list(cls, ip_list):
        """Find IPs from ip_list which exist in database.

        :param ip_list: List of IP adresses
        :type ip_list: list
        :returns: set of IPs in ip_list that exist in database
        """
        params = {
            'options': {'distinct': ['ip_addr']},
            'filters': [
                {'name': 'ip_addr', 'op': 'in', 'val': ip_list}
            ]
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
                {'name': 'vip_name', 'op': 'isnot', 'val': None},
                {
                    'name': 'network_data__group_id',
                    'op': 'eq',
                    'val': node_group_id
                }
            ]
        }
        return cls.proxy.filter(params)

    @classmethod
    def delete_by_network(cls, ip, network):
        params = {
            'filters': [
                {'name': 'ip_addr', 'op': 'eq', 'val': ip},
                {'name': 'network', 'op': 'eq', 'val': network}
            ]
        }

        cls.proxy.filter_delete(params)


class IPAddrRange(NailgunObject):
    model = models.IPAddrRange
    serializer = BasicSerializer
    proxy = IPAddrRangeProxy()

    @classmethod
    def get_by_cluster(cls, cluster_id):
        """Get IP Address ranges for all node groups in cluster

        :param cluster: Cluster ID
        :type cluster_id: int
        :returns: VIPs for given cluster
        """
        params = {
            'options': {
                'fields': ['first', 'last']
            },
            'filters': [
                {
                    'name': 'network_group__nodegroup__cluster_id',
                    'op': 'eq',
                    'val': cluster_id
                }
            ]
        }

        return cls.proxy.filter(params)


class IPAddrCollection(NailgunCollection):

    single = IPAddr

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
