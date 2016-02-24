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

import six

import nailgun
from nailgun.objects.serializers.base import BasicSerializer


class DeploymentGraphTaskSerializer(BasicSerializer):

    fields = (
        "task_name",
        "version",
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

        # fixme(ikutukov): remove this when orchestrator will be ready
        for new, old in six.iteritems(legacy_fields_mapping):
            if new in serialized_task:
                serialized_task[old] = serialized_task[new]

        return serialized_task


class DeploymentGraphSerializer(BasicSerializer):

    fields = (
        "id",
        "verbose_name"
    )

    @classmethod
    def serialize(cls, instance, fields=None):
        serialized_graph = super(
            DeploymentGraphSerializer, cls
        ).serialize(instance, fields=None)

        tasks = nailgun.objects.DeploymentGraph\
            .get_tasks(instance=instance)
        serialized_graph['deployment_tasks'] = tasks
        return serialized_graph
