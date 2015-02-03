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

from nailgun.orchestrator import deployment_graph
from nailgun.test import base


class TestDeploymentGraphViualization(base.BaseUnitTest):

    def test_add_stage(self):
        tasks = [
            {'id': 'pre_deployment', 'type': 'stage'},
        ]
        graph = deployment_graph.DeploymentGraph()
        graph.add_tasks(tasks)
        dotgraph = graph.get_dotgraph()

        self.assertIn('color=red', dotgraph)
        self.assertIn('shape=rect', dotgraph)
        self.assertIn('group=stages', dotgraph)
        self.assertIn('pre_deployment', dotgraph)

    def test_add_simple_connection(self):
        tasks = [
            {'id': 'task-A'},
            {'id': 'task-B', 'requires': ['task-A']},
        ]
        graph = deployment_graph.DeploymentGraph()
        graph.add_tasks(tasks)
        dotgraph = graph.get_dotgraph()
        self.assertIn('"task-A" -> "task-B"', dotgraph)
