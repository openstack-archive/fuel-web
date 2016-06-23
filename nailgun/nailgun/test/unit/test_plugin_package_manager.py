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

import mock

from nailgun import consts
from nailgun import errors
from nailgun.objects import Plugin
from nailgun.settings import settings
from nailgun.test import base

from nailgun.plugins.package_manager.base import BasePluginPackage
from nailgun.plugins.package_manager import manager
from nailgun.plugins.package_manager.package_fp import PluginPackageFP
from nailgun.plugins.package_manager.package_rpm import PluginPackageRPM


class BasePluginPackageTestCase(base.BaseTestCase):

    def setUp(self):
        super(BasePluginPackageTestCase, self).setUp()
        self.package = None  # should be overridden
        self.dir = settings.PLUGINS_PATH
        self.path = '/tmp/plugin/path'
        self.name = 'plugin_name'
        self.version = '0.0.1'
        self.metadata = """
        name: 'plugin_name'
        version: '0.0.1'
        """


class TestBasePluginPackage(BasePluginPackageTestCase):

    def setUp(self):
        super(TestBasePluginPackage, self).setUp()
        self.package = BasePluginPackage

    def test_check_package_version(self):
        package_version = '2.5.1'
        self.assertTrue(self.package.check_package_version(
            package_version, '1.0.0', '3.0.0'))
        self.assertTrue(self.package.check_package_version(
            package_version, '2.5.1', '3.0.0'))
        self.assertTrue(self.package.check_package_version(
            package_version, '2.0.0'))
        self.assertFalse(self.package.check_package_version(
            package_version, '2.5.0', '2.5.1'))
        self.assertFalse(self.package.check_package_version(
            package_version, '2.7.0', '3.0.0'))
        self.assertFalse(self.package.check_package_version(
            package_version, '2.0.0', '2.5.0'))

    def test_get_major_version(self):
        pairs = [
            ('1.2.3', '1.2'),
            ('123456789.123456789.12121', '123456789.123456789'),
            ('1.2', '1.2')
        ]
        for arg, expected in pairs:
            self.assertEqual(self.package.get_major_version(arg), expected)


class TestPluginPackageFP(BasePluginPackageTestCase):

    def setUp(self):
        super(TestPluginPackageFP, self).setUp()
        self.package = PluginPackageFP

    @mock.patch('nailgun.plugins.package_manager.package_fp.tarfile')
    def test_install(self, tar_mock):
        tar_obj = mock.MagicMock()
        tar_mock.open.return_value = tar_obj

        self.package.install(self.path)

        tar_obj.extractall.assert_called_once_with(self.dir)
        tar_obj.close.assert_called_once_with()

    @mock.patch.object(PluginPackageFP, 'install')
    @mock.patch.object(PluginPackageFP, 'remove')
    @mock.patch.object(PluginPackageFP, 'get_metadata')
    def test_reinstall(self, meta_mock, remove_mock, install_mock):
        meta_mock.return_value = {'name': self.name, 'version': self.version}

        self.package.reinstall(self.path)

        meta_mock.assert_called_once_with(self.path)
        remove_mock.assert_called_once_with(self.name, self.version)
        install_mock.assert_called_once_with(self.path)

    def test_upgrade(self):
        self.assertRaisesWithMessage(
            errors.UpgradeIsNotSupported,
            "Upgrade action is not supported for plugins with package "
            "version '1.0.0'. You must use newer plugin format.",
            self.package.upgrade, 'some_string'
        )

    def test_downgrade(self):
        self.assertRaisesWithMessage(
            errors.DowngradeIsNotSupported,
            "Downgrade action is not supported for plugins with package "
            "version '1.0.0'. You must use newer plugin format.",
            self.package.downgrade, 'some_string'
        )

    @mock.patch('nailgun.plugins.package_manager.package_fp.shutil.rmtree')
    def test_remove(self, rmtree_mock):
        self.package.remove(self.name, self.version)

        rmtree_mock.assert_called_once_with('{}/{}-{}'.format(
            self.dir, self.name, self.version))

    def test_is_compatible(self):
        versions_valid = ('1.0.0', '1.3.0')
        versions_invalid = ('0.0.1', '2.0.0')

        for arg in versions_valid:
            self.assertTrue(self.package.is_compatible(arg))
        for arg in versions_invalid:
            self.assertFalse(self.package.is_compatible(arg))

    @mock.patch('nailgun.plugins.package_manager.package_fp.tarfile')
    def test_get_metadata(self, tar_mock):
        tar_obj = mock.MagicMock()
        tar_mock.open.return_value = tar_obj
        tar_file = mock.MagicMock()
        tar_obj.getnames.return_value = [consts.PLUGIN_CONFIG_METADATA]
        tar_obj.extractfile.return_value = tar_file
        tar_file.read.return_value = self.metadata
        expected = {'name': self.name, 'version': self.version}

        self.assertDictEqual(self.package.get_metadata(self.path), expected)
        tar_obj.close.assert_called_once_with()


class TestPluginPackageRPM(BasePluginPackageTestCase):

    def setUp(self):
        super(TestPluginPackageRPM, self).setUp()
        self.package = PluginPackageRPM

    def test_is_compatible(self):
        versions_valid = ('2.0.0', '2.1.0', '5.0.0')
        versions_invalid = ('1.0.0',)

        for arg in versions_valid:
            self.assertTrue(self.package.is_compatible(arg))
        for arg in versions_invalid:
            self.assertFalse(self.package.is_compatible(arg))

    @mock.patch('nailgun.plugins.package_manager.package_rpm.utils.exec_cmd')
    def test_get_metadata(self, cmd_mock):
        cmd_mock.return_value = self.metadata
        expected = {'name': self.name, 'version': self.version}
        self.assertDictEqual(self.package.get_metadata(self.path), expected)


class BasePackageManagerTestCase(base.BaseTestCase):

    def setUp(self):
        super(BasePackageManagerTestCase, self).setUp()
        self.manager = None  # should be overridden
        self.path_v1 = '/tmp/plugin_name-1.2.0.fp'
        self.path_v2 = '/tmp/plugin_name-1.2-1.2.0-1.noarch.rpm'

    def _create_test_plugins(self):
        plugins_attrs = [
            {'name': 'single_plugin', 'version': '0.1.5'},
            {'name': 'multiversion_plugin', 'version': '1.0.0'},
            {'name': 'multiversion_plugin', 'version': '2.0.0'},
            {'name': 'multiversion_plugin', 'version': '2.1.0',
             'package_version': '2.0.0'},
        ]
        plugin_ids = []
        for attrs in plugins_attrs:
            metadata = self.env.get_default_plugin_metadata(**attrs)
            plugin = Plugin.create(metadata)
            plugin_ids.append(plugin.id)

        return plugin_ids


class TestBasePackageManager(BasePackageManagerTestCase):

    def setUp(self):
        super(TestBasePackageManager, self).setUp()
        self.manager = manager.BasePackageManager

    def test_get_plugins_by(self):
        ids = self._create_test_plugins()
        plugins = self.manager._get_plugins_by(name='single_plugin')
        self.assertEqual(len(plugins), 1)
        plugins = self.manager._get_plugins_by(name='multiversion_plugin')
        self.assertEqual(len(plugins), 3)
        plugins = self.manager._get_plugins_by(name='multiversion_plugin',
                                               version='2.0.0')
        self.assertEqual(len(plugins), 1)
        self.assertEqual(plugins[0]['id'], ids[2])
        self.assertEqual(plugins[0]['version'], '2.0.0')


class TestPackageInstallManager(BasePackageManagerTestCase):

    def setUp(self):
        super(TestPackageInstallManager, self).setUp()
        self.manager = manager.PackageInstallManager

    def _process(self, action, path, force=False, mock_action=True):
        with mock.patch.object(self.manager, '_get_params_of_uploaded_file',
                               return_value=(path, force)):
            pm = self.manager()
            if not mock_action:
                return pm.process_file()
            with mock.patch.object(pm.handler, action):
                return pm.process_file()

    @mock.patch.object(PluginPackageRPM, 'get_metadata')
    @mock.patch.object(PluginPackageFP, 'get_metadata')
    def test_get_package_handler(self, meta_mock_fp, meta_mock_rpm):
        meta_mock_fp.return_value = self.env.get_default_plugin_metadata(
            package_version='1.0.0')
        handler = self.manager._get_package_handler(self.path_v1)
        self.assertEqual(handler, PluginPackageFP)

        meta_mock_rpm.return_value = self.env.get_default_plugin_metadata(
            package_version='2.0.0')
        handler = self.manager._get_package_handler(self.path_v2)
        self.assertEqual(handler, PluginPackageRPM)

        self.assertRaisesWithMessage(
            errors.PackageFormatIsNotCompatible,
            "Plugin 'plugin_name-1.2.0.deb' has unsupported format 'deb'",
            self.manager._get_package_handler, '/tmp/plugin_name-1.2.0.deb'
        )

    @mock.patch.object(PluginPackageFP, 'get_metadata')
    def test_install_v1(self, meta_mock):
        meta_mock.return_value = self.env.get_default_plugin_metadata(
            package_version='1.0.0')
        self.assertEqual(self._process('install', self.path_v1), 'installed')

    @mock.patch.object(PluginPackageFP, 'get_metadata')
    def test_reinstall_v1(self, meta_mock):
        self._create_test_plugins()
        meta_mock.return_value = self.env.get_default_plugin_metadata(
            name='single_plugin', version='0.1.5', package_version='1.0.0')
        self.assertRaisesWithMessage(
            errors.AlreadyExists,
            "Plugin with the same version already exists",
            self._process, 'reinstall', self.path_v1
        )
        self.assertEqual(self._process('reinstall', self.path_v1, force=True),
                         'reinstalled')

    @mock.patch.object(PluginPackageRPM, 'get_metadata')
    def test_install_v2(self, meta_mock):
        meta_mock.return_value = self.env.get_default_plugin_metadata(
            package_version='2.0.0')
        self.assertEqual(self._process('install', self.path_v2), 'installed')

    @mock.patch.object(PluginPackageRPM, 'get_metadata')
    def test_reinstall_v2(self, meta_mock):
        self._create_test_plugins()
        meta_mock.return_value = self.env.get_default_plugin_metadata(
            name='single_plugin', version='0.1.5', package_version='2.0.0')
        self.assertRaisesWithMessage(
            errors.AlreadyExists,
            "Plugin with the same version already exists",
            self._process, 'reinstall', self.path_v2
        )
        self.assertEqual(self._process('reinstall', self.path_v2, force=True),
                         'reinstalled')

    @mock.patch.object(PluginPackageFP, 'get_metadata')
    def test_upgrade_v1(self, meta_mock):
        self._create_test_plugins()
        meta_mock.return_value = self.env.get_default_plugin_metadata(
            name='single_plugin', version='0.1.7', package_version='1.0.0')
        self.assertRaisesWithMessage(
            errors.UpgradeIsNotSupported,
            "Upgrade action is not supported for plugins with package "
            "version '1.0.0'. You must use newer plugin format.",
            self._process, 'upgrade', self.path_v1, mock_action=False
        )

    @mock.patch.object(PluginPackageFP, 'get_metadata')
    def test_downgrade_v1(self, meta_mock):
        self._create_test_plugins()
        meta_mock.return_value = self.env.get_default_plugin_metadata(
            name='single_plugin', version='0.1.3', package_version='1.0.0')
        self.assertRaisesWithMessage(
            errors.DowngradeIsNotSupported,
            "Downgrade action is not supported for plugins with package "
            "version '1.0.0'. You must use newer plugin format.",
            self._process, 'downgrade', self.path_v1, mock_action=False
        )

    @mock.patch.object(PluginPackageRPM, 'get_metadata')
    def test_upgrade_v2(self, meta_mock):
        self._create_test_plugins()
        meta_mock.return_value = self.env.get_default_plugin_metadata(
            name='single_plugin', version='0.1.7', package_version='2.0.0')
        self.assertEqual(self._process('upgrade', self.path_v2), 'upgraded')

    @mock.patch.object(PluginPackageRPM, 'get_metadata')
    def test_downgrade_v2(self, meta_mock):
        self._create_test_plugins()
        meta_mock.return_value = self.env.get_default_plugin_metadata(
            name='single_plugin', version='0.1.3', package_version='2.0.0')
        self.assertEqual(self._process('downgrade', self.path_v2),
                         'downgraded')


class TestPackageRemoveManager(BasePackageManagerTestCase):

    def setUp(self):
        super(TestPackageRemoveManager, self).setUp()
        self.manager = manager.PackageRemoveManager
        self.dir = settings.PLUGINS_PATH

    def test_get_package_handler(self):
        handler = self.manager._get_package_handler('1.0.0')
        self.assertEqual(handler, PluginPackageFP)
        handler = self.manager._get_package_handler('2.0.0')
        self.assertEqual(handler, PluginPackageRPM)
        self.assertRaisesWithMessage(
            errors.PackageVersionIsNotCompatible,
            "Package version is not compatible",
            self.manager._get_package_handler, '0.0.1'
        )

    def test_set_handler(self):
        self._create_test_plugins()

        pm = self.manager('multiversion_plugin', '2.0.0')
        self.assertEqual(pm.handler, PluginPackageFP)

        pm = self.manager('multiversion_plugin', '2.0.0',
                          package_version='2.0.0')
        self.assertEqual(pm.handler, PluginPackageRPM)

        pm = self.manager('multiversion_plugin', '2.1.0')
        self.assertEqual(pm.handler, PluginPackageRPM)

        pm = self.manager('multiversion_plugin', '2.1.0',
                          package_version='1.0.0')
        self.assertEqual(pm.handler, PluginPackageFP)

        self.assertRaisesWithMessage(
            errors.ObjectNotFound,
            "Cannot define suitable handler for plugin package.",
            self.manager, 'multiversion_plugin', '3.0.0'
        )

    @mock.patch('nailgun.plugins.package_manager.package_fp.shutil.rmtree')
    def test_remove_v1(self, rmtree_mock):
        self._create_test_plugins()
        pm = self.manager('multiversion_plugin', '2.0.0')
        pm.remove()
        rmtree_mock.assert_called_once_with('{}/{}-{}'.format(
            self.dir, pm.name, pm.version))

    def test_remove_v2(self):
        self._create_test_plugins()
        pm = self.manager('multiversion_plugin', '2.1.0')
        with mock.patch.object(pm.handler, 'remove'):
            pm.remove()
            pm.handler.remove.assert_called_once_with(pm.name, pm.version)
