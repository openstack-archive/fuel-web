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


from nailgun.objects.serializers.node_group import NodeGroupSerializer

from nailgun.db import db
from nailgun.db.sqlalchemy import models
from nailgun import errors
from nailgun.extensions import fire_callback_on_nodegroup_create
from nailgun.extensions import fire_callback_on_nodegroup_delete
from nailgun.objects import Cluster
from nailgun.objects import NailgunCollection
from nailgun.objects import NailgunObject


class NodeGroup(NailgunObject):

    model = models.NodeGroup
    serializer = NodeGroupSerializer

    @classmethod
    def create(cls, data):
        new_group = super(NodeGroup, cls).create(data)
        cluster = Cluster.get_by_uid(new_group.cluster_id)
        try:
            fire_callback_on_nodegroup_create(new_group)
        except errors.CannotCreate:
            db().delete(new_group)

        db().flush()
        db().refresh(cluster)
        return new_group

    @classmethod
    def delete(cls, instance):
        fire_callback_on_nodegroup_delete(instance)
        super(NodeGroup, cls).delete(instance)


class NodeGroupCollection(NailgunCollection):

    single = NodeGroup

    @classmethod
    def get_by_cluster_id(cls, cluster_id):
        if not cluster_id:
            return cls.filter_by(None, cluster_id=None)
        return cls.filter_by(None, cluster_id=cluster_id)
