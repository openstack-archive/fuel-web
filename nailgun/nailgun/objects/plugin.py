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

from nailgun.db.sqlalchemy.models import plugins as plugin_db_model
from nailgun.objects import base
from nailgun.objects.serializers import plugin

from nailgun.db import db


class Plugin(base.NailgunObject):

    model = plugin_db_model.Plugin
    serializer = plugin.PluginSerializer

    @classmethod
    def get_by_name_version(cls, name, version):
        return db().query(cls.model).\
            filter_by(name=name, version=version).first()


class PluginCollection(base.NailgunCollection):

    single = Plugin
