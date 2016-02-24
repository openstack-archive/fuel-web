# -*- coding: utf-8 -*-

#    Copyright 2016 Mirantis, Inc.
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

from nailgun.objects.deployment_graph import DeploymentGraph
from nailgun.test import base

JSON_TASKS = [
    {
        'id': 'post_deployment_end',
        'type': 'stage',
        'requires': ['post_deployment_start']
    },
    {
        'id': 'primary-controller',
        'parameters': {'strategy': {'type': 'one_by_one'}},
        'required_for': ['deploy_end'],
        'requires': ['deploy_start'],
        'role': ['primary-controller'],
        'type': 'group'
    },
    {
        'id': 'cross-dep-test',
        'type': 'puppet',
        'cross-depended-by': ['a', 'b'],
        'cross-depends': ['c', 'd']
    }
]


class TestDeploymentGraphModel(base.BaseTestCase):
    def test_deployment_graph_creation(self):
        expected_tasks = [
            {
                'task_name': u'cross-dep-test',
                'id': u'cross-dep-test',  # legacy
                'type': 'puppet',
                'version': u'1.0.0',
                'reexecute_on': [],
                'refresh_on': [],
                'required_for': [],
                'requires': [],
                'cross_depended_by': [u'a', u'b'],
                'cross_depends': [u'c', u'd'],
                'cross-depended-by': [u'a', u'b'],  # legacy
                'cross-depends': [u'c', u'd'],      # legacy
                'roles': [],
                'role': [],     # legacy
                'tasks': [],
                'groups': [],
                'parameters': {},
            }, {
                'task_name': u'post_deployment_end',
                'id': u'post_deployment_end',  # legacy
                'type': 'stage',
                'version': u'1.0.0',
                'reexecute_on': [],
                'refresh_on': [],
                'required_for': [],
                'requires': [u'post_deployment_start'],
                'cross_depended_by': [],
                'cross_depends': [],
                'cross-depended-by': [],    # legacy
                'cross-depends': [],        # legacy
                'roles': [],
                'role': [],     # legacy
                'tasks': [],
                'groups': [],
                'parameters': {},
            }, {
                'task_name': u'primary-controller',
                'id': u'primary-controller',    # legacy
                'type': 'group',
                'version': u'1.0.0',
                'reexecute_on': [],
                'refresh_on': [],
                'required_for': [u'deploy_end'],
                'requires': [u'deploy_start'],
                'cross_depended_by': [],
                'cross_depends': [],
                'cross-depended-by': [],    # legacy
                'cross-depends': [],        # legacy
                'roles': [u'primary-controller'],
                'role': [u'primary-controller'],    # legacy
                'tasks': [],
                'groups': [],
                'parameters': {u'strategy': {u'type': u'one_by_one'}},
            }
        ]
        dg = DeploymentGraph.create(JSON_TASKS, verbose_name='test_graph')
        serialized = DeploymentGraph.to_dict(dg)
        self.assertEqual(serialized['verbose_name'], 'test_graph')
        self.assertItemsEqual(serialized['deployment_tasks'], expected_tasks)
