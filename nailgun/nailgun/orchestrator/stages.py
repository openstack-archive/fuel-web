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


import itertools
from nailgun.orchestrator import plugins_serializers
from nailgun.orchestrator.priority_serializers import PriorityStrategy


def stage_serialize(serializer, graph_tasks):
    """Serialize tasks for given stage

    :param serializer: plugins_serializers.BasePluginDeploymentHooksSerializer
    :param graph_tasks: list of tasks
    """

    tasks = list(itertools.chain(
        serializer.serialize_begin_tasks(),
        graph_tasks,
        serializer.serialize_end_tasks()))
    PriorityStrategy().one_by_one(tasks)
    return tasks


def pre_deployment_serialize(orchestrator_graph, cluster, nodes,
                             role_resolver=None):
    graph_tasks = orchestrator_graph.pre_tasks_serialize(nodes)
    return stage_serialize(
        plugins_serializers.PluginsPreDeploymentHooksSerializer(
            cluster, nodes, role_resolver=role_resolver), graph_tasks)


def post_deployment_serialize(orchestrator_graph, cluster, nodes,
                              role_resolver=None):
    graph_tasks = orchestrator_graph.post_tasks_serialize(nodes)
    return stage_serialize(
        plugins_serializers.PluginsPostDeploymentHooksSerializer(
            cluster, nodes, role_resolver=role_resolver), graph_tasks)
