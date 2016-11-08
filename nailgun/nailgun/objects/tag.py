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
    def get_cluster_tags(cls, cluster, **kwargs):
        plugins_ids = (ClusterPlugin.get_enabled(cluster.id)
                       .with_entities(models.Plugin.id).subquery())
        return db().query(models.Tag).filter(
            ((models.Tag.owner_id == cluster.release.id) &
             (models.Tag.owner_type == 'release')) |
            ((models.Tag.owner_id == cluster.id) &
             (models.Tag.owner_type == 'cluster')) |
            ((models.Tag.owner_id.in_(plugins_ids)) &
             (models.Tag.owner_type == 'plugin'))
        ).filter_by(**kwargs)

    @classmethod
    def get_node_tags(cls, node):
        return db().query(models.Tag).join(
            models.NodeTag
        ).filter(
            models.NodeTag.node_id == node.id
        )

    @classmethod
    def get_node_tags_ids(cls, node):
        return cls.get_node_tags(node).with_entities(
            models.NodeTag.tag_id
        )

    @classmethod
    def get_node_tags_ids_in_range(cls, node, tag_ids):
        return cls.get_node_tags_ids(node).filter(
            models.NodeTag.tag_id.in_(tag_ids)
        )

    @classmethod
    def get_tag_nodes(cls, tag):
        return db().query(models.Node).join(
            models.NodeTag
        ).filter(
            models.NodeTag.tag_id == tag.id
        )

    single = Tag
