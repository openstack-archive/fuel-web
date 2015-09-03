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

from distutils.version import LooseVersion
from itertools import groupby

from nailgun.db import db
from nailgun.db.sqlalchemy import models
from nailgun.objects import base
from nailgun.objects.serializers.plugin import PluginSerializer


class Plugin(base.NailgunObject):

    model = models.Plugin
    serializer = PluginSerializer

    @classmethod
    def create(cls, data):
        plugin = super(Plugin, cls).create(data)

        # Prevent circular dependencies
        from nailgun.plugins.adapters import wrap_plugin

        # Populate all compatible clusters with this plugin
        plugin_adapter = wrap_plugin(plugin)
        for cluster in db().query(models.Cluster):
            if plugin_adapter.validate_cluster_compatibility(cluster):
                PluginCollection.connect_with_cluster(
                    plugin.id,
                    cluster.id,
                    plugin_adapter.get_plugin_attributes()
                )

        return plugin

    @classmethod
    def get_by_name_version(cls, name, version):
        return db().query(cls.model).\
            filter_by(name=name, version=version).first()


class PluginCollection(base.NailgunCollection):

    single = Plugin

    @classmethod
    def all_newest(cls):
        """Returns new plugins.
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
        """Returns plugins by given ids.

        :param plugin_ids: list of plugin ids
        :type plugin_ids: list
        :returns: iterable (SQLAlchemy query)
        """
        return cls.filter_by_id_list(
            cls.all(), plugin_ids)

    @classmethod
    def connect_with_cluster(cls, plugin_id, cluster_id, attrs):
        """Connects newest plugin with cluster.

        :param plugin_id: Plugin ID
        :type plugin_id: int
        :param cluster_id: Cluster ID
        :type cluster_id: int
        :param attrs: Plugin metadata
        :type attrs: dict
        """
        cluster_plugin = models.ClusterPlugins(
            plugin_id=plugin_id,
            cluster_id=cluster_id,
            enabled=False,
            attributes=attrs)
        db().add(cluster_plugin)
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
            models.ClusterPlugins.enabled,
            models.ClusterPlugins.attributes
        ).join(models.ClusterPlugins)\
            .filter(models.ClusterPlugins.cluster_id == cluster_id)\
            .order_by(models.Plugin.name)\
            .order_by(models.Plugin.version)

    @classmethod
    def set_attributes(cls, plugin_id, cluster_id, enabled=None, attrs=None):
        """Sets plugin's attributes in cluster_plugins table.

        :param plugin_id: Plugin ID
        :type plugin_id: int
        :param cluster_id: Cluster ID
        :type cluster_id: int
        :param enabled: Enabled or disabled plugin for given cluster
        :type enabled: bool
        :param attrs: Plugin metadata
        :type attrs: dict
        """
        params = {}
        if enabled is not None:
            params.update({'enabled': enabled})
        if attrs is not None:
            params.update({'attributes': attrs})

        db().query(models.ClusterPlugins).\
            filter_by(plugin_id=plugin_id, cluster_id=cluster_id).\
            update(params, synchronize_session='fetch')

    @classmethod
    def get_enabled(cls, cluster_id):
        """Returns a list of plugins enabled for a given cluster.

        :param cluster_id: Cluster ID
        :type cluster_id: int
        :returns: List of plugin instances
        :rtype: iterable (SQLAlchemy query)
        """
        return db().query(models.Plugin)\
            .join(models.ClusterPlugins)\
            .filter(models.ClusterPlugins.cluster_id == cluster_id)\
            .filter(True == models.ClusterPlugins.enabled)\
            .all()
