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

from nailgun.consts import TAG_OWNER_TYPES
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
    def get_release_tags_query(cls, release_ids):
        return db().query(models.Tag).filter(
            ((models.Tag.owner_id.in_(release_ids)) &
             (models.Tag.owner_type == TAG_OWNER_TYPES.release))
        )

    @classmethod
    def get_cluster_tags_query(cls, cluster_ids):
        return db().query(models.Tag).filter(
            ((models.Tag.owner_id.in_(cluster_ids)) &
             (models.Tag.owner_type == TAG_OWNER_TYPES.cluster))
        )

    @classmethod
    def get_plugin_tags_query(cls, plugin_ids):
        return db().query(models.Tag).filter(
            ((models.Tag.owner_id.in_(plugin_ids)) &
             (models.Tag.owner_type == TAG_OWNER_TYPES.plugin))
        )

    @classmethod
    def get_cluster_nm_tags_query(cls, cluster):
        plugin_ids = (ClusterPlugin.get_enabled(cluster.id)
                      .with_entities(models.Plugin.id).subquery())
        return cls.get_cluster_tags_query([cluster.id]).union(
            cls.get_plugin_tags_query(plugin_ids)
        ).union(
            cls.get_release_tags_query([cluster.release.id])
        )

    @classmethod
    def get_release_nm_tags_query(cls, release):
        cluster_ids = (db().query(models.Cluster.id)
                       .filter_by(release_id=release.id).subquery())

        plugin_ids = (db().query(models.ClusterPlugin.plugin_id)
                      .filter(
                          ((models.ClusterPlugin.enabled.is_(True)) &
                           (models.ClusterPlugin.cluster_id.in_(cluster_ids))))
                      .subquery())

        return cls.get_release_tags_query([release.id]).union(
            cls.get_cluster_tags_query(cluster_ids)
        ).union(
            cls.get_plugin_tags_query(plugin_ids)
        )

    @classmethod
    def get_plugin_nm_tags_query(cls, plugin):
        cluster_ids = (db().query(models.ClusterPlugin.cluster_id)
                       .filter_by(plugin_id=plugin.id, enabled=True)
                       .subquery())

        release_ids = (db().query(models.Release.id).join(models.Cluster)
                       .filter(models.Cluster.id.in_(cluster_ids)).subquery())

        return cls.get_plugin_tags_query([plugin.id]).union(
            cls.get_cluster_tags_query(cluster_ids)
        ).union(
            cls.get_release_tags_query(release_ids)
        )

    @classmethod
    def get_node_tags_query(cls, node_id):
        return db().query(models.Tag).join(
            models.NodeTag
        ).filter(
            models.NodeTag.node_id == node_id
        )

    @classmethod
    def get_cluster_nm_tags_in_range(cls, cluster, tag_ids):
        return cls.get_cluster_nm_tags_query(cluster).filter(
            models.Tag.id.in_(tag_ids)
        ).with_entities(models.Tag.id)

    @classmethod
    def get_tag_nodes_query(cls, tag_id):
        return db().query(models.Node).join(
            models.NodeTag
        ).filter(
            models.NodeTag.tag_id == tag_id
        )

    @classmethod
    def get_node_tags_ids_query(cls, node_id):
        return cls.get_node_tags_query(node_id).with_entities(
            models.NodeTag.tag_id
        )

    @classmethod
    def get_node_tags_ids_in_range(cls, node_id, tag_ids):
        return cls.get_node_tags_ids_query(node_id).filter(
            models.NodeTag.tag_id.in_(tag_ids)
        )

    @classmethod
    def get_cluster_tags(cls, cluster, **kwargs):
        return cls.get_cluster_tags_query(cluster).filter_by(**kwargs)

    single = Tag
