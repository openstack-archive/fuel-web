
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

import mock
from nailgun.test import base

from nailgun.orchestrator import plugins_serializers
from nailgun.orchestrator.plugins_serializers import \
    BasePluginDeploymentHooksSerializer


class TestMakeTask(base.BaseTestCase):

    def test_make_ubuntu_repo_task(self):
        result = plugins_serializers.make_ubuntu_repo_task(
            'plugin_name',
            'http://url',
            [1, 2, 3])

        self.assertEqual(
            result,
            {'parameters': {
                'data': 'deb http://url /',
                'path': '/etc/apt/sources.list.d/plugin_name.list'},
             'type': 'upload_file',
             'uids': [1, 2, 3]})


class TestBasePluginDeploymentHooksSerializer(base.BaseTestCase):

    def setUp(self):
        super(TestBasePluginDeploymentHooksSerializer, self).setUp()
        cluster_mock = mock.Mock()
        self.cluster = cluster_mock
        self.nodes = [
            {'id': 1, 'role': 'controller'},
            {'id': 2, 'role': 'compute'}
        ]
        self.hook = BasePluginDeploymentHooksSerializer(
            self.nodes,
            self.cluster)

    @mock.patch('nailgun.orchestrator.plugins_serializers.' \
        'BasePluginDeploymentHooksSerializer.get_uids_for_tasks')
    def test_original_order_of_deployment_tasks(self, get_uids_for_tasks_mock):
        stage = 'pre_deployment'
        role = 'controller'

        plugin = mock.Mock()
        plugin.full_name = 'plugin_name'
        plugin.tasks = [
            {'type': 'shell', 'role': role, 'id': '1', 'stage': stage,
             'parameters': {'cmd': 'test1', 'cwd': '/', 'timeout': 15}},
            {'type': 'puppet', 'role': role, 'id': '2', 'stage': stage,
             'parameters': {
                 'puppet_manifest': 'manifests/site.pp',
                 'puppet_modules': 'modules',
                 'cwd': '/etc/puppet/plugins/plugin_name',
                 'timeout': 150}},
            {'type': 'shell', 'role': role, 'id': '3', 'stage': stage,
             'parameters': {'cmd': 'test2', 'cwd': '/', 'timeout': 15}}
        ]

        get_uids_for_tasks_mock.return_value = [1, 2]

        raw_result = self.hook.deployment_tasks([plugin], stage)
        result = [r['type'] for r in raw_result]
        self.assertEqual(result, ['shell', 'puppet', 'shell'])
        self.assertEqual(raw_result[0]['parameters']['cmd'], 'test1')
        self.assertEqual(
            raw_result[1]['parameters']['puppet_modules'],
            'modules')
        self.assertEqual(raw_result[2]['parameters']['cmd'], 'test2')
