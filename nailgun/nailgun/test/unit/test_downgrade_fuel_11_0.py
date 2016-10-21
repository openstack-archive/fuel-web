# coding: utf-8

# Copyright 2016 Mirantis, Inc.
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

import alembic
from oslo_serialization import jsonutils

import six
import sqlalchemy as sa

from nailgun.db import db
from nailgun.db import dropdb
from nailgun.db.migration import ALEMBIC_CONFIG
from nailgun.test import base


_prepare_revision = 'dc8bc8751c42'
_test_revision = 'c6edea552f1e'


def setup_module():
    dropdb()
    alembic.command.upgrade(ALEMBIC_CONFIG, _prepare_revision)

    prepare()
    db.commit()

    alembic.command.downgrade(ALEMBIC_CONFIG, _test_revision)


def prepare():
    meta = base.reflect_db_metadata()

    db.execute(
        meta.tables['plugins'].insert(),
        [{
            'name': 'test_plugin_a',
            'title': 'Test plugin A',
            'version': '2.0.0',
            'description': 'Test plugin A for Fuel',
            'homepage': 'http://fuel_plugins.test_plugin.com',
            'package_version': '5.0.0',
            'groups': jsonutils.dumps(['tgroup']),
            'authors': jsonutils.dumps(['tauthor']),
            'licenses': jsonutils.dumps(['tlicense']),
            'releases': jsonutils.dumps([
                {'repository_path': 'repositories/ubuntu'}
            ]),
            'fuel_version': jsonutils.dumps(['10.0']),
            'roles_metadata': jsonutils.dumps({
                'role_x': {
                    'name': 'role_x',
                    'has_primary': False,
                    'tags': ['role_x']
                },
            }),
            'tags_metadata': jsonutils.dumps({
                'role_x': {
                    'has_primary': False
                },
            })
        }]
    )


class TestPluginTags(base.BaseAlembicMigrationTest):

    def test_tag_column_is_absent(self):
        plugins = self.meta.tables['plugins']
        self.assertNotIn('tags_metadata', plugins.c)

    def test_tags_are_absent_in_role_meta(self):
        plugins = self.meta.tables['plugins']
        q_roles_meta = sa.select([plugins.c.roles_metadata])
        for role_meta in db.execute(q_roles_meta):
            for role, meta in six.iteritems(jsonutils.loads(role_meta[0])):
                self.assertNotIn('tags', meta)
