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

from nailgun.extensions import BaseExtension
from nailgun.test.base import BaseTestCase


class TestBaseExtension(BaseTestCase):

    def setUp(self):
        super(TestBaseExtension, self).setUp()

        class Extexnsion(BaseExtension):
            name = 'ext_name'
            version = '1.0.0'

        self.extension = Extexnsion()

    def test_alembic_table_version(self):
        self.assertEqual(
            self.extension.alembic_table_version(),
            'ext_name_1_0_0_alembic_version')

    def test_table_prefix(self):
        self.assertEqual(
            self.extension.table_prefix(),
            'ext_name_1_0_0_')

    def test_alembic_migrations_path_none_by_default(self):
        self.assertIsNone(self.extension.alembic_migrations_path())

    def test_full_name(self):
        self.assertEqual(
            self.extension.full_name(),
            'ext_name-1.0.0')
