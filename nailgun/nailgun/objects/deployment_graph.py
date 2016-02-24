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

from nailgun.db import db
from nailgun.db.sqlalchemy.models import DeploymentGraph
from nailgun.db.sqlalchemy.models import DeploymentGraphTasks
from nailgun.objects import base
from nailgun.objects.serializers.deployment_graph import \
    DeployementGraphSerializer


class Graph(base.NailgunObject):

    model = DeploymentGraph
    serializer = DeployementGraphSerializer


class GraphCollection(base.NailgunCollection):

    single = DeploymentGraph

    @classmethod
    def create(cls, deployment_tasks_data):
        """Create DeploymentGraphModel and related DeploymentGraphTasksModel in DB.

        :param deployment_tasks_data: list of deployment_tasks
        :type deployment_tasks_data: list[dict]
        :returns: instance of new NetworkGroup
        """
        deployment_graph_instance = super(GraphCollection, cls).create({})
        for deployment_task in deployment_tasks_data:
            deployment_task_instance = DeploymentGraphTasks(
                graph_id=deployment_graph_instance.id,
                **deployment_task)
            db().add(deployment_task_instance)
        db().refresh(deployment_graph_instance)
        return deployment_graph_instance
