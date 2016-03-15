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

import nailgun
from nailgun import consts
from nailgun.objects.serializers.base import BasicSerializer


class DeploymentGraphTaskSerializer(BasicSerializer):

    fields = (
        "task_name",
        "version",
        "condition",
        "type",
        "groups",
        "tasks",
        "roles",
        "reexecute_on",
        "refresh_on",
        "required_for",
        "requires",
        "cross_depended_by",
        "cross_depends",
        "parameters"
    )

    @classmethod
    def serialize(cls, instance, fields=None):
        legacy_fields_mapping = {
            'task_name': 'id',
            'cross_depends': 'cross-depends',
            'cross_depended_by': 'cross-depended-by',
            'roles': 'role'
        }
        serialized_task = super(
            DeploymentGraphTaskSerializer, cls
        ).serialize(instance, fields=None)

        result = {}
        for field in cls.fields:
            value = serialized_task.get(field)
            if value:
                result[field] = value
                if field in legacy_fields_mapping:
                    result[legacy_fields_mapping[field]] = value
                # `role` for backward-compatibility should be string
                # instead of list
                if field == 'roles':
                    # map role: ['*'] that old serialized do not get back
                    # to role: '*'
                    if len(value) == 1 and value[0] in consts.TASK_ROLES:
                        result['role'] = value[0]
        # unwrap custom field
        result.update(instance._custom)
        return result


class DeploymentGraphSerializer(BasicSerializer):

    fields = (
        "id",
        "name"
        # tasks will be added below
    )

    @classmethod
    def serialize(cls, instance, fields=None):
        serialized_graph = super(
            DeploymentGraphSerializer, cls
        ).serialize(instance, fields=fields)
        if not fields or 'tasks' in fields:
            tasks = nailgun.objects.DeploymentGraph\
                .get_tasks(deployment_graph_instance=instance)
            serialized_graph['tasks'] = tasks

        # append relations info
        serialized_graph['relations'] = []
        for relation in nailgun.objects.DeploymentGraph.get_related_models(
                instance):
            serialized_graph['relations'].append({
                'type': relation.get('type'),
                'model': relation.get('model').__class__.__name__,
                'model_id': relation.get('model').id
            })
        return serialized_graph
