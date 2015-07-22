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


from nailgun.objects.serializers.network_group import NetworkGroupSerializer

from nailgun.db import db
from nailgun.db.sqlalchemy.models import NetworkGroup as DBNetworkGroup
from nailgun import objects


class NetworkGroup(objects.NailgunObject):

    model = DBNetworkGroup
    serializer = NetworkGroupSerializer

    @classmethod
    def get_from_node_group_by_name(cls, node_group_id, network_name):
        ng = db().query(DBNetworkGroup).filter_by(group_id=node_group_id,
                                                  name=network_name)
        return ng.first() if ng else None


class NetworkGroupCollection(objects.NailgunCollection):

    single = NetworkGroup
