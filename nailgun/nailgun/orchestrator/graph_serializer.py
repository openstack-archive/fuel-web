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
from itertools import groupby

import networkx as nx
import yaml

from nailgun.orchestrator.priority_serializers import Priority
from nailgun.orchestrator.priority_serializers import PriorityStrategy
import nailgun.orchestrator.tasks_templates as templates


#(dshulyak) temporary, this config will be moved to fuel-library
ROLES_CONFIG = """
- id: primary-controller
  type: role
  stage: deploy
  requires: [mongo, zabbix-server]
  strategy:
    type: onebyone
- id: controller
  type: role
  stage: deploy
  requires: [primary-controller]
  strategy:
    type: parallel
    amount: 8
- id: cinder
  type: role
  stage: deploy
  requires: [controller]
  strategy:
    type: parallel
- id: compute
  type: role
  stage: deploy
  requires: [controller]
  strategy:
    type: parallel
- id: zabbix-server
  type: role
  role: zabbix-server
  stage: deploy
  strategy:
    type: onebyone
- id: mongo
  type: role
  role: mongo
  stage: deploy
  requires: [zabbix-server]
  strategy:
    type: onebyone
- id: ceph-osd
  type: role
  role: ceph-osd
  stage: deploy
  requires: [controller]
  strategy:
    type: parallel
"""

TASKS_CONFIG = """
- type: puppet
  stage: deploy
  roles: '*'
  parameters:
    puppet_manifests: /etc/puppet/manifests/site.pp
    puppet_modules: /etc/puppet/modules
    timeout: 360
"""


class DeploymentGraph(nx.DiGraph):

    def add_task(self, task):
        self.add_node(task['id'], subtasks=DeploymentGraph(), **task)
        if 'before' in task:
            self.add_edge(task['id'], task['before'])
        if 'requires' in task:
            for req in task['requires']:
                self.add_edge(req, task['id'])

    def add_subtask(self, main, task):
        self.node[main]['subtasks'].add_task(task)

    @property
    def topology(self):
        topo = []
        for task in nx.topological_sort(self):
            topo.append(self.node[task])
        return topo


def initialize_graph(tasks):
    """Initializez graph with dependences between roles and tasks.
    Provided in CONFIG,

    :param tasks: list of tasks in predefined format
    :returns: DeploymentGraph instance
    """
    graph = DeploymentGraph()
    roles = [task for task in tasks if task['type'] == 'role']
    other = [task for task in tasks if task['type'] != 'role']
    for role in roles:
        graph.add_task(role)
    for task in other:
        if task['roles'] == '*':
            for role in graph.node:
                graph.add_subtask(role, task)
        else:
            for role in task['roles']:
                if role in graph.node:
                    graph.add_subtask(role, task)
    return graph


def add_dependencies(nodes, graph):
    """Add priorities and tasks for all nodes

    :param nodes: {'controller': [...], 'compute': [...]}
    :param graph: DeploymentGraph instance populated with tasks
    """
    priority = PriorityStrategy()
    topo = graph.topology
    prev = None
    keep_current = False
    for role in topo:
        if role['id'] in nodes:
            task = graph.node[role['id']]
            #If role has same predecessor as previous, we should not
            #increase priority
            if prev and (
                graph.predecessors(prev['id'])
                    == graph.predecessors(role['id'])):
                keep_current = True
            else:
                keep_current = False
            if task['strategy']['type'] == 'parallel':
                if 'amount' in task['strategy']:
                    priority.in_parallel_by(
                        nodes[role['id']], task['strategy']['amount'])
                else:
                    priority.in_parallel(
                        nodes[role['id']], keep=keep_current)
            else:
                # if strategy not specified prioritize tasks one by one
                priority.one_by_one(nodes[role['id']])
            prev = role


def get_tasks(node, graph):
    """Get serialized tasks with priorities and necessery for orchestrator
    format

    :param node: dict with serialized node
    :param graph: DeploymentGraph instance populated with tasks
    """
    tasks = graph.node['subtasks'].topology
    serialized = []
    priority = Priority()
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


def serialize(nodes):
    """Adds tasks and priorities for nodes in list

    :param nodes: list of serialized nodes
    """
    graph = initialize_graph(yaml.load(ROLES_CONFIG))
    group_by_roles = defaultdict(list)
    for role, group in groupby(nodes, lambda node: node['role']):
        group_by_roles.extend(list(group))
    add_dependencies(group_by_roles, graph)
    for node in nodes:
        node['tasks'] = get_tasks(node, graph)
    return nodes
