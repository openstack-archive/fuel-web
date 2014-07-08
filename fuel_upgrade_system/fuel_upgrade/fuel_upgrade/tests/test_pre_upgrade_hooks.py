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

from fuel_upgrade.tests.base import BaseTestCase

from fuel_upgrade.pre_upgrade_hooks.base import PreUpgradeHookBase
from fuel_upgrade.pre_upgrade_hooks.from_5_0_to_any_add_credentials \
    import AddCredentialsHook
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
        self.additional_keys = ['astute', 'cobbler', 'mcollective', 'postgres']

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
            'postgres': {}})

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
