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


from nailgun.objects.serializers.node_group import NodeGroupSerializer

from nailgun.db import db
from nailgun.db.sqlalchemy import models
from nailgun.errors import errors
from nailgun.objects import Cluster
from nailgun.objects import NailgunCollection
from nailgun.objects import NailgunObject


class NodeGroup(NailgunObject):

    model = models.NodeGroup
    serializer = NodeGroupSerializer

    @classmethod
    def create(cls, data):
        new_group = super(NodeGroup, cls).create(data)
        try:
            cluster = Cluster.get_by_uid(new_group.cluster_id)
            nm = Cluster.get_network_manager(cluster)
            nst = cluster.network_config.segmentation_type
            nm.check_gw_in_default_node_group(cluster)
            nm.create_network_groups(
                cluster, neutron_segment_type=nst, node_group_id=new_group.id,
                set_all_gateways=True)
            nm.create_admin_network_group(new_group.cluster_id, new_group.id)
        except (
            errors.OutOfVLANs,
            errors.OutOfIPs,
            errors.NoSuitableCIDR
        ) as exc:
            db().delete(new_group)
            raise errors.CannotCreate(exc.message)

        db().flush()
        return new_group


class NodeGroupCollection(NailgunCollection):

    single = NodeGroup

    @classmethod
    def get_by_cluster_id(cls, cluster_id):
        if not cluster_id:
            return cls.filter_by(None, cluster_id=None)
        return cls.filter_by(None, cluster_id=cluster_id)
