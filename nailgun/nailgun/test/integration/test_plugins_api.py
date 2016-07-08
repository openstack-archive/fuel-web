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

import collections

import mock
from oslo_serialization import jsonutils
import yaml

from nailgun import consts
from nailgun.db.sqlalchemy.models import DeploymentGraph
from nailgun import objects
from nailgun.plugins import adapters
from nailgun.test import base

from nailgun.plugins.package_manager.package_fp import PluginPackageFP
from nailgun.plugins.package_manager.package_rpm import PluginPackageRPM


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

    def delete_plugin(self, plugin_id, expect_errors=False):
        resp = self.app.delete(
            base.reverse('PluginHandler', {'obj_id': plugin_id}),
            headers=self.default_headers,
            expect_errors=expect_errors
        )
        return resp

    def create_cluster(self, nodes=None):
        nodes = nodes if nodes else []
        cluster = self.env.create(
            release_kwargs={'version': '2014.2-6.0',
                            'operating_system': 'Ubuntu',
                            'deployment_tasks': []},
            nodes_kwargs=nodes)
        return cluster

    def default_attributes(self, cluster):
        resp = self.app.get(
            base.reverse('ClusterAttributesDefaultsHandler',
                         {'cluster_id': cluster.id}),
            headers=self.default_headers)
        return resp

    def modify_plugin(self, cluster, plugin_name, plugin_id, enabled):
        editable_attrs = objects.Cluster.get_editable_attributes(
            cluster, all_plugins_versions=True)
        editable_attrs[plugin_name]['metadata']['enabled'] = enabled
        editable_attrs[plugin_name]['metadata']['chosen_id'] = plugin_id

        resp = self.app.put(
            base.reverse('ClusterAttributesHandler',
                         {'cluster_id': cluster.id}),
            jsonutils.dumps({'editable': editable_attrs}),
            headers=self.default_headers)

        return resp

    def enable_plugin(self, cluster, plugin_name, plugin_id):
        return self.modify_plugin(cluster, plugin_name, plugin_id, True)

    def disable_plugin(self, cluster, plugin_name):
        return self.modify_plugin(cluster, plugin_name, None, False)

    def get_pre_hooks(self, cluster):
        with mock.patch('nailgun.plugins.adapters.glob') as glob:
            glob.glob.return_value = ['/some/path']
            resp = self.app.get(
                base.reverse('DefaultPrePluginsHooksInfo',
                             {'cluster_id': cluster.id}),
                headers=self.default_headers,
                expect_errors=True
            )
        return resp

    def get_post_hooks(self, cluster):
        resp = self.app.get(
            base.reverse('DefaultPostPluginsHooksInfo',
                         {'cluster_id': cluster.id}),
            headers=self.default_headers,
            expect_errors=True
        )
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

    def upload_plugin(self, file_name, force=False, expect_errors=False):
        return self.app.post(
            base.reverse('PluginUploadHandler'),
            collections.OrderedDict([('force', force)]),
            upload_files=[('uploaded', file_name, 'some plugin data')],
            expect_errors=expect_errors
        )


class TestPluginsApi(BasePluginTest):

    def setUp(self):
        super(TestPluginsApi, self).setUp()
        self.plugin_fp_old = 'fake_plugin-1.0.0.fp'
        self.plugin_fp_new = 'fake_plugin-1.0.1.fp'
        self.plugin_rpm_old = 'fake_plugin-2.0-2.0.0-1.noarch.rpm'
        self.plugin_rpm_new = 'fake_plugin-2.0-2.0.1-1.noarch.rpm'

    def test_plugin_created_on_post(self):
        resp = self.env.create_plugin(api=True)
        self.assertEqual(resp.status_code, 201)
        metadata = resp.json
        del metadata['id']

        self.assertEqual(metadata, self.sample_plugin)

    def test_env_create_and_load_env_config(self):
        self.env.create_plugin(api=True)
        cluster = self.create_cluster()
        self.assertIn(self.sample_plugin['name'],
                      objects.Cluster.get_editable_attributes(
                          cluster, all_plugins_versions=True))

    def test_enable_disable_plugin(self):
        resp = self.env.create_plugin(api=True)
        plugin = objects.Plugin.get_by_uid(resp.json['id'])
        cluster = self.create_cluster()
        self.assertItemsEqual(
            [],
            objects.ClusterPlugin.get_enabled(cluster.id)
        )

        resp = self.enable_plugin(cluster, plugin.name, plugin.id)
        self.assertEqual(resp.status_code, 200)
        self.assertItemsEqual(
            [plugin],
            objects.ClusterPlugin.get_enabled(cluster.id)
        )

        resp = self.disable_plugin(cluster, plugin.name)
        self.assertEqual(resp.status_code, 200)
        self.assertItemsEqual(
            [],
            objects.ClusterPlugin.get_enabled(cluster.id)
        )

    def test_delete_plugin(self):
        resp = self.env.create_plugin(api=True)
        graphs_before_deletion = self.db.query(DeploymentGraph).count()
        with mock.patch.object(PluginPackageFP, 'remove'):
            del_resp = self.delete_plugin(resp.json['id'])
        self.assertEqual(del_resp.status_code, 204)
        graphs_after_deletion = self.db.query(DeploymentGraph).count()
        self.assertEqual(1, graphs_before_deletion - graphs_after_deletion)

    def test_delete_unused_plugin(self):
        self.create_cluster()
        resp = self.env.create_plugin(api=True)
        with mock.patch.object(PluginPackageFP, 'remove'):
            del_resp = self.delete_plugin(resp.json['id'])
        self.assertEqual(del_resp.status_code, 204)

    def test_no_delete_of_used_plugin(self):
        resp = self.env.create_plugin(api=True)
        plugin = objects.Plugin.get_by_uid(resp.json['id'])
        cluster = self.create_cluster()
        enable_resp = self.enable_plugin(cluster, plugin.name, plugin.id)
        self.assertEqual(enable_resp.status_code, 200)
        del_resp = self.delete_plugin(resp.json['id'], expect_errors=True)
        self.assertEqual(del_resp.status_code, 400)

    def test_update_plugin(self):
        resp = self.env.create_plugin(api=True)
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
        self.env.create_plugin(api=True)
        cluster = self.create_cluster()
        default_attributes = self.default_attributes(cluster)
        self.assertIn(self.sample_plugin['name'],
                      default_attributes.json_body['editable'])

    def test_attributes_after_plugin_is_created(self):
        self.env.create_plugin(
            api=True,
            attributes_metadata={
                "attributes": {
                    "attr_text": {
                        "value": "value",
                        "type": "text",
                        "description": "description",
                        "weight": 25,
                        "label": "label"}}})
        cluster = self.create_cluster()
        editable = self.default_attributes(cluster).json_body['editable']
        self.assertIn(
            'attr_text',
            editable[self.sample_plugin['name']]['metadata']['versions'][0]
        )

    def test_plugins_multiversioning(self):
        def create_with_version(plugin_version):
            response = self.env.create_plugin(
                api=True,
                name='multiversion_plugin',
                version=plugin_version
            )
            return response.json_body['id']

        def get_num_enabled(cluster_id):
            return objects.ClusterPlugin.get_enabled(cluster_id).count()

        def get_enabled_version(cluster_id):
            plugin = objects.ClusterPlugin.get_enabled(cluster_id).first()
            return plugin.version

        plugin_ids = []
        for version in ['1.0.0', '2.0.0', '0.0.1']:
            plugin_ids.append(create_with_version(version))

        cluster = self.create_cluster()
        self.assertEqual(get_num_enabled(cluster.id), 0)

        self.enable_plugin(cluster, 'multiversion_plugin', plugin_ids[1])
        self.assertEqual(get_num_enabled(cluster.id), 1)
        self.assertEqual(get_enabled_version(cluster.id), '2.0.0')

        # Create new plugin after environment is created
        plugin_ids.append(create_with_version('5.0.0'))
        self.assertEqual(len(cluster.plugins), 4)
        self.assertEqual(get_num_enabled(cluster.id), 1)
        self.assertEqual(get_enabled_version(cluster.id), '2.0.0')

        self.enable_plugin(cluster, 'multiversion_plugin', plugin_ids[3])
        self.assertEqual(get_num_enabled(cluster.id), 1)
        self.assertEqual(get_enabled_version(cluster.id), '5.0.0')

        self.disable_plugin(cluster, 'multiversion_plugin')
        self.assertEqual(get_num_enabled(cluster.id), 0)

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
        resp = self.env.create_plugin(api=True, **old_version_plugin)
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
        resp = self.env.create_plugin(api=True, **new_version_plugin_1)
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
        resp = self.env.create_plugin(api=True, **new_version_plugin_2)
        self.assertEqual(resp.status_code, 201)
        plugin_ids.append(resp.json['id'])

        return plugin_ids

    def test_install_uploaded_plugin_fp(self):
        with mock.patch.object(PluginPackageFP, 'get_metadata') as meta_mock:
            meta_mock.return_value = self.env.get_default_plugin_metadata(
                name='fake_plugin', version='1.0.0', package_version='1.0.0')
            with mock.patch.object(PluginPackageFP, 'install'):
                resp = self.upload_plugin(self.plugin_fp_old)
                self.assertEqual(resp.json['action'], 'installed')

    def test_install_uploaded_plugin_rpm(self):
        with mock.patch.object(PluginPackageRPM, 'get_metadata') as meta_mock:
            meta_mock.return_value = self.env.get_default_plugin_metadata(
                name='fake_plugin', version='2.0.0', package_version='4.0.0')
            with mock.patch.object(PluginPackageRPM, 'install'):
                resp = self.upload_plugin(self.plugin_rpm_old)
                self.assertEqual(resp.json['action'], 'installed')

    def test_reinstall_uploaded_plugin_fp(self):
        self.env.create_plugin(api=True, name='fake_plugin', version='1.0.0',
                               package_version='1.0.0')
        with mock.patch.object(PluginPackageFP, 'get_metadata') as meta_mock:
            meta_mock.return_value = self.env.get_default_plugin_metadata(
                name='fake_plugin', version='1.0.0', package_version='1.0.0')

            resp = self.upload_plugin(self.plugin_fp_old, expect_errors=True)
            self.assertEqual(resp.status_code, 409)

            with mock.patch.object(PluginPackageFP, 'reinstall'):
                resp = self.upload_plugin(self.plugin_fp_old, force=True)
                self.assertEqual(resp.json['action'], 'reinstalled')

    def test_reinstall_uploaded_plugin_rpm(self):
        self.env.create_plugin(api=True, name='fake_plugin', version='2.0.0',
                               package_version='4.0.0')
        with mock.patch.object(PluginPackageRPM, 'get_metadata') as meta_mock:
            meta_mock.return_value = self.env.get_default_plugin_metadata(
                name='fake_plugin', version='2.0.0', package_version='4.0.0')

            resp = self.upload_plugin(self.plugin_rpm_old, expect_errors=True)
            self.assertEqual(resp.status_code, 409)

            with mock.patch.object(PluginPackageRPM, 'reinstall'):
                resp = self.upload_plugin(self.plugin_rpm_old, force=True)
                self.assertEqual(resp.json['action'], 'reinstalled')

    def test_upgrade_uploaded_plugin_fp(self):
        self.env.create_plugin(api=True, name='fake_plugin', version='1.0.0',
                               package_version='1.0.0')
        with mock.patch.object(PluginPackageFP, 'get_metadata') as meta_mock:
            meta_mock.return_value = self.env.get_default_plugin_metadata(
                name='fake_plugin', version='1.0.3', package_version='1.0.0')
            resp = self.upload_plugin(self.plugin_fp_new, expect_errors=True)
            self.assertEqual(resp.status_code, 406)

    def test_upgrade_uploaded_plugin_rpm(self):
        self.env.create_plugin(api=True, name='fake_plugin', version='2.0.0',
                               package_version='4.0.0')
        with mock.patch.object(PluginPackageRPM, 'get_metadata') as meta_mock:
            meta_mock.return_value = self.env.get_default_plugin_metadata(
                name='fake_plugin', version='2.0.1', package_version='4.0.0')
            with mock.patch.object(PluginPackageRPM, 'upgrade'):
                resp = self.upload_plugin(self.plugin_rpm_new)
                self.assertEqual(resp.json['action'], 'upgraded')

    def test_downgrade_uploaded_plugin_fp(self):
        self.env.create_plugin(api=True, name='fake_plugin', version='1.0.3',
                               package_version='1.0.0')
        with mock.patch.object(PluginPackageFP, 'get_metadata') as meta_mock:
            meta_mock.return_value = self.env.get_default_plugin_metadata(
                name='fake_plugin', version='1.0.0', package_version='1.0.0')
            resp = self.upload_plugin(self.plugin_fp_old, expect_errors=True)
            self.assertEqual(resp.status_code, 406)

    def test_downgrade_uploaded_plugin_rpm(self):
        self.env.create_plugin(api=True, name='fake_plugin', version='2.0.1',
                               package_version='4.0.0')
        with mock.patch.object(PluginPackageRPM, 'get_metadata') as meta_mock:
            meta_mock.return_value = self.env.get_default_plugin_metadata(
                name='fake_plugin', version='2.0.0', package_version='4.0.0')
            with mock.patch.object(PluginPackageRPM, 'downgrade'):
                resp = self.upload_plugin(self.plugin_rpm_old)
                self.assertEqual(resp.json['action'], 'downgraded')


class TestPrePostHooks(BasePluginTest):

    def setUp(self):
        super(TestPrePostHooks, self).setUp()

        self._requests_mock = mock.patch(
            'nailgun.utils.debian.requests.get',
            return_value=mock.Mock(text='Archive: test'))
        self._requests_mock.start()

        resp = self.env.create_plugin(api=True, tasks=self.TASKS_CONFIG)
        self.plugin = adapters.wrap_plugin(
            objects.Plugin.get_by_uid(resp.json['id']))
        self.cluster = self.create_cluster([
            {'roles': ['controller'], 'pending_addition': True},
            {'roles': ['compute'], 'pending_addition': True}]
        )
        objects.Cluster.prepare_for_deployment(self.cluster)

        self.enable_plugin(
            self.cluster, self.sample_plugin['name'], resp.json['id']
        )

    def tearDown(self):
        self._requests_mock.stop()
        super(TestPrePostHooks, self).tearDown()

    def test_generate_pre_hooks_for_legacy_env(self):
        resp = self.get_pre_hooks(self.cluster)
        self.assertEqual(200, resp.status_code)
        tasks = resp.json
        plugins_tasks = [t for t in tasks if t.get('diagnostic_name')]
        upload_file = [t for t in plugins_tasks if t['type'] == 'upload_file']
        rsync = [t for t in plugins_tasks if t['type'] == 'sync']
        cmd_tasks = [t for t in plugins_tasks if t['type'] == 'shell']
        self.assertEqual(len(upload_file), 2)
        self.assertEqual(len(rsync), 1)
        self.assertEqual(len(cmd_tasks), 2)
        for t in plugins_tasks:
            # should uid be a string
            self.assertEqual(
                sorted(t['uids']), sorted([n.uid for n in self.cluster.nodes]))
            # diagnostic name is present only for plugin tasks
            self.assertEqual(t['diagnostic_name'], self.plugin.full_name)
        apt_update = [t for t in cmd_tasks
                      if u'apt-get update' in t['parameters']['cmd']]
        self.assertEqual(len(apt_update), 1)

    def test_generate_post_hooks_for_legacy_env(self):
        resp = self.get_post_hooks(self.cluster)
        self.assertEqual(200, resp.status_code)
        tasks = resp.json
        self.assertEqual(len(tasks), 1)
        task = tasks[0]
        controller_id = [n.uid for n in self.cluster.nodes
                         if 'controller' in n.roles]
        self.assertEqual(controller_id, task['uids'])
        self.assertEqual(task['diagnostic_name'], self.plugin.full_name)

    def test_generate_hooks_is_not_supported_since_90(self):
        self.env.create(
            nodes_kwargs=[
                {'roles': ['controller'], 'pending_addition': True},
                {'roles': ['compute'], 'pending_addition': True},
                {'roles': ['cinder'], 'pending_addition': True}],
            release_kwargs={
                'version': 'mitaka-9.0',
                'operating_system': consts.RELEASE_OS.ubuntu
            }
        )
        resp = self.get_pre_hooks(self.env.clusters[-1])
        self.assertEqual(405, resp.status_code)
        resp = self.get_post_hooks(self.env.clusters[-1])
        self.assertEqual(405, resp.status_code)


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
            ]
        }
        resp = self.env.create_plugin(sample=sample, api=True)
        self.assertEqual(resp.status_code, 201)

    def test_releases_not_provided(self):
        sample = {
            'name': 'test_name',
            'version': '0.1.1',
            'fuel_version': ['6.0'],
            'title': 'Test plugin',
            'package_version': '1.0.0'
        }
        resp = self.env.create_plugin(
            sample=sample, api=True, expect_errors=True)
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
        resp = self.env.create_plugin(
            sample=sample, api=True, expect_errors=True)
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
        resp = self.env.create_plugin(
            sample=sample, api=True, expect_errors=True)
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
        resp = self.env.create_plugin(
            sample=sample, api=True, expect_errors=True)
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
