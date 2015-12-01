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
from nailgun.objects.serializers.ip_address import IPAddressSerializer


class IPAddress(NailgunObject):

    model = models.IPAddr
    serializer = IPAddressSerializer


class IPAddressCollection(NailgunCollection):

    single = IPAddress

    @classmethod
    def get_by_cluster_id(cls, cluster_id):
        q = cls.all()
        if cluster_id is not None:
            q = q.join(models.NetworkGroup)\
                .join(models.NodeGroup)\
                .filter(models.NodeGroup.cluster_id == int(cluster_id))
        return q

    @classmethod
    def get_vips_by_cluster_id(cls, cluster_id):
        return cls.get_by_cluster_id(cluster_id)\
            .filter(models.IPAddr.vip_info.isnot(None))
