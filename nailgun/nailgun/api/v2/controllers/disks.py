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

"""
Controllers dealing with disks
"""

import pecan

from nailgun.api.v2.controllers.base import BaseController

from nailgun.api.v1.validators.node import NodeDisksValidator

from nailgun import objects

from nailgun.db import db
from nailgun.db.sqlalchemy.models import NodeAttributes
from nailgun.volumes.manager import DisksFormatConvertor


class NodeDefaultsDisksController(BaseController):
    """Node default disks handler
    """

    @pecan.expose(template='json:', content_type='application/json')
    def get_all(self, node_id):
        """:returns: JSONized node disks.
        :http: * 200 (OK)
               * 404 (node or its attributes not found in db)
        """
        node = self.get_object_or_404(objects.Node, node_id)
        if not node.attributes:
            raise self.http(404)

        volumes = DisksFormatConvertor.format_disks_to_simple(
            node.volume_manager.gen_volumes_info())

        return volumes


class NodeDisksController(BaseController):
    """Node disks handler
    """

    defaults = NodeDefaultsDisksController()

    validator = NodeDisksValidator

    @pecan.expose(template='json:', content_type='application/json')
    def get_all(self, node_id):
        """:returns: JSONized node disks.
        :http: * 200 (OK)
               * 404 (node not found in db)
        """
        node = self.get_object_or_404(objects.Node, node_id)
        node_volumes = node.attributes.volumes
        return DisksFormatConvertor.format_disks_to_simple(node_volumes)

    @pecan.expose(template='json:', content_type='application/json')
    def put_all(self, node_id):
        """:returns: JSONized node disks.
        :http: * 200 (OK)
               * 400 (invalid disks data specified)
               * 404 (node not found in db)
        """
        node = self.get_object_or_404(objects.Node, node_id)
        data = self.checked_data()

        if node.cluster:
            objects.Cluster.add_pending_changes(
                node.cluster,
                'disks',
                node_id=node.id
            )

        volumes_data = DisksFormatConvertor.format_disks_to_full(node, data)
        # For some reasons if we update node attributes like
        #   node.attributes.volumes = volumes_data
        # after
        #   db().commit()
        # it resets to previous state
        db().query(NodeAttributes).filter_by(node_id=node_id).update(
            {'volumes': volumes_data})
        db().flush()
        db().refresh(node)

        return DisksFormatConvertor.format_disks_to_simple(
            node.attributes.volumes)


class NodeVolumesInformationController(BaseController):
    """Node volumes information handler
    """

    @pecan.expose(template='json:', content_type='application/json')
    def get_all(self, node_id):
        """:returns: JSONized volumes info for node.
        :http: * 200 (OK)
               * 404 (node not found in db)
        """
        node = self.get_object_or_404(objects.Node, node_id)
        if node.cluster is None:
            raise self.http(404, 'Cannot calculate volumes info. '
                                 'Please, add node to an environment.')
        volumes_info = DisksFormatConvertor.get_volumes_info(node)
        return volumes_info
