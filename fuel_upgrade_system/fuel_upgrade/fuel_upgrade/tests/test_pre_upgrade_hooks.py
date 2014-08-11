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
import os

from fuel_upgrade.tests.base import BaseTestCase

from fuel_upgrade.pre_upgrade_hooks.base import PreUpgradeHookBase
from fuel_upgrade.pre_upgrade_hooks.from_5_0_to_any_add_credentials \
    import AddCredentialsHook
from fuel_upgrade.pre_upgrade_hooks.from_5_0_to_any_add_versions_yaml \
    import AddVersionsYaml
from fuel_upgrade.pre_upgrade_hooks.from_5_0_to_any_apply_versioncmp_fix \
    import ApplyVersioncmpFix
from fuel_upgrade.pre_upgrade_hooks.from_5_0_to_any_sync_dns \
    import SyncDnsHook
from fuel_upgrade.pre_upgrade_hooks import PreUpgradeHookManager


class TestPreUpgradeHooksBase(BaseTestCase):
    def setUp(self):
        class Upgrader1(mock.MagicMock):
            pass

        class Upgrader2(mock.MagicMock):
            pass

        self.upgraders_cls = [Upgrader1, Upgrader2]
        self.upgraders = [upgrade_cls() for upgrade_cls in self.upgraders_cls]


class TestAddCredentialsHook(TestPreUpgradeHooksBase):

    def setUp(self):
        super(TestAddCredentialsHook, self).setUp()
        self.additional_keys = [
            'astute',
            'cobbler',
            'mcollective',
            'postgres',
            'keystone',
            'FUEL_ACCESS']

    def get_hook(self, astute):
        config = self.fake_config
        config.astute = astute
        return AddCredentialsHook(self.upgraders, config)

    def test_is_required_returns_true(self):
        hook = self.get_hook({})
        self.assertTrue(hook.check_if_required())

    def test_is_required_returns_false(self):
        hook = self.get_hook({
            'astute': {},
            'cobbler': {},
            'mcollective': {},
            'postgres': {},
            'keystone': {},
            'FUEL_ACCESS': {}})

        self.assertFalse(hook.check_if_required())

    @mock.patch('fuel_upgrade.pre_upgrade_hooks.'
                'from_5_0_to_any_add_credentials.utils')
    def test_run(self, utils_mock):
        file_key = 'this_key_was_here_before_upgrade'
        hook = self.get_hook({file_key: file_key})
        hook.run()

        utils_mock.copy_file.assert_called_once_with(
            '/etc/fuel/astute.yaml',
            '/etc/fuel/astute.yaml_0',
            overwrite=False)

        agrs = utils_mock.save_as_yaml.call_args
        self.assertEqual(agrs[0][0], '/etc/fuel/astute.yaml')

        # Check that the key which was in file
        # won't be overwritten
        self.additional_keys.append(file_key)
        # Check that all required keys are in method call
        self.assertTrue(all(
            key in self.additional_keys
            for key in agrs[0][1].keys()))


class TestSyncDnsHook(TestPreUpgradeHooksBase):

    def setUp(self):
        super(TestSyncDnsHook, self).setUp()
        self.additional_keys = [
            'DNS_DOMAIN',
            'DNS_SEARCH']

    def get_hook(self, astute):
        config = self.fake_config
        config.astute = astute
        return SyncDnsHook(self.upgraders, config)

    def test_is_required_returns_true(self):
        hook = self.get_hook({
            'DNS_DOMAIN': 'veryunlikelydomain',
            'DNS_SEARCH': 'veryunlikelydomain'})
        self.assertTrue(hook.check_if_required())

    def test_is_required_returns_false(self):
        hostname, sep, realdomain = os.uname()[1].partition('.')
        hook = self.get_hook({
            'DNS_DOMAIN': realdomain,
            'DNS_SEARCH': realdomain})

        self.assertFalse(hook.check_if_required())

    @mock.patch('fuel_upgrade.pre_upgrade_hooks.'
                'from_5_0_to_any_sync_dns.utils')
    def test_run(self, utils_mock):
        file_key = 'this_key_was_here_before_upgrade'
        hook = self.get_hook({file_key: file_key})
        hook.run()

        utils_mock.copy_file.assert_called_once_with(
            '/etc/fuel/astute.yaml',
            '/etc/fuel/astute.yaml_0',
            overwrite=False)

        args = utils_mock.save_as_yaml.call_args
        self.assertEqual(args[0][0], '/etc/fuel/astute.yaml')

        # Check that the key which was in file
        # won't be overwritten
        self.additional_keys.append(file_key)
        # Check that all required keys are in method call
        self.assertTrue(all(
            key in self.additional_keys
            for key in args[0][1].keys()))


class TestAddVersionsYamlHook(TestPreUpgradeHooksBase):

    def setUp(self):
        super(TestAddVersionsYamlHook, self).setUp()
        self.hook = AddVersionsYaml(self.upgraders, self.fake_config)

    @mock.patch(
        'fuel_upgrade.pre_upgrade_hooks.from_5_0_to_any_add_versions_yaml.'
        'os.path.exists', return_value=False)
    def test_is_required_returns_true(self, _):
        self.assertTrue(self.hook.check_if_required())

    @mock.patch(
        'fuel_upgrade.pre_upgrade_hooks.from_5_0_to_any_add_versions_yaml.'
        'os.path.exists', return_value=True)
    def test_is_required_returns_false(self, _):
        self.assertFalse(self.hook.check_if_required())

    @mock.patch(
        'fuel_upgrade.pre_upgrade_hooks.from_5_0_to_any_add_versions_yaml.'
        'copy')
    def test_run(self, copy):
        self.hook.run()

        self.called_times(copy, len(self.hook.versions_yaml))


class TestApplyVersioncmpFixHook(TestPreUpgradeHooksBase):

    def setUp(self):
        super(TestApplyVersioncmpFixHook, self).setUp()
        self.hook = ApplyVersioncmpFix(self.upgraders, self.fake_config)

    @mock.patch(
        'fuel_upgrade.pre_upgrade_hooks.from_5_0_to_any_apply_versioncmp_fix.'
        'file_contains_lines', return_value=False)
    def test_is_required_returns_true(self, _):
        self.hook.config.from_version = '5.0'
        self.assertTrue(self.hook.check_if_required())

        self.hook.config.from_version = '5.0.1'
        self.assertTrue(self.hook.check_if_required())

    @mock.patch(
        'fuel_upgrade.pre_upgrade_hooks.from_5_0_to_any_apply_versioncmp_fix.'
        'file_contains_lines', return_value=True)
    def test_is_required_returns_false(self, _):
        self.hook.config.from_version = '999'
        self.assertFalse(self.hook.check_if_required())

        self.hook.config.from_version = '5.0'
        self.assertFalse(self.hook.check_if_required())

    @mock.patch(
        'fuel_upgrade.pre_upgrade_hooks.from_5_0_to_any_add_versions_yaml.'
        'os.path.exists', return_value=False)
    @mock.patch(
        'fuel_upgrade.pre_upgrade_hooks.from_5_0_to_any_apply_versioncmp_fix.'
        'copy')
    def test_run_for_5_0(self, copy, _):
        self.hook.config.from_version = '5.0'
        self.hook.run()

        copy.assert_called_with(
            '/tmp/upgrade_path/config/5.0/yum.rb',
            '/etc/puppet/modules/package/lib/puppet/provider/package/yum.rb',
            overwrite=True)

    @mock.patch(
        'fuel_upgrade.pre_upgrade_hooks.from_5_0_to_any_add_versions_yaml.'
        'os.path.exists', return_value=False)
    @mock.patch(
        'fuel_upgrade.pre_upgrade_hooks.from_5_0_to_any_apply_versioncmp_fix.'
        'copy')
    def test_run_for_5_0_1(self, copy, _):
        self.hook.config.from_version = '5.0.1'
        self.hook.run()

        copy.assert_called_with(
            '/tmp/upgrade_path/config/5.0.1/yum.rb',
            '/etc/puppet/modules/package/lib/puppet/provider/package/yum.rb',
            overwrite=True)

    @mock.patch(
        'fuel_upgrade.pre_upgrade_hooks.from_5_0_to_any_add_versions_yaml.'
        'os.path.exists', return_value=True)
    @mock.patch(
        'fuel_upgrade.pre_upgrade_hooks.from_5_0_to_any_apply_versioncmp_fix.'
        'copy')
    def test_run_for_5_0_and_5_0_1(self, copy, _):
        self.hook.run()

        copy.assert_has_calls([
            mock.call(
                '/tmp/upgrade_path/config/5.0/yum.rb',
                '/etc/puppet/modules/package/lib/puppet/provider'
                '/package/yum.rb', overwrite=True),
            mock.call(
                '/tmp/upgrade_path/config/5.0.1/yum.rb',
                '/etc/puppet/5.0.1/modules/package/lib/puppet/provider'
                '/package/yum.rb', overwrite=True)])


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
