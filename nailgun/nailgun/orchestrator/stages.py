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


from nailgun.orchestrator import plugins_serializers
from nailgun.orchestrator.priority_serializers import PriorityStrategy


def stage_serialize(serializer, graph_tasks, cluster, nodes):
    """Serialize tasks for given stage

    :param serializer: plugins_serializers.BasePluginDeploymentHooksSerializer
    :param graph_tasks: list of tasks
    :param cluster: cluster db object
    :param nodes: list of node db objects
    """
    priority = PriorityStrategy()
    tasks = []

    tasks.extend(graph_tasks)

    plugins = serializer(cluster, nodes)
    tasks.extend(plugins.serialize())
    priority.one_by_one(tasks)

    return tasks


def pre_deployment_serialize(orchestrator_graph, cluster, nodes):
    graph_tasks = orchestrator_graph.pre_tasks_serialize(nodes)
    return stage_serialize(
        plugins_serializers.PluginsPreDeploymentHooksSerializer,
        graph_tasks, cluster, nodes)


def post_deployment_serialize(orchestrator_graph, cluster, nodes):
    graph_tasks = orchestrator_graph.post_tasks_serialize(nodes)
    return stage_serialize(
        plugins_serializers.PluginsPostDeploymentHooksSerializer,
        graph_tasks, cluster, nodes)
