# -*- coding: utf-8 -*-

#    Copyright 2016 Mirantis, Inc.
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

"""
Tag object and collection
"""

from nailgun.db import db
from nailgun.db.sqlalchemy import models
from nailgun.objects import NailgunCollection
from nailgun.objects import NailgunObject
from nailgun.objects.plugin import ClusterPlugin
from nailgun.objects.serializers.tag import TagSerializer


class Tag(NailgunObject):

    model = models.Tag
    serializer = TagSerializer


class TagCollection(NailgunCollection):

    @classmethod
    def get_cluster_tags_query(cls, cluster):
        plugins_ids = (ClusterPlugin.get_enabled(cluster.id)
                       .with_entities(models.Plugin.id).subquery())
        return db().query(models.Tag).filter(
            ((models.Tag.owner_id == cluster.release.id) &
             (models.Tag.owner_type == 'release')) |
            ((models.Tag.owner_id == cluster.id) &
             (models.Tag.owner_type == 'cluster')) |
            ((models.Tag.owner_id.in_(plugins_ids)) &
             (models.Tag.owner_type == 'plugin'))
        )

    @classmethod
    def get_node_tags_query(cls, node_id):
        return db().query(models.Tag).join(
            models.NodeTag
        ).filter(
            models.NodeTag.node_id == node_id
        )

    @classmethod
    def get_cluster_tags(cls, cluster, **kwargs):
        return cls.get_cluster_tags_query(cluster).filter_by(**kwargs)

    single = Tag
