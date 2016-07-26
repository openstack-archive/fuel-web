# -*- coding: utf-8 -*-
#    Copyright 2016 Mirantis, Inc.
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

from nailgun.api.v1.validators.base import BasicValidator
from nailgun.api.v1.validators.json_schema import deployment_graph as schema

from nailgun import errors


class DeploymentGraphValidator(BasicValidator):
    single_schema = schema.DEPLOYMENT_GRAPH_SCHEMA
    collection_schema = schema.DEPLOYMENT_GRAPHS_SCHEMA

    @classmethod
    def validate_update(cls, data, instance):
        parsed = super(DeploymentGraphValidator, cls).validate(data)
        cls.validate_schema(
            parsed,
            cls.single_schema
        )
        return parsed


class DeploymentGraphExecuteParamsValidator(BasicValidator):
    single_schema = schema.DEPLOYMENT_GRAPHS_EXECUTE_PARAMS_SCHEMA

    @classmethod
    def validate_params(cls, data):
        parsed = cls.validate_json(data)
        cls.validate_schema(parsed, cls.single_schema)
        return parsed

    @classmethod
    def validate_nodes(cls, nodes, cluster_id):
        invalid_node_ids = [n.uid for n in nodes if n.cluster_id != cluster_id]
        if invalid_node_ids:
            raise errors.InvalidData(
                'Nodes {} do not belong to the same cluster {} like as other'
                .format(', '.join(invalid_node_ids), cluster_id)
            )
