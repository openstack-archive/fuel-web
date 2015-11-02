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

import six

from distutils.version import LooseVersion
from itertools import groupby

from nailgun.db import db
from nailgun.db.sqlalchemy import models
from nailgun.objects import NailgunCollection
from nailgun.objects import NailgunObject
from nailgun.objects.serializers.plugin import PluginSerializer


class Plugin(NailgunObject):

    model = models.Plugin
    serializer = PluginSerializer

    @classmethod
    def create(cls, data):
        new_plugin = super(Plugin, cls).create(data)
        ClusterPlugins.add_compatible_clusters(new_plugin)

        return new_plugin

    @classmethod
    def get_by_name_version(cls, name, version):
        return db()\
            .query(cls.model)\
            .filter_by(name=name, version=version)\
            .first()


class PluginCollection(NailgunCollection):

    single = Plugin

    @classmethod
    def all_newest(cls):
        """Returns plugins in most recent versions

        Example:
        There are 4 plugins:
        - name: plugin_name, version: 1.0.0
        - name: plugin_name, version: 2.0.0
        - name: plugin_name, version: 0.1.0
        - name: plugin_another_name, version: 1.0.0
        In this case the method returns 2 plugins:
        - name: plugin_name, version: 2.0.0
        - name: plugin_another_name, version: 1.0.0

        :returns: list of Plugin models
        """
        newest_plugins = []
        grouped_by_name = groupby(cls.all(), lambda p: p.name)
        for name, plugins in grouped_by_name:
            newest_plugin = sorted(
                plugins,
                key=lambda p: LooseVersion(p.version),
                reverse=True)[0]

            newest_plugins.append(newest_plugin)

        return newest_plugins

    @classmethod
    def get_by_uids(cls, plugin_ids):
        """Returns plugins by given IDs.

        :param plugin_ids: list of plugin IDs
        :type plugin_ids: list
        :returns: iterable (SQLAlchemy query)
        """
        return cls.filter_by_id_list(cls.all(), plugin_ids)

    @classmethod
    def get_by_release(cls, release):
        release_plugins = set()
        release_os = release.operating_system.lower()
        release_version = release.version

        for plugin in PluginCollection.all():
            for plugin_release in plugin.releases:
                if (release_os == plugin_release.get('os') and
                        release_version == plugin_release.get('version')):
                    release_plugins.add(plugin)

        return release_plugins


class ClusterPlugins(NailgunObject):

    model = models.ClusterPlugins

    @classmethod
    def validate_compatibility(cls, cluster, plugin):
        """Validates if plugin is compatible with cluster.

        - validates operating systems
        - modes of clusters (simple or ha)
        - release version

        :param cluster: A cluster instance
        :type cluster: nailgun.objects.cluster.Cluster
        :param plugin: A plugin instance
        :type plugin: nailgun.objects.plugin.Plugin
        :return: True if compatible, False if not
        :rtype: bool
        """
        for release in plugin.releases:
            os_compat = cluster.release.operating_system.lower()\
                == release['os'].lower()
            # plugin writer should be able to specify ha in release['mode']
            # and know nothing about ha_compact
            mode_compat = any(mode in cluster.mode for mode in release['mode'])
            release_version_compat = cls.is_release_version_compatible(
                cluster.release.version, release['version'])
            if all((os_compat, mode_compat, release_version_compat)):
                return True
        return False

    @staticmethod
    def is_release_version_compatible(rel_version, plugin_rel_version):
        """Checks if release version is compatible with plugin version.

        :param rel_version: Release version
        :type rel_version: str
        :param plugin_rel_version: Plugin release version
        :type plugin_rel_version: str
        :return: True if compatible, False if not
        :rtype: bool
        """
        rel_os, rel_fuel = rel_version.split('-')
        plugin_os, plugin_rel = plugin_rel_version.split('-')

        return rel_os.startswith(plugin_os) and rel_fuel.startswith(plugin_rel)

    @classmethod
    def get_compatible_plugins(cls, cluster):
        """Returns a list of plugins that are compatible with a given cluster.

        :param cluster: A cluster instance
        :type cluster: nailgun.objects.cluster.Cluster
        :return: A list of plugin instances
        :rtype: list
        """
        return list(six.moves.filter(
            lambda p: cls.validate_compatibility(cluster, p),
            PluginCollection.all()))

    @classmethod
    def add_compatible_plugins(cls, cluster):
        """Populates 'cluster_plugins' table with compatible plugins.

        :param cluster: A cluster instance
        :type cluster: nailgun.objects.cluster.Cluster
        """
        for plugin in cls.get_compatible_plugins(cluster):
            cls.create({
                'cluster_id': cluster.id,
                'plugin_id': plugin.id,
                'enabled': False,
                'attributes': plugin.attributes_metadata
            })

    @classmethod
    def get_compatible_clusters(cls, plugin):
        """Returns a list of clusters that are compatible with a given plugin.

        :param plugin: A plugin instance
        :type plugin: nailgun.objects.plugin.Plugin
        :return: A list of cluster instances
        :rtype: list
        """
        return list(six.moves.filter(
            lambda c: cls.validate_compatibility(c, plugin),
            db().query(models.Cluster)))

    @classmethod
    def add_compatible_clusters(cls, plugin):
        """Populates 'cluster_plugins' table with compatible cluster.

        :param plugin: A plugin instance
        :type plugin: nailgun.objects.plugin.Plugin
        """
        for cluster in cls.get_compatible_clusters(plugin):
            cls.create({
                'cluster_id': cluster.id,
                'plugin_id': plugin.id,
                'enabled': False,
                'attributes': plugin.attributes_metadata
            })

    @classmethod
    def set_attributes(cls, cluster_id, plugin_id, enabled=None, attrs=None):
        """Sets plugin's attributes in cluster_plugins table.

        :param cluster_id: Cluster ID
        :type cluster_id: int
        :param plugin_id: Plugin ID
        :type plugin_id: int
        :param enabled: Enabled or disabled plugin for given cluster
        :type enabled: bool
        :param attrs: Plugin metadata
        :type attrs: dict
        """
        params = {}
        if enabled is not None:
            params['enabled'] = enabled
        if attrs is not None:
            params['attributes'] = attrs

        db().query(cls.model)\
            .filter_by(plugin_id=plugin_id, cluster_id=cluster_id)\
            .update(params, synchronize_session='fetch')
        db().flush()

    @classmethod
    def get_connected(cls, cluster_id):
        """Returns plugins connected with cluster.

        :param cluster_id: Cluster ID
        :type cluster_id: int
        :returns: List of plugins
        :rtype: iterable (SQLAlchemy query)
        """
        return db().query(
            models.Plugin.id,
            models.Plugin.name,
            models.Plugin.title,
            models.Plugin.version,
            cls.model.enabled,
            models.Plugin.attributes_metadata,
            cls.model.attributes
        ).join(cls.model)\
            .filter(cls.model.cluster_id == cluster_id)\
            .order_by(models.Plugin.name)\
            .order_by(models.Plugin.version)

    @classmethod
    def get_enabled(cls, cluster_id):
        """Returns a list of plugins enabled for a given cluster.

        :param cluster_id: Cluster ID
        :type cluster_id: int
        :returns: List of plugin instances
        :rtype: iterable (SQLAlchemy query)
        """
        return db().query(models.Plugin)\
            .join(cls.model)\
            .filter(cls.model.cluster_id == cluster_id)\
            .filter(cls.model.enabled.is_(True))\
            .all()
