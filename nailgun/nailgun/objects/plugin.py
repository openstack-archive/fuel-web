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

from nailgun.db.sqlalchemy import models
from nailgun.objects import base
from nailgun.objects.cluster import ClusterCollection
from nailgun.objects.serializers import plugin

from nailgun.plugins import hooks

from nailgun import db


class Plugin(base.NailgunObject):

    model = models.plugins.Plugin
    serializer = plugin.PluginSerializer

    @classmethod
    def create(cls, data):
        super(Plugin, cls).create(data)
        db().flush()
        # required for case when Clusters created before plugins uploaded,
        # so in next hook - each plugin will look at cluster
        # and decide whether it should be applied to this cluster
        for cluster in ClusterCollection.all():
            hooks.cluster.upload_plugin_attributes(cluster)


class PluginCollection(base.NailgunCollection):

    single = Plugin
