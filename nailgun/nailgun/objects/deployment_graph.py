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

from nailgun import consts
from nailgun.db import db
from nailgun.db.sqlalchemy import models
from nailgun.objects.serializers.deployment_graph import \
    DeploymentGraphSerializer
from nailgun.objects.serializers.deployment_graph import \
    DeploymentGraphTaskSerializer
from nailgun.objects import NailgunObject
from nailgun.objects import NailgunCollection
from nailgun.errors import errors


class DeploymentGraphTask(NailgunObject):

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


class DeploymentGraphTaskCollection(NailgunCollection):

    single = DeploymentGraphTask

    @classmethod
    def get_by_deployment_graph_uid(cls, deployment_graph_uid):
        return cls.filter_by(None, deployment_graph_id=deployment_graph_uid)


class DeploymentGraph(NailgunObject):

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

    @classmethod
    def get_for_model(
            cls, model,
            graph_type=consts.DEPLOYMENT_GRAPH_STANDARD_TYPES.default):
        """Get deployment graph related to given model.

        :param model: model that could have relation to graph
        :type model: models.Plugin|models.Cluster|models.Release|
        :param graph_type: graph type
        :type graph_type: basestring
        :return: graph instance
        :rtype: DeploymentGraph
        """

        if isinstance(model, models.Plugin):
            transitive_model = models.PluginDeploymentGraph
        elif isinstance(model, models.Release):
            transitive_model = models.ReleaseDeploymentGraph
        elif isinstance(model, models.Cluster):
            transitive_model = models.ClusterDeploymentGraph
        elif isinstance(model, models.ClusterPlugins):
            transitive_model = models.ClusterPluginsDeploymentGraph
        else:
            raise errors.UnknownModel

        query = db().query(
            models.DeploymentGraph
        ).join(
            transitive_model
        ).filter(
            models.ReleaseDeploymentGraph.type==graph_type,
            models.ReleaseDeploymentGraph.release_id==model.id
        ).scalar()
        return query


class DeploymentGraphCollection(NailgunCollection):

    single = DeploymentGraph
