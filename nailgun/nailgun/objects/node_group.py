# -*- coding: utf-8 -*-

#    Copyright 2014 Mirantis, Inc.
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


from nailgun.api.serializers.node_group import NodeGroupSerializer

from nailgun.db.sqlalchemy.models import NodeGroup as DBNodeGroup

from nailgun.objects import NailgunCollection
from nailgun.objects import NailgunObject


class NodeGroup(NailgunObject):

    model = DBNodeGroup
    serializer = NodeGroupSerializer

    schema = {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "title": "NodeGroup",
        "description": "Serialized NodeGroup object",
        "type": "object",
        "properties": {
            "id": {"type": "number"},
            "cluster_id": {"type": "number"},
            "name": {"type": "string"}
        }
    }


class NodeGroupCollection(NailgunCollection):

    single = NodeGroup

    @classmethod
    def get_by_cluster_id(cls, cluster_id):
        if cluster_id == '':
            return cls.filter_by(cluster_id=None)
        return cls.filter_by(cluster_id=cluster_id)
