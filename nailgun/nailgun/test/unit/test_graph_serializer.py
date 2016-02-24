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
import copy
from itertools import groupby

import mock
import yaml

from nailgun import objects
from nailgun.db.sqlalchemy import models
from nailgun.errors import errors
from nailgun.orchestrator import deployment_graph
from nailgun.orchestrator import graph_configuration
from nailgun.test import base


TASKS = """

- id: pre_deployment_start
  type: stage

- id: pre_deployment
  type: stage
  requires: [pre_deployment_start]

- id: deploy_start
  type: stage
  requires: [pre_deployment]

- id: deploy_end
  type: stage
  requires: [deploy_start]

- id: primary-controller
  type: group
  role: [primary-controller]
  required_for: [deploy_end]
  requires: [deploy_start]
  parameters:
    strategy:
      type: one_by_one
- id: controller
  type: group
  role: [controller]
  requires: [primary-controller]
  required_for: [deploy_end]
  parameters:
    strategy:
      type: parallel
      amount: 2
- id: cinder
  type: group
  role: [cinder]
  requires: [controller]
  required_for: [deploy_end]
  parameters:
    strategy:
      type: parallel
- id: compute
  type: group
  role: [compute]
  requires: [controller]
  required_for: [deploy_end]
  parameters:
    strategy:
        type: parallel
- id: network
  type: group
  role: [network]
  requires: [controller]
  required_for: [compute, deploy_end]
  parameters:
    strategy:
        type: parallel
"""

SUBTASKS = """
- id: install_controller
  type: puppet
  requires: [setup_network]
  groups: [controller, primary-controller]
  required_for: [deploy_end]
  parameters:
    puppet_manifests: /etc/puppet/manifests/controller.pp
    puppet_modules: /etc/puppet/modules
    timeout: 360
- id: setup_network
  type: puppet
  groups: [controller, primary-controller]
  required_for: [deploy_end]
  requires: [deploy_start]
  parameters:
    puppet_manifest: run_setup_network.pp
    puppet_modules: /etc/puppet
    timeout: 120
- id: setup_anything
  requires: [pre_deployment_start]
  required_for: [pre_deployment]
  type: shell
- id: setup_more_stuff
  type: shell
  requires_for: [pre_deployment]
  requires: [setup_anything]
"""

SUBTASKS_WITH_REGEXP = """
- id: setup_something
  type: puppet
  groups: ['/cinder|compute/', '/(?=controller)(?=^((?!^primary).)*$)/']
  required_for: [deploy_end]
  requires: [deploy_start]
  parameters:
    puppet_manifest: run_setup_something.pp
    puppet_modules: /etc/puppet
    timeout: 120
"""


class TestGraphDependencies(base.BaseTestCase):

    def setUp(self):
        super(TestGraphDependencies, self).setUp()
        self.tasks = yaml.load(TASKS)
        self.subtasks = yaml.load(SUBTASKS)
        self.subtasks_with_regexp = yaml.load(SUBTASKS_WITH_REGEXP)
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
        subtasks = self.graph.get_group_tasks('controller')
        topology_by_id = [item['id'] for item in subtasks]
        self.assertItemsEqual(
            topology_by_id,
            ['setup_network', 'install_controller'])


class TestUpdateGraphDependencies(base.BaseTestCase):

    def setUp(self):
        super(TestUpdateGraphDependencies, self).setUp()
        self.tasks = yaml.load(TASKS)
        self.subtasks = yaml.load(SUBTASKS_WITH_REGEXP)

    def test_groups_regexp_resolution(self):
        graph = deployment_graph.DeploymentGraph()
        graph.add_tasks(self.tasks + self.subtasks)
        self.assertItemsEqual(
            graph.succ['setup_something'],
            {'deploy_end': {}, 'cinder': {}, 'compute': {}, 'controller': {}})

    def test_support_for_all_groups(self):
        graph = deployment_graph.DeploymentGraph()
        subtasks = copy.deepcopy(self.subtasks)
        subtasks[0]['groups'] = ['/.*/']
        graph.add_tasks(self.tasks + subtasks)
        self.assertItemsEqual(
            graph.succ['setup_something'],
            {'deploy_end': {}, 'primary-controller': {}, 'network': {},
             'cinder': {}, 'compute': {}, 'controller': {}})

    def test_simple_string_in_group(self):
        graph = deployment_graph.DeploymentGraph()
        subtasks = copy.deepcopy(self.subtasks)
        subtasks[0]['groups'] = ['controller']
        graph.add_tasks(self.tasks + subtasks)
        self.assertItemsEqual(
            graph.succ['setup_something'],
            {'deploy_end': {}, 'controller': {}})


class TestAddDependenciesToNodes(base.BaseTestCase):

    def setUp(self):
        super(TestAddDependenciesToNodes, self).setUp()
        with mock.patch('nailgun.objects.Cluster') as cluster_m:
            cluster_m.get_deployment_tasks.return_value = yaml.load(
                TASKS + SUBTASKS)
            self.cluster = mock.Mock()
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
        with mock.patch('nailgun.objects.Cluster') as cluster_m:
            cluster_m.get_deployment_tasks.return_value = yaml.load(
                graph_configuration.DEPLOYMENT_51_60)
            self.cluster = mock.Mock()
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
        with mock.patch('nailgun.objects.Cluster') as cluster_m:
            cluster_m.get_deployment_tasks.return_value = yaml.load(
                TASKS + SUBTASKS)
            self.cluster = mock.Mock()
            self.astute = deployment_graph.AstuteGraph(self.cluster)

    def test_only_tasks(self):
        self.astute.only_tasks(['setup_network'])
        tasks = self.astute.graph.get_group_tasks('controller')
        self.assertEqual(len(tasks), 1)
        self.assertItemsEqual(tasks[0]['id'], 'setup_network')

    def test_full_graph_content(self):
        self.astute.only_tasks([])
        tasks = self.astute.graph.get_group_tasks('controller')
        self.assertEqual(len(tasks), 2)
        self.assertItemsEqual(
            [t['id'] for t in tasks], ['setup_network', 'install_controller'])


class GroupsTraversalTest(base.BaseTestCase):

    GROUPS = ""

    def setUp(self):
        super(GroupsTraversalTest, self).setUp()
        with mock.patch('nailgun.objects.Cluster') as cluster_m:
            cluster_m.get_deployment_tasks.return_value = yaml.load(
                self.GROUPS)
            self.cluster = mock.Mock()
            self.astute = deployment_graph.AstuteGraph(self.cluster)
            self.nodes = []

    def get_node_by_role(self, role):
        return next(n for n in self.nodes if n['role'] == role)


class TestParallelGroupsTraversal(GroupsTraversalTest):

    GROUPS = """
    - id: a
      type: group
      role: [a]
      parameters:
          strategy:
             type: parallel
    - id: b
      type: group
      requires: [a]
      role: [b]
      parameters:
          strategy:
             type: parallel
    - id: c
      type: group
      requires: [b]
      role: [c]
      parameters:
          strategy:
             type: parallel
    - id: d
      type: group
      requires: [c]
      role: [d]
      parameters:
          strategy:
             type: parallel
    """

    def test_with_all_nodes_present(self):
        self.nodes = [{'uid': '3', 'role': 'a'},
                      {'uid': '1', 'role': 'b'},
                      {'uid': '2', 'role': 'c'},
                      {'uid': '4', 'role': 'd'}]

        self.astute.add_priorities(self.nodes)
        self.assertEqual(self.get_node_by_role('a')['priority'], 100)
        self.assertEqual(self.get_node_by_role('b')['priority'], 200)
        self.assertEqual(self.get_node_by_role('c')['priority'], 300)
        self.assertEqual(self.get_node_by_role('d')['priority'], 400)

    def test_middle_role_is_not_present(self):
        self.nodes = [{'uid': '3', 'role': 'a'},
                      {'uid': '1', 'role': 'b'},
                      {'uid': '2', 'role': 'd'}]
        self.astute.add_priorities(self.nodes)
        self.assertEqual(self.get_node_by_role('a')['priority'], 100)
        self.assertEqual(self.get_node_by_role('b')['priority'], 200)
        self.assertEqual(self.get_node_by_role('d')['priority'], 300)

    def test_two_middle_roles_is_not_present(self):
        self.nodes = [{'uid': '3', 'role': 'a'},
                      {'uid': '2', 'role': 'd'}]
        self.astute.add_priorities(self.nodes)
        self.assertEqual(self.get_node_by_role('a')['priority'], 100)
        self.assertEqual(self.get_node_by_role('d')['priority'], 200)


class TestMixedGroupsTraversal(GroupsTraversalTest):

    GROUPS = """
    - id: a
      type: group
      role: [a]
      parameters:
          strategy:
             type: one_by_one
    - id: b
      type: group
      role: [b]
      parameters:
          strategy:
             type: parallel
    - id: c
      type: group
      requires: [a]
      role: [c]
      parameters:
          strategy:
             type: parallel
    - id: d
      type: group
      requires: [c]
      role: [d]
      parameters:
          strategy:
             type: parallel
    - id: e
      type: group
      requires: [d, c]
      role: [e]
      parameters:
          strategy:
             type: one_by_one
    """

    def test_one_by_one_will_be_earlier(self):
        self.nodes = [{'uid': '3', 'role': 'a'},
                      {'uid': '1', 'role': 'b'}]
        self.astute.add_priorities(self.nodes)
        self.assertEqual(self.get_node_by_role('a')['priority'], 100)
        self.assertEqual(self.get_node_by_role('b')['priority'], 200)

    def test_couple_missed_without_last(self):
        self.nodes = [{'uid': '3', 'role': 'a'},
                      {'uid': '1', 'role': 'c'},
                      {'uid': '4', 'role': 'd'}]
        self.astute.add_priorities(self.nodes)
        self.assertEqual(self.get_node_by_role('a')['priority'], 100)
        self.assertEqual(self.get_node_by_role('c')['priority'], 200)
        self.assertEqual(self.get_node_by_role('d')['priority'], 300)

    def test_only_one_by_one(self):
        self.nodes = [{'uid': '3', 'role': 'a'},
                      {'uid': '1', 'role': 'e'}]
        self.astute.add_priorities(self.nodes)
        self.assertEqual(self.get_node_by_role('a')['priority'], 100)
        self.assertEqual(self.get_node_by_role('e')['priority'], 200)


COMPLEX_DEPENDENCIES = """
- id: pre_deployment_start
  type: stage

- id: pre_deployment
  type: stage
  requires: [pre_deployment_start]

- id: deploy_start
  type: stage
  requires: [pre_deployment]

- id: deploy_end
  type: stage
  requires: [deploy_start]

- id: post_deployment_start
  type: stage
  requires: [deploy_end]

- id: post_deployment
  type: stage
  requires: [post_deployment_start]

- id: pre_a
  requires: [pre_deployment_start]
  type: shell
- id: pre_b
  requires: [pre_a]
  type: shell
- id: pre_c
  required_for: [pre_deployment]
  type: shell
- id: pre_d
  required_for: [pre_deployment]
  requires: [pre_b]
  type: shell

- id: group_a
  type: group
  requires: [deploy_start]
  required_for: [deploy_end]
- id: group_b
  type: group
  required_for: [deploy_end]
  requires: [group_a]
- id: group_c
  type: group
  required_for: [deploy_end]
  requires: [deploy_start]

- id: task_a
  groups: [group_a, group_b]
  required_for: [deploy_end]
  requires: [deploy_start]
  type: puppet
- id: task_b
  requires: [task_a]
  required_for: [deploy_end]
  type: puppet
  groups: [group_a, group_c]
- id: task_c
  requires: [task_a]
  type: puppet
  required_for: [deploy_end]
  groups: [group_a, group_b]
- id: task_d
  requires: [task_b, task_c]
  type: puppet
  groups: [group_b]
  required_for: [deploy_end]

- id: post_a
  requires: [post_deployment_start]
  required_for: [post_deployment]
  type: shell
"""


class TestFindGraph(base.BaseTestCase):

    def setUp(self):
        super(TestFindGraph, self).setUp()
        self.tasks = yaml.load(COMPLEX_DEPENDENCIES)
        self.graph = deployment_graph.DeploymentGraph()
        self.graph.add_tasks(self.tasks)

    def test_end_at_pre_deployment(self):
        """Only pre_deployment tasks, groups and stages."""
        subgraph = self.graph.find_subgraph(end="pre_deployment")
        self.assertItemsEqual(
            subgraph.nodes(),
            ['pre_d', 'pre_c', 'pre_b', 'pre_a',
             'pre_deployment', 'pre_deployment_start'])

    def test_end_at_task_in_pre_deployment(self):
        """Task pre_d doesnt requires pre_c, but requires pre_b."""
        subgraph = self.graph.find_subgraph(end="pre_d")
        self.assertItemsEqual(
            subgraph.nodes(),
            ['pre_d', 'pre_b', 'pre_a', 'pre_deployment_start'])

    def test_end_at_deploy(self):
        """All tasks should be included because deploy is last node in graph

        All tasks from pre_deployment and deploy stage will be added
        post_a not included
        """
        subgraph = self.graph.find_subgraph(end="deploy_end")

        self.assertItemsEqual(
            subgraph.nodes(),
            ['pre_d', 'pre_c', 'pre_b', 'pre_a', 'deploy_end', 'deploy_start',
             'pre_deployment_start',
             'pre_deployment', 'group_c', 'group_b', 'group_a', 'task_a',
             'task_b', 'task_c', 'task_d'])

    def test_end_at_post_deployment(self):
        """All tasks will be included."""
        subgraph = self.graph.find_subgraph(end="post_deployment")
        self.assertItemsEqual(
            subgraph.nodes(),
            [t['id'] for t in self.tasks])

    def test_end_at_group(self):
        """end_at group should be used in certain conditions

        these condistions are: when tasks that are
        specific for that group, and there is no deps between those groups

        In current graph only task_a and task_b will be present, because
        there is link between them
        """
        subgraph = self.graph.find_subgraph(end="group_c")
        self.assertItemsEqual(
            subgraph.nodes(),
            ['pre_d', 'pre_c', 'pre_b', 'pre_a', 'pre_deployment',
             'pre_deployment_start', 'deploy_start',
             'group_c', 'task_a', 'task_b'])

    def test_end_at_task_that_has_two_parents(self):
        """Both parents should be in the graph

        Parents are task_b and task_c, the only absent task is post_a
        """
        subgraph = self.graph.find_subgraph(end="task_d")
        self.assertItemsEqual(
            subgraph.nodes(),
            ['pre_d', 'pre_c', 'pre_b', 'pre_a', 'deploy_start',
             'pre_deployment_start',
             'pre_deployment', 'task_a',
             'task_b', 'task_c', 'task_d'])

    def test_end_at_first_task(self):
        subgraph = self.graph.find_subgraph(end="task_a")
        self.assertItemsEqual(
            subgraph.nodes(),
            ['pre_d', 'pre_c', 'pre_b', 'pre_a',
             'pre_deployment', 'task_a', 'pre_deployment_start',
             'deploy_start'])

    def test_start_at_task_a(self):
        """Everything except predeployment tasks will be included."""
        subgraph = self.graph.find_subgraph(start="task_a")
        self.assertItemsEqual(
            subgraph.nodes(),
            ['deploy_end', 'post_deployment_start', 'group_c', 'group_b',
             'group_a',
             'task_a', 'task_b', 'task_c', 'task_d', 'post_deployment',
             'post_a'])

    def test_start_at_pre_deployment(self):
        """Everything except pre_deployment tasks."""
        subgraph = self.graph.find_subgraph(start="pre_deployment")
        self.assertItemsEqual(
            subgraph.nodes(),
            ['deploy_end', 'pre_deployment', 'group_c', 'group_b', 'group_a',
             'task_a', 'task_b', 'task_c', 'task_d', 'post_deployment',
             'post_a', 'post_deployment_start', 'deploy_start'])

    def test_start_at_post_a(self):
        """Only post_a task."""
        subgraph = self.graph.find_subgraph(start="post_a")
        self.assertItemsEqual(
            subgraph.nodes(),
            ['post_deployment', 'post_a'])

    def test_start_pre_a_end_at_pre_d(self):
        """pre_c will not be included, not a dependency for pre_d"""
        subgraph = self.graph.find_subgraph(start="pre_a", end="pre_d")
        self.assertItemsEqual(
            subgraph.nodes(),
            ['pre_d', 'pre_b', 'pre_a'])

    def test_start_pre_a_end_at_post_a(self):
        subgraph = self.graph.find_subgraph(start="pre_a", end="post_a")
        self.assertItemsEqual(
            subgraph.nodes(),
            ['deploy_end', 'pre_deployment', 'group_c', 'group_b', 'group_a',
             'task_a', 'task_b', 'task_c', 'task_d', 'post_deployment_start',
             'post_a', 'pre_d', 'pre_b', 'pre_a', 'deploy_start'])

    def test_start_task_a_end_at_task_d(self):
        """All tasks in deploy stage will be included."""
        subgraph = self.graph.find_subgraph(start="task_a", end="task_d")
        self.assertItemsEqual(
            subgraph.nodes(),
            ['task_a', 'task_b', 'task_c', 'task_d'])

    def test_preserve_ordering_when_task_skipped(self):
        self.graph.only_tasks(['task_a', 'task_d'])
        # we skipped both tasks that are predecessors for task_d
        self.assertTrue(self.graph.node['task_b']['skipped'])
        self.assertTrue(self.graph.node['task_c']['skipped'])
        self.assertEqual(
            [t['id'] for t in self.graph.get_group_tasks('group_b')],
            ['task_a', 'task_d'])


class TestOrdered(base.BaseTestCase):

    TASKS = """
    - id: a
    - id: b
      requires: [a]
    - id: c
      requires: [a]
    - id: d
      requires: [a]
    - id: e
      requires: [b,c,d]
    - id: f
      requires: [e]
    """

    def setUp(self):
        super(TestOrdered, self).setUp()
        self.tasks = yaml.load(self.TASKS)

    def test_always_same_order(self):

        graph = deployment_graph.DeploymentGraph(tasks=self.tasks)
        # (dshulyak) order should be static
        self.assertEqual(
            [n['id'] for n in graph.topology],
            ['a', 'b', 'c', 'd', 'e', 'f'])


class TestIncludeSkipped(base.BaseTestCase):

    TASKS = """
    - id: a
      type: puppet
    - id: b
      requires: [a]
      skipped: true
      type: shell
    - id: c
      requires: [b]
      type: puppet
    """

    def setUp(self):
        super(TestIncludeSkipped, self).setUp()
        self.tasks = yaml.load(self.TASKS)
        self.graph = deployment_graph.DeploymentGraph(tasks=self.tasks)

    def test_filter_subgraph_will_not_return_skipped(self):

        subgraph = self.graph.filter_subgraph(start='a', end='c')
        self.assertItemsEqual(
            subgraph.nodes(),
            ['a', 'c'])

    def test_filter_subgraph_will_return_skipped_if_included(self):
        subgraph = self.graph.filter_subgraph(
            start='a', end='c', include=('b',))
        self.assertItemsEqual(
            subgraph.nodes(),
            [t['id'] for t in self.tasks])

    def test_include_task_with_only_tasks_routine(self):
        self.graph.only_tasks(['a', 'b', 'c'])
        subgraph = self.graph.filter_subgraph(start='a', end='c')
        self.assertItemsEqual(
            subgraph.nodes(),
            [t['id'] for t in self.tasks])


class TestDeploymentGraphValidator(base.BaseTestCase):

    def test_validation_pass_with_existing_dependencies(self):
        yaml_tasks = """
        - id: deploy_end
          type: stage
        - id: pre_deployment_start
          type: stage
        - id: test-controller
          type: group
          role: [test-controller]
          requires: [pre_deployment_start]
          required_for: [deploy_end]
          parameters:
            strategy:
              type: parallel
              amount: 2
          """
        tasks = yaml.load(yaml_tasks)
        graph_validator = deployment_graph.DeploymentGraphValidator(tasks)
        graph_validator.check()

    def test_validation_failed_with_not_existing_dependencies(self):
        dependencies_types = ['requires', 'required_for', 'groups', 'tasks']

        for dependency_type in dependencies_types:
            yaml_tasks = """
            - id: test-controller
              type: group
              role: [test-controlle]
              {dependency_type}: [non_existing_stage]
              parameters:
                strategy:
                  type: one_by_one
              """.format(dependency_type=dependency_type)
            tasks = yaml.load(yaml_tasks)
            graph_validator = deployment_graph.DeploymentGraphValidator(tasks)

            with self.assertRaisesRegexp(
                    errors.InvalidData,
                    "Tasks 'non_existing_stage' can't be in requires|"
                    "required_for|groups|tasks for \['test-controller'\] "
                    "because they don't exist in the graph"):
                graph_validator.check()

    def test_validation_failed_with_cycling_dependencies(self):
        yaml_tasks = """
        - id: test-controller-1
          type: role
          requires: [test-controller-2]
        - id: test-controller-2
          type: role
          requires: [test-controller-1]
        """
        tasks = yaml.load(yaml_tasks)
        graph_validator = deployment_graph.DeploymentGraphValidator(tasks)
        with self.assertRaisesRegexp(
                errors.InvalidData,
                "Tasks can not be processed because it contains cycles in it"):
            graph_validator.check()
