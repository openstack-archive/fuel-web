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
Handlers dealing with fencing
"""

import web

from nailgun.api.handlers.base import BaseHandler
from nailgun.api.handlers.base import content_json
from nailgun.api.validators.node import NodeDisksValidator
from nailgun.db import db
from nailgun.db.sqlalchemy.models import Cluster
from nailgun.db.sqlalchemy.models import NodeAttributes
from nailgun.volumes.manager import DisksFormatConvertor


class FencingConfigurationHandler(BaseHandler):
    """obtain/update fencing configuration of cluster
    """

    #validator = NodeDisksValidator

    @content_json
    def GET(self, cluster_id):
        """:returns: JSONized node disks.
        :http: * 200 (OK)
               * 404 (node not found in db)
        """
        node = self.get_object_or_404(Node, node_id)
        node_volumes = node.attributes.volumes
        return DisksFormatConvertor.format_disks_to_simple(node_volumes)

    @content_json
    def PUT(self, node_id):
        """:returns: JSONized node disks.
        :http: * 200 (OK)
               * 400 (invalid disks data specified)
               * 404 (node not found in db)
        """
        node = self.get_object_or_404(Node, node_id)
        data = self.checked_data()

        if node.cluster:
            node.cluster.add_pending_changes('disks', node_id=node.id)

        volumes_data = DisksFormatConvertor.format_disks_to_full(node, data)
        # For some reasons if we update node attributes like
        #   node.attributes.volumes = volumes_data
        # after
        #   db().commit()
        # it resets to previous state
        db().query(NodeAttributes).filter_by(node_id=node_id).update(
            {'volumes': volumes_data})
        db().commit()

        return DisksFormatConvertor.format_disks_to_simple(
            node.attributes.volumes)


class FencingPrimitivesHandler(BaseHandler):
    """obtain fencing primitives parameters for cluster
    """

    @content_json
    def GET(self, cluster_id):
        """:returns: JSONized fencing primitives parameters.
        :http: * 200 (OK)
               * 404 (cluster, release or its fencing metadata not found in db)
        """
        cluster = self.get_object_or_404(Cluster, cluster_id)
        if cluster.mode == 'multinode':
            return []
        prim_params = cluster.release.fencing_metadata[
            'primitives_ui_parameters']
        ui_params = []
        common = prim_params['common']
        for p in prim_params.keys():
            if p != 'common':
                ui_params.append(
                    {
                        'name': p,
                        'type': prim_params[p]['type'],
                        'multi': (prim_params[p]['per_node_relation'] != 1),
                        'parameters': prim_params[p]['parameters'] +
                        common['parameters']
                    }
                )

        return ui_params
