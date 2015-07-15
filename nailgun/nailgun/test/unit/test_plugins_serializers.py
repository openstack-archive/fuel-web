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

import copy
import mock

from nailgun import consts
from nailgun.test import base

from nailgun.orchestrator.plugins_serializers import \
    BasePluginDeploymentHooksSerializer
from nailgun.orchestrator.plugins_serializers import \
    PluginsPreDeploymentHooksSerializer


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

    @mock.patch('nailgun.orchestrator.plugins_serializers.get_uids_for_roles')
    def test_original_order_of_deployment_tasks(self, get_uids_for_roles_mock):
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

        get_uids_for_roles_mock.return_value = [1, 2]

        raw_result = self.hook.deployment_tasks([plugin], stage)
        result = [r['type'] for r in raw_result]
        self.assertEqual(result, ['shell', 'puppet', 'shell'])
        self.assertEqual(raw_result[0]['parameters']['cmd'], 'test1')
        self.assertEqual(
            raw_result[1]['parameters']['puppet_modules'],
            'modules')
        self.assertEqual(raw_result[2]['parameters']['cmd'], 'test2')

    @mock.patch('nailgun.orchestrator.plugins_serializers.get_uids_for_roles')
    def test_support_reboot_type_task(self, get_uids_for_roles_mock):
        stage = 'pre_deployment'

        plugin = mock.Mock()
        plugin.full_name = 'plugin_name'
        plugin.slaves_scripts_path = 'plugin_path'

        plugin.tasks = [{
            'type': 'reboot',
            'role': 'controller',
            'stage': stage,
            'parameters': {'timeout': 15}}]

        get_uids_for_roles_mock.return_value = [1, 2]

        result = self.hook.deployment_tasks([plugin], stage)
        expecting_format = {
            'diagnostic_name': 'plugin_name',
            'fail_on_error': True,
            'parameters': {'timeout': 15},
            'type': 'reboot',
            'uids': [1, 2]}

        self.assertEqual(result, [expecting_format])

    @mock.patch('nailgun.orchestrator.plugins_serializers.get_uids_for_roles',
                return_value=[1, 2])
    def test_generates_scripts_path_in_case_of_several_plugins(self, _):
        stage = 'pre_deployment'
        plugins = []
        names = ['plugin_name1', 'plugin_name2']

        for name in names:
            plugin = mock.Mock()
            plugin.full_name = name
            plugin.slaves_scripts_path = name

            plugin.tasks = [{
                'type': 'shell',
                'role': 'controller',
                'stage': stage,
                'parameters': {'timeout': 15, 'cmd': 'cmd'}}]
            plugins.append(plugin)

        result = self.hook.deployment_tasks(plugins, stage)
        script_paths = sorted(map(lambda p: p['parameters']['cwd'], result))
        self.assertEqual(script_paths, names)


@mock.patch('nailgun.orchestrator.plugins_serializers.get_uids_for_roles',
            return_value=[1, 2])
class TestTasksDeploymentOrder(base.BaseTestCase):

    def setUp(self):
        super(TestTasksDeploymentOrder, self).setUp()
        self.cluster = mock.Mock()
        self.nodes = [
            {'id': 1, 'role': 'controller'},
            {'id': 2, 'role': 'compute'}]
        self.hook = BasePluginDeploymentHooksSerializer(
            self.nodes,
            self.cluster)

    def make_plugin_mock_with_stages(self, plugin_name, stages):
        common_attrs = {
            'type': 'shell',
            'role': '*',
            'parameters': {'cmd': 'cmd', 'timeout': 100}}

        tasks = []
        for stage in stages:
            task = copy.deepcopy(common_attrs)
            task['stage'] = stage
            task['parameters']['cmd'] = stage
            tasks.append(task)

        plugin = mock.Mock()
        plugin.tasks = tasks
        plugin.plugin.name = plugin_name

        return plugin

    def test_sorts_plugins_by_numerical_postfixes(self, _):
        plugin1 = self.make_plugin_mock_with_stages('name1', [
            'pre_deployment/-100',
            'pre_deployment/100.0',
            'pre_deployment/+100',
            'pre_deployment'])
        plugin2 = self.make_plugin_mock_with_stages('name2', [
            'pre_deployment/-99',
            'pre_deployment/100',
            'pre_deployment'])

        tasks = self.hook.deployment_tasks(
            # Pass plugins in reverse alphabetic order, to make
            # sure that plugin name sorting works
            [plugin2, plugin1],
            consts.STAGES.pre_deployment)

        commands = map(lambda t: t['parameters']['cmd'], tasks)

        self.assertEqual(
            commands,
            ['pre_deployment/-100',
             'pre_deployment/-99',
             'pre_deployment',
             'pre_deployment',
             'pre_deployment/100.0',
             'pre_deployment/+100',
             'pre_deployment/100'])


class TestPluginsPreDeploymentHooksSerializer(base.BaseTestCase):

    def setUp(self):
        super(TestPluginsPreDeploymentHooksSerializer, self).setUp()
        self.cluster = mock.Mock()
        self.cluster.release.operating_system = 'ubuntu'
        self.nodes = [
            {'id': 1, 'role': 'controller'},
            {'id': 2, 'role': 'compute'}
        ]
        self.hook = PluginsPreDeploymentHooksSerializer(
            self.cluster,
            self.nodes)

        plugin = mock.Mock(tasks=[], deployment_tasks=[])
        self.plugins = [plugin]

    @mock.patch(
        'nailgun.orchestrator.plugins_serializers.get_uids_for_tasks',
        return_value=[1, 2])
    @mock.patch(
        'nailgun.orchestrator.plugins_serializers.'
        'templates.make_ubuntu_sources_task',
        return_value={'task_type': 'ubuntu_sources_task',
                      'parameters': {}})
    @mock.patch(
        'nailgun.orchestrator.plugins_serializers.'
        'templates.make_ubuntu_preferences_task',
        return_value=None)
    @mock.patch(
        'nailgun.orchestrator.plugins_serializers.'
        'templates.make_apt_update_task',
        return_value={'task_type': 'apt_update_task',
                      'parameters': {}})
    def test_create_repositories_ubuntu_does_not_generate_prefences_if_none(
            self, _, __, ___, ____):
        self.cluster.release.operating_system = consts.RELEASE_OS.ubuntu
        tasks = self.hook.create_repositories(self.plugins)
        self.assertItemsEqual(
            map(lambda t: t['task_type'], tasks),
            ['ubuntu_sources_task',
             'apt_update_task'])
