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
from nailgun.objects import NailgunCollection
from nailgun.objects import NailgunObject
from nailgun.objects.serializers.ip_addr import IPAddrSerializer
from nailgun.utils import filter_dict

# for current implementation with just two updatable fields
# this approach may seem overcomplicated but it will give favor
# if more fields or json fields will be used during further
# feature development

VIP_UPDATABLE_FIELDS = (
    "ip_addr",
    "is_user_defined"
)


class IPAddr(NailgunObject):

    model = models.IPAddr
    serializer = IPAddrSerializer

    @classmethod
    def update_vip(cls, instance, data):
        """Update existing instance with specified parameters.

        :param instance: object (model) instance
        :param data: dictionary of key-value pairs as object fields
        :returns: instance of an object (model)
        """
        return cls.update(
            instance,
            filter_dict(data, VIP_UPDATABLE_FIELDS)
        )


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
        q = cls.all()
        if cluster_id is not None:
            q = q.join(models.NetworkGroup)\
                .join(models.NodeGroup)\
                .filter(models.NodeGroup.cluster_id == int(cluster_id))
        return q

    @classmethod
    def get_vips_by_cluster_id(cls, cluster_id):
        """Get VIP filtered by cluster ID.

        VIP is determined by not NULL vip_name field of IPAddr model.

        :param cluster_id: cluster identifier or None to get all records
        :type cluster_id: int|None
        :return: vips query
        :rtype: SQLAlchemy Query
        """
        return cls.get_by_cluster_id(cluster_id)\
            .filter(models.IPAddr.vip_name.isnot(None))

    @classmethod
    def update_vips(cls, new_data_list):
        """Perform batch update of VIP data.

        :param new_data_list:
        :type new_data_list: list(dict)
        :return: vips query
        :rtype: SQLAlchemy Query
        """
        # create dictionary where key is id
        data_by_ids = {item.get('id'): item for item in new_data_list}

        # get db instances
        q = cls.filter_by_list(None, 'id', list(data_by_ids.keys()))

        cls.lock_for_update(q).all()
        for existing_instance in q:
            cls.single.update_vip(
                existing_instance,
                data_by_ids[existing_instance.id]
            )
        return q
