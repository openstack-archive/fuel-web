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


from nailgun import consts
from nailgun.errors import errors
from nailgun.policy.merge import NetworkRoleMergePolicy
from nailgun.policy.name_match import ExactMatch
from nailgun.policy.name_match import NameMatchPolicy
from nailgun.policy.name_match import PatternMatch
from nailgun.test.base import BaseUnitTest


class TestNetworkRoleMergePolicy(BaseUnitTest):
    def setUp(self):
        super(TestNetworkRoleMergePolicy, self).setUp()
        self.policy = NetworkRoleMergePolicy()

    @staticmethod
    def _make_plugin_network_role(**kwargs):
        properties = {
            'subnet': True,
            'gateway': False,
            'vip': []
        }

        properties.update(kwargs)

        return {
            'id': 'test_network_role',
            'default_mapping': consts.NETWORKS.public,
            'properties': properties
        }

    def test_apply_path(self):
        target = self._make_plugin_network_role(vip=[{'name': 'test_vip_a'}])
        patch = self._make_plugin_network_role(vip=[{'name': 'test_vip_b'}])
        self.policy.apply_patch(target, patch)
        expected = self._make_plugin_network_role(
            vip=[{'name': 'test_vip_a'}, {'name': 'test_vip_b'}]
        )

        self.assertDictEqual(expected, target)

    def test_apply_patch_vips_without_duplicates(self):
        target = self._make_plugin_network_role(
            vip=[{'name': 'test_vip_a'}, {'name': 'test_vip_b'}]
        )
        patch = self._make_plugin_network_role(vip=[{'name': 'test_vip_a'}])
        self.policy.apply_patch(target, patch)
        self.assertItemsEqual(
            [{'name': 'test_vip_a'}, {'name': 'test_vip_b'}],
            target['properties']['vip']
        )

    def test_apply_patch_fail_if_conflict(self):
        with self.assertRaisesRegexp(errors.UnresolvableConflict, 'subnet'):
            self.policy.apply_patch(
                self._make_plugin_network_role(subnet=True),
                self._make_plugin_network_role(subnet=False)
            )

        with self.assertRaisesRegexp(errors.UnresolvableConflict, 'prop1'):
            self.policy.apply_patch(
                self._make_plugin_network_role(prop1=0.1),
                self._make_plugin_network_role(prop1=1)
            )

    def test_apply_path_fail_if_vip_conflict(self):
        with self.assertRaisesRegexp(
                errors.UnresolvableConflict,
                "VIP 'test' conflicts with existing one"):
            self.policy.apply_patch(
                self._make_plugin_network_role(
                    vip=[{"name": "test", "value": 1}]
                ),
                self._make_plugin_network_role(
                    vip=[{"name": "test", "value": 2}]
                )
            )


class TestNameMatchPolicy(BaseUnitTest):
    def test_exact_match(self):
        match_policy = NameMatchPolicy.create("controller")
        self.assertIsInstance(match_policy, ExactMatch)
        self.assertTrue(match_policy.match("controller"))
        self.assertFalse(match_policy.match("controller1"))

    def test_pattern_match(self):
        match_policy = NameMatchPolicy.create("/controller/")
        self.assertIsInstance(match_policy, PatternMatch)
        self.assertTrue(match_policy.match("controller"))
        self.assertTrue(match_policy.match("controller1"))
