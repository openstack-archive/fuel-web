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

from nailgun.orchestrator import graph_serializer
from nailgun.test import base


TASKS = """
- id: primary-controller
  type: role
  stage: deploy
  strategy:
    type: onebyone
- id: controller
  type: role
  stage: deploy
  requires: [primary-controller]
  strategy:
    type: parallel
    amount: 2
- id: cinder
  type: role
  stage: deploy
  requires: [controller]
  strategy:
    type: parallel
"""

SUBTASKS = """
- id: install_controller
  type: puppet
  stage: deploy
  requires: [setup_network]
  roles: [controller]
  parameters:
    puppet_manifests: /etc/puppet/manifests/controller.pp
    puppet_modules: /etc/puppet/modules
    timeout: 360
- id: setup_network
  type: shell
  stage: deploy
  roles: [controller]
  parameters:
    cmd: run_setup_network.sh
    timeout: 120
"""


class TestGraphDependencies(base.BaseTestCase):

    def setUp(self):
        super(TestGraphDependencies, self).setUp()
        self.tasks = yaml.load(TASKS)
        self.subtasks = yaml.load(SUBTASKS)

    def test_build_deployment_graph(self):
        graph = graph_serializer.initialize_graph(self.tasks)
        topology_by_id = [item['id'] for item in graph.topology]
        self.assertEqual(
            topology_by_id,
            ['primary-controller', 'controller', 'cinder'])

    def test_subtasks_in_correct_order(self):
        graph = graph_serializer.initialize_graph(self.tasks + self.subtasks)
        subtask_graph = graph.node['controller']['subtasks']
        topology_by_id = [item['id'] for item in subtask_graph.topology]
        self.assertEqual(
            topology_by_id,
            ['setup_network', 'install_controller'])


class TestAddDependenciesToNodes(base.BaseTestCase):

    def setUp(self):
        super(TestAddDependenciesToNodes, self).setUp()
        tasks = yaml.load(TASKS + SUBTASKS)
        self.graph = graph_serializer.initialize_graph(tasks)

    def test_priority_serilized_correctly_for_all_roles(self):
        nodes = [{'uid': '3', 'role': 'primary-controller'},
                 {'uid': '1', 'role': 'controller'},
                 {'uid': '2', 'role': 'controller'},
                 {'uid': '4', 'role': 'controller'},
                 {'uid': '6', 'role': 'controller'},
                 {'uid': '7', 'role': 'cinder'},
                 {'uid': '8', 'role': 'cinder'}]

        by_roles = defaultdict(list)
        for role, group in groupby(nodes, lambda node: node['role']):
            by_roles[role].extend(list(group))

        graph_serializer.add_dependencies(by_roles, self.graph)

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
             {'uid': '8', 'role': 'cinder', 'priority': 400}])
