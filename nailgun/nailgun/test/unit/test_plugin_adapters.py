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

import abc
import os

import mock
import six
import yaml

from nailgun import consts
from nailgun.db import db
from nailgun.errors import errors
from nailgun.expression import Expression
from nailgun.objects import ClusterPlugins
from nailgun.objects import Plugin
from nailgun.plugins import adapters
from nailgun.settings import settings
from nailgun.test import base


@six.add_metaclass(abc.ABCMeta)
class TestPluginBase(base.BaseTestCase):

    # Prevent running tests in base class
    __test__ = False
    # Should be overridden in child
    package_version = None

    def setUp(self):
        super(TestPluginBase, self).setUp()
        self.plugin_metadata = self.env.get_default_plugin_metadata(
            package_version=self.package_version,
            roles_metadata={
                'role_x': {
                    'name': 'Role X',
                    'description': 'Role X is ...',
                },
                'role_y': {
                    'name': 'Role Y',
                    'description': 'Role Y is ...',
                    'restrictions': []
                },
                'role_z': {
                    'name': 'Role Z',
                    'description': 'Role Z is ...',
                    'restrictions': [
                        'settings:some.stuff.value == false'
                    ]
                }
            }
        )
        self.plugin = Plugin.create(self.plugin_metadata)
        self.env.create(
            cluster_kwargs={'mode': consts.CLUSTER_MODES.multinode},
            release_kwargs={
                'version': '2015.1-8.0',
                'operating_system': 'Ubuntu',
                'modes': [consts.CLUSTER_MODES.multinode,
                          consts.CLUSTER_MODES.ha_compact]})
        self.cluster = self.env.clusters[0]
        self.plugin_adapter = adapters.wrap_plugin(self.plugin)
        self.env_config = self.env.get_default_plugin_env_config()
        self.get_config = lambda *args: mock.mock_open(
            read_data=yaml.dump(self.env_config))()

        db().flush()

    def test_plugin_release_versions(self):
        """Should return set of all versions this plugin is applicable to"""
        self.assertEqual(
            self.plugin_adapter.plugin_release_versions,
            set(['2014.2-6.0', '2015.1-8.0'])
        )

    def test_full_name(self):
        """Plugin full name should be made from name and version."""
        self.assertEqual(
            self.plugin_adapter.full_name,
            '{0}-{1}'.format(self.plugin.name, self.plugin.version))

    def test_get_release_info(self):
        """Should return 1st plugin release info which matches release"""
        self.cluster.release.version = '2014.2.2-6.0.1'
        release = self.plugin_adapter.get_release_info(self.cluster.release)
        self.assertEqual(release, self.plugin_metadata['releases'][0])

    def test_plugin_role_restrictions_normalization(self):
        # checking presence and syntax of generated restriction
        for role, meta in six.iteritems(
                self.plugin_adapter.normalized_roles_metadata):
            for condition in meta['restrictions']:
                self.assertNotRaises(
                    errors.ParseError,
                    lambda: Expression(
                        condition,
                        {'settings': self.cluster.attributes.editable},
                        strict=False
                    ).evaluate()
                )

    def test_slaves_scripts_path(self):
        expected = settings.PLUGINS_SLAVES_SCRIPTS_PATH.format(
            plugin_name=self.plugin_adapter.path_name)
        self.assertEqual(expected, self.plugin_adapter.slaves_scripts_path)

    @mock.patch('nailgun.plugins.adapters.glob')
    def test_repo_files(self, glob_mock):
        self.plugin_adapter.repo_files(self.cluster)
        expected_call = os.path.join(
            settings.PLUGINS_PATH,
            self.plugin_adapter.path_name,
            'repositories/ubuntu',
            '*')
        glob_mock.glob.assert_called_once_with(expected_call)

    @mock.patch('nailgun.plugins.adapters.urljoin')
    def test_repo_url(self, murljoin):
        self.plugin_adapter.repo_url(self.cluster)
        repo_base = settings.PLUGINS_REPO_URL.format(
            master_ip=settings.MASTER_IP,
            plugin_name=self.plugin_adapter.path_name)
        murljoin.assert_called_once_with(repo_base, 'repositories/ubuntu')

    def test_master_scripts_path(self):
        base_url = settings.PLUGINS_SLAVES_RSYNC.format(
            master_ip=settings.MASTER_IP,
            plugin_name=self.plugin_adapter.path_name)

        expected = '{0}{1}'.format(base_url, 'deployment_scripts/')
        self.assertEqual(
            expected, self.plugin_adapter.master_scripts_path(self.cluster))

    def test_get_metadata(self):
        plugin_metadata = self.env.get_default_plugin_metadata()
        attributes_metadata = self.env.get_default_plugin_env_config()
        tasks = self.env.get_default_plugin_tasks()

        mocked_metadata = {
            self._find_path('metadata'): plugin_metadata,
            self._find_path('environment_config'): attributes_metadata,
            self._find_path('tasks'): tasks
        }

        with mock.patch.object(
                self.plugin_adapter, '_load_config') as load_conf:
            load_conf.side_effect = lambda key: mocked_metadata[key]
            Plugin.update(self.plugin, self.plugin_adapter.get_metadata())

            for key, val in six.iteritems(plugin_metadata):
                self.assertEqual(
                    getattr(self.plugin, key), val)

    def test_get_deployment_tasks(self):
        self.plugin_adapter.deployment_tasks = \
            self.env.get_default_plugin_deployment_tasks()

        depl_task = self.plugin_adapter.deployment_tasks[0]
        self.assertEqual(depl_task['parameters'].get('cwd'),
                         self.plugin_adapter.slaves_scripts_path)

    def test_get_deployment_tasks_params_not_changed(self):
        expected = 'path/to/some/dir'
        self.plugin_adapter.deployment_tasks = \
            self.env.get_default_plugin_deployment_tasks(
                parameters={'cwd': expected}
            )
        depl_task = self.plugin_adapter.deployment_tasks[0]
        self.assertEqual(depl_task['parameters'].get('cwd'), expected)

    def _find_path(self, config_name):
        return '{0}.yaml'.format(config_name)


class TestPluginV1(TestPluginBase):

    __test__ = True
    package_version = '1.0.0'

    def test_primary_added_for_version(self):
        with mock.patch.object(
                self.plugin_adapter, '_load_config') as load_conf:
            load_conf.return_value = [{'role': ['controller']}]

            tasks = self.plugin_adapter._load_tasks()
            self.assertItemsEqual(
                tasks[0]['role'], ['primary-controller', 'controller'])

    def test_path_name(self):
        self.assertEqual(
            self.plugin_adapter.path_name,
            self.plugin_adapter.full_name)


class TestPluginV2(TestPluginBase):

    __test__ = True
    package_version = '2.0.0'

    def test_role_not_changed_for_version(self):
        with mock.patch.object(
                self.plugin_adapter, '_load_config') as load_conf:
            load_conf.return_value = [{'role': ['controller']}]

            tasks = self.plugin_adapter._load_tasks()
            self.assertItemsEqual(
                tasks[0]['role'], ['controller'])

    def test_path_name(self):
        self.assertEqual(
            self.plugin_adapter.path_name,
            '{0}-{1}'.format(self.plugin.name, '0.1'))


class TestPluginV3(TestPluginBase):

    __test__ = True
    package_version = '3.0.0'

    def test_get_metadata(self):
        self.maxDiff = None
        plugin_metadata = self.env.get_default_plugin_metadata()
        attributes_metadata = self.env.get_default_plugin_env_config()
        roles_metadata = self.env.get_default_plugin_node_roles_config()
        volumes_metadata = self.env.get_default_plugin_volumes_config()
        network_roles_metadata = self.env.get_default_network_roles_config()
        deployment_tasks = self.env.get_default_plugin_deployment_tasks()
        tasks = self.env.get_default_plugin_tasks()

        mocked_metadata = {
            self._find_path('metadata'): plugin_metadata,
            self._find_path('environment_config'): attributes_metadata,
            self._find_path('node_roles'): roles_metadata,
            self._find_path('volumes'): volumes_metadata,
            self._find_path('network_roles'): network_roles_metadata,
            self._find_path('deployment_tasks'): deployment_tasks,
            self._find_path('tasks'): tasks,
        }

        with mock.patch.object(
                self.plugin_adapter, '_load_config') as load_conf:
            load_conf.side_effect = lambda key: mocked_metadata[key]
            Plugin.update(self.plugin, self.plugin_adapter.get_metadata())

            for key, val in six.iteritems(plugin_metadata):
                self.assertEqual(
                    getattr(self.plugin, key), val)

            self.assertEqual(
                self.plugin.attributes_metadata,
                attributes_metadata['attributes'])
            self.assertEqual(
                self.plugin.roles_metadata, roles_metadata)
            self.assertEqual(
                self.plugin.volumes_metadata, volumes_metadata)
            self.assertEqual(
                self.plugin.tasks, tasks)
            # deployment tasks returning all non-defined fields, so check
            # should differ from JSON-stored fields
            for k, v in six.iteritems(deployment_tasks[0]):
                # this field is updated by plugin adapter
                if k is 'parameters':
                    v.update({
                        'cwd': '/etc/fuel/plugins/testing_plugin-0.1/'
                    })
                self.assertEqual(self.plugin_adapter.deployment_tasks[0][k], v)


class TestPluginV4(TestPluginBase):

    __test__ = True
    package_version = '4.0.0'

    def test_get_metadata(self):
        plugin_metadata = self.env.get_default_plugin_metadata()
        attributes_metadata = self.env.get_default_plugin_env_config()
        roles_metadata = self.env.get_default_plugin_node_roles_config()
        volumes_metadata = self.env.get_default_plugin_volumes_config()
        network_roles_metadata = self.env.get_default_network_roles_config()
        deployment_tasks = self.env.get_default_plugin_deployment_tasks()
        tasks = self.env.get_default_plugin_tasks()
        components_metadata = self.env.get_default_components()

        mocked_metadata = {
            self._find_path('metadata'): plugin_metadata,
            self._find_path('environment_config'): attributes_metadata,
            self._find_path('node_roles'): roles_metadata,
            self._find_path('volumes'): volumes_metadata,
            self._find_path('network_roles'): network_roles_metadata,
            self._find_path('deployment_tasks'): deployment_tasks,
            self._find_path('tasks'): tasks,
            self._find_path('components'): components_metadata
        }

        with mock.patch.object(
                self.plugin_adapter, '_load_config') as load_conf:
            load_conf.side_effect = lambda key: mocked_metadata[key]
            Plugin.update(self.plugin, self.plugin_adapter.get_metadata())

            for key, val in six.iteritems(plugin_metadata):
                self.assertEqual(
                    getattr(self.plugin, key), val)

            self.assertEqual(
                self.plugin.attributes_metadata,
                attributes_metadata['attributes'])
            self.assertEqual(
                self.plugin.roles_metadata, roles_metadata)
            self.assertEqual(
                self.plugin.volumes_metadata, volumes_metadata)
            self.assertEqual(
                self.plugin.tasks, tasks)
            self.assertEqual(
                self.plugin.components_metadata, components_metadata)
            # deployment tasks returning all non-defined fields, so check
            # should differ from JSON-stored fields
            for k, v in six.iteritems(deployment_tasks[0]):
                # this field is updated by plugin adapter
                if k is 'parameters':
                    v.update({
                        'cwd': '/etc/fuel/plugins/testing_plugin-0.1/'
                    })
                self.assertEqual(self.plugin_adapter.deployment_tasks[0][k], v)


class TestClusterCompatibilityValidation(base.BaseTestCase):

    def setUp(self):
        super(TestClusterCompatibilityValidation, self).setUp()
        self.plugin = Plugin.create(self.env.get_default_plugin_metadata(
            releases=[{
                'version': '2014.2-6.0',
                'os': 'ubuntu',
                'mode': ['ha']}]))
        self.plugin_adapter = adapters.PluginAdapterV1(self.plugin)

    def cluster_mock(self, os, mode, version):
        release = mock.Mock(operating_system=os, version=version)
        cluster = mock.Mock(mode=mode, release=release)
        return cluster

    def validate_with_cluster(self, **kwargs):
        cluster = self.cluster_mock(**kwargs)
        return ClusterPlugins.is_compatible(cluster, self.plugin)

    def test_validation_ubuntu_ha(self):
        self.assertTrue(self.validate_with_cluster(
            os='Ubuntu',
            mode=consts.CLUSTER_MODES.ha_compact,
            version='2014.2-6.0'))

    def test_plugin_provided_ha_compact(self):
        self.assertTrue(self.validate_with_cluster(
            os='Ubuntu',
            mode=consts.CLUSTER_MODES.ha_compact,
            version='2014.2-6.0'))

    def test_not_existent_os(self):
        self.assertFalse(self.validate_with_cluster(
            os='Centos',
            mode=consts.CLUSTER_MODES.multinode,
            version='2014.2-6.0'))

    def test_version_fuel_mismatch(self):
        self.assertFalse(self.validate_with_cluster(
            os='Ubuntu',
            mode=consts.CLUSTER_MODES.ha_compact,
            version='2014.2-6.1'))

    def test_version_os_mismatch(self):
        self.assertFalse(self.validate_with_cluster(
            os='Ubuntu',
            mode=consts.CLUSTER_MODES.ha_compact,
            version='2014.3-6.1'))

    def test_validation_centos_multinode(self):
        self.assertFalse(self.validate_with_cluster(
            os='Ubuntu',
            mode=consts.CLUSTER_MODES.multinode,
            version='2014.2-6.0'))

    def test_validation_centos_different_minor_version(self):
        self.assertTrue(self.validate_with_cluster(
            os='Ubuntu',
            mode=consts.CLUSTER_MODES.ha_compact,
            version='2014.2.99-6.0.99'))
