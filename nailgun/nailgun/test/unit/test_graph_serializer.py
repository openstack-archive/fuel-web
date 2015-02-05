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
- id: pre_deployment
  type: stage
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
  type: puppet
  groups: [controller, primary-controller]
  required_for: [deploy]
  parameters:
    puppet_manifest: run_setup_network.pp
    puppet_modules: /etc/puppet
    timeout: 120

- id: setup_anything
  stage: pre_deployment
  type: shell
- id: setup_more_stuff
  stage: pre_deployment
  type: shell
  requires: [setup_anything]
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
            topology_by_id[:2], ['primary-controller', 'controller'])
        network_pos = topology_by_id.index('network')
        compute_pos = topology_by_id.index('compute')
        cinder_pos = topology_by_id.index('cinder')
        controller_pos = topology_by_id.index('controller')
        # we dont have constraint on certain order between cinder and network
        # therefore there should not be one
        self.assertGreater(compute_pos, network_pos)
        self.assertGreater(cinder_pos, controller_pos)

    def test_subtasks_in_correct_order(self):
        self.graph.add_tasks(self.tasks + self.subtasks)
        subtask_graph = self.graph.get_tasks('controller')
        topology_by_id = [item['id'] for item in subtask_graph.topology]
        self.assertItemsEqual(
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
        by_uid = defaultdict(list)
        for role, group in groupby(nodes, lambda node: node['uid']):
            by_uid[role].extend(list(group))
        self.assertItemsEqual(
            by_uid['3'],
            [{'uid': '3', 'role': 'primary-controller', 'priority': 100}])
        self.assertItemsEqual(
            by_uid['1'],
            [{'uid': '1', 'role': 'cinder', 'priority': 300},
             {'priority': 200, 'role': 'controller', 'uid': '1'}])
        self.assertItemsEqual(
            by_uid['2'],
            [{'uid': '2', 'role': 'controller', 'priority': 200}])
        # cinder and network roles are equal, so the only condition is that
        # one of the roles should be deployed first
        uid_4_priorities = [i['priority'] for i in by_uid['4']]
        self.assertItemsEqual(uid_4_priorities, [300, 400])


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


class TestTasksRemoval(base.BaseTestCase):

    def setUp(self):
        super(TestTasksRemoval, self).setUp()
        self.cluster = mock.Mock()
        self.cluster.deployment_tasks = yaml.load(TASKS + SUBTASKS)
        self.astute = deployment_graph.AstuteGraph(self.cluster)

    def test_only_tasks(self):
        self.astute.only_tasks(['setup_network'])
        tasks = self.astute.graph.get_tasks('controller')
        self.assertEqual(len(tasks), 1)
        self.assertItemsEqual(tasks.node.keys(), ['setup_network'])

    def test_full_graph_content(self):
        self.astute.only_tasks([])
        tasks = self.astute.graph.get_tasks('controller')
        self.assertEqual(len(tasks), 2)
        self.assertItemsEqual(
            tasks.node.keys(), ['setup_network', 'install_controller'])


COMPLEX_DEPENDENCIES = """
- id: pre_deployment
  type: stage
- id: deploy
  type: stage

- id: pre_a
  stage: pre_deployment
  type: shell
- id: pre_b
  stage: pre_deployment
  requires: [pre_a]
  type: shell
- id: pre_c
  stage: pre_deployment
  requires: [pre_a]
  type: shell
- id: pre_d
  stage: pre_deployment
  requires: [pre_b]
  type: shell

- id: group_a
  type: group
  stage: deploy
- id: group_b
  type: group
  stage: deploy
  requires: [group_a]
- id: group_c
  type: group
  stage: deploy

- id: task_a
  groups: [group_a, group_b]
  stage: deploy
  type: puppet
- id: task_b
  requires: [task_a]
  type: puppet
  stage: deploy
  groups: [group_a, group_c]
- id: task_c
  requires: [task_a]
  type: puppet
  stage: deploy
  groups: [group_a, group_b]
- id: task_d
  requires: [task_b, task_c]
  type: puppet
  groups: [group_b]
  stage: deploy
"""


class TestFindGraph(base.BaseTestCase):

    def setUp(self):
        super(TestFindGraph, self).setUp()
        self.tasks = yaml.load(COMPLEX_DEPENDENCIES)
        self.graph = deployment_graph.DeploymentGraph()
        self.graph.add_tasks(self.tasks)

    def test_end_at_pre_deployment(self):
        """Only pre_deployment tasks, groups and stages."""
        subgraph = self.graph.find_subgraph("pre_deployment")
        self.assertItemsEqual(
            subgraph.nodes(),
            ['pre_d', 'pre_c', 'pre_b', 'pre_a', 'deploy',
             'pre_deployment', 'group_b', 'group_a', 'group_c'])

    def test_end_at_task_in_pre_deployment(self):
        """Task pre_d doesnt requires pre_c, but requires pre_b."""
        subgraph = self.graph.find_subgraph("pre_d")
        self.assertItemsEqual(
            subgraph.nodes(),
            ['pre_d', 'pre_b', 'pre_a', 'deploy',
             'pre_deployment', 'group_b', 'group_a', 'group_c'])

    def test_end_at_deploy(self):
        """All tasks should be included because deploy is last node
        in this graph.
        """
        subgraph = self.graph.find_subgraph("deploy")
        self.assertItemsEqual(
            subgraph.nodes(),
            [t['id'] for t in self.tasks])

    def test_end_at_group(self):
        """In general end_at group should be used only when tasks that are
        specific for that group, and there is no deps between those groups

        In current graph only task_a and task_b will be present, because
        there is link between them
        """
        subgraph = self.graph.find_subgraph("group_c")
        self.assertItemsEqual(
            subgraph.nodes(),
            ['pre_d', 'pre_c', 'pre_b', 'pre_a', 'deploy', 'pre_deployment',
             'group_c', 'group_b', 'group_a', 'task_a', 'task_b'])

    def test_end_at_task_that_has_two_parents(self):
        """Both parents should be in the graph."""
        subgraph = self.graph.find_subgraph("task_d")
        self.assertItemsEqual(
            subgraph.nodes(),
            [t['id'] for t in self.tasks])

    def test_end_at_first_task(self):
        """Only that task will be present."""
        subgraph = self.graph.find_subgraph("task_a")
        self.assertItemsEqual(
            subgraph.nodes(),
            ['pre_d', 'pre_c', 'pre_b', 'pre_a', 'deploy',
             'pre_deployment', 'group_c', 'group_b', 'group_a', 'task_a'])
