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

import mock
import yaml

from nailgun.orchestrator import deployment_graph
from nailgun.orchestrator import graph_configuration
from nailgun.test import base


TASKS = """
- id: deploy
  type: stage
- id: primary-controller
  type: group
  role: [primary-controller]
  required_for: [deploy]
  parameters:
    strategy:
      type: one_by_one
- id: controller
  type: group
  role: [controller]
  requires: [primary-controller]
  required_for: [deploy]
  parameters:
    strategy:
      type: parallel
      amount: 2
- id: cinder
  type: group
  role: [cinder]
  requires: [controller]
  required_for: [deploy]
  parameters:
    strategy:
      type: parallel
- id: compute
  type: group
  role: [compute]
  requires: [controller]
  required_for: [deploy]
  parameters:
    strategy:
        type: parallel
- id: network
  type: group
  role: [network]
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
  groups: [controller, primary-controller]
  required_for: [deploy]
  parameters:
    puppet_manifests: /etc/puppet/manifests/controller.pp
    puppet_modules: /etc/puppet/modules
    timeout: 360
- id: setup_network
  type: shell
  groups: [controller, primary-controller]
  required_for: [deploy]
  parameters:
    cmd: run_setup_network.sh
    timeout: 120
"""


class TestGraphDependencies(base.BaseTestCase):

    def setUp(self):
        super(TestGraphDependencies, self).setUp()
        self.tasks = yaml.load(TASKS)
        self.subtasks = yaml.load(SUBTASKS)
        self.graph = deployment_graph.DeploymentGraph()

    def test_build_deployment_graph(self):
        self.graph.add_tasks(self.tasks)
        roles = self.graph.get_groups_subgraph()
        topology_by_id = [item['id'] for item in roles.topology]
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


class TestAddDependenciesToNodes(base.BaseTestCase):

    def setUp(self):
        super(TestAddDependenciesToNodes, self).setUp()
        self.cluster = mock.Mock()
        self.cluster.deployment_tasks = yaml.load(TASKS + SUBTASKS)
        self.graph = deployment_graph.AstuteGraph(self.cluster)

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

        self.graph.add_priorities(nodes)
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

    def test_serialize_priority_for_same_node_diff_roles(self):
        nodes = [{'uid': '3', 'role': 'primary-controller'},
                 {'uid': '1', 'role': 'controller'},
                 {'uid': '2', 'role': 'controller'},
                 {'uid': '1', 'role': 'cinder'},
                 {'uid': '4', 'role': 'cinder'},
                 {'uid': '4', 'role': 'network'}]
        self.graph.add_priorities(nodes)
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
            [{'uid': '1', 'role': 'cinder', 'priority': 300},
             {'uid': '4', 'role': 'cinder', 'priority': 300}])
        self.assertEqual(
            by_priority[400],
            [{'uid': '4', 'role': 'network', 'priority': 400}])


class TestLegacyGraphSerialized(base.BaseTestCase):

    def setUp(self):
        super(TestLegacyGraphSerialized, self).setUp()
        self.cluster = mock.Mock()
        self.cluster.deployment_tasks = yaml.load(
            graph_configuration.DEPLOYMENT_CURRENT)
        self.graph = deployment_graph.AstuteGraph(self.cluster)

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
        self.graph.add_priorities(nodes)
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
