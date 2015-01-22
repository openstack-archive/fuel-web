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


from nailgun import consts
from nailgun.orchestrator import plugins_serializers
from nailgun.orchestrator.priority_serializers import PriorityStrategy


def stage_serialize(stage, serializer, orchestrator_graph, cluster, nodes,
                    serialized_cluster):
    """Serialize tasks for given stage

    :param stage: oneOf consts.STAGES
    :param serialize: orchestrator.plugins.BasePluginDeploymentHooksSerializer
    :param orchestrator_graph: instance of AstuteGraph
    :param cluster: cluster db object
    :param nodes: list of node db objects
    :param serialized_cluster: cluster serialized for deployment
    """
    priority = PriorityStrategy()
    tasks = orchestrator_graph.stage_tasks_serialize(stage, nodes,
                                                     serialized_cluster)
    plugins = serializer(cluster, nodes)
    tasks.extend(plugins.serialize())
    priority.one_by_one(tasks)
    return tasks


def pre_deployment_serialize(orchestrator_graph, cluster, nodes,
                             serialized_cluster):
    """Serializes tasks for pre_deployment stage

    :param orchestrator_graph: instance of AstuteGraph
    :param cluster: cluster db object
    :param nodes: list of node db objects
    :param serialized_cluster: cluster serialized for deployment
    """
    return stage_serialize(
        consts.STAGES.pre_deployment,
        plugins_serializers.PluginsPreDeploymentHooksSerializer,
        orchestrator_graph, cluster, nodes, serialized_cluster)


def post_deployment_serialize(orchestrator_graph, cluster, nodes,
                              serialized_cluster):
    """Serializes tasks for post_deployment stage

    :param orchestrator_graph: instance of AstuteGraph
    :param cluster: cluster db object
    :param nodes: list of node db objects
    :param serialized_cluster: cluster serialized for deployment
    """
    return stage_serialize(
        consts.STAGES.post_deployment,
        plugins_serializers.PluginsPostDeploymentHooksSerializer,
        orchestrator_graph, cluster, nodes, serialized_cluster)
