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

import copy

import six

from nailgun import consts
from nailgun.db import db
from nailgun.db.sqlalchemy import models
from nailgun.logger import logger
from nailgun.objects import NailgunCollection
from nailgun.objects import NailgunObject
from nailgun.objects.serializers.deployment_graph import \
    DeploymentGraphSerializer
from nailgun.objects.serializers.deployment_graph import \
    DeploymentGraphTaskSerializer


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
        db_fields = set(c.name for c in cls.model.__table__.columns)
        data_to_create = {}
        custom_fields = {}  # fields that is not in table
        for field, value in six.iteritems(data):
            # pack string roles to be [role]
            if field in ('role', 'groups') and \
                    isinstance(value, six.string_types):
                value = [value]
            # remap fields
            if field in cls._incoming_fields_map:
                data_to_create[cls._incoming_fields_map[field]] = value
            else:
                if field in db_fields:
                    data_to_create[field] = value
                else:
                    custom_fields[field] = value
        # wrap custom fields
        if custom_fields:
            data_to_create['_custom'] = custom_fields

        deployment_task_instance = models.DeploymentGraphTask(**data_to_create)
        db().add(deployment_task_instance)
        return deployment_task_instance


class DeploymentGraphTaskCollection(NailgunCollection):

    single = DeploymentGraphTask

    @classmethod
    def get_by_deployment_graph_uid(cls, deployment_graph_uid):
        filtered = cls.filter_by(
            None, deployment_graph_id=deployment_graph_uid)
        return cls.to_list(filtered.order_by('id'))


class DeploymentGraph(NailgunObject):

    model = models.DeploymentGraph
    serializer = DeploymentGraphSerializer

    @classmethod
    def _get_association_for_model(cls, target_model):
        relation_model = None
        if isinstance(target_model, models.Plugin):
            relation_model = models.PluginDeploymentGraph
        elif isinstance(target_model, models.Release):
            relation_model = models.ReleaseDeploymentGraph
        elif isinstance(target_model, models.Cluster):
            relation_model = models.ClusterDeploymentGraph
        return relation_model

    @classmethod
    def create(cls, deployment_tasks_data=None, verbose_name=None):
        """Create DeploymentGraph and related DeploymentGraphTask models.

        It is possible to create empty graphs if not tasks data provided.

        :param deployment_tasks_data: list of deployment_tasks
        :type deployment_tasks_data: list[dict]|None
        :param verbose_name: graph verbose name
        :type verbose_name: basestring|None
        :returns: instance of new DeploymentGraphModel
        :rtype: DeploymentGraphModel
        """
        # it is possible to create empty graphs

        # create graph
        deployment_graph_instance = super(DeploymentGraph, cls).create({
            'verbose_name': verbose_name
        })
        # create tasks
        if deployment_tasks_data:
            for deployment_task in copy.deepcopy(deployment_tasks_data):
                deployment_task["deployment_graph_id"] = \
                    deployment_graph_instance.id
                DeploymentGraphTask.create(deployment_task)
        db().flush()
        return deployment_graph_instance

    @classmethod
    def get_tasks(cls, deployment_graph_instance):
        if not isinstance(deployment_graph_instance, models.DeploymentGraph):
            raise Exception('This method is allowed only for '
                            'the deployment graph instance.')
        return DeploymentGraphTaskCollection.get_by_deployment_graph_uid(
            deployment_graph_instance.id
        )

    @classmethod
    def get_for_model(
            cls, instance,
            graph_type=consts.DEFAULT_DEPLOYMENT_GRAPH_TYPE):
        """Get deployment graph related to given model.

        :param instance: model that could have relation to graph
        :type instance: models.Plugin|models.Cluster|models.Release|
        :param graph_type: graph type
        :type graph_type: basestring
        :return: graph instance
        :rtype: model.DeploymentGraph
        """
        association_model = cls._get_association_for_model(instance)
        if association_model:
            association = instance.deployment_graphs.filter(
                association_model.type == graph_type
            ).scalar()
            if association:
                return cls.get_by_uid(association.deployment_graph_id)
        else:
            logger.warning("Graph association with type '{0}' was requested "
                           "for the unappropriated model instance {1} with "
                           "ID={2}".format(graph_type, instance, instance.id))

    @classmethod
    def attach_to_model(
            cls, graph_instance, instance,
            graph_type=consts.DEFAULT_DEPLOYMENT_GRAPH_TYPE, rewrite=True):
        """Attach existing deployment graph to given model.

        graph_type is working like unique namespace and if there are existing
        graph with this type attached to model it will be replaced.

        :param instance: model that should have relation to graph
        :type instance: models.Plugin|models.Cluster|models.Release|
        :param graph_instance: deployment graph model
        :type graph_instance: models.DeploymentGraph
        :param graph_type: graph type
        :type graph_type: basestring
        :param rewrite: remove existing graph with given type if True or
                        integrity exception will be thrown if another graph is
                        exists if False
        :type rewrite: boolean
        :return: graph instance
        :rtype: models.DeploymentGraph

        :raises: IntegrityError
        """
        if rewrite:
            cls.detach_from_model(instance, graph_type)
        association_class = cls._get_association_for_model(instance)
        if association_class:
            association = association_class(
                type=graph_type,
                deployment_graph_id=graph_instance.id
            )
            instance.deployment_graphs.append(association)
        db().flush()

    @classmethod
    def detach_from_model(
            cls, instance,
            graph_type=consts.DEFAULT_DEPLOYMENT_GRAPH_TYPE):
        """Detach existing deployment graph to given model if it exists.

        :param instance: model that should have relation to graph
        :type instance: models.Plugin|models.Cluster|models.Release|
        :param graph_type: graph type
        :type graph_type: basestring
        :returns: if graph was detached
        :rtype: bool
        """
        existing_graph = cls.get_for_model(instance, graph_type)
        if existing_graph:
            association = cls._get_association_for_model(instance)
            instance.deployment_graphs.filter(
                association.type == graph_type
            ).delete()
            db().flush()
            logger.debug(
                'Graph with ID={0} was detached from model {1} with ID={2}'
                .format(existing_graph.id, instance, instance.id))
            return existing_graph


class DeploymentGraphCollection(NailgunCollection):

    single = DeploymentGraph
