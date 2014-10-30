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


import mock
import yaml

from nailgun import objects
from nailgun.openstack.common import jsonutils
from nailgun.plugins import attr_plugin
from nailgun.test import base


def get_config(config):
    def _get_config(*args):
        return mock.mock_open(read_data=yaml.dump(config))()
    return _get_config


class BasePluginTest(base.BaseIntegrationTest):

    SAMPLE_PLUGIN = {
        'version': '1.1.0',
        'name': 'testing',
        'package_version': '1',
        'description': 'Enable to use plugin X for Neutron',
        'types': ['nailgun', 'repository', 'deployment_scripts'],
        'fuel_version': "6.0",
        'releases': [
            {'repository_path': 'repositories/ubuntu',
             'version': '2014.2-6.0',
             'os': 'ubuntu',
             'mode': ['ha_compact', 'multinode'],
             'deployment_scripts_path': 'deployment_scripts/'},
            {'repository_path': 'repositories/centos',
             'version': '2014.2-6.0', 'os': 'centos',
             'mode': ['ha', 'multinode'],
             'deployment_scripts_path': 'deployment_scripts/'}]}

    ENVIRONMENT_CONFIG = {
        'attributes': {
            'lbaas_simple_text': {
                'value': 'Set default value',
                'type': 'text',
                'description': 'Description for text field',
                'weight': 25,
                'label': 'Text field'}}}

    TASKS_CONFIG = [
        {'priority': 10,
         'role': ['controller'],
         'type': 'shell',
         'parameters': {'cmd': './lbaas_enable.sh', 'timeout': 42},
         'stage': 'post_deployment'},
        {'priority': 10,
         'role': '*',
         'type': 'shell',
         'parameters': {'cmd': 'echo all > /tmp/plugin.all', 'timeout': 42},
         'stage': 'pre_deployment'}]

    def create_plugin(self, sample=None, expect_errors=False):
        sample = sample or self.SAMPLE_PLUGIN
        resp = self.app.post(
            base.reverse('PluginCollectionHandler'),
            jsonutils.dumps(sample),
            headers=self.default_headers,
            expect_errors=expect_errors
        )
        return resp

    def delete_plugin(self, plugin_id):
        resp = self.app.delete(
            base.reverse('PluginHandler', {'obj_id': plugin_id}),
            headers=self.default_headers
        )
        return resp

    def create_cluster(self, nodes=None):
        nodes = nodes if nodes else []
        with mock.patch('nailgun.plugins.attr_plugin.os') as os:
            with mock.patch('nailgun.plugins.attr_plugin.open',
                            create=True) as f_m:
                os.access.return_value = True
                os.path.exists.return_value = True
                f_m.side_effect = get_config(self.ENVIRONMENT_CONFIG)
                self.env.create(
                    release_kwargs={'version': '2014.2-6.0',
                                    'operating_system': 'Ubuntu'},
                    nodes_kwargs=nodes)
        return self.env.clusters[0]

    def default_attributes(self, cluster):
        resp = self.app.get(
            base.reverse('ClusterAttributesDefaultsHandler',
                         {'cluster_id': cluster.id}),
            headers=self.default_headers)
        return resp

    def modify_plugin(self, cluster, plugin_name, enabled):
        editable_attrs = cluster.attributes.editable
        editable_attrs[plugin_name]['metadata']['enabled'] = enabled
        resp = self.app.put(
            base.reverse('ClusterAttributesHandler',
                         {'cluster_id': cluster.id}),
            jsonutils.dumps({'editable': editable_attrs}),
            headers=self.default_headers)
        return resp

    def enable_plugin(self, cluster, plugin_name):
        return self.modify_plugin(cluster, plugin_name, True)

    def disable_plugin(self, cluster, plugin_name):
        return self.modify_plugin(cluster, plugin_name, False)

    def get_pre_hooks(self, cluster):
        with mock.patch('nailgun.plugins.attr_plugin.glob') as glob:
            glob.glob.return_value = ['/some/path']
            with mock.patch('nailgun.plugins.attr_plugin.os') as os:
                with mock.patch('nailgun.plugins.attr_plugin.open',
                                create=True) as f_m:
                    os.access.return_value = True
                    os.path.exists.return_value = True
                    f_m.side_effect = get_config(self.TASKS_CONFIG)
                    resp = self.app.get(
                        base.reverse('DefaultPrePluginsHooksInfo',
                                     {'cluster_id': cluster.id}),
                        headers=self.default_headers)
                return resp

    def get_post_hooks(self, cluster):
        with mock.patch('nailgun.plugins.attr_plugin.os') as os:
            with mock.patch('nailgun.plugins.attr_plugin.open',
                            create=True) as f_m:
                os.access.return_value = True
                os.path.exists.return_value = True
                f_m.side_effect = get_config(self.TASKS_CONFIG)
                resp = self.app.get(
                    base.reverse('DefaultPostPluginsHooksInfo',
                                 {'cluster_id': cluster.id}),
                    headers=self.default_headers)
                return resp


class TestPluginsApi(BasePluginTest):

    def test_plugin_created_on_post(self):
        resp = self.create_plugin()
        self.assertEqual(resp.status_code, 201)

    def test_env_create_and_load_env_config(self):
        self.create_plugin()
        cluster = self.create_cluster()
        self.assertIn(self.SAMPLE_PLUGIN['name'], cluster.attributes.editable)

    def test_enable_disable_plugin(self):
        resp = self.create_plugin()
        plugin = objects.Plugin.get_by_uid(resp.json['id'])
        cluster = self.create_cluster()
        self.assertEqual(plugin.clusters, [])
        resp = self.enable_plugin(cluster, plugin.name)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(cluster, plugin.clusters)
        resp = self.disable_plugin(cluster, plugin.name)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(plugin.clusters, [])

    def test_delete_plugin(self):
        resp = self.create_plugin()
        del_resp = self.delete_plugin(resp.json['id'])
        self.assertEqual(del_resp.status_code, 204)

    def test_update_plugin(self):
        resp = self.create_plugin()
        data = resp.json
        data['package_version'] = '2'
        plugin_id = data.pop('id')
        resp = self.app.put(
            base.reverse('PluginHandler', {'obj_id': plugin_id}),
            jsonutils.dumps(data),
            headers=self.default_headers
        )
        self.assertEqual(resp.status_code, 200)
        updated_data = resp.json
        updated_data.pop('id')
        self.assertEqual(updated_data, data)

    def test_default_attributes_after_plugin_is_created(self):
        self.create_plugin()
        cluster = self.create_cluster()
        default_attributes = self.default_attributes(cluster)
        self.assertIn(self.SAMPLE_PLUGIN['name'], default_attributes)


class TestPrePostHooks(BasePluginTest):

    def setUp(self):
        super(TestPrePostHooks, self).setUp()
        resp = self.create_plugin()
        self.plugin = attr_plugin.ClusterAttributesPlugin(
            objects.Plugin.get_by_uid(resp.json['id']))
        self.cluster = self.create_cluster([
            {'roles': ['controller'], 'pending_addition': True},
            {'roles': ['compute'], 'pending_addition': True}])
        self.enable_plugin(self.cluster, self.SAMPLE_PLUGIN['name'])

    def test_generate_pre_hooks(self):
        tasks = self.get_pre_hooks(self.cluster).json
        upload_file = [t for t in tasks if t['type'] == 'upload_file']
        rsync = [t for t in tasks if t['type'] == 'sync']
        self.assertEqual(len(upload_file), 1)
        self.assertEqual(len(rsync), 1)
        for t in tasks:
            #shoud uid be a string
            self.assertEqual(
                sorted(t['uids']), sorted([n.id for n in self.cluster.nodes]))
            self.assertTrue(t['fail_on_error'])
            self.assertEqual(t['diagnostic_name'], self.plugin.full_name)

    def test_generate_post_hooks(self):
        tasks = self.get_post_hooks(self.cluster).json
        self.assertEqual(len(tasks), 1)
        task = tasks[0]
        controller_id = [n.id for n in self.cluster.nodes
                         if 'controller' in n.roles]
        self.assertEqual(controller_id, task['uids'])
        self.assertTrue(task['fail_on_error'])
        self.assertEqual(task['diagnostic_name'], self.plugin.full_name)


class TestPluginValidation(BasePluginTest):

    def test_releases_not_provided(self):
        sample = {
            'name': 'test_name',
            'version': '0.1.1',
            'package_version': '1'
        }
        resp = self.create_plugin(sample=sample, expect_errors=True)
        self.assertEqual(resp.status_code, 400)

    def test_version_is_not_present_in_release_data(self):
        sample = {
            'name': 'test_name',
            'version': '0.1.1',
            'package_version': '1',
            'releases': [
                {'os': 'Ubuntu', 'mode': ['ha_compact', 'multinode']}
            ]
        }
        resp = self.create_plugin(sample=sample, expect_errors=True)
        self.assertEqual(resp.status_code, 400)

    def test_plugin_version_is_floating(self):
        sample = {
            'name': 'test_name',
            'version': 1.1,
            'package_version': '1',
            'releases': [
                {'os': 'Ubuntu',
                 'mode': ['ha_compact', 'multinode'],
                 'version': '2014.2.1-5.1'}
            ]
        }
        resp = self.create_plugin(sample=sample, expect_errors=True)
        self.assertEqual(resp.status_code, 400)
