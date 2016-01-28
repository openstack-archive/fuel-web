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
import sqlalchemy as sa

from nailgun.db import db
from nailgun.db.sqlalchemy.models import cluster_plugin_link \
    as cluster_plugin_link_db_model
from nailgun.errors import errors
from nailgun.objects.base import NailgunCollection
from nailgun.objects.base import NailgunObject
from nailgun.objects.serializers import plugin_link


class ClusterPluginLink(NailgunObject):

    model = cluster_plugin_link_db_model.ClusterPluginLink
    serializer = plugin_link.PluginLinkSerializer

    @classmethod
    def update(cls, instance, data):
        try:
            return super(ClusterPluginLink, cls).update(instance, data)
        except sa.exc.IntegrityError as exc:
            db.rollback()
            raise errors.AlreadyExists(exc.message)


class ClusterPluginLinkCollection(NailgunCollection):

    single = ClusterPluginLink

    @classmethod
    def get_by_cluster_id(cls, cluster_id):
        if cluster_id is not None:
            return cls.filter_by(None, cluster_id=cluster_id)
        else:
            return cls.all()

    @classmethod
    def create_with_cluster_id(cls, data, cluster_id):
        data['cluster_id'] = cluster_id
        try:
            return cls.create(data)
        except sa.exc.IntegrityError as exc:
            db.rollback()
            raise errors.AlreadyExists(exc.message)
