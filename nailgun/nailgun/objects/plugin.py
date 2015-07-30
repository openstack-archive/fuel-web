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
from nailgun.objects.serializers import plugin


class Plugin(base.NailgunObject):

    model = models.Plugin
    serializer = plugin.PluginSerializer

    @classmethod
    def create(cls, data):
        # FIXME(ikalnitsky): resolve these circular dependencies :(
        from nailgun.plugins.adapters import wrap_plugin

        plugin = super(Plugin, cls).create(data)

        # populate all compatible clusters with this plugin
        plugin_adapter = wrap_plugin(plugin)
        for cluster in db.query(models.Cluster):
            if plugin_adapter.validate_cluster_compatibility(cluster):
                cluster_plugin = models.ClusterPlugins(
                    cluster_id=cluster.id,
                    plugin_id=plugin.id,
                    enabled=False,
                    attributes=plugin_adapter.get_plugin_attributes(cluster))
                db().add(cluster_plugin)

        db().flush()
        return plugin

    @classmethod
    def get_by_name_version(cls, name, version):
        return db().query(cls.model).\
            filter_by(name=name, version=version).first()

    @classmethod
    def set_enabled(cls, plugin, cluster, enabled):
        """Enables/disabled a given plugin for a given cluster.

        :param plugin: a plugin instance
        :param cluster: a cluster instance
        :param enabled: If True - enables it; otherwise - disables
        """
        db().query(models.ClusterPlugins).\
            filter_by(plugin_id=plugin.id, cluster_id=cluster.id).\
            update({'enabled': enabled}, synchronize_session='fetch')


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
