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

from nailgun.db import db
from nailgun.db.sqlalchemy import models
from nailgun.objects import base
from nailgun.objects.serializers.deployment_graph import \
    DeploymentGraphSerializer
from nailgun.objects.serializers.deployment_graph import \
    DeploymentGraphTaskSerializer


class DeploymentGraphTask(base.NailgunObject):

    model = models.DeploymentGraphTask
    serializer = DeploymentGraphTaskSerializer

    _incoming_fields_map = {
        'id': 'task_name',
        'cross-depends': 'cross_depends',
        'cross-depended-by': 'cross_depended_by',
        'role': 'roles'
    }

    @classmethod
    def create(cls, data):
        """Create DeploymentTask model.

        :param data: task data
        :type data: dict
        :return: DeploymentGraphTask instance
        :rtype: DeploymentGraphTask
        """
        data_to_create = {}
        for field, value in six.iteritems(data):
            # remap fields
            if field in cls._incoming_fields_map:
                data_to_create[cls._incoming_fields_map[field]] = value
            else:
                data_to_create[field] = value
        deployment_task_instance = models.DeploymentGraphTask(**data_to_create)
        db().add(deployment_task_instance)
        return deployment_task_instance


class DeploymentGraphTaskCollection(base.NailgunCollection):

    single = DeploymentGraphTask

    @classmethod
    def get_by_deployment_graph_uid(cls, deployment_graph_uid):
        return cls.filter_by(None, deployment_graph_id=deployment_graph_uid)


class DeploymentGraph(base.NailgunObject):

    model = models.DeploymentGraph
    serializer = DeploymentGraphSerializer

    @classmethod
    def create(cls, deployment_tasks_data, verbose_name=None):
        """Create DeploymentGraph and related DeploymentGraphTask models.

        :param deployment_tasks_data: list of deployment_tasks
        :type deployment_tasks_data: list[dict]
        :param verbose_name: graph verbose name
        :type verbose_name: basestring|None
        :returns: instance of new DeploymentGraphModel
        :rtype: DeploymentGraphModel
        """
        # create graph
        deployment_graph_instance = super(DeploymentGraph, cls).create({
            'verbose_name': verbose_name
        })
        # create tasks
        for deployment_task in deployment_tasks_data:
            deployment_task["deployment_graph_id"] = \
                deployment_graph_instance.id
            DeploymentGraphTask.create(deployment_task)
        return deployment_graph_instance

    @classmethod
    def get_tasks(cls, instance):
        return DeploymentGraphTaskCollection.get_by_deployment_graph_uid(
            instance.id
        )


class DeploymentGraphCollection(base.NailgunCollection):

    single = DeploymentGraph
