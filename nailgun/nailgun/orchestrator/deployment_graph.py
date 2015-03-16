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

from tasks_validator import graph as d_graph

import networkx as nx

from nailgun import consts
from nailgun.errors import errors
from nailgun.logger import logger
from nailgun import objects
from nailgun.orchestrator import priority_serializers as ps
from nailgun.orchestrator.tasks_serializer import TaskSerializers


class AstuteGraph(object):
    """This object stores logic that required for working with astute
    orchestrator.
    """

    def __init__(self, cluster):
        self.cluster = cluster
        self.tasks = objects.Cluster.get_deployment_tasks(cluster)
        self.graph = d_graph.DeploymentGraph()
        self.graph.add_tasks(self.tasks)
        self.serializers = TaskSerializers()

    def only_tasks(self, task_ids):
        self.graph.only_tasks(task_ids)

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

        # get list with names ['controller', 'compute', 'cinder']
        all_groups = groups_subgraph.nodes()
        grouped_nodes = self.group_nodes_by_roles(nodes)

        # if there is no nodes with some roles - mark them as success roles
        processed_groups = set(all_groups) - set(grouped_nodes.keys())
        current_groups = groups_subgraph.get_next_groups(processed_groups)

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

    def stage_tasks_serialize(self, tasks, nodes):
        """Serialize tasks for certain stage

        :param stage: oneof consts.STAGES
        :param nodes: list of node db objects
        """
        serialized = []
        for task in tasks:

            if task['type'] in consts.INTERNAL_TASKS:
                continue

            serializer = self.serializers.get_stage_serializer(task)(
                task, self.cluster, nodes)

            if not serializer.should_execute():
                continue

            serialized.extend(serializer.serialize())
        return serialized

    def post_tasks_serialize(self, nodes):
        """Serialize tasks for post_deployment hook

        :param nodes: list of node db objects
        """
        # FIXME(dshulyak) remove this conditions
        # they are required to merge patches in library and nailgun
        # smoothly, there is small window when iso on library CI is outdated
        if 'deploy_end' in self.graph:
            subgraph = self.graph.find_subgraph(start='deploy_end')
        else:
            subgraph = self.graph.get_tasks(consts.STAGES.post_deployment)
        return self.stage_tasks_serialize(subgraph.topology, nodes)

    def pre_tasks_serialize(self, nodes):
        """Serialize tasks for pre_deployment hook

        :param nodes: list of node db objects
        """
        # FIXME(dshulyak) remove this conditions
        # they are required to merge patches in library and nailgun
        # smoothly, there is small window when iso on library CI is outdated
        if 'deploy_start' in self.graph:
            subgraph = self.graph.find_subgraph(end='deploy_start')
        else:
            subgraph = self.graph.get_tasks(consts.STAGES.pre_deployment)
        return self.stage_tasks_serialize(subgraph.topology, nodes)

    def deploy_task_serialize(self, node):
        """Serialize tasks with necessary for orchestrator attributes

        :param node: dict with serialized node
        """
        tasks = self.graph.get_tasks(node['role']).topology
        serialized = []
        priority = ps.PriorityStrategy()

        for task in tasks:
            serializer = self.serializers.get_deploy_serializer(task)(
                task, self.cluster, node)

            if not serializer.should_execute():
                continue
            serialized.extend(serializer.serialize())

        priority.one_by_one(serialized)
        return serialized
