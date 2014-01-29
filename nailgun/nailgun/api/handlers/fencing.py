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

from nailgun.api.handlers.base import BaseHandler
from nailgun.api.handlers.base import content_json
from nailgun.api.validators.fencing import FencingConfigValidator
from nailgun.db import db
from nailgun.db.sqlalchemy.models import Cluster
from nailgun.db.sqlalchemy.models import fencing
from nailgun.db.sqlalchemy.models import FencingConfiguration
from nailgun.db.sqlalchemy.models import FencingPrimitive
from nailgun.fixtures.fencing import fencing_metadata


class FencingConfigurationHandler(BaseHandler):
    """obtain/update fencing configuration of cluster
    """

    #serializer = FencingConfigSerializer
    validator = FencingConfigValidator

    @content_json
    def GET(self, cluster_id):
        """:returns: JSONized fencing configuration of cluster.
        :http: * 200 (OK)
               * 404 (cluster or fencing configuration is not found)
        """
        cluster = self.get_object_or_404(Cluster, cluster_id)
        if not cluster.fencing_config:
            db().add(FencingConfiguration(
                cluster_id=cluster_id,
                policy=fencing.FENCING_POLICIES.disabled
            ))
            db().flush()
        cfg = cluster.fencing_config
        resp = {
            'policy': cfg['policy'],
            'primitive_configuration': []
        }
        prim_names = set(p.name for p in cfg.primitives)
        for pn in prim_names:
            prims_by_name = [
                {
                    'node_id': p.node_id,
                    'index': p.index,
                    'parameters': p.parameters
                }
                for p in cfg.primitives
                if p.name == pn
            ]
            resp['primitive_configuration'].append({
                'name': pn,
                'node_primitive_configuration': prims_by_name
            })
        return resp

    @content_json
    def PUT(self, cluster_id):
        """:returns: JSONized fencing configuration of cluster.
        :http: * 200 (OK)
               * 400 (invalid data is specified)
               * 404 (cluster or fencing configuration is not found)
        """
        cluster = self.get_object_or_404(Cluster, cluster_id)
        data = self.checked_data(self.validator.validate_update)
        if cluster.fencing_config:
            fencing_config = cluster.fencing_config
            fencing_config.primitives = []
        else:
            fencing_config = FencingConfiguration(
                cluster_id=cluster_id,
                policy=data['policy']
            )
            db().add(fencing_config)
            db().flush()
        for prim_type in data['primitive_configuration']:
            name = prim_type['name']
            for prim in prim_type['node_primitive_configuration']:
                db().add(FencingPrimitive(
                    name=name,
                    index=prim['index'],
                    configuration_id=fencing_config.id,
                    node_id=prim['node_id'],
                    parameters=prim['parameters']
                ))
        db().flush()
        return data


class FencingPrimitivesHandler(BaseHandler):
    """obtain fencing primitives parameters for cluster
    """

    @content_json
    def GET(self, cluster_id):
        """:returns: JSONized fencing primitives parameters.
        :http: * 200 (OK)
               * 404 (cluster is not found)
        """
        cluster = self.get_object_or_404(Cluster, cluster_id)
        if cluster.mode == 'multinode':
            return []
        prim_params = fencing_metadata['primitives_ui_parameters']
        ui_params = [
            {
                'name': p,
                'type': prim_params[p]['type'],
                'multi': (prim_params[p]['per_node_relation'] != 1),
                'parameters': prim_params[p]['parameters'] +
                prim_params['common']['parameters']
            }
            for p in prim_params.keys() if p != 'common'
        ]
        return ui_params
