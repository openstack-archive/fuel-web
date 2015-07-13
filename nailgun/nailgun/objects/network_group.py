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

from nailgun.db.sqlalchemy.models import NetworkGroup as DBNetworkGroup
from nailgun.objects import NailgunCollection
from nailgun.objects import NailgunObject


class NetworkGroup(NailgunObject):

    model = DBNetworkGroup
    serializer = NetworkGroupSerializer

    schema = {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "title": "NetworkGroup",
        "description": "Serialized NetworkGroup object",
        "type": "object",
        "properties": {
            "id": {"type": "number"},
            "name": {"type": "string"},
            "release": {"type": "number"},
            "vlan_start": {"type": "number"},
            "cidr": {"type": "string"},
            "gateway": {"type": "string"},
            "group_id": {"type": "integer"},
            "meta": {"type": "object"}
        }
    }


class NetworkGroupCollection(NailgunCollection):

    single = NetworkGroup
