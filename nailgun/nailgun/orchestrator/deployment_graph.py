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
from nailgun.orchestrator.tasks_serializer import TaskSerializers


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
    role: direct dependencies
    stage: direct dependency
    parameters: specific for each task type parameters
    """

    def add_tasks(self, tasks):
        for task in tasks:
            self.add_task(task)

    def add_task(self, task):
        self.add_node(task['id'], **task)
        for req in task.get('required_for', ()):
            self.add_edge(task['id'], req)
        for req in task.get('requires', ()):
            self.add_edge(req, task['id'])
        for req in task.get('role', ()):
            if not req == consts.ALL_ROLES:
                self.add_edge(task['id'], req)
        if 'stage' in task:
            self.add_edge(task['id'], task['stage'])

    def is_acyclic(self):
        """Verify that graph doesnot contain any cycles in it."""
        return nx.is_directed_acyclic_graph(self)

    def get_root_roles(self):
        """Return roles that doesnt have predecessors

        :returns: list of roles names
        """
        result = []
        for node in self.nodes():
            if not self.predecessors(node):
                result.append(node)
        return result

    def get_next_roles(self, processed_nodes):
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

    def get_roles_subgraph(self):
        roles = [t['id'] for t in self.node.values() if t['type'] == 'role']
        return self.subgraph(roles)

    def get_tasks(self, role_name):
        tasks = []
        for task in self.predecessors(role_name):
            if self.node[task]['type'] not in ('role', 'stage'):
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
        self.serializers = TaskSerializers.init_default()

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

    def process_parallel_nodes(self, priority, parallel_roles, grouped_nodes):
        """Process both types of parallel deployment nodes

        :param priority: PriorityStrategy instance
        :param parallel_roles: list of dict object
        :param grouped_nodes: dict with {role: nodes} mapping
        """
        parallel_nodes = []
        for role in parallel_roles:
            if 'amount' in role['parameters']['strategy']:
                priority.in_parallel_by(
                    grouped_nodes[role['id']],
                    role['parameters']['strategy']['amount'])
            else:
                parallel_nodes.extend(grouped_nodes[role['id']])
        if parallel_nodes:
            #check assign_parallel_nodes docstring for explanation
            self.assign_parallel_nodes(priority, parallel_nodes)

    def add_priorities(self, nodes):
        """Add priorities and tasks for all nodes

        :param nodes: list of node db object
        """
        priority = ps.PriorityStrategy()
        roles_subgraph = self.graph.get_roles_subgraph()
        current_roles = roles_subgraph.get_root_roles()
        # get list with names ['controller', 'compute', 'cinder']
        all_roles = roles_subgraph.nodes()
        grouped_nodes = self.group_nodes_by_roles(nodes)
        #if there is no nodes with some roles - mark them as success roles
        processed_roles = set(all_roles) - set(grouped_nodes.keys())

        while current_roles:
            one_by_one = []
            parallel = []

            for r in current_roles:
                role = self.graph.node[r]
                if (role['parameters']['strategy']['type']
                        == consts.DEPLOY_STRATEGY.one_by_one):
                    one_by_one.append(role)
                elif (role['parameters']['strategy']['type']
                      == consts.DEPLOY_STRATEGY.parallel):
                    parallel.append(role)

            for role in one_by_one:
                priority.one_by_one(grouped_nodes[role['id']])

            self.process_parallel_nodes(priority, parallel, grouped_nodes)

            processed_roles.update(current_roles)
            current_roles = roles_subgraph.get_next_roles(processed_roles)

    def stage_tasks_serialize(self, stage, nodes):
        tasks = self.graph.get_tasks(stage).topology
        serialized = []
        for task in tasks:
            serializer = self.serializers.get_stage_serializer(task)(
                task, self.cluster, nodes)
            if not serializer.should_execute():
                continue
            for task in serializer.serialize():
                serialized.append(task)
        return serialized

    def post_tasks_serialize(self, nodes):
        return self.stage_tasks_serialize(consts.STAGES.post_deployment, nodes)

    def pre_tasks_serialize(self, nodes):
        """Serialize tasks for pre_deployment hook

        :param nodes: list of node db objects
        """
        return self.stage_tasks_serialize(consts.STAGES.pre_deployment, nodes)

    def deploy_task_serialize(self, node):
        """Serialize tasks with necessary for orchestrator attributes

        :param graph: DeploymentGraph instance with loaded tasks
        :param node: dict with serialized node
        """
        tasks = self.graph.get_tasks(node['role']).topology
        serialized = []
        priority = ps.Priority()
        for task in tasks:
            serializer = self.serializers.get_deploy_serializer(task)(
                task, node)

            if not serializer.should_execute():
                continue
            for item in serializer.serialize():
                item['priority'] = priority.next()
                serialized.append(item)
        return serialized
