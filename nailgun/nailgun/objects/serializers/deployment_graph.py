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
        "id",
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
            'cross_depends': 'cross-depends',
            'cross_depended_by': 'cross-depended-by',
            'roles': 'role'
        }
        # task_name should be re-mapped to ID during output
        serialized_task = super(
            DeploymentGraphTaskSerializer, cls
        ).serialize(instance, fields=cls.fields + ('task_name',))

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
                        result['roles'] = value[0]
        result['id'] = serialized_task.get('task_name')
        # unwrap custom field
        result.update(instance._custom)
        return result


class DeploymentGraphSerializer(BasicSerializer):

    fields = (
        "id",
        "name",
        "tasks",
        "relations"
    )

    @classmethod
    def serialize(cls, instance, fields=None):
        use_fields = fields if fields else cls.fields
        data_dict = {}
        for field in use_fields:
            if field == 'tasks':
                tasks = nailgun.objects.DeploymentGraph\
                    .get_tasks(deployment_graph_instance=instance)
                data_dict['tasks'] = tasks
            elif field == 'relations':
                data_dict['relations'] = []
                for relation in nailgun.objects.DeploymentGraph.\
                        get_related_models(instance):
                    model = relation.get('model')
                    data_dict['relations'].append({
                        'type': relation.get('type'),
                        'model': model.__class__.__name__.lower(),
                        'model_id': model.id
                    })
            else:
                value = getattr(instance, field)
                if value is None:
                    data_dict[field] = value
                else:
                    f = getattr(instance.__class__, field)
                    if hasattr(f, "impl"):
                        rel = f.impl.__class__.__name__
                        if rel == 'ScalarObjectAttributeImpl':
                            data_dict[field] = value.id
                        elif rel == 'CollectionAttributeImpl':
                            data_dict[field] = [v.id for v in value]
                        else:
                            data_dict[field] = value
                    else:
                        data_dict[field] = value
        return data_dict
