# -*- coding: utf-8 -*-

#    Copyright 2015 Mirantis, Inc.
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

import six

from nailgun.orchestrator import graph_visualization
from nailgun.orchestrator import orchestrator_graph
from nailgun.test import base


class TestOrchestratorGraphViualization(base.BaseUnitTest):

    def get_dotgraph_with_tasks(self, tasks):
        graph = orchestrator_graph.OrchestratorGraph()
        graph.add_tasks(tasks)
        visualization = graph_visualization.GraphVisualization(graph)
        dotgraph = visualization.get_dotgraph()
        return dotgraph.to_string()

    def test_stage_type(self):
        tasks = [
            {'id': 'pre_deployment', 'type': 'stage'},
        ]

        dotgraph = self.get_dotgraph_with_tasks(tasks)

        six.assertRegex(self, dotgraph, 'pre_deployment .*color=red.*;')
        six.assertRegex(self, dotgraph, 'pre_deployment .*shape=rect.*;')
        six.assertRegex(self, dotgraph, 'pre_deployment .*style=filled.*;')

    def test_group_type(self):
        tasks = [
            {'id': 'controller', 'type': 'group'},
        ]

        dotgraph = self.get_dotgraph_with_tasks(tasks)

        six.assertRegex(self, dotgraph, 'controller .*color=lightskyblue.*;')
        six.assertRegex(self, dotgraph, 'controller .*shape=box.*;')
        six.assertRegex(self, dotgraph,
                        'controller .*style="filled, rounded".*;')

    def test_skipped_type(self):
        tasks = [
            {'id': 'hiera', 'type': 'skipped'},
        ]
        dotgraph = self.get_dotgraph_with_tasks(tasks)
        self.assertIn('hiera [color=gray95];', dotgraph)

    def test_add_simple_connection(self):
        tasks = [
            {'id': 'task-A'},
            {'id': 'task-B', 'requires': ['task-A']},
        ]

        dotgraph = self.get_dotgraph_with_tasks(tasks)

        self.assertIn('"task-A" -> "task-B"', dotgraph)

    def test_node_default_attrs(self):
        tasks = [
            {'id': 'task-A'},
        ]
        dotgraph = self.get_dotgraph_with_tasks(tasks)
        six.assertRegex(self, dotgraph, '"task-A" .*color=yellowgreen.*;')
        six.assertRegex(self, dotgraph, '"task-A" .*style=filled.*;')

    def test_skipped_metaparam(self):
        tasks = [
            {'id': 'task_a', 'skipped': True},
        ]
        dotgraph = self.get_dotgraph_with_tasks(tasks)
        self.assertIn('task_a [color=gray95];', dotgraph)
