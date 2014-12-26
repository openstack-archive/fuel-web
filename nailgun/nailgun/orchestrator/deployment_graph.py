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

from collections import defaultdict

import networkx as nx

from nailgun import consts
from nailgun.errors import errors
from nailgun import objects
from nailgun.orchestrator import priority_serializers as ps
from nailgun.orchestrator import tasks_templates as templates


class DeploymentGraph(nx.DiGraph):
    """DirectedGraph that is used to generate configuration for speficific
    orchestrators.

    In case of astute - we are working with priorities
    In - mistral - we will serialize workbook from this graph

    General task format

    id: string
    type: string - one of - role, stage, puppet, shell, upload_file, sync
    required_for: direct dependencies
    requires: reverse dependencies

    groups: direct dependencies for different levels
    tasks: reverse dependencies for different levels

    stage: direct dependency
    parameters: specific for each task type parameters
    """

    def add_tasks(self, tasks):
        for task in tasks:
            self.add_task(task)

    def add_task(self, task):
        self.add_node(task['id'], **task)

        # standart direct and backward dependencies, should be used for
        # declaring dependencies on one level (group to group, task to task)
        for req in task.get('required_for', ()):
            self.add_edge(task['id'], req)
        for req in task.get('requires', ()):
            self.add_edge(req, task['id'])

        # tasks and groups should be used for declaring dependencies between
        # tasks and roles (which are simply group of tasks)
        for req in task.get('groups', ()):
            self.add_edge(task['id'], req)
        for req in task.get('tasks', ()):
            self.add_edge(req, task['id'])

        # required for compatability with astute orchestration approach
        if 'stage' in task:
            self.add_edge(task['id'], task['stage'])

    def is_acyclic(self):
        """Verify that graph doesnot contain any cycles in it."""
        return nx.is_directed_acyclic_graph(self)

    def get_root_groups(self):
        """Return groups that doesnt have predecessors

        :returns: list of group names
        """
        result = []
        for node in self.nodes():
            if not self.predecessors(node):
                result.append(node)
        return result

    def get_next_groups(self, processed_nodes):
        """Get nodes that have predecessors in processed_nodes list

        :param processed_nodes: set of nodes names
        :returns: list of nodes names
        """
        result = []
        for role in self.nodes():
            if (set(self.predecessors(role)) <= processed_nodes
                    and role not in processed_nodes):
                result.append(role)
        return result

    def get_groups_subgraph(self):
        roles = [t['id'] for t in self.node.values()
                 if t['type'] == consts.ORCHESTRATOR_TASK_TYPES.group]
        return self.subgraph(roles)

    def get_tasks(self, group_name):
        tasks = []
        filter_by = (consts.ORCHESTRATOR_TASK_TYPES.group,
                     consts.ORCHESTRATOR_TASK_TYPES.stage)
        for task in self.predecessors(group_name):
            if self.node[task]['type'] not in filter_by:
                tasks.append(task)
        return self.subgraph(tasks)

    @property
    def topology(self):
        return map(lambda t: self.node[t], nx.topological_sort(self))


class AstuteGraph(object):
    """This object stores logic that required for working with astute
    orchestrator.
    """

    def __init__(self, cluster):
        self.cluster = cluster
        self.tasks = objects.Cluster.get_deployment_tasks(cluster)
        self.graph = DeploymentGraph()
        self.graph.add_tasks(self.tasks)

    def group_nodes_by_roles(self, nodes):
        """Group nodes by roles

        :param nodes: list of node db object
        :param roles: list of roles names
        :returns: dict of {role_name: nodes_list} pairs
        """
        res = defaultdict(list)
        for node in nodes:
            res[node['role']].append(node)
        return res

    def get_nodes_with_roles(self, grouped_nodes, roles):
        """Returns nodes with provided roles.

        :param grouped_nodes: sorted nodes by role keys
        :param roles: list of roles
        :returns: list of nodes (dicts)
        """
        result = []
        for role in roles:
            if role in grouped_nodes:
                result.extend(grouped_nodes[role])
        return result

    def assign_parallel_nodes(self, priority, nodes):
        """It is possible that same node have 2 or more roles that can be
        deployed in parallel. We can not allow it. That is why priorities
        will be assigned in chunks

        :params priority: PriorityStrategy instance
        :params nodes: list of serialized nodes (dicts)
        """
        current_nodes = nodes
        while current_nodes:
            next_nodes = []
            group = []
            added_uids = []
            for node in current_nodes:
                if 'uid' not in node or 'role' not in node:
                    raise errors.InvalidSerializedNode(
                        'uid and role are mandatory fields. Node: {0}'.format(
                            node))
                if node['uid'] not in added_uids:
                    group.append(node)
                    added_uids.append(node['uid'])
                else:
                    next_nodes.append(node)
            priority.in_parallel(group)
            current_nodes = next_nodes

    def process_parallel_nodes(self, priority, parallel_groups, grouped_nodes):
        """Process both types of parallel deployment nodes

        :param priority: PriorityStrategy instance
        :param parallel_groups: list of dict objects
        :param grouped_nodes: dict with {role: nodes} mapping
        """
        parallel_nodes = []
        for group in parallel_groups:
            nodes = self.get_nodes_with_roles(grouped_nodes, group['role'])
            if 'amount' in group['parameters']['strategy']:
                priority.in_parallel_by(
                    nodes,
                    group['parameters']['strategy']['amount'])
            else:
                parallel_nodes.extend(nodes)
        if parallel_nodes:
            # check assign_parallel_nodes docstring for explanation
            self.assign_parallel_nodes(priority, parallel_nodes)

    def add_priorities(self, nodes):
        """Add priorities and tasks for all nodes

        :param nodes: list of node db object
        """
        priority = ps.PriorityStrategy()
        groups_subgraph = self.graph.get_groups_subgraph()
        current_groups = groups_subgraph.get_root_groups()

        # get list with names ['controller', 'compute', 'cinder']
        all_groups = groups_subgraph.nodes()
        grouped_nodes = self.group_nodes_by_roles(nodes)

        # if there is no nodes with some roles - mark them as success roles
        processed_groups = set(all_groups) - set(grouped_nodes.keys())

        while current_groups:
            one_by_one = []
            parallel = []

            for r in current_groups:
                group = self.graph.node[r]
                if (group['parameters']['strategy']['type']
                        == consts.DEPLOY_STRATEGY.one_by_one):
                    one_by_one.append(group)
                elif (group['parameters']['strategy']['type']
                      == consts.DEPLOY_STRATEGY.parallel):
                    parallel.append(group)

            for group in one_by_one:
                nodes = self.get_nodes_with_roles(grouped_nodes, group['role'])
                priority.one_by_one(nodes)

            self.process_parallel_nodes(priority, parallel, grouped_nodes)

            # fetch next part of groups
            processed_groups.update(current_groups)
            current_groups = groups_subgraph.get_next_groups(processed_groups)

    def serialize_tasks(self, node):
        """Serialize tasks with necessary for orchestrator attributes

        :param node: dict with serialized node
        """
        tasks = self.graph.get_tasks(node['role']).topology
        serialized = []
        priority = ps.Priority()
        for task in tasks:
            if task['type'] == consts.ORCHESTRATOR_TASK_TYPES.puppet:
                item = templates.make_puppet_task(
                    [node['uid']],
                    task)
            elif task['type'] == consts.ORCHESTRATOR_TASK_TYPES.shell:
                item = templates.make_shell_task(
                    [node['uid']],
                    task)
            item['priority'] = priority.next()
            serialized.append(item)
        return serialized
