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
        mapper_mock = mock.patch.object(role_resolver.RoleResolver,
                                        'mapper_func')
        self.addCleanup(mapper_mock.stop)
        mapper_mock.start().side_effect = self.roles_of_nodes

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
        self.assertItemsEqual(
            [consts.MASTER_NODE_UID],
            resolver.resolve(consts.TASK_ROLES.master)
        )
        self.assertItemsEqual(
            [consts.MASTER_NODE_UID, '2', '3'],
            resolver.resolve([consts.TASK_ROLES.master, 'controller'])
        )

    def test_resolve_any(self):
        resolver = role_resolver.RoleResolver(self.nodes)
        all_nodes = resolver.resolve("*", consts.NODE_RESOLVE_POLICY.all)
        self.assertItemsEqual(
            all_nodes,
            (n.uid for n in self.nodes)
        )
        any_node = resolver.resolve("*", consts.NODE_RESOLVE_POLICY.any)
        self.assertEqual(1, len(any_node))
        self.assertTrue(any_node.issubset(all_nodes))

    def test_get_all_roles(self):
        resolver = role_resolver.RoleResolver(self.nodes)
        all_roles = {r for roles in self.roles_of_nodes for r in roles}
        self.assertEqual(all_roles, resolver.get_all_roles())
        self.assertEqual(all_roles, resolver.get_all_roles(
            consts.TASK_ROLES.all
        ))
        self.assertEqual(
            {'controller', 'primary-controller'},
            resolver.get_all_roles("/.*controller/")
        )
        self.assertEqual(
            {'compute', "cinder"},
            resolver.get_all_roles(["compute", "cinder", "cinder2"])
        )


class TestNullResolver(BaseUnitTest):
    def test_resolve(self):
        node_ids = ['1', '2', '3']
        self.assertIs(
            node_ids,
            role_resolver.NullResolver(node_ids).resolve("controller")
        )


class TestTagResolver(BaseUnitTest):
    @classmethod
    def setUpClass(cls):
        cls.tags_of_nodes = [
            ["database", "rabbitmq"],
            ["nova-controller"],
            ["horizon", "keystone", "database"],
            ["compute"]
        ]
        cls.nodes = [
            mock.MagicMock(uid=str(i))
            for i in six.moves.range(len(cls.tags_of_nodes))
        ]

    def setUp(self):
        mapper_mock = mock.patch.object(role_resolver.TagResolver,
                                        'mapper_func')
        self.addCleanup(mapper_mock.stop)
        mapper_mock.start().side_effect = self.tags_of_nodes

    def test_resolve_by_tag(self):
        resolver = role_resolver.TagResolver(self.nodes)
        self.assertItemsEqual(
            ["0", "2"],
            resolver.resolve(["/.*database/"])
        )
        self.assertItemsEqual(
            ["1"],
            resolver.resolve(["nova-controller"])
        )
        self.assertItemsEqual(
            ["0", "2"],
            resolver.resolve(["horizon", "keystone", "database"])
        )

    def test_resolve_all(self):
        resolver = role_resolver.TagResolver(self.nodes)
        self.assertItemsEqual(
            (x.uid for x in self.nodes),
            resolver.resolve("*")
        )

    def test_resolve_master(self):
        resolver = role_resolver.TagResolver(self.nodes)
        self.assertItemsEqual(
            [consts.MASTER_NODE_UID],
            resolver.resolve(consts.TASK_ROLES.master)
        )
