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

import itertools
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
    def create(cls, data, flush=True):
        """Create DeploymentTask model.

        :param data: task data
        :type data: dict
        :param flush: do SQLAlchemy flush
        :type flush: bool
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

        # todo(ikutukov): super for this create method is not called to avoid
        # force flush in base method.
        # In future flushing should became optional param of CRUD method for
        # the base nailgun object.
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
    def get_association_for_model(cls, target_model):
        relation_model = None
        if isinstance(target_model, models.Plugin):
            relation_model = models.PluginDeploymentGraph
        elif isinstance(target_model, models.Release):
            relation_model = models.ReleaseDeploymentGraph
        elif isinstance(target_model, models.Cluster):
            relation_model = models.ClusterDeploymentGraph
        return relation_model

    @classmethod
    def _add_tasks(cls, instance, new_tasks):
        instance.tasks = []
        db().commit()  # commit is required to update related models
        for task in new_tasks:
            task["deployment_graph_id"] = instance.id
            DeploymentGraphTask.create(task)
        db().flush()

    @classmethod
    def create(cls, data):
        """Create DeploymentGraph and related DeploymentGraphTask models.

        It is possible to create empty graphs if not tasks data provided.

        :param data: tasks and graph name
        :type data: dict
        :returns: instance of new DeploymentGraphModel
        :rtype: DeploymentGraphModel
        """

        tasks = data.pop('tasks', None)

        deployment_graph_instance = super(DeploymentGraph, cls).create(data)
        if tasks:
            for task in tasks:
                deployment_graph_instance.tasks.append(
                    DeploymentGraphTask.create(task, False))
        db().flush()
        return deployment_graph_instance

    @classmethod
    def update(cls, instance, data):
        """Create DeploymentGraph and related DeploymentGraphTask models.

        It is possible to create empty graphs if not tasks data provided.

        :param instance: DeploymentGraph instance
        :type instance: DeploymentGraph
        :param data: data to update
        :type data: dict
        :returns: instance of new DeploymentGraphModel
        :rtype: DeploymentGraphModel
        """

        tasks = data.pop('tasks', None)

        super(DeploymentGraph, cls).update(instance, data)

        # remove old tasks
        instance.tasks = []

        if tasks:
            for task in tasks:
                instance.tasks.append(
                    DeploymentGraphTask.create(task, False))
        db().flush()
        return instance

    @classmethod
    def get_tasks(cls, deployment_graph_instance):
        if not isinstance(deployment_graph_instance, models.DeploymentGraph):
            raise Exception('This method is allowed only for '
                            'the deployment graph instance.')
        return DeploymentGraphTaskCollection.get_by_deployment_graph_uid(
            deployment_graph_instance.id
        )

    @classmethod
    def upsert_for_model(
            cls, data, instance,
            graph_type=consts.DEFAULT_DEPLOYMENT_GRAPH_TYPE):
        """Create or update graph of given type attached to model instance.

        This method is recommended to create or update graphs.

        :param data: graph data
        :type data: dict
        :param instance: external model
        :type instance: models.Cluster|models.Plugin|models.Release
        :param graph_type: graph type, default is 'default'
        :type graph_type: basestring
        :return: models.DeploymentGraph
        """
        graph = cls.get_for_model(instance, graph_type=graph_type)
        if graph:
            cls.update(graph, data)
        else:
            graph = cls.create(data)
            cls.attach_to_model(graph, instance, graph_type)
        return graph

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
        association_model = cls.get_association_for_model(instance)
        if association_model:
            association = instance.deployment_graphs_assoc.filter(
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

        :param graph_instance: deployment graph model
        :type graph_instance: models.DeploymentGraph
        :param instance: model that should have relation to graph
        :type instance: models.Plugin|models.Cluster|models.Release|
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
        association_class = cls.get_association_for_model(instance)
        if association_class:
            association = association_class(
                type=graph_type,
                deployment_graph_id=graph_instance.id
            )
            instance.deployment_graphs_assoc.append(association)
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
            association = cls.get_association_for_model(instance)
            instance.deployment_graphs_assoc.filter(
                association.type == graph_type
            ).delete()
            db().flush()
            logger.debug(
                'Graph with ID={0} was detached from model {1} with ID={2}'
                .format(existing_graph.id, instance, instance.id))
            return existing_graph

    @classmethod
    def get_related_models(cls, instance):
        """Get all models instanced related to this graph.

        :param instance: deployment graph instance.
        :type instance: models.DeploymentGraph

        :return: list of {
                    'type': 'graph_type',
                    'model': Cluster|Plugin|Release
                 }
        :rtype: list[dict]
        """
        result = []
        for relation in itertools.chain(
                instance.clusters_assoc,
                instance.releases_assoc,
                instance.plugins_assoc):
            for attr in ('plugin', 'release', 'cluster'):
                external_model = getattr(relation, attr, None)
                if external_model:
                    result.append({
                        'type': relation.type,
                        'model': external_model})
        return result


class DeploymentGraphCollection(NailgunCollection):

    single = DeploymentGraph

    @classmethod
    def get_for_model(cls, instance):
        """Get deployment graphs related to given model.

        :param instance: model that could have relation to graph
        :type instance: models.Plugin|models.Cluster|models.Release|
        :return: graph instance
        :rtype: model.DeploymentGraph
        """
        association_model = cls.single.get_association_for_model(instance)
        graphs = db.query(
            models.DeploymentGraph
        ).join(
            association_model
        ).join(
            instance.__class__
        ).filter(
            instance.__class__.id == instance.id
        )
        return list(graphs)
