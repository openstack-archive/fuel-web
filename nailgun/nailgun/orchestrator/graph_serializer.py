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

import nailgun.orchestrator.priority_serializers as ps
import nailgun.orchestrator.tasks_templates as templates


#(dshulyak) temporary, this config will be moved to fuel-library
ROLES_CONFIG = """
- id: deploy
  type: stage
- id: primary-controller
  type: role
  required_for: [deploy]
  parameters:
    strategy:
      type: one_by_one
- id: controller
  type: role
  requires: [primary-controller]
  required_for: [deploy]
  parameters:
    strategy:
      type: parallel
      amount: 8
- id: cinder
  type: role
  stage: deploy
  requires: [controller]
  required_for: [deploy]
  parameters:
    strategy:
      type: parallel
- id: compute
  type: role
  requires: [controller]
  required_for: [deploy]
  parameters:
    strategy:
      type: parallel
- id: zabbix-server
  type: role
  required_for: [deploy]
  parameters:
    strategy:
      type: one_by_one
- id: mongo
  type: role
  requires: [zabbix-server]
  required_for: [deploy]
  parameters:
    strategy:
      type: parallel
- id: primary-mongo
  type: role
  requires: [mongo]
  required_for: [deploy, primary-controller]
  parameters:
    strategy:
      type: one_by_one
- id: ceph-osd
  type: role
  requires: [controller]
  required_for: [deploy]
  parameters:
    strategy:
      type: parallel
- id: deploy_legacy
  type: puppet
  required_for: [primary-controller, controller,
                 cinder, compute, ceph-osd,
                 zabbix-server, primary-mongo, mongo]
  parameters:
    puppet_manifest: /etc/puppet/manifests/site.pp
    puppet_modules: /etc/puppet/modules
    timeout: 360
"""


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
    graph.add_tasks(tasks)
    return graph


def add_dependencies(nodes, graph):
    """Add priorities and tasks for all nodes

    :param nodes: {'controller': [...], 'compute': [...]}
    :param graph: DeploymentGraph instance populated with tasks
    """
    priority = ps.PriorityStrategy()
    roles_subgraph = graph.roles_subgraph
    topo = graph.roles_subgraph.topology
    prev = None
    keep_current = False
    for role in topo:
        if role['id'] in nodes:
            task = roles_subgraph.node[role['id']]
            #If role has same predecessor as previous, we should not
            #increase priority
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


def get_tasks(node, graph):
    """Get serialized tasks with priorities and necessery for orchestrator
    format

    :param node: dict with serialized node
    :param graph: DeploymentGraph instance populated with tasks
    """
    tasks = graph.get_tasks_for_role(node['role']).topology
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


def serialize(nodes):
    """Adds tasks and priorities for nodes in list

    :param nodes: list of serialized nodes
    """
    graph = initialize_graph(yaml.load(ROLES_CONFIG))
    group_by_roles = defaultdict(list)
    for role, group in groupby(nodes, lambda node: node['role']):
        group_by_roles[role].extend(list(group))
    add_dependencies(group_by_roles, graph)
    for node in nodes:
        node['tasks'] = get_tasks(node, graph)
    return nodes


class GraphBasedPrioritySerializer(ps.PrioritySerializer):
    """This just a hack to use existing interface, something smarter is
    required.
    """

    def set_deployment_priorities(self, nodes):
        serialize(nodes)
