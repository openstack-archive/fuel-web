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

from nailgun.db import db
from nailgun.db.sqlalchemy.models import dashboard_entry \
    as dashboard_entry_db_model
from nailgun.objects import base
from nailgun.objects.serializers import dashboard_entry


class DashboardEntry(base.NailgunObject):

    model = dashboard_entry_db_model.DashboardEntry
    serializer = dashboard_entry.DashboardEntrySerializer

    schema = {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "title": "DashboardEntry",
        "description": "Serialized DashboardEntry object",
        "type": "object",
        "properties": {
            "id": {"type": "number"},
            "cluster_id": {"type": "number"},
            "name": {"type": "string",},
            "url": {"type": "string",},
            "description": {"type": "string"},
        }
    }


class DashboardEntryCollection(base.NailgunCollection):

    single = DashboardEntry

    @classmethod
    def get_by_cluster_id(cls, cluster_id):
        if cluster_id == '':
            return cls.filter_by(None, cluster_id=None)
        return cls.filter_by(None, cluster_id=cluster_id)

    @classmethod
    def create_with_cluster_id(cls, data, cluster_id):
        data['cluster_id'] = cluster_id
        return cls.create(data)
