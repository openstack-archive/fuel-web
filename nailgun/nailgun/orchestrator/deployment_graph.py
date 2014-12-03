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
            self.add_edge(task['id'], task['stage'])

    def add_priorities(self, nodes):
        """Add priorities and tasks for all nodes
        :param nodes: {'controller': [...], 'compute': [...]}
        :param graph: DeploymentGraph instance populated with tasks
        """
        priority = ps.PriorityStrategy()
        roles_subgraph = self.roles_subgraph
        success_roles = set()
        current_roles = self.roles_subgraph.root_roles
        while current_roles:
            increase = True
            existing_roles = [self.node[role] for role in current_roles
                              if role in nodes]
            one_by_one = [
                r for r in existing_roles
                if r['parameters']['strategy']['type'] == 'one_by_one']
            parallel = [
                r for r in existing_roles
                if r['parameters']['strategy']['type'] == 'parallel']
            for role in one_by_one:
                priority.one_by_one(nodes[role['id']])
            for role in parallel:
                if 'amount' in role['parameters']['strategy']:
                    priority.in_parallel_by(
                        nodes[role['id']],
                        role['parameters']['strategy']['amount'])
                else:
                    if increase:
                        priority.increment()
                    priority.add_in_parallel(nodes[role['id']])
                    increase = False
            success_roles.update(current_roles)
            current_roles = roles_subgraph.get_next_roles(success_roles)

    @property
    def root_roles(self):
        """Return roles that doesnt have predecessors

        :returns: list of roles names
        """
        result = []
        for node in self.nodes():
            if not self.predecessors(node):
                result.append(node)
        return result

    def get_next_roles(self, success_roles):
        """Get roles that have predecessors in success_roles list

        :param success_roles: list of roles names
        :returns: list of roles names
        """
        result = []
        for role in self.nodes():
            if (set(self.predecessors(role)) <= success_roles
                    and role not in success_roles):
                result.append(role)
        return result

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
        tasks = graph_configuration.DEPLOYMENT_CURRENT
    elif env_version.startswith('5.0'):
        tasks = graph_configuration.DEPLOYMENT_50
    if cluster.pending_release_id:
        tasks = graph_configuration.PATCHING
    graph = DeploymentGraph()
    graph.add_tasks(yaml.load(tasks))
    return graph
