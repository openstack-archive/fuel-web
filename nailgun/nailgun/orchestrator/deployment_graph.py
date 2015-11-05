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
try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict

import networkx as nx
import six

from nailgun import consts
from nailgun.errors import errors
from nailgun.logger import logger
from nailgun import objects
from nailgun.orchestrator import priority_serializers as ps
from nailgun.orchestrator.tasks_serializer import TaskSerializers
from nailgun.policy.name_match import NameMatchPolicy


class DeploymentGraph(nx.DiGraph):
    """DirectedGraph used to generate configs for speficific orchestrators

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

    node_dict_factory = OrderedDict
    adjlist_dict_factory = OrderedDict

    def __init__(self, tasks=None, *args, **kwargs):
        super(DeploymentGraph, self).__init__(*args, **kwargs)
        # (dshulyak) we need to monkey patch created dicts, 1.9.1
        # doesnt support chaning those data structures by fabric
        self.node = self.node_dict_factory()
        self.adj = self.adjlist_dict_factory()
        self.pred = self.adjlist_dict_factory()
        self.succ = self.adj  # successor

        if tasks is not None:
            self.add_tasks(tasks)

    def add_node(self, n, **attr):
        if n not in self.succ:
            self.succ[n] = self.adjlist_dict_factory()
            self.pred[n] = self.adjlist_dict_factory()
            self.node[n] = attr
        super(DeploymentGraph, self).add_node(n, **attr)

    def add_edge(self, u, v, **attr):
        if u not in self.succ:
            self.succ[u] = self.adjlist_dict_factory()
            self.pred[u] = self.adjlist_dict_factory()
            self.node[u] = self.node_dict_factory()
        if v not in self.succ:
            self.succ[v] = self.adjlist_dict_factory()
            self.pred[v] = self.adjlist_dict_factory()
            self.node[v] = self.node_dict_factory()
        super(DeploymentGraph, self).add_edge(u, v, **attr)

    def add_tasks(self, tasks):
        for task in tasks:
            self.add_task(task)

        self._update_dependencies()

    def add_task(self, task):
        self.add_node(task['id'], **task)

        # standart direct and backward dependencies, should be used for
        # declaring dependencies on one level (group to group, task to task)
        for req in task.get('required_for', ()):
            self.add_edge(task['id'], req)
        for req in task.get('requires', ()):
            self.add_edge(req, task['id'])

        # FIXME(dshulyak) remove it after change in library will be merged
        if 'stage' in task:
            self.add_edge(task['id'], task['stage'])

    def _update_dependencies(self):
        """Create dependencies that rely on regexp matching."""

        for task in six.itervalues(self.node):
            # tasks and groups should be used for declaring dependencies
            # between tasks and roles (which are simply group of tasks)
            available_groups = self.get_groups_subgraph().nodes()
            for group in task.get('groups', ()):
                pattern = NameMatchPolicy.create(group)
                not_matched = []
                for available_group in available_groups:
                    if pattern.match(available_group):
                        self.add_edge(task['id'], available_group)
                    else:
                        not_matched.append(available_group)
                # Add dependency for non-existing group which will be
                # resolved in DeploymentGraphValidator
                if len(available_groups) == len(not_matched):
                    self.add_edge(task['id'], group)
                    logger.warning(
                        'Group "%s" is an invalid dependency', group)

                available_groups = not_matched

            for req in task.get('tasks', ()):
                self.add_edge(req, task['id'])

    def is_acyclic(self):
        """Verify that graph doesnot contain any cycles in it."""
        return nx.is_directed_acyclic_graph(self)

    def get_next_groups(self, processed_nodes):
        """Get nodes that have predecessors in processed_nodes list.

        All predecessors should be taken into account, not only direct
        parents

        :param processed_nodes: set of nodes names
        :returns: list of nodes names
        """
        result = []
        for node in self.nodes():
            if node in processed_nodes:
                continue

            predecessors = nx.dfs_predecessors(self.reverse(), node)
            if (set(predecessors.keys()) <= processed_nodes):
                result.append(node)

        return result

    def get_groups_subgraph(self):
        """Return subgraph containing all the groups of tasks."""
        roles = [t['id'] for t in six.itervalues(self.node)
                 if t.get('type') == consts.ORCHESTRATOR_TASK_TYPES.group]
        return self.subgraph(roles)

    def get_group_tasks(self, group_name):
        rst = []
        predecessors = self.predecessors(group_name)
        for task in nx.topological_sort(self):

            if task not in predecessors:
                continue
            elif self.should_exclude_task(task):
                continue

            rst.append(self.node[task])
        return rst

    def should_exclude_task(self, task):
        """Stores all conditions when task should be excluded from execution.

        :param task: task name
        """
        if self.node[task]['type'] in consts.INTERNAL_TASKS:
            logger.debug(
                'Excluding task %s that is used'
                ' for internal reasons.', task)
            return True
        elif self.node[task].get('skipped'):
            logger.debug(
                'Task %s will be skipped for %s', task)
            return True
        return False

    @property
    def topology(self):
        return map(lambda t: self.node[t], nx.topological_sort(self))

    def make_skipped_task(self, task):
        """Make some task in graph skipped

        We can not just remove node because it also stores edges, that connects
        graph in correct order

        :param task: dict with task data
        """
        if task['type'] in consts.INTERNAL_TASKS:
            logger.debug(
                'Task of type group/stage cannot be skipped.\n'
                'Task: %s', task)
            return

        task['skipped'] = True

    def only_tasks(self, task_ids):
        """Leave only tasks that are specified in request.

        :param task_ids: list of task ids
        """
        if not task_ids:
            return

        for task in self.node.values():
            if task['id'] not in task_ids:
                self.make_skipped_task(task)
            else:
                task['skipped'] = False

    def reexecutable_tasks(self, task_filter):
        """Keep only reexecutable tasks which match the filter.

        Filter is the list of values. If task has reexecute_on key and its
        value matches the value from filter then task is not skipped.
        :param task_filter: filter (list)
        """
        if not task_filter:
            return

        task_filter = set(task_filter)
        for task in six.itervalues(self.node):
            reexecute_on = task.get('reexecute_on')
            if reexecute_on is not None and task_filter.issubset(reexecute_on):
                task['skipped'] = False
            else:
                self.make_skipped_task(task)

    def find_subgraph(self, start=None, end=None):
        """Find subgraph by provided start and end endpoints

        :param end: task name
        :param start: task name
        :param include: iterable with task names
        :returns: DeploymentGraph instance (subgraph from original)
        """
        working_graph = self

        if start:
            # simply traverse starting from root,
            # A->B, B->C, B->D, C->E
            working_graph = self.subgraph(
                nx.dfs_postorder_nodes(working_graph, start))

        if end:
            # nx.dfs_postorder_nodes traverses graph from specified point
            # to the end by following successors, here is example:
            # A->B, C->D, B->D , and we want to traverse up to the D
            # for this we need to reverse graph and make it
            # B->A, D->C, D->B and use dfs_postorder
            working_graph = self.subgraph(nx.dfs_postorder_nodes(
                working_graph.reverse(), end))

        return working_graph

    def filter_subgraph(self, start=None, end=None, include=()):
        """Exclude tasks that is not meant to be executed

        :param include: container with task names
        """
        wgraph = self.find_subgraph(start=start, end=end)
        for task in wgraph:
            if self.should_exclude_task(task) and task not in include:
                wgraph.remove_node(task)
        return wgraph


class AstuteGraph(object):
    """This object stores logic that required for working with astute"""

    def __init__(self, cluster):
        self.cluster = cluster
        self.tasks = objects.Cluster.get_deployment_tasks(cluster)
        self.graph = DeploymentGraph()
        self.graph.add_tasks(self.tasks)
        self.serializers = TaskSerializers()

    def only_tasks(self, task_ids):
        self.graph.only_tasks(task_ids)

    def reexecutable_tasks(self, task_filter):
        self.graph.reexecutable_tasks(task_filter)

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
        """Assign parallel nodes

        It is possible that same node have 2 or more roles that can be
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

            if self.graph.should_exclude_task(task['id']):
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
        if 'deploy_end' in self.graph:
            subgraph = self.graph.find_subgraph(start='deploy_end')
        else:
            errors.NotEnoughInformation(
                '*deploy_end* stage must be provided')
        return self.stage_tasks_serialize(subgraph.topology, nodes)

    def pre_tasks_serialize(self, nodes):
        """Serialize tasks for pre_deployment hook

        :param nodes: list of node db objects
        """
        if 'deploy_start' in self.graph:
            subgraph = self.graph.find_subgraph(end='deploy_start')
        else:
            raise errors.NotEnoughInformation(
                '*deploy_start* stage must be provided')
        return self.stage_tasks_serialize(subgraph.topology, nodes)

    def deploy_task_serialize(self, node):
        """Serialize tasks with necessary for orchestrator attributes

        :param node: dict with serialized node
        """

        serialized = []
        priority = ps.PriorityStrategy()

        for task in self.graph.get_group_tasks(node['role']):

            serializer = self.serializers.get_deploy_serializer(task)(
                task, self.cluster, node)

            if not serializer.should_execute():
                continue
            serialized.extend(serializer.serialize())

        priority.one_by_one(serialized)
        return serialized


class DeploymentGraphValidator(object):

    def __init__(self, tasks):
        self.graph = DeploymentGraph()
        self.graph.add_tasks(tasks)

    def check(self):
        if not self.graph.is_acyclic():
            raise errors.InvalidData(
                "Tasks can not be processed because it contains cycles in it.")

        non_existing_tasks = []
        invalid_tasks = []

        for node_key, node_value in six.iteritems(self.graph.node):
            if not node_value.get('id'):
                successors = self.graph.successors(node_key)
                predecessors = self.graph.predecessors(node_key)

                neighbors = successors + predecessors

                non_existing_tasks.append(node_key)
                invalid_tasks.extend(neighbors)

        if non_existing_tasks:
            raise errors.InvalidData(
                "Tasks '{non_existing_tasks}' can't be in requires"
                "|required_for|groups|tasks for [{invalid_tasks}]"
                " because they don't exist in the graph".format(
                    non_existing_tasks=', '.join(
                        str(x) for x in sorted(non_existing_tasks)),
                    invalid_tasks=', '.join(
                        str(x) for x in sorted(set(invalid_tasks)))))
