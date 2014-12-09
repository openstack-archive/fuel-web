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


import nailgun.orchestrator.tasks_templates as templates


def get_uids_for_tasks(nodes, tasks):
    uids = []
    for task in tasks:
        if isinstance(task['role'], list):
            for node in nodes:
                required_for_node = set(task['role']) & set(node.all_roles)
                if required_for_node:
                    uids.append(node.uid)
        elif task['role'] == '*':
            uids.extend([n.uid for n in nodes])
        else:
            logger.warn(
                'Wrong task format, `role` should be a list or "*": %s',
                task)

    return list(set(uids))


def get_uids_for_task(nodes, task):
    return get_uids_for_tasks(nodes, [task])


class GraphStagesSerializer(object):
    """Current serializer generates tasks received from configuration."""

    def __init__(self, graph, cluster, nodes, stage):
        self.graph = graph
        self.cluster = cluster
        self.nodes = nodes
        self.stage = stage

    def serialize(self):
        serialized = []
        tasks = self.graph.get_tasks(self.stage).topology
        for task in tasks:
            uids = get_uids_for_task(self.nodes, task)
            serialized.append(make_generic_task(uids, task))
        return serialized


class NailgunTask(object):

    @classmethod
    def condition(cls, cluster, nodes):
        return False

    @classmethod
    def serialize(cls, cluster, nodes):
        return {'type': 'shell'}


class UploadGlance(NailgunTask):

    stage = 'post_deployment'


class GenerateKeys(NailgunTask):

    stage = 'pre_deployment'


STAGE_TASKS = {'post_deployment': [UploadGlance],
               'pre_deployment': [GenerateKeys]}


class NailgunTaskSerializer(object):
    """Nailgun based task serializer.
    Will be used for tasks that can not be defined without complex logic
    for condition and serialization.
    For example upload_glance, should be executed only on one controller,
    and this kind of logic will result in very complex DSL, which we should
    avoid.
    """

    def __init__(self, cluster, nodes, stage):
        self.cluster = []
        self.nodes = []
        self.tasks = STAGE_TASKS[stage]

    def serialize(self):
        serialized = []
        for task in tasks:
            if task.condition(cluster, nodes):
                serialized.append(task.serialize(cluster, nodes))
        return serialized
