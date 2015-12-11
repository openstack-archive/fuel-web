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

import mock
import six

from nailgun import consts
from nailgun.test.base import BaseUnitTest
from nailgun.utils import role_resolver


class TestNameMatchPolicy(BaseUnitTest):
    def test_exact_match(self):
        match_policy = role_resolver.NameMatchPolicy.create("controller")
        self.assertIsInstance(match_policy, role_resolver.ExactMatch)
        self.assertTrue(match_policy.match("controller"))
        self.assertFalse(match_policy.match("controller1"))

    def test_pattern_match(self):
        match_policy = role_resolver.NameMatchPolicy.create("/controller/")
        self.assertIsInstance(match_policy, role_resolver.PatternMatch)
        self.assertTrue(match_policy.match("controller"))
        self.assertTrue(match_policy.match("controller1"))


class TestPatternBasedRoleResolver(BaseUnitTest):
    @classmethod
    def setUpClass(cls):
        cls.roles_of_nodes = [
            ["primary-controller"],
            ["cinder"],
            ["controller", "compute"],
            ["controller", "cinder"],
            ["compute"],
        ]
        cls.nodes = [
            mock.MagicMock(uid=str(i))
            for i in six.moves.range(len(cls.roles_of_nodes))
        ]

    def setUp(self):
        objs_mock = mock.patch('nailgun.utils.role_resolver.objects')
        self.addCleanup(objs_mock.stop)
        objs_mock.start()
        objs_mock.Node.all_roles.side_effect = self.roles_of_nodes

    def test_resolve_by_pattern(self):
        resolver = role_resolver.RoleResolver(self.nodes)
        self.assertItemsEqual(
            ["0", "2", "3"],
            resolver.resolve(["/.*controller/"])
        )
        self.assertItemsEqual(
            ["2", "3"],
            resolver.resolve(["controller"])
        )
        self.assertItemsEqual(
            ["1", "2", "3", "4"],
            resolver.resolve(["/c.+/"])
        )

    def test_resolve_all(self):
        resolver = role_resolver.RoleResolver(self.nodes)
        self.assertItemsEqual(
            (x.uid for x in self.nodes),
            resolver.resolve("*")
        )

    def test_resolve_master(self):
        resolver = role_resolver.RoleResolver(self.nodes)
        self.assertEqual(
            [consts.MASTER_ROLE],
            resolver.resolve(consts.MASTER_ROLE)
        )

    def test_resolve_any(self):
        resolver = role_resolver.RoleResolver(self.nodes)
        all_nodes = resolver.resolve("*", consts.NODE_RESOLVE_POLICY.all)
        any_node = resolver.resolve("*", consts.NODE_RESOLVE_POLICY.any)
        self.assertEqual(1, len(any_node))
        self.assertIn(any_node[0], all_nodes)


class TestNullResolver(BaseUnitTest):
    def test_resolve(self):
        node_ids = ['1', '2', '3']
        self.assertIs(
            node_ids,
            role_resolver.NullResolver(node_ids).resolve("controller")
        )
