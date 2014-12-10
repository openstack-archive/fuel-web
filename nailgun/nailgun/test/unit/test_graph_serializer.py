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

import yaml

from nailgun.orchestrator import deployment_graph
from nailgun.orchestrator import graph_configuration
from nailgun.test import base


TASKS = """
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
      amount: 2
- id: cinder
  type: role
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
- id: network
  type: role
  requires: [controller]
  required_for: [compute, deploy]
  parameters:
    strategy:
        type: parallel
"""

SUBTASKS = """
- id: install_controller
  type: puppet
  requires: [setup_network]
  role: [controller, primary-controller]
  required_for: [deploy]
  parameters:
    puppet_manifests: /etc/puppet/manifests/controller.pp
    puppet_modules: /etc/puppet/modules
    timeout: 360
- id: setup_network
  type: shell
  role: [controller, primary-controller]
  required_for: [deploy]
  parameters:
    cmd: run_setup_network.sh
    timeout: 120
"""

ADDITIONAL_TASKS = """
- id: setup_network
  type: puppet
  role: [controller, primary-controller, cinder, compute, network]
- id: setup_cinder
  type: puppet
  requires: [setup_network]
  role: [cinder]
- id: setup_compute
  type: puppet
  requires: [setup_network]
  role: [compute]
- id: setup_controller
  type: puppet
  role: [primary-controller, controller]
  requires: [setup_network]
- id: setup_neutron
  type: puppet
  requires: [setup_network]
  role: [network]
- id: setup_bash
  type: shell
  required_for: [setup_cinder]
  requires: [setup_network]
  role: [cinder]
"""


class TestGraphDependencies(base.BaseTestCase):

    def setUp(self):
        super(TestGraphDependencies, self).setUp()
        self.tasks = yaml.load(TASKS)
        self.subtasks = yaml.load(SUBTASKS)
        self.additional = yaml.load(ADDITIONAL_TASKS)
        self.graph = deployment_graph.DeploymentGraph()

    def test_build_deployment_graph(self):
        self.graph.add_tasks(self.tasks)
        topology_by_id = [item['id'] for item
                          in self.graph.roles_subgraph.topology]
        self.assertEqual(
            topology_by_id,
            ['primary-controller', 'controller',
             'network', 'compute', 'cinder'])

    def test_subtasks_in_correct_order(self):
        self.graph.add_tasks(self.tasks + self.subtasks)
        subtask_graph = self.graph.get_tasks('controller')
        topology_by_id = [item['id'] for item in subtask_graph.topology]
        self.assertEqual(
            topology_by_id,
            ['setup_network', 'install_controller'])

    def test_subtasks_correct_priority(self):
        self.graph.add_tasks(self.tasks + self.additional)
        self.graph.prioritize_tasks(self.graph.roles_subgraph)


class TestAddDependenciesToNodes(base.BaseTestCase):

    def setUp(self):
        super(TestAddDependenciesToNodes, self).setUp()
        tasks = yaml.load(TASKS + SUBTASKS)
        self.graph = deployment_graph.DeploymentGraph()
        self.graph.add_tasks(tasks)

    def test_priority_serilized_correctly_for_all_roles(self):
        nodes = [{'uid': '3', 'role': 'primary-controller'},
                 {'uid': '1', 'role': 'controller'},
                 {'uid': '2', 'role': 'controller'},
                 {'uid': '4', 'role': 'controller'},
                 {'uid': '6', 'role': 'controller'},
                 {'uid': '7', 'role': 'cinder'},
                 {'uid': '8', 'role': 'cinder'},
                 {'uid': '9', 'role': 'network'},
                 {'uid': '10', 'role': 'compute'}]

        by_roles = defaultdict(list)
        for role, group in groupby(nodes, lambda node: node['role']):
            by_roles[role].extend(list(group))

        self.graph.add_priorities(by_roles)
        by_priority = defaultdict(list)
        for role, group in groupby(nodes, lambda node: node['priority']):
            by_priority[role].extend(list(group))
        self.assertEqual(
            by_priority[100],
            [{'uid': '3', 'role': 'primary-controller', 'priority': 100}])
        self.assertEqual(
            by_priority[200],
            [{'uid': '1', 'role': 'controller', 'priority': 200},
             {'uid': '2', 'role': 'controller', 'priority': 200}])
        self.assertEqual(
            by_priority[300],
            [{'uid': '4', 'role': 'controller', 'priority': 300},
             {'uid': '6', 'role': 'controller', 'priority': 300}])
        self.assertEqual(
            by_priority[400],
            [{'uid': '7', 'role': 'cinder', 'priority': 400},
             {'uid': '8', 'role': 'cinder', 'priority': 400},
             {'uid': '9', 'role': 'network', 'priority': 400}])
        self.assertEqual(
            by_priority[500],
            [{'uid': '10', 'role': 'compute', 'priority': 500}])


class TestLegacyGraphSerialized(base.BaseTestCase):

    def setUp(self):
        super(TestLegacyGraphSerialized, self).setUp()
        self.graph = deployment_graph.DeploymentGraph()
        self.tasks = yaml.load(graph_configuration.DEPLOYMENT_CURRENT)
        self.graph.add_tasks(self.tasks)

    def test_serialized_with_tasks_and_priorities(self):
        """Test verifies that priorities and tasks."""
        nodes = [{'uid': '3', 'role': 'primary-controller'},
                 {'uid': '1', 'role': 'controller'},
                 {'uid': '2', 'role': 'controller'},
                 {'uid': '7', 'role': 'cinder'},
                 {'uid': '8', 'role': 'compute'},
                 {'uid': '9', 'role': 'mongo'},
                 {'uid': '10', 'role': 'primary-mongo'},
                 {'uid': '11', 'role': 'ceph-osd'},
                 {'uid': '12', 'role': 'zabbix-server'}]
        group_by_roles = defaultdict(list)
        for role, group in groupby(nodes, lambda node: node['role']):
            group_by_roles[role].extend(list(group))
        self.graph.add_priorities(group_by_roles)
        by_priority = defaultdict(list)
        for role, group in groupby(nodes, lambda node: node['priority']):
            by_priority[role].extend(list(group))
        self.assertEqual(by_priority[100][0]['role'], 'zabbix-server')
        self.assertEqual(by_priority[200][0]['role'], 'mongo')
        self.assertEqual(by_priority[300][0]['role'], 'primary-mongo')
        self.assertEqual(by_priority[400][0]['role'], 'primary-controller')
        self.assertEqual(by_priority[500][0]['role'], 'controller')
        self.assertEqual(by_priority[500][1]['role'], 'controller')
        self.assertEqual(
            set([i['role'] for i in by_priority[600]]),
            set(['compute', 'cinder', 'ceph-osd']))
