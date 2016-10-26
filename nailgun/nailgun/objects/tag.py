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
import six

from nailgun import consts
from nailgun.db import db
from nailgun.db.sqlalchemy import models
from nailgun import errors
from nailgun.objects import NailgunCollection
from nailgun.objects import NailgunObject
from nailgun.objects.plugin import ClusterPlugin
from nailgun.objects.serializers.tag import TagSerializer


class Tag(NailgunObject):

    model = models.Tag
    serializer = TagSerializer


class TagCollection(NailgunCollection):

    @classmethod
    def create_tags(cls, instance, owner_type):
        tag_meta = instance.tags_metadata
        role_meta = instance.roles_metadata
        for role, role_data in role_meta.items():
            role_tags = role_data.get('tags', [])
            if not role_tags:
                if role in tag_meta:
                    raise errors.InvalidData(
                        "Release has tag {} and it's not linked with role {}."
                        " It's not possible to create so-called independent"
                        " tags and roles.".format(role))
                tag_meta[role] = {
                    'tag': role,
                    'has_primary': role_data.get('has_primary', False),
                    'public_ip_required':
                        role_data.get('public_ip_required', False),
                    'public_for_dvr_required':
                        role_data.get('public_for_dvr_required', False)
                }
                role_data['tags'] = [role]
                role_meta.mark_dirty()
            missed = set(role_tags) - set(tag_meta)
            if missed:
                raise errors.InvalidData('Missed metadata for tag: {}'
                                         .format(','.join(missed)))

        for name, meta in six.iteritems(tag_meta):
            data = {
                'owner_id': instance.id,
                'owner_type': owner_type,
                'tag': name,
                'has_primary': meta.get('has_primary', False),
                'public_ip_required':
                    meta.get('public_ip_required', False),
                'public_for_dvr_required':
                    meta.get('public_for_dvr_required', False),
                'read_only': True
            }
            Tag.create(data)

    @classmethod
    def get_release_tags(cls, release_ids, **kwargs):
        return db().query(models.Tag).filter(
            ((models.Tag.owner_id.in_(release_ids)) &
             (models.Tag.owner_type == consts.TAG_OWNER_TYPES.release))
        ).filter_by(**kwargs)

    @classmethod
    def get_cluster_tags(cls, cluster_ids, **kwargs):
        return db().query(models.Tag).filter(
            ((models.Tag.owner_id.in_(cluster_ids)) &
             (models.Tag.owner_type == consts.TAG_OWNER_TYPES.cluster))
        ).filter_by(**kwargs)

    @classmethod
    def get_plugin_tags(cls, plugin_ids, **kwargs):
        return db().query(models.Tag).filter(
            ((models.Tag.owner_id.in_(plugin_ids)) &
             (models.Tag.owner_type == consts.TAG_OWNER_TYPES.plugin))
        ).filter_by(**kwargs)

    @classmethod
    def get_cluster_nm_tags(cls, cluster, **kwargs):
        """Return list of tags used in cluster's namespace.

        Cluster namespace  including:
            * tags created by user for this cluster
            * tags created by user for cluster's release
            * tags created by user for plugins enabled for cluster
            * core tags of release(described in release metadata) of cluster's
              release
            * core tags of plugins(described in plugin metadata) enabled for
              this cluster

        :param cluster: nailgun.db.sqlalchemy.models.Cluster instance
        :return: query with Tag models
        """
        plugin_ids = (ClusterPlugin.get_enabled(cluster.id)
                      .with_entities(models.Plugin.id).subquery())
        return cls.get_cluster_tags([cluster.id]).union(
            cls.get_plugin_tags(plugin_ids)
        ).union(
            cls.get_release_tags([cluster.release.id])
        ).filter_by(**kwargs)

    @classmethod
    def get_release_nm_tags(cls, release, **kwargs):
        """Return list of tags used in release's namespace.

        Release namespace  including:
            * tags created by user for this release
            * tags created by user for clusters created with this release
            * tags created by user for plugins enabled for cluster created
              with this release
            * core tags of this release(described in release metadata)
            * core tags of plugins(described in plugin metadata) enabled for
              cluster created with this release

        :param release: nailgun.db.sqlalchemy.models.Release instance
        :return: query with Tag models
        """
        cluster_ids = (db().query(models.Cluster.id)
                       .filter_by(release_id=release.id).subquery())

        plugin_ids = (db().query(models.ClusterPlugin.plugin_id)
                      .filter(
                          ((models.ClusterPlugin.enabled.is_(True)) &
                           (models.ClusterPlugin.cluster_id.in_(cluster_ids))))
                      .subquery())

        return cls.get_release_tags([release.id]).union(
            cls.get_cluster_tags(cluster_ids)
        ).union(
            cls.get_plugin_tags(plugin_ids)
        ).filter_by(**kwargs)

    @classmethod
    def get_plugin_nm_tags(cls, plugin, **kwargs):
        """Return list of tags used in plugin's namespace.

        Plugin namespace  including:
            * tags created by user for set of plugins what are enabled
              for clusters connected with current plugin
            * tags created by user for clusters where plugin is enabled
            * tags created by user for releases associated with plugin
              through cluster(plugin is enabled for cluster created with
              release)
            * core tags of releases(described in release metadata) associated
              with plugin through clusters(plugin is enabled for cluster
              created with release)
            * core tags of plugins(described in plugin metadata) what are
              enabled for all clusters where current plugin is enabled

        :param plugin: nailgun.db.sqlalchemy.models.Plugin instance
        :return: query with Tag models
        """
        cluster_ids = (db().query(models.ClusterPlugin.cluster_id)
                       .filter_by(plugin_id=plugin.id, enabled=True)
                       .subquery())

        release_ids = (db().query(models.Release.id).join(models.Cluster)
                       .filter(models.Cluster.id.in_(cluster_ids)).subquery())

        return cls.get_plugin_tags([plugin.id]).union(
            cls.get_cluster_tags(cluster_ids)
        ).union(
            cls.get_release_tags(release_ids)
        ).filter_by(**kwargs)

    @classmethod
    def get_cluster_nm_tags_in_range(cls, cluster, tag_ids):
        return cls.get_cluster_nm_tags(cluster).filter(
            models.Tag.id.in_(tag_ids)
        ).with_entities(models.Tag.id)

    @classmethod
    def should_have_public_with_ip(cls, node):
        return cls.get_node_tags(node).filter(
            models.Tag.public_ip_required.is_(True)
        ).first()

    @classmethod
    def should_have_public_for_dvr(cls, node):
        return cls.get_node_tags(node).filter(
            models.Tag.public_for_dvr_required.is_(True)).first()

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

    @classmethod
    def get_tag_nodes_ids(cls, tag):
        return cls.get_tag_nodes(tag).with_entities(
            models.NodeTag.node_id
        )

    single = Tag
