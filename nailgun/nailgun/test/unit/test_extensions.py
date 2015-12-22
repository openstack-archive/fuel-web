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

from nailgun.errors import errors
from nailgun.extensions import BaseExtension
from nailgun.extensions import fire_callback_on_cluster_delete
from nailgun.extensions import fire_callback_on_node_collection_delete
from nailgun.extensions import fire_callback_on_node_create
from nailgun.extensions import fire_callback_on_node_delete
from nailgun.extensions import fire_callback_on_node_reset
from nailgun.extensions import fire_callback_on_node_update
from nailgun.extensions import get_extension
from nailgun.extensions import node_extension_call
from nailgun.test.base import BaseTestCase


class TestBaseExtension(BaseTestCase):

    def setUp(self):
        super(TestBaseExtension, self).setUp()

        class Extension(BaseExtension):
            name = 'ext_name'
            version = '1.0.0'
            description = 'ext description'

        self.extension = Extension()

    def test_alembic_table_version(self):
        self.assertEqual(
            self.extension.alembic_table_version(),
            'ext_name_alembic_version')

    def test_table_prefix(self):
        self.assertEqual(
            self.extension.table_prefix(),
            'ext_name_')

    def test_alembic_migrations_path_none_by_default(self):
        self.assertIsNone(self.extension.alembic_migrations_path())

    def test_full_name(self):
        self.assertEqual(
            self.extension.full_name(),
            'ext_name-1.0.0')


def make_mock_extensions():
    mocks = []
    for name in ['ex1', 'ex2']:
        # NOTE(eli): since 'name' is reserved world
        # for mock constructor, we should assign
        # name explicitly
        ex_m = mock.MagicMock()
        ex_m.name = name
        ex_m.provides = ['method_call']
        mocks.append(ex_m)

    return mocks


class TestExtensionUtils(BaseTestCase):

    def make_node(self, node_extensions=[], cluster_extensions=[]):
        node = mock.MagicMock()
        node.extensions = node_extensions
        node.cluster.extensions = cluster_extensions

        return node

    @mock.patch('nailgun.extensions.manager.get_all_extensions',
                return_value=make_mock_extensions())
    def test_get_extension(self, get_m):
        get_extension('ex1')

    @mock.patch('nailgun.extensions.manager.get_all_extensions',
                return_value=make_mock_extensions())
    def test_get_extension_raises_errors(self, get_m):
        self.assertRaisesRegexp(
            errors.CannotFindExtension,
            "Cannot find extension with name 'unknown_ex'",
            get_extension,
            'unknown_ex')

    @mock.patch('nailgun.extensions.manager.get_all_extensions',
                return_value=make_mock_extensions())
    def test_node_extension_call_raises_error(self, _):
        self.assertRaisesRegexp(
            errors.CannotFindExtension,
            "Cannot find extension which provides 'method_call' call",
            node_extension_call,
            'method_call',
            self.make_node())

    @mock.patch('nailgun.extensions.manager.get_all_extensions',
                return_value=make_mock_extensions())
    def test_node_extension_call_extension_from_node(self, get_m):
        node = self.make_node(
            node_extensions=['ex1'],
            cluster_extensions=['ex2'])

        node_extension_call('method_call', node)
        ex1 = get_m.return_value[0]
        self.assertEqual('ex1', ex1.name)
        ex2 = get_m.return_value[1]
        self.assertEqual('ex2', ex2.name)

        ex1.method_call.assert_called_once_with(node)
        self.assertFalse(ex2.method_call.called)

    @mock.patch('nailgun.extensions.manager.get_all_extensions',
                return_value=make_mock_extensions())
    def test_node_extension_call_default_extension_from_cluster(self, get_m):
        node = self.make_node(
            node_extensions=[],
            cluster_extensions=['ex2'])

        node_extension_call('method_call', node)
        ex1 = get_m.return_value[0]
        self.assertEqual('ex1', ex1.name)
        ex2 = get_m.return_value[1]
        self.assertEqual('ex2', ex2.name)

        self.assertFalse(ex1.method_call.called)
        ex2.method_call.assert_called_once_with(node)

    @mock.patch('nailgun.extensions.manager.get_all_extensions',
                return_value=make_mock_extensions())
    def test_fire_callback_on_node_create(self, get_m):
        node = mock.MagicMock()
        fire_callback_on_node_create(node)

        for ext in get_m.return_value:
            ext.on_node_create.assert_called_once_with(node)

    @mock.patch('nailgun.extensions.manager.get_all_extensions',
                return_value=make_mock_extensions())
    def test_fire_callback_on_node_update(self, get_m):
        node = mock.MagicMock()
        fire_callback_on_node_update(node)

        for ext in get_m.return_value:
            ext.on_node_update.assert_called_once_with(node)

    @mock.patch('nailgun.extensions.manager.get_all_extensions',
                return_value=make_mock_extensions())
    def test_fire_callback_on_node_reset(self, get_m):
        node = mock.MagicMock()
        fire_callback_on_node_reset(node)

        for ext in get_m.return_value:
            ext.on_node_reset.assert_called_once_with(node)

    @mock.patch('nailgun.extensions.manager.get_all_extensions',
                return_value=make_mock_extensions())
    def test_fire_callback_on_node_delete(self, get_m):
        node = mock.MagicMock()
        fire_callback_on_node_delete(node)

        for ext in get_m.return_value:
            ext.on_node_delete.assert_called_once_with(node)

    @mock.patch('nailgun.extensions.manager.get_all_extensions',
                return_value=make_mock_extensions())
    def test_fire_callback_on_node_collection_delete(self, get_m):
        node_ids = [1, 2, 3, 4]
        fire_callback_on_node_collection_delete(node_ids)

        for ext in get_m.return_value:
            ext.on_node_collection_delete.assert_called_once_with(node_ids)

    @mock.patch('nailgun.extensions.manager.get_all_extensions',
                return_value=make_mock_extensions())
    def test_fire_callback_on_cluster_deletion(self, get_m):
        cluster = mock.MagicMock()
        fire_callback_on_cluster_delete(cluster)

        for ext in get_m.return_value:
            ext.on_cluster_delete.assert_called_once_with(cluster)
