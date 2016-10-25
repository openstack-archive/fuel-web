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
from nailgun.objects.plugin import Plugin
from nailgun.objects.serializers.tag import TagSerializer


class Tag(NailgunObject):

    model = models.Tag
    serializer = TagSerializer

    @staticmethod
    def get_owner(self, owner_type, owner_id):
        from nailgun.objects import Cluster
        from nailgun.objects import Release

        obj_cls = {
            'releases': Release,
            'clusters': Cluster,
            'plugins': Plugin
        }[owner_type]
        return obj_cls, obj_cls.get_by_uid(owner_id)

    @classmethod
    def create(cls, data):
        """Create tag.

        :param data: data
        :type data: dict

        :return: plugin instance
        :rtype: models.Plugin
        """
        # update only if user specified this field
        if data.get('volumes_tags_mapping') is not None:
            owner_cls, owner_obj = cls.get_owner(data['owner_type'],
                                                 data['owner_id'])
            owner_cls.update_tag_volumes(owner_obj, data)
            data.pop('volumes_tags_mapping')
        return super(Tag, cls).create(data)

    @classmethod
    def delete(cls, instance):
        """Delete tag.

        :param instance: Tag model instance
        :type instance: models.Tag
        """
        owner_cls, owner_obj = cls._get_owner(instance.owner_type,
                                              instance.owner_id)
        owner_cls.delete_tag_volumes(owner_obj, instance.tag)
        super(Tag, cls).delete(instance)


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
