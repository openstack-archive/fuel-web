# -*- coding: utf-8 -*-

#    Copyright 2013 Mirantis, Inc.
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
Handlers dealing with networks
"""

import traceback
import web

from nailgun.api.handlers.base import BaseHandler
from nailgun.api.handlers.base import content_json
from nailgun.api.serializers.network_group import NetworkGroupSerializer
from nailgun.api.validators.base import BasicValidator

from nailgun.db import db
from nailgun.db.sqlalchemy.models import Cluster
from nailgun.db.sqlalchemy.models import IPAddrRange
from nailgun.db.sqlalchemy.models import NetworkGroup

from nailgun.logger import logger


class NetworkGroupHandler(BaseHandler):
    """Network group handler
    """

    validator = BasicValidator

    @content_json
    def GET(self, net_id):
        """:returns: JSONized network group definition.
        :http: * 200 (OK)
               * 404 (network group not found in db)
        """
        network_group = self.get_object_or_404(NetworkGroup, net_id)
        return self.render(network_group)

    @content_json
    def PUT(self, net_id):
        net = self.get_object_or_404(NetworkGroup, net_id)
        data = self.validator.validate(web.data())
        for key, value in data.iteritems():
            setattr(net, key, value)
        db().add(net)
        return self.render(net)

    def DELETE(self, net_id):
        """:returns: Empty string
        :http: * 204 (network group successfully deleted)
               * 404 (network group not found in db)
        """
        network_group = self.get_object_or_404(NetworkGroup, net_id)
        db().delete(network_group)
        db().commit()
        raise web.webapi.HTTPError(
            status="204 No Content",
            data=""
        )


class NetworkGroupCollectionHandler(BaseHandler):

    serializer = NetworkGroupSerializer

    @classmethod
    def render(cls, ngs):
        json_list = []
        for ng in ngs:
            try:
                json_data = cls.serializer.serialize(ng)
                json_list.append(json_data)
            except Exception:
                logger.error(traceback.format_exc())
        return json_list

    @content_json
    def GET(self, cluster_id):
        """:returns: JSONized network group definition.
        :http: * 200 (OK)
               * 404 (network group not found in db)
        """
        cluster_db = db().query(Cluster).get(cluster_id)
        network_groups = cluster_db.network_groups
        return self.render(network_groups)

    @content_json
    def POST(self, group_id):
        data = self.checked_data()

        ng = NetworkGroup()
        for key, value in data.iteritems():
            if key == 'id':
                continue
            else:
                setattr(ng, key, value)

        db().add(ng)
        db().commit()

        if data.get('ip_start') and data.get('ip_end') and ng.id:
            ipr = IPAddrRange(
                network_group_id=ng.id,
                first=data['ip_start'],
                last=data['ip_end']
            )
            db().add(ipr)
            db().commit()

        return ng.id
