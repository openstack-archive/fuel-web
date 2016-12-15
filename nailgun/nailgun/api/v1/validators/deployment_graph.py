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
from nailgun import objects


class DeploymentGraphValidator(BasicValidator):
    single_schema = schema.DEPLOYMENT_GRAPH_SCHEMA
    collection_schema = schema.DEPLOYMENT_GRAPHS_SCHEMA

    @classmethod
    def validate(cls, data):
        parsed = super(DeploymentGraphValidator, cls).validate(data)
        cls.validate_tasks_ids(parsed)
        return parsed

    @classmethod
    def validate_update(cls, data, instance):
        parsed = super(DeploymentGraphValidator, cls).validate(data)
        cls.validate_schema(
            parsed,
            cls.single_schema
        )
        cls.validate_tasks_ids(parsed)
        return parsed

    @classmethod
    def validate_tasks_ids(cls, parsed):
        tasks = parsed.get('tasks', [])
        ids = set()
        dup = set()
        for task in tasks:
            if task['id'] in ids:
                dup.add(task['id'])
            else:
                ids.add(task['id'])
        if dup:
            raise errors.InvalidData(
                "Tasks duplication found: {0}".format(', '.join(dup))
            )


class GraphExecuteParamsValidator(BasicValidator):

    single_schema = schema.GRAPH_EXECUTE_PARAMS_SCHEMA

    @classmethod
    def validate(cls, data):
        parsed = cls.validate_json(data)
        cls.validate_schema(parsed, cls.single_schema)

        nodes_to_check = set()
        for graph in parsed['graphs']:
            nodes_to_check.update(graph.get('nodes') or [])

        if nodes_to_check:
            cls.validate_nodes(nodes_to_check, parsed['cluster'])
        return parsed

    @classmethod
    def validate_nodes(cls, ids, cluster_id):
        nodes = objects.NodeCollection.filter_by(None, cluster_id=cluster_id)
        nodes = objects.NodeCollection.filter_by_list(nodes, 'id', ids)

        if nodes.count() != len(ids):
            raise errors.InvalidData(
                'Nodes {} do not belong to the same cluster {}'
                .format(', '.join(ids), cluster_id)
            )
