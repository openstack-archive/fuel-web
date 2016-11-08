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
import sqlalchemy as sa

from nailgun.db import db
from nailgun.db import dropdb
from nailgun.db.migration import ALEMBIC_CONFIG
from nailgun.test import base


_prepare_revision = 'c6edea552f1e'
_test_revision = '675105097a69'


def setup_module():
    dropdb()
    alembic.command.upgrade(ALEMBIC_CONFIG, _prepare_revision)

    prepare()
    db.commit()

    alembic.command.downgrade(ALEMBIC_CONFIG, _test_revision)


def prepare():
    meta = base.reflect_db_metadata()

    result = db.execute(
        meta.tables['releases'].insert(),
        [{
            'name': 'test_name',
            'version': '2015.1-10.0',
            'operating_system': 'ubuntu',
            'state': 'available',
            'deployment_tasks': '{}',
            'roles': '{}',
            'roles_metadata': '{}',
            'is_deployable': True,
            'required_component_types': ['network', 'storage']
        }]
    )

    release_id = result.inserted_primary_key[0]

    result = db.execute(
        meta.tables['clusters'].insert(),
        [{
            'name': 'test',
            'release_id': release_id,
            'mode': 'ha_compact',
            'status': 'new',
            'net_provider': 'neutron',
            'grouping': 'roles',
            'fuel_version': '10.0',
        }]
    )
    cluster_id = result.inserted_primary_key[0]

    TestPluginLinksConstraints.prepare(meta, cluster_id)


class TestPluginLinksConstraints(base.BaseAlembicMigrationTest):
    test_link = {
        'title': 'title',
        'url': 'http://www.zzz.com',
        'description': 'description',
        'hidden': False
    }

    @classmethod
    def prepare(cls, meta, cluster_id):
        cls.test_link['cluster_id'] = cluster_id

        db.execute(
            meta.tables['cluster_plugin_links'].insert(),
            [cls.test_link],
        )

    def test_duplicate_cluster_link(self):
        db.execute(
            self.meta.tables['cluster_plugin_links'].insert(),
            [self.test_link]
        )

        links_count = db.execute(
            sa.select(
                [sa.func.count(self.meta.tables['cluster_plugin_links'].c.id)]
            )).fetchone()[0]
        self.assertEqual(links_count, 2)


class TestRequiredComponentTypesField(base.BaseAlembicMigrationTest):

    def test_downgrade_release_required_component_types(self):
        releases_table = self.meta.tables['releases']
        self.assertNotIn('required_component_types', releases_table.c)
