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
from oslo_serialization import jsonutils
import yaml

from nailgun import objects
from nailgun.plugins import adapters
from nailgun.test import base


def get_config(config):
    def _get_config(*args):
        return mock.mock_open(read_data=yaml.dump(config))()
    return _get_config


class BasePluginTest(base.BaseIntegrationTest):

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

    def setUp(self):
        super(BasePluginTest, self).setUp()
        self.sample_plugin = self.env.get_default_plugin_metadata()
        self.plugin_env_config = self.env.get_default_plugin_env_config()

    def create_plugin(self, sample=None, expect_errors=False):
        sample = sample or self.sample_plugin
        resp = self.app.post(
            base.reverse('PluginCollectionHandler'),
            jsonutils.dumps(sample),
            headers=self.default_headers,
            expect_errors=expect_errors
        )
        return resp

    def delete_plugin(self, plugin_id, expect_errors=False):
        resp = self.app.delete(
            base.reverse('PluginHandler', {'obj_id': plugin_id}),
            headers=self.default_headers,
            expect_errors=expect_errors
        )
        return resp

    def create_cluster(self, nodes=None):
        nodes = nodes if nodes else []
        with mock.patch('nailgun.plugins.adapters.os') as os:
            with mock.patch(
                    'nailgun.plugins.adapters.open',
                    create=True,
                    side_effect=get_config(self.plugin_env_config)):
                os.access.return_value = True
                os.path.exists.return_value = True
                self.env.create(
                    release_kwargs={'version': '2014.2-6.0',
                                    'operating_system': 'Ubuntu',
                                    'deployment_tasks': []},
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
        with mock.patch('nailgun.plugins.adapters.glob') as glob:
            glob.glob.return_value = ['/some/path']
            with mock.patch('nailgun.plugins.adapters.os') as os:
                with mock.patch(
                        'nailgun.plugins.adapters.open',
                        create=True,
                        side_effect=get_config(self.TASKS_CONFIG)):
                    os.access.return_value = True
                    os.path.exists.return_value = True
                    resp = self.app.get(
                        base.reverse('DefaultPrePluginsHooksInfo',
                                     {'cluster_id': cluster.id}),
                        headers=self.default_headers)
                return resp

    def get_post_hooks(self, cluster):
        with mock.patch('nailgun.plugins.adapters.os') as os:
            with mock.patch(
                    'nailgun.plugins.adapters.open',
                    create=True,
                    side_effect=get_config(self.TASKS_CONFIG)):
                os.access.return_value = True
                os.path.exists.return_value = True
                resp = self.app.get(
                    base.reverse('DefaultPostPluginsHooksInfo',
                                 {'cluster_id': cluster.id}),
                    headers=self.default_headers)
                return resp

    def sync_plugins(self, params=None, expect_errors=False):
        post_data = jsonutils.dumps(params) if params else ''

        resp = self.app.post(
            base.reverse('PluginSyncHandler'),
            post_data,
            headers=self.default_headers,
            expect_errors=expect_errors
        )

        self.assertValidJSON(resp.body)

        return resp


class TestPluginsApi(BasePluginTest):

    def test_plugin_created_on_post(self):
        resp = self.create_plugin()
        self.assertEqual(resp.status_code, 201)
        metadata = resp.json
        del metadata['id']
        self.assertEqual(metadata, self.sample_plugin)

    def test_env_create_and_load_env_config(self):
        self.create_plugin()
        cluster = self.create_cluster()
        self.assertIn(self.sample_plugin['name'], cluster.attributes.editable)

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

    def test_no_delete_of_used_plugin(self):
        resp = self.create_plugin()
        plugin = objects.Plugin.get_by_uid(resp.json['id'])
        cluster = self.create_cluster()
        enable_resp = self.enable_plugin(cluster, plugin.name)
        self.assertEqual(enable_resp.status_code, 200)
        del_resp = self.delete_plugin(resp.json['id'], expect_errors=True)
        self.assertEqual(del_resp.status_code, 400)

    def test_update_plugin(self):
        resp = self.create_plugin()
        data = resp.json
        data['package_version'] = '2.0.0'
        plugin_id = data.pop('id')
        resp = self.app.put(
            base.reverse('PluginHandler', {'obj_id': plugin_id}),
            jsonutils.dumps(data),
            headers=self.default_headers
        )
        self.assertEqual(resp.status_code, 200)
        updated_data = resp.json
        updated_plugin_id = updated_data.pop('id')
        self.assertEqual(plugin_id, updated_plugin_id)
        self.assertEqual(updated_data, data)

    def test_default_attributes_after_plugin_is_created(self):
        self.create_plugin()
        cluster = self.create_cluster()
        default_attributes = self.default_attributes(cluster)
        self.assertIn(self.sample_plugin['name'], default_attributes)

    def test_plugins_multiversioning(self):
        def create_with_version(version):
            self.create_plugin(sample=self.env.get_default_plugin_metadata(
                name='multiversion_plugin', version=version))

        for version in ['1.0.0', '2.0.0', '0.0.1']:
            create_with_version(version)

        cluster = self.create_cluster()
        # Create new plugin after environment is created
        create_with_version('5.0.0')

        self.enable_plugin(cluster, 'multiversion_plugin')
        self.assertEqual(len(cluster.plugins), 1)
        enabled_plugin = cluster.plugins[0]
        # Should be enabled the newest plugin,
        # at the moment of environment creation
        self.assertEqual(enabled_plugin.version, '2.0.0')

        self.disable_plugin(cluster, 'multiversion_plugin')
        self.assertEqual(len(cluster.plugins), 0)

    def test_sync_all_plugins(self):
        self._create_new_and_old_version_plugins_for_sync()

        resp = self.sync_plugins()
        self.assertEqual(resp.status_code, 200)

    def test_sync_specific_plugins(self):
        plugin_ids = self._create_new_and_old_version_plugins_for_sync()
        ids = plugin_ids[:1]

        resp = self.sync_plugins(params={'ids': ids})
        self.assertEqual(resp.status_code, 200)

    def test_sync_failed_when_plugin_not_found(self):
        plugin_ids = self._create_new_and_old_version_plugins_for_sync()
        ids = [plugin_ids.pop() + 1]

        resp = self.sync_plugins(params={'ids': ids}, expect_errors=True)
        self.assertEqual(resp.status_code, 404)

    @mock.patch('nailgun.plugins.adapters.open', create=True)
    @mock.patch('nailgun.plugins.adapters.os.access')
    def test_sync_with_invalid_yaml_files(self, maccess, mopen):
        maccess.return_value = True

        self._create_new_and_old_version_plugins_for_sync()
        with mock.patch.object(yaml, 'safe_load') as yaml_safe_load:
            yaml_safe_load.side_effect = yaml.YAMLError()
            resp = self.sync_plugins(expect_errors=True)
            self.assertEqual(resp.status_code, 400)
            self.assertRegexpMatches(
                resp.json_body["message"],
                'Problem with loading YAML file')

    def _create_new_and_old_version_plugins_for_sync(self):
        plugin_ids = []

        old_version_plugin = {
            'name': 'test_name_0',
            'version': '0.1.1',
            'fuel_version': ['6.0'],
            'title': 'Test plugin',
            'package_version': '1.0.0',
            'releases': [
                {'os': 'Ubuntu',
                 'mode': ['ha', 'multinode'],
                 'version': '2014.2.1-5.1'}
            ],
        }
        resp = self.create_plugin(sample=old_version_plugin)
        self.assertEqual(resp.status_code, 201)

        new_version_plugin_1 = {
            'name': 'test_name_1',
            'version': '0.1.1',
            'fuel_version': ['7.0'],
            'title': 'Test plugin',
            'package_version': '3.0.0',
            'releases': [
                {'os': 'Ubuntu',
                 'mode': ['ha', 'multinode'],
                 'version': '2014.2.1-5.1'}
            ],
        }
        resp = self.create_plugin(sample=new_version_plugin_1)
        self.assertEqual(resp.status_code, 201)
        # Only plugins with version 3.0.0 will be synced
        plugin_ids.append(resp.json['id'])

        new_version_plugin_2 = {
            'name': 'test_name_2',
            'version': '0.1.1',
            'fuel_version': ['7.0'],
            'title': 'Test plugin',
            'package_version': '3.0.0',
            'releases': [
                {'os': 'Ubuntu',
                 'mode': ['ha'],
                 'version': '2014.2.1-5.1'}
            ],
        }
        resp = self.create_plugin(sample=new_version_plugin_2)
        self.assertEqual(resp.status_code, 201)
        plugin_ids.append(resp.json['id'])

        return plugin_ids


class TestPrePostHooks(BasePluginTest):

    def setUp(self):
        super(TestPrePostHooks, self).setUp()

        self._requests_mock = mock.patch(
            'nailgun.utils.debian.requests.get',
            return_value=mock.Mock(text='Archive: test'))
        self._requests_mock.start()

        resp = self.create_plugin()
        self.plugin = adapters.wrap_plugin(
            objects.Plugin.get_by_uid(resp.json['id']))
        self.cluster = self.create_cluster([
            {'roles': ['controller'], 'pending_addition': True},
            {'roles': ['compute'], 'pending_addition': True}])
        objects.NodeCollection.prepare_for_deployment(self.cluster.nodes)
        self.enable_plugin(self.cluster, self.sample_plugin['name'])

    def tearDown(self):
        self._requests_mock.stop()
        super(TestPrePostHooks, self).tearDown()

    def test_generate_pre_hooks(self):
        tasks = self.get_pre_hooks(self.cluster).json
        plugins_tasks = [t for t in tasks if t.get('diagnostic_name')]
        upload_file = [t for t in plugins_tasks if t['type'] == 'upload_file']
        rsync = [t for t in plugins_tasks if t['type'] == 'sync']
        cmd_tasks = [t for t in plugins_tasks if t['type'] == 'shell']
        self.assertEqual(len(upload_file), 2)
        self.assertEqual(len(rsync), 1)
        self.assertEqual(len(cmd_tasks), 2)
        for t in plugins_tasks:
            #shoud uid be a string
            self.assertEqual(
                sorted(t['uids']), sorted([n.uid for n in self.cluster.nodes]))
            #diagnostic name is present only for plugin tasks
            self.assertEqual(t['diagnostic_name'], self.plugin.full_name)
        apt_update = [t for t in cmd_tasks
                      if u'apt-get update' in t['parameters']['cmd']]
        self.assertEqual(len(apt_update), 1)

    def test_generate_post_hooks(self):
        tasks = self.get_post_hooks(self.cluster).json
        self.assertEqual(len(tasks), 1)
        task = tasks[0]
        controller_id = [n.uid for n in self.cluster.nodes
                         if 'controller' in n.roles]
        self.assertEqual(controller_id, task['uids'])
        self.assertEqual(task['diagnostic_name'], self.plugin.full_name)


class TestPluginValidation(BasePluginTest):

    def test_valid(self):
        sample = {
            'name': 'test_name',
            'version': '0.1.1',
            'fuel_version': ['6.0'],
            'title': 'Test plugin',
            'package_version': '1.0.0',
            'releases': [
                {'os': 'Ubuntu',
                 'mode': ['ha', 'multinode'],
                 'version': '2014.2.1-5.1'}
            ],
        }
        resp = self.create_plugin(sample=sample)
        self.assertEqual(resp.status_code, 201)

    def test_releases_not_provided(self):
        sample = {
            'name': 'test_name',
            'version': '0.1.1',
            'fuel_version': ['6.0'],
            'title': 'Test plugin',
            'package_version': '1.0.0'
        }
        resp = self.create_plugin(sample=sample, expect_errors=True)
        self.assertEqual(resp.status_code, 400)

    def test_version_is_not_present_in_release_data(self):
        sample = {
            'name': 'test_name',
            'version': '0.1.1',
            'fuel_version': ['6.0'],
            'title': 'Test plugin',
            'package_version': '1.0.0',
            'releases': [
                {'os': 'Ubuntu', 'mode': ['ha', 'multinode']}
            ]
        }
        resp = self.create_plugin(sample=sample, expect_errors=True)
        self.assertEqual(resp.status_code, 400)

    def test_plugin_version_is_floating(self):
        sample = {
            'name': 'test_name',
            'title': 'Test plugin',
            'version': 1.1,
            'fuel_version': ['6.0'],
            'package_version': '1.0.0',
            'releases': [
                {'os': 'Ubuntu',
                 'mode': ['ha', 'multinode'],
                 'version': '2014.2.1-5.1'}
            ]
        }
        resp = self.create_plugin(sample=sample, expect_errors=True)
        self.assertEqual(resp.status_code, 400)

    def test_title_is_not_present(self):
        sample = {
            'name': 'test_name',
            'version': '1.1',
            'fuel_version': ['6.0'],
            'package_version': '1.0.0',
            'releases': [
                {'os': 'Ubuntu',
                 'mode': ['multinode'],
                 'version': '2014.2.1-5.1'}
            ]
        }
        resp = self.create_plugin(sample=sample, expect_errors=True)
        self.assertEqual(resp.status_code, 400)


class TestPluginSyncValidation(BasePluginTest):

    def test_valid(self):
        resp = self.sync_plugins()
        self.assertEqual(resp.status_code, 200)

    def test_ids_not_present(self):
        sample = {'test': '1'}
        resp = self.sync_plugins(params=sample, expect_errors=True)
        self.assertEqual(resp.status_code, 400)

    def test_ids_not_array_type(self):
        sample = {'ids': {}}
        resp = self.sync_plugins(params=sample, expect_errors=True)
        self.assertEqual(resp.status_code, 400)
