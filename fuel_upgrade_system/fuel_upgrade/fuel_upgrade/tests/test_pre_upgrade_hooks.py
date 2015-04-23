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


import itertools
import os
import textwrap

import mock
import six

from fuel_upgrade.tests.base import BaseTestCase
from fuel_upgrade.tests.base import FakeFile

from fuel_upgrade.pre_upgrade_hooks.base import PreUpgradeHookBase
from fuel_upgrade.pre_upgrade_hooks.from_5_0_1_to_any_fix_host_system_repo \
    import FixHostSystemRepoHook
from fuel_upgrade.pre_upgrade_hooks.from_5_0_to_any_add_credentials \
    import AddCredentialsHook
from fuel_upgrade.pre_upgrade_hooks.from_5_0_to_any_fix_puppet_manifests \
    import FixPuppetManifests
from fuel_upgrade.pre_upgrade_hooks.from_5_0_to_any_sync_dns \
    import SyncDnsHook
from fuel_upgrade.pre_upgrade_hooks import PreUpgradeHookManager
from fuel_upgrade.pre_upgrade_hooks. \
    from_5_0_x_to_any_copy_openstack_release_versions \
    import CopyOpenstackReleaseVersions
from fuel_upgrade.pre_upgrade_hooks.from_5_1_to_any_add_keystone_credentials \
    import AddKeystoneCredentialsHook
from fuel_upgrade.pre_upgrade_hooks.from_5_1_to_any_ln_fuelweb_x86_64 \
    import AddFuelwebX8664LinkForUbuntu
from fuel_upgrade.pre_upgrade_hooks.from_6_0_to_any_add_dhcp_gateway \
    import AddDhcpGateway
from fuel_upgrade.pre_upgrade_hooks.from_6_0_to_any_add_monitord_credentials \
    import AddMonitordKeystoneCredentialsHook
from fuel_upgrade.pre_upgrade_hooks.from_6_0_to_any_copy_keys \
    import MoveKeysHook
from fuel_upgrade.pre_upgrade_hooks.from_any_to_6_1_dhcrelay_conf \
    import FixDhcrelayConf
from fuel_upgrade.pre_upgrade_hooks.from_any_to_6_1_dhcrelay_monitor \
    import FixDhcrelayMonitor
from fuel_upgrade.pre_upgrade_hooks.from_any_to_6_1_fix_version_in_supervisor \
    import SetFixedVersionInSupervisor
from fuel_upgrade.pre_upgrade_hooks.from_any_to_6_1_recreate_containers \
    import RecreateNailgunInPriveleged


class TestPreUpgradeHooksBase(BaseTestCase):

    HookClass = None

    def setUp(self):
        class Upgrader1(mock.MagicMock):
            pass

        class Upgrader2(mock.MagicMock):
            pass

        self.upgraders_cls = [Upgrader1, Upgrader2]
        self.upgraders = [upgrade_cls() for upgrade_cls in self.upgraders_cls]

    def get_hook(self, conf={}):
        config = self.fake_config

        for key, value in six.iteritems(conf):
            setattr(config, key, value)

        return self.HookClass(self.upgraders, config)


class TestAddCredentialsHook(TestPreUpgradeHooksBase):

    HookClass = AddCredentialsHook

    def setUp(self):
        super(TestAddCredentialsHook, self).setUp()
        self.additional_keys = [
            'astute',
            'cobbler',
            'mcollective',
            'postgres',
            'keystone',
            'FUEL_ACCESS']

    def test_is_required_returns_true(self):
        hook = self.get_hook({'astute': {}})
        self.assertTrue(hook.check_if_required())

    def test_is_required_returns_false(self):
        hook = self.get_hook({
            'astute': {
                'astute': {},
                'cobbler': {},
                'mcollective': {},
                'postgres': {},
                'keystone': {},
                'FUEL_ACCESS': {}}})

        self.assertFalse(hook.check_if_required())

    @mock.patch('fuel_upgrade.pre_upgrade_hooks.base.read_yaml_config')
    @mock.patch('fuel_upgrade.pre_upgrade_hooks.base.utils.copy_file')
    @mock.patch('fuel_upgrade.pre_upgrade_hooks.base.utils.save_as_yaml')
    def test_run(self,
                 utils_save_as_yaml_mock,
                 utils_copy_file_mock,
                 read_yaml_config_mock):
        file_key = 'this_key_was_here_before_upgrade'
        hook = self.get_hook({'astute': {file_key: file_key}})
        read_yaml_config_mock.return_value = hook.config.astute
        hook.run()

        utils_copy_file_mock.assert_called_once_with(
            '/etc/fuel/astute.yaml',
            '/etc/fuel/astute.yaml_0',
            overwrite=False)

        agrs = utils_save_as_yaml_mock.call_args
        self.assertEqual(agrs[0][0], '/etc/fuel/astute.yaml')

        # Check that the key which was in file
        # won't be overwritten
        self.additional_keys.append(file_key)
        # Check that all required keys are in method call
        self.assertTrue(all(
            key in self.additional_keys
            for key in agrs[0][1].keys()))


class TestAddFuelwebX8664LinkForUbuntu(TestPreUpgradeHooksBase):

    HookClass = AddFuelwebX8664LinkForUbuntu

    @mock.patch(
        'fuel_upgrade.pre_upgrade_hooks.from_5_1_to_any_ln_fuelweb_x86_64.'
        'utils.file_exists', side_effect=[True, False])
    def test_is_required_returns_true(self, file_exists_mock):
        hook = self.get_hook({'new_version': '6.0'})
        self.assertTrue(hook.check_if_required())

    @mock.patch(
        'fuel_upgrade.pre_upgrade_hooks.from_5_1_to_any_ln_fuelweb_x86_64.'
        'utils.file_exists', side_effect=[False, False])
    def test_is_required_returns_false_1(self, file_exists_mock):
        hook = self.get_hook({'new_version': '6.0'})
        self.assertFalse(hook.check_if_required())

    @mock.patch(
        'fuel_upgrade.pre_upgrade_hooks.from_5_1_to_any_ln_fuelweb_x86_64.'
        'utils.file_exists', side_effect=[True, True])
    def test_is_required_returns_false_2(self, file_exists_mock):
        hook = self.get_hook({'new_version': '6.0'})
        self.assertFalse(hook.check_if_required())

    @mock.patch(
        'fuel_upgrade.pre_upgrade_hooks.from_5_1_to_any_ln_fuelweb_x86_64.'
        'utils.symlink')
    def test_run(self, symlink_mock):
        hook = self.get_hook({'new_version': '6.0'})
        hook.run()

        self.called_once(symlink_mock)


class TestAddKeystoneCredentialsHook(TestPreUpgradeHooksBase):

    HookClass = AddKeystoneCredentialsHook

    def setUp(self):
        super(TestAddKeystoneCredentialsHook, self).setUp()
        self.keystone_keys = [
            'nailgun_user',
            'nailgun_password',
            'ostf_user',
            'ostf_password',
        ]

    def test_is_required_returns_true(self):
        hook = self.get_hook({})
        self.assertTrue(hook.check_if_required())

    def test_is_required_returns_false(self):
        hook = self.get_hook({
            'astute': {
                'keystone': {
                    'nailgun_user': '',
                    'nailgun_password': '',
                    'ostf_user': '',
                    'ostf_password': '',
                }
            }
        })

        self.assertFalse(hook.check_if_required())

    @mock.patch('fuel_upgrade.pre_upgrade_hooks.base.read_yaml_config')
    @mock.patch('fuel_upgrade.pre_upgrade_hooks.base.utils.copy_file')
    @mock.patch('fuel_upgrade.pre_upgrade_hooks.base.utils.save_as_yaml')
    def test_run(self,
                 utils_save_as_yaml_mock,
                 utils_copy_file_mock,
                 read_yaml_config_mock):
        file_key = 'this_key_was_here_before_upgrade'
        hook = self.get_hook({
            'astute': {
                'keystone': {file_key: file_key}}
        })
        read_yaml_config_mock.return_value = hook.config.astute
        hook.run()

        utils_copy_file_mock.assert_called_once_with(
            '/etc/fuel/astute.yaml',
            '/etc/fuel/astute.yaml_0',
            overwrite=False)

        agrs = utils_save_as_yaml_mock.call_args
        self.assertEqual(agrs[0][0], '/etc/fuel/astute.yaml')

        # Check that the key which was in
        self.keystone_keys.append(file_key)
        # Check that all required keys are in method call
        self.assertTrue(all(
            key in self.keystone_keys
            for key in agrs[0][1]['keystone'].keys()))


class TestSyncDnsHook(TestPreUpgradeHooksBase):

    HookClass = SyncDnsHook

    def setUp(self):
        super(TestSyncDnsHook, self).setUp()
        self.additional_keys = [
            'DNS_DOMAIN',
            'DNS_SEARCH']

    def test_is_required_returns_true(self):
        hook = self.get_hook({
            'astute': {
                'DNS_DOMAIN': 'veryunlikelydomain',
                'DNS_SEARCH': 'veryunlikelydomain'}})
        self.assertTrue(hook.check_if_required())

    def test_is_required_returns_false(self):
        hostname, sep, realdomain = os.uname()[1].partition('.')
        hook = self.get_hook({
            'astute': {
                'DNS_DOMAIN': realdomain,
                'DNS_SEARCH': realdomain}})

        self.assertFalse(hook.check_if_required())

    @mock.patch('fuel_upgrade.pre_upgrade_hooks.base.read_yaml_config')
    @mock.patch('fuel_upgrade.pre_upgrade_hooks.base.utils.copy_file')
    @mock.patch('fuel_upgrade.pre_upgrade_hooks.base.utils.save_as_yaml')
    def test_run(self,
                 utils_save_as_yaml_mock,
                 utils_copy_file_mock,
                 read_yaml_config):
        file_key = 'this_key_was_here_before_upgrade'
        hook = self.get_hook({'astute': {file_key: file_key}})
        read_yaml_config.return_value = hook.config.astute
        hook.run()

        utils_copy_file_mock.assert_called_once_with(
            '/etc/fuel/astute.yaml',
            '/etc/fuel/astute.yaml_0',
            overwrite=False)

        args = utils_save_as_yaml_mock.call_args
        self.assertEqual(args[0][0], '/etc/fuel/astute.yaml')

        # Check that the key which was in file
        # won't be overwritten
        self.additional_keys.append(file_key)
        # Check that all required keys are in method call
        self.assertTrue(all(
            key in self.additional_keys
            for key in args[0][1].keys()))


class TestFixPuppetManifestHook(TestPreUpgradeHooksBase):

    iterfiles_returns = [
        '/tmp/upgrade_path/config/5.0/modules/package/lib/puppet'
        '/provider/package/yum.rb',
        '/tmp/upgrade_path/config/5.0/manifests/centos-versions.yaml']

    def setUp(self):
        super(TestFixPuppetManifestHook, self).setUp()

        conf = self.fake_config
        conf.from_version = '5.0'

        self.hook = FixPuppetManifests(self.upgraders, conf)

    def test_is_required_returns_true(self):
        self.hook.config.from_version = '5.0'
        self.assertTrue(self.hook.check_if_required())

        self.hook.config.from_version = '5.0.1'
        self.assertTrue(self.hook.check_if_required())

    def test_is_required_returns_false(self):
        self.hook.config.from_version = '5.1'
        self.assertFalse(self.hook.check_if_required())

    @mock.patch(
        'fuel_upgrade.pre_upgrade_hooks.from_5_0_to_any_fix_puppet_manifests.'
        'iterfiles', return_value=iterfiles_returns)
    @mock.patch(
        'fuel_upgrade.pre_upgrade_hooks.from_5_0_to_any_fix_puppet_manifests.'
        'copy')
    def test_run(self, copy, _):
        self.hook.run()

        copy.assert_has_calls([
            mock.call(
                '/tmp/upgrade_path/config/5.0/modules/package/lib'
                '/puppet/provider/package/yum.rb',
                '/etc/puppet/modules/package/lib/puppet/provider/package'
                '/yum.rb'),
            mock.call(
                '/tmp/upgrade_path/config/5.0/manifests'
                '/centos-versions.yaml',
                '/etc/puppet/manifests/centos-versions.yaml')])


class TestFixHostSystemRepoHook(TestPreUpgradeHooksBase):

    def setUp(self):
        super(TestFixHostSystemRepoHook, self).setUp()

        conf = self.fake_config
        conf.from_version = '5.0.1'

        self.hook = FixHostSystemRepoHook(self.upgraders, conf)

    @mock.patch(
        'fuel_upgrade.pre_upgrade_hooks.'
        'from_5_0_1_to_any_fix_host_system_repo.'
        'utils.file_exists', return_value=True)
    def test_is_required_returns_true(self, exists_mock):
        self.hook.config.from_version = '5.0.1'
        self.assertTrue(self.hook.check_if_required())
        self.assertEqual(
            exists_mock.call_args_list,
            [mock.call('/var/www/nailgun/5.0.1/centos/x86_64'),
             mock.call('/etc/yum.repos.d/5.0.1_nailgun.repo')])

    def test_is_required_returns_false(self):
        self.hook.config.from_version = '5.0'
        self.assertFalse(self.hook.check_if_required())

        self.hook.config.from_version = '5.1'
        self.assertFalse(self.hook.check_if_required())

    @mock.patch(
        'fuel_upgrade.pre_upgrade_hooks.'
        'from_5_0_1_to_any_fix_host_system_repo.'
        'utils.file_exists', return_value=False)
    def test_is_required_returns_false_if_repo_file_does_not_exist(self, _):
        self.assertFalse(self.hook.check_if_required())

    @mock.patch(
        'fuel_upgrade.pre_upgrade_hooks.'
        'from_5_0_1_to_any_fix_host_system_repo.'
        'utils.file_exists', side_effect=[True, False])
    def test_is_required_returns_false_repo_does_not_exist(self, _):
        self.assertFalse(self.hook.check_if_required())

    @mock.patch(
        'fuel_upgrade.pre_upgrade_hooks.'
        'from_5_0_1_to_any_fix_host_system_repo.utils')
    def test_run(self, mock_utils):
        self.hook.run()
        args, _ = mock_utils.render_template_to_file.call_args_list[0]
        # The first argument is a path to
        # template in upgrade script directory
        # it can be different and depends on
        # code allocation
        self.assertTrue(args[0].endswith('templates/nailgun.repo'))
        self.assertEqual(
            args[1:],
            ('/etc/yum.repos.d/5.0.1_nailgun.repo',
             {'repo_path': '/var/www/nailgun/5.0.1/centos/x86_64',
              'version': '5.0.1'}))


class TestPreUpgradeHookBase(TestPreUpgradeHooksBase):

    def get_hook(self, check_if_required=False, enable_for_engines=[]):
        class PreUpgradeHook(PreUpgradeHookBase):

            def check_if_required(self):
                return check_if_required

            @property
            def enable_for_engines(self):
                return enable_for_engines

            def run(self):
                pass

        return PreUpgradeHook(self.upgraders, self.fake_config)

    @mock.patch('fuel_upgrade.pre_upgrade_hooks.base.'
                'PreUpgradeHookBase.is_enabled_for_engines',
                return_value=False)
    def test_is_required_returns_false(self, _):
        self.assertFalse(self.get_hook().is_required)

    @mock.patch('fuel_upgrade.pre_upgrade_hooks.base.'
                'PreUpgradeHookBase.is_enabled_for_engines',
                return_value=True)
    def test_is_required_returns_true(self, _):
        self.assertTrue(self.get_hook(check_if_required=True).is_required)

    def test_is_enabled_for_engines_returns_true(self):
        self.assertTrue(
            self.get_hook(
                check_if_required=True,
                enable_for_engines=[self.upgraders_cls[0]]).is_required)

    def test_is_enabled_for_engines_returns_false(self):
        class SomeEngine(object):
            pass

        self.assertFalse(
            self.get_hook(
                check_if_required=True,
                enable_for_engines=[SomeEngine]).is_required)

    @mock.patch('fuel_upgrade.pre_upgrade_hooks.base.read_yaml_config')
    @mock.patch('fuel_upgrade.pre_upgrade_hooks.base.utils.copy_file')
    @mock.patch('fuel_upgrade.pre_upgrade_hooks.base.utils.save_as_yaml')
    def test_update_astute_config(self,
                                  utils_save_as_yaml_mock,
                                  utils_copy_file_mock,
                                  read_yaml_config_mock):
        hook = self.get_hook()
        read_yaml_config_mock.return_value = {
            'a': 1,
            'dict': {
                'a': 1,
                'b': 2,
            }
        }

        defaults = {'b': 2, 'dict': {'a': 5, 'c': 6}}
        hook.update_astute_config(defaults=defaults)
        args = utils_save_as_yaml_mock.call_args
        self.assertDictEqual(
            args[0][1],
            {'a': 1, 'b': 2, 'dict': {'a': 1, 'b': 2, 'c': 6}})

        defaults = {'a': 2, 'dict': {'c': 5}}
        hook.update_astute_config(defaults=defaults)
        args = utils_save_as_yaml_mock.call_args
        self.assertDictEqual(
            args[0][1],
            {'a': 1, 'dict': {'a': 1, 'b': 2, 'c': 5}})

        overwrites = {'a': 2, 'dict': {'a': 5}}
        hook.update_astute_config(overwrites=overwrites)
        args = utils_save_as_yaml_mock.call_args
        self.assertDictEqual(
            args[0][1],
            {'a': 2, 'dict': {'a': 5, 'b': 2}})

        overwrites = {'b': 2, 'dict': {'c': 5}}
        hook.update_astute_config(overwrites=overwrites)
        args = utils_save_as_yaml_mock.call_args
        self.assertDictEqual(
            args[0][1],
            {'a': 1, 'b': 2, 'dict': {'a': 1, 'b': 2, 'c': 5}})


class TestPreUpgradeHookManager(TestPreUpgradeHooksBase):

    def setUp(self):
        super(TestPreUpgradeHookManager, self).setUp()

        self.required_hooks = [mock.MagicMock(), mock.MagicMock()]
        for hook in self.required_hooks:
            type(hook).is_required = mock.PropertyMock(return_value=True)

        self.not_required_hooks = [mock.MagicMock()]
        for hook in self.not_required_hooks:
            type(hook).is_required = mock.PropertyMock(return_value=False)

        self.hooks = []
        self.hooks.extend(self.required_hooks)
        self.hooks.extend(self.not_required_hooks)

        self.hook_manager = PreUpgradeHookManager(
            self.upgraders, self.fake_config)

    def test_run(self):
        self.hook_manager.pre_upgrade_hooks = self.hooks
        self.hook_manager.run()

        for hook in self.required_hooks:
            self.called_once(hook.run)

        for hook in self.not_required_hooks:
            self.method_was_not_called(hook.run)


class TestCopyOpenstackReleaseVersions(TestPreUpgradeHooksBase):

    iterfiles_returns = [
        '/tmp/upgrade_path/config/5.0/modules/package/lib/puppet'
        '/provider/package/yum.rb',
        '/tmp/upgrade_path/config/5.0/manifests/centos-versions.yaml']

    def setUp(self):
        super(TestCopyOpenstackReleaseVersions, self).setUp()

        conf = self.fake_config
        conf.from_version = '5.0.1'

        self.hook = CopyOpenstackReleaseVersions(self.upgraders, conf)

    def test_is_required_returns_true(self):
        self.hook.config.from_version = '5.0'
        self.assertTrue(self.hook.check_if_required())

        self.hook.config.from_version = '5.0.1'
        self.assertTrue(self.hook.check_if_required())

    def test_is_required_returns_false(self):
        self.hook.config.from_version = '5.1'
        self.assertFalse(self.hook.check_if_required())

    @mock.patch(
        'fuel_upgrade.pre_upgrade_hooks.'
        'from_5_0_x_to_any_copy_openstack_release_versions.utils')
    def test_run(self, mock_utils):
        self.hook.run()
        self.assertEqual(
            mock_utils.create_dir_if_not_exists.call_args_list,
            [mock.call(self.hook.release_dir)])

        self.assertEqual(
            mock_utils.copy_if_exists.call_args_list,
            [mock.call(self.hook.version_path_5_0,
                       self.hook.dst_version_path_5_0),
             mock.call(self.hook.version_path_5_0_1,
                       self.hook.dst_version_path_5_0_1)])

    @mock.patch(
        'fuel_upgrade.pre_upgrade_hooks.'
        'from_5_0_x_to_any_copy_openstack_release_versions.utils')
    def test_run_from_5_0(self, mock_utils):
        self.hook.config.from_version = '5.0'
        self.hook.run()
        self.assertEqual(
            mock_utils.copy_if_exists.call_args_list,
            [mock.call(self.hook.version_path_5_0,
                       self.hook.dst_version_path_5_0)])


class TestAddMonitordKeystoneCredentialsHook(TestPreUpgradeHooksBase):

    HookClass = AddMonitordKeystoneCredentialsHook

    def setUp(self):
        super(TestAddMonitordKeystoneCredentialsHook, self).setUp()
        self.monitord_keys = [
            'monitord_user',
            'monitord_password',
        ]

    def test_is_required_returns_true(self):
        hook = self.get_hook({})
        self.assertTrue(hook.check_if_required())

    def test_is_required_returns_false(self):
        hook = self.get_hook({
            'astute': {
                'keystone': {
                    'monitord_user': '',
                    'monitord_password': '',
                }
            }
        })

        self.assertFalse(hook.check_if_required())

    @mock.patch('fuel_upgrade.pre_upgrade_hooks.base.read_yaml_config')
    @mock.patch('fuel_upgrade.pre_upgrade_hooks.base.utils.copy_file')
    @mock.patch('fuel_upgrade.pre_upgrade_hooks.base.utils.save_as_yaml')
    def test_run(self, msave_as_yaml, mcopy_file, mread_yaml_config):
        file_key = 'this_key_was_here_before_upgrade'
        file_value = 'some value'
        hook = self.get_hook({
            'astute': {
                'keystone': {file_key: file_value}}
        })
        mread_yaml_config.return_value = hook.config.astute
        hook.run()

        mcopy_file.assert_called_once_with(
            '/etc/fuel/astute.yaml',
            '/etc/fuel/astute.yaml_0',
            overwrite=False)

        args = msave_as_yaml.call_args
        self.assertEqual(args[0][0], '/etc/fuel/astute.yaml')

        # Check that all required keys are in method call
        called_config = args[0][1]['keystone']
        self.assertTrue(set(self.monitord_keys).issubset(called_config))
        # Check that nothing else was changed
        self.assertEqual(called_config[file_key], file_value)


class TestAddDhcpGatewayHook(TestPreUpgradeHooksBase):

    HookClass = AddDhcpGateway

    def test_is_required_returns_true(self):
        hook = self.get_hook({})
        self.assertTrue(hook.check_if_required())

    def test_is_required_returns_false(self):
        hook = self.get_hook({
            'astute': {
                'ADMIN_NETWORK': {
                    'dhcp_gateway': '10.20.0.2',
                }
            }})

        self.assertFalse(hook.check_if_required())

    @mock.patch('fuel_upgrade.pre_upgrade_hooks.base.read_yaml_config')
    @mock.patch('fuel_upgrade.pre_upgrade_hooks.base.utils.copy_file')
    @mock.patch('fuel_upgrade.pre_upgrade_hooks.base.utils.save_as_yaml')
    def test_run(self, msave_as_yaml, mcopy_file, mread_yaml_config):
        hook = self.get_hook({
            'astute': {
                'ADMIN_NETWORK': {
                    'a': 1,
                    'b': 2,
                }
            }})
        mread_yaml_config.return_value = hook.config.astute
        hook.run()

        mcopy_file.assert_called_once_with(
            '/etc/fuel/astute.yaml',
            '/etc/fuel/astute.yaml_0',
            overwrite=False)

        args = msave_as_yaml.call_args
        self.assertEqual(args[0][0], '/etc/fuel/astute.yaml')

        # Check that all required keys are in method call
        admin_network = args[0][1]['ADMIN_NETWORK']
        self.assertEqual(admin_network, {
            'a': 1,
            'b': 2,
            'dhcp_gateway': '0.0.0.0',
        })


class TestMoveKeysHook(TestPreUpgradeHooksBase):

    def setUp(self):
        super(TestMoveKeysHook, self).setUp()

        conf = self.fake_config
        conf.from_version = '6.0'

        self.hook = MoveKeysHook(self.upgraders, conf)

    def test_is_required_returns_true(self):
        self.hook.config.from_version = '6.0'
        self.assertTrue(self.hook.check_if_required())

        self.hook.config.from_version = '6.0.1'
        self.assertTrue(self.hook.check_if_required())

    def test_is_required_returns_false(self):
        self.hook.config.from_version = '6.1'
        self.assertFalse(self.hook.check_if_required())

        self.hook.config.from_version = '6.2'
        self.assertFalse(self.hook.check_if_required())

    @mock.patch(
        'fuel_upgrade.pre_upgrade_hooks.from_6_0_to_any_copy_keys.utils.'
        'file_exists', return_value=True)
    @mock.patch(
        'fuel_upgrade.pre_upgrade_hooks.from_6_0_to_any_copy_keys.utils.'
        'exec_cmd')
    def test_run(self, cmd_exec, f_exist):
        self.hook.run()

        f_exist.assert_called_once_with(self.hook.dst_path)
        cmd_exec.assert_has_calls(
            [mock.call('docker cp fuel-core-6.0-astute:/var/lib/astute/ '
                       '/var/lib/fuel/keys/'),
             mock.call('mv /var/lib/fuel/keys/astute/* /var/lib/fuel/keys/'),
             mock.call('rm -r /var/lib/fuel/keys/astute/')])


class TestRecreateNailgunInPriveleged(TestPreUpgradeHooksBase):

    HookClass = RecreateNailgunInPriveleged

    @mock.patch(
        'fuel_upgrade.pre_upgrade_hooks.from_any_to_6_1_recreate_containers.'
        'exec_cmd_iterator')
    def test_is_required_returns_true(self, mock_exec):
        testcases = [
            (
                ['[{ "HostConfig": { "Privileged": false } }]'],
                ['Docker version 0.10.0, build dc9c28f/0.10.0'],
            ),
            (
                ['[{ "HostConfig": { "Privileged": false } }]'],
                ['Docker version 0.8.0, build a768964'],
            )]

        hook = self.get_hook({'from_version': '6.0'})
        for case in testcases:
            mock_exec.side_effect = case
            self.assertTrue(hook.check_if_required())

    @mock.patch(
        'fuel_upgrade.pre_upgrade_hooks.from_any_to_6_1_recreate_containers.'
        'exec_cmd_iterator')
    def test_is_required_returns_false(self, mock_exec):
        testcases = [
            (
                ['[{ "HostConfig": { "Privileged": false } }]'],
                ['Docker version 0.11.0, build dc9c28f/0.11.0'],
            ),
            (
                ['[{ "HostConfig": { "Privileged": false } }]'],
                ['Docker version 1.4.1, build d344625'],
            ),
            (
                ['[{ "HostConfig": { "Privileged": true } }]'],
                ['Docker version 0.10.0, build dc9c28f/0.10.0'],
            ),
        ]

        hook = self.get_hook({'from_version': '6.0'})
        for case in testcases:
            mock_exec.side_effect = case
            self.assertFalse(hook.check_if_required())

    @mock.patch(
        'fuel_upgrade.pre_upgrade_hooks.from_any_to_6_1_recreate_containers.'
        'safe_exec_cmd')
    def test_run(self, mock_safe_exec_cmd):
        hook = self.get_hook()
        hook.run()

        mock_safe_exec_cmd.assert_has_calls([
            mock.call('docker stop fuel-core-0-nailgun'),
            mock.call('docker rm -f fuel-core-0-nailgun'),
            mock.call(
                'docker run -d -t --privileged '
                '-p 0.0.0.0:8001:8001 '
                '-p 127.0.0.1:8001:8001 '
                '-v /etc/nailgun -v /var/log/docker-logs:/var/log '
                '-v /var/www/nailgun:/var/www/nailgun:rw '
                '-v /etc/yum.repos.d:/etc/yum.repos.d:rw '
                '-v /etc/fuel:/etc/fuel:ro '
                '-v /root/.ssh:/root/.ssh:ro '
                '--name=fuel-core-0-nailgun '
                'fuel/nailgun_0')])


class TestFixDhcrelayConf(TestPreUpgradeHooksBase):

    HookClass = FixDhcrelayConf

    @mock.patch(
        'fuel_upgrade.pre_upgrade_hooks.from_any_to_6_1_dhcrelay_conf.'
        'os.path.exists', side_effect=[True, False])
    def test_is_required_returns_true(self, _):
        hook = self.get_hook()
        self.assertTrue(hook.check_if_required())

    @mock.patch(
        'fuel_upgrade.pre_upgrade_hooks.from_any_to_6_1_dhcrelay_conf.'
        'os.path.exists',)
    def test_is_required_returns_false(self, mock_exists):
        testcases = [
            # save_from exists, save_as exists
            (True, True),
            (False, True),
            (False, False),
        ]

        hook = self.get_hook()
        for case in testcases:
            mock_exists.side_effect = case
            self.assertFalse(hook.check_if_required())

    @mock.patch(
        'fuel_upgrade.pre_upgrade_hooks.from_any_to_6_1_dhcrelay_conf.'
        'safe_exec_cmd')
    @mock.patch(
        'fuel_upgrade.pre_upgrade_hooks.from_any_to_6_1_dhcrelay_conf.'
        'remove')
    @mock.patch(
        'fuel_upgrade.pre_upgrade_hooks.from_any_to_6_1_dhcrelay_conf.'
        'copy_file')
    def test_run(self, mock_cp, mock_rm, mock_exec):
        hook = self.get_hook()
        hook.run()

        mock_cp.assert_called_with(
            '/etc/supervisord.d/dhcrelay.conf',
            '/etc/supervisord.d/0/dhcrelay.conf')
        mock_rm.assert_called_with(
            '/etc/supervisord.d/dhcrelay.conf')
        mock_exec.assert_called_with(
            'supervisorctl stop dhcrelay_monitor')


class TestFixDhcrelayMontitor(TestPreUpgradeHooksBase):

    HookClass = FixDhcrelayMonitor

    def test_is_required_returns_true(self):
        hook = self.get_hook({'from_version': '6.0'})
        self.assertTrue(hook.check_if_required())

    def test_is_required_returns_false(self):
        hook = self.get_hook({'from_version': '6.1'})
        self.assertFalse(hook.check_if_required())

    @mock.patch(
        'fuel_upgrade.pre_upgrade_hooks.from_any_to_6_1_dhcrelay_monitor.'
        'os')
    @mock.patch(
        'fuel_upgrade.pre_upgrade_hooks.from_any_to_6_1_dhcrelay_monitor.'
        'utils.copy')
    def test_run(self, mock_copy, mock_os):
        hook = self.get_hook()
        hook.run()

        self.assertIn(
            'templates/dhcrelay_monitor', mock_copy.call_args[0][0])
        self.assertEqual(
            '/usr/local/bin/dhcrelay_monitor', mock_copy.call_args[0][1])


class TestSetFixedVersionInSupervisor(TestPreUpgradeHooksBase):

    _module = 'fuel_upgrade.pre_upgrade_hooks.' \
              'from_any_to_6_1_fix_version_in_supervisor'

    _supervisor_conf = textwrap.dedent('''\
        [program:docker-astute]
        command=dockerctl start astute --attach
        numprocs=1
        numprocs_start=0
        priority=30
        autostart=true
        autorestart=true
    ''')

    _supervisor_conf_patched = textwrap.dedent('''\
        [program:docker-astute]
        command=docker start -a fuel-core-6.0.1-astute
        numprocs=1
        numprocs_start=0
        priority=30
        autostart=true
        autorestart=true
    ''')

    HookClass = SetFixedVersionInSupervisor

    def test_is_required_returns_true(self):
        hook = self.get_hook({'from_version': '6.0'})
        self.assertTrue(hook.check_if_required())

    def test_is_required_returns_false(self):
        hook = self.get_hook({'from_version': '6.1'})
        self.assertFalse(hook.check_if_required())

    @mock.patch('{0}.utils.safe_exec_cmd'.format(_module))
    @mock.patch('{0}.os.path.exists'.format(_module),
                side_effect=itertools.chain([True], itertools.repeat(False)))
    def test_run_patches(self, _, m_exec):

        f_read = FakeFile(self._supervisor_conf)
        f_write = FakeFile()

        with mock.patch('{0}.open'.format(self._module)) as m_open:
            hook = self.get_hook({'from_version': '6.0.1'})

            m_open.side_effect = [f_read, f_write]
            hook.run()

            m_open.assert_has_calls([
                mock.call('/etc/supervisord.d/6.0.1/astute.conf',
                          'rt', encoding='utf-8'),
                mock.call('/etc/supervisord.d/6.0.1/astute.conf',
                          'wt', encoding='utf-8')])

        self.assertEquals(f_write.getvalue(), self._supervisor_conf_patched)
        m_exec.assert_called_once_with('supervisorctl update')

    @mock.patch('{0}.utils.safe_exec_cmd'.format(_module))
    @mock.patch('{0}.os.path.exists'.format(_module),
                return_value=False)
    def test_run_do_not_patch(self, _, m_exec):

        with mock.patch('{0}.open'.format(self._module)) as m_open:
            hook = self.get_hook({'from_version': '6.0.1'})
            hook.run()

            self.assertEqual(m_open.call_count, 0)

        m_exec.assert_called_once_with('supervisorctl update')
