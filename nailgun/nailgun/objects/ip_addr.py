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
from nailgun.objects import Cluster
from nailgun.objects import NailgunCollection
from nailgun.objects import NailgunObject
from nailgun.objects.serializers.ip_addr import IPAddrSerializer


class IPAddr(NailgunObject):

    model = models.IPAddr
    serializer = IPAddrSerializer


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
