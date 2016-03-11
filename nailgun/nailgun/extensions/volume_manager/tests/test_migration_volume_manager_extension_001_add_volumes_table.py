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

# TODO(eli): All extension specific tests will be moved
# into extension directory.
# Will be done as a part of blueprint:
# https://blueprints.launchpad.net/fuel/+spec/volume-manager-refactoring

import alembic
from oslo_serialization import jsonutils
import sqlalchemy as sa

from nailgun.db import db
from nailgun.db import dropdb
from nailgun.db.migration import ALEMBIC_CONFIG
from nailgun.db.migration import make_alembic_config_from_extension
from nailgun.extensions.consts import extensions_migration_buffer_table_name
from nailgun.extensions.volume_manager.extension import VolumeManagerExtension
from nailgun.test import base


_core_test_revision = '1e50a4903910'
_extension_test_revision = '086cde3de7cf'


def setup_module(module):
    dropdb()
    # Run core migration in order to create buffer table
    alembic.command.upgrade(ALEMBIC_CONFIG, _core_test_revision)
    prepare()
    # Run extension migrations
    ext_alembic_config = make_alembic_config_from_extension(
        VolumeManagerExtension)
    alembic.command.upgrade(ext_alembic_config, _extension_test_revision)


def prepare():
    meta = base.reflect_db_metadata()

    # Fill in migration table with data
    db.execute(
        meta.tables[extensions_migration_buffer_table_name].insert(),
        [{'extension_name': 'volume_manager',
          'data': jsonutils.dumps({'node_id': 1, 'volumes': [{'volume': 1}]})},
         {'extension_name': 'volume_manager',
          'data': jsonutils.dumps({'node_id': 2, 'volumes': [{'volume': 2}]})},
         {'extension_name': 'some_different_extension',
          'data': 'some_data'}])

    db.commit()


class TestVolumeManagerExtensionAddVolumesTable(base.BaseAlembicMigrationTest):

    def test_add_volumes_table(self):
        result = db.execute(
            sa.select([
                self.meta.tables['volume_manager_node_volumes'].c.node_id,
                self.meta.tables['volume_manager_node_volumes'].c.volumes]))
        records = list(result)

        node_ids = [r[0] for r in records]
        self.assertItemsEqual(node_ids, [1, 2])

        volumes = [jsonutils.loads(r[1]) for r in records]
        self.assertItemsEqual(
            [[{'volume': 1}], [{'volume': 2}]],
            volumes)

        result = db.execute(
            sa.select([
                self.meta.tables[
                    extensions_migration_buffer_table_name].c.extension_name,
                self.meta.tables[
                    extensions_migration_buffer_table_name].c.data]))
        self.assertEqual(
            list(result),
            [('some_different_extension', 'some_data')])
