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
from nailgun.db.sqlalchemy.models import plugins as plugin_db_model
from nailgun.objects import base
from nailgun.objects import Release
from nailgun.objects.serializers import plugin


class Plugin(base.NailgunObject):

    model = plugin_db_model.Plugin
    serializer = plugin.PluginSerializer

    @classmethod
    def get_by_name_version(cls, name, version):
        return db().query(cls.model).\
            filter_by(name=name, version=version).first()


class PluginCollection(base.NailgunCollection):

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
        """Returns plugins by given ids.

        :param plugin_ids: list of plugin ids
        :type plugin_ids: list

        :returns: iterable (SQLAlchemy query)
        """
        return cls.filter_by_id_list(
            cls.all(), plugin_ids)

    @classmethod
    def get_all_by_release(cls, release_id):
        """Returns plugins compatible with specific release

        :param release_id: release ID
        :type release_id: int

        :returns: list - collection of plugins
        """

        related_plugins = []
        related_plugins_ids = set()
        release = Release.get_by_uid(release_id)
        release_os = release.operating_system.lower()
        release_version = release.version

        for db_plugin in cls.all():
            plugin_id = db_plugin.id
            for plugin_release in db_plugin.releases:
                if (release_os == plugin_release.get('os') and
                        release_version == plugin_release.get('version')):
                    if plugin_id not in related_plugins_ids:
                        related_plugins_ids.add(plugin_id)
                        related_plugins.append(db_plugin)

        return related_plugins
