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

import networkx as nx
import yaml

from nailgun.errors import errors
from nailgun.orchestrator import graph_configuration
import nailgun.orchestrator.priority_serializers as ps
import nailgun.orchestrator.tasks_templates as templates
from nailgun.utils import extract_env_version


class DeploymentGraph(nx.DiGraph):

    def add_tasks(self, tasks):
        for task in tasks:
            self.add_task(task)

    def add_task(self, task):
        self.add_node(task['id'], **task)
        if 'required_for' in task:
            for req in task['required_for']:
                self.add_edge(task['id'], req)
        if 'requires' in task:
            for req in task['requires']:
                self.add_edge(req, task['id'])
        if 'role' in task:
            for req in task['role']:
                self.add_edge(task['id'], req)
        if 'stage' in task:
            self.add_edge(task['id'], req)

    def add_priorities(self, nodes):
        """Add priorities and tasks for all nodes

        :param nodes: {'controller': [...], 'compute': [...]}
        :param graph: DeploymentGraph instance populated with tasks
        """
        priority = ps.PriorityStrategy()
        roles_subgraph = self.roles_subgraph
        topo = self.roles_subgraph.topology
        prev = None
        keep_current = False
        for role in topo:
            if role['id'] in nodes:
                task = roles_subgraph.node[role['id']]
                #NOTE(dshulyak) if role has same predecessor as previous,
                #we should not increase priority, it is not always correct
                #but it will cover all current cases, and all others
                #will be covered by using mistral
                if prev and (
                    roles_subgraph.predecessors(prev['id'])
                        == roles_subgraph.predecessors(role['id'])):
                    keep_current = True
                else:
                    keep_current = False
                if task['parameters']['strategy']['type'] == 'parallel':
                    if 'amount' in task['parameters']['strategy']:
                        priority.in_parallel_by(
                            nodes[role['id']],
                            task['parameters']['strategy']['amount'])
                    else:
                        if keep_current:
                            priority.add_in_parallel(nodes[role['id']])
                        else:
                            priority.in_parallel(nodes[role['id']])
                else:
                    # if strategy not specified prioritize tasks one by one
                    priority.one_by_one(nodes[role['id']])
                prev = role

    @property
    def roles_subgraph(self):
        roles = [t['id'] for t in self.node.values() if t['type'] == 'role']
        return self.subgraph(roles)

    def get_tasks_for_role(self, role_name):
        tasks = []
        for task in self.predecessors(role_name):
            if self.node[task]['type'] not in ('role', 'stage'):
                tasks.append(task)
        return self.subgraph(tasks)

    def serialize_tasks(self, node):
        """Get serialized tasks with priorities and necessery for orchestrator
        format

        :param node: dict with serialized node
        """
        tasks = self.get_tasks_for_role(node['role']).topology
        serialized = []
        priority = ps.Priority()
        for task in tasks:
            if task['type'] == 'puppet':
                item = templates.make_puppet_task(
                    [node['uid']],
                    task)
            elif task['type'] == 'shell':
                item = templates.make_shell_task(
                    [node['uid']],
                    task)
            item['priority'] = priority.next()
            serialized.append(item)
        return serialized

    @property
    def topology(self):
        topo = []
        for task in nx.topological_sort(self):
            topo.append(self.node[task])
        return topo


def initialize_graph(cluster):
    """Initializez graph with dependences between roles and tasks.
    Provided in CONFIG,

    :param cluster: DB Cluster object
    :returns: DeploymentGraph instance
    """
    env_version = extract_env_version(cluster.release.version)
    if env_version.startswith('6.0') or env_version.startswith('5.1'):
        tasks = graph_configuration.DEPLOYMENT_51
    elif env_version.startswith('5.0'):
        tasks = graph_configuration.DEPLOYMENT_50
    else:
        raise errors.UnsupportedSerializer(
            "Version %s is not supported", env_version)
    if cluster.pending_release_id:
        tasks = graph_configuration.PATCHING
    graph = DeploymentGraph()
    graph.add_tasks(yaml.load(tasks))
    return graph
