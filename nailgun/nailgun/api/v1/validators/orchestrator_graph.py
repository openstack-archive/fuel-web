# -*- coding: utf-8 -*-
#    Copyright 2014 Mirantis, Inc.
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
from nailgun.api.v1.validators.json_schema import base_types
from nailgun.api.v1.validators.json_schema import tasks
from nailgun import consts
from nailgun.errors import errors
from nailgun import objects
from nailgun.orchestrator import orchestrator_graph


class GraphSolverTasksValidator(BasicValidator):

    @classmethod
    def validate_update(cls, data, instance):
        parsed = cls.validate(data)
        cls.validate_schema(parsed, tasks.TASKS_SCHEMA)
        return parsed


class TaskDeploymentValidator(BasicValidator):

    @classmethod
    def validate_tasks(cls, tasks, cluster):
        """Check that passed tasks are present in deployment graph

        :param tasks: list of tasks
        :param cluster: Cluster DB object
        :returns: list of tasks
        """
        cls.validate_schema(tasks, base_types.STRINGS_ARRAY)

        deployment_tasks = objects.Cluster.get_deployment_tasks(cluster)
        graph = orchestrator_graph.GraphSolver()
        graph.add_tasks(deployment_tasks)

        non_existent_tasks = set(tasks) - set(graph.nodes())
        if non_existent_tasks:
            raise errors.InvalidData(
                'Tasks {0} are not present in deployment graph'.format(
                    ','.join(non_existent_tasks)))

        return tasks

    @classmethod
    def validate_tasks_types(cls, types):
        """Check that passed types are actuall tasks types

        :param types: list of types
        """
        cls.validate_schema(types, base_types.STRINGS_ARRAY)

        non_existent_types = set(types) - set(consts.INTERNAL_TASKS)
        if non_existent_types:
            raise errors.InvalidData("Task types {0} do not exist".format(
                ','.join(non_existent_types)))
        return types


class GraphSolverVisualizationValidator(TaskDeploymentValidator):

    @classmethod
    def validate(cls, data, cluster):
        """Check that passed tasks are present in deployment graph

        :param data: list of tasks in string representation.
                      Example: "hiera,controller"
        :param cluster: Cluster DB object
        """
        tasks = list(set(data.split(',')))
        return cls.validate_tasks(tasks, cluster)

    @classmethod
    def validate_task_presence(cls, task, graph):
        """Checks if task is present in graph.

        :param task: task name to check
        :param graph: graph where task presence will be check
        """
        if not graph.has_node(task):
            raise errors.InvalidData(
                'Task {0} is not present in graph'.format(task))

        return task
