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


import alembic
from oslo.serialization import jsonutils
import sqlalchemy as sa

from nailgun.db import db
from nailgun.db import dropdb
from nailgun.db.migration import ALEMBIC_CONFIG
from nailgun.test import base


_test_revision = '1a317451edf8'


def setup_module(module):
    dropdb()
    alembic.command.upgrade(ALEMBIC_CONFIG, _test_revision)
    prepare()


def prepare():
    meta = base.reflect_db_metadata()

    db.execute(
        meta.tables['plugins'].insert(),
        [{
            'name': 'test_plugin',
            'title': 'Test plugin',
            'version': '1.0.0',
            'description': 'Test plugin for Fuel',
            'homepage': 'http://fuel_plugins.test_plugin.com',
            'releases': jsonutils.dumps([
                {'repository_path': 'repositories/ubuntu'}
            ]),
            'package_version': '3.0.0',
            'fuel_version': jsonutils.dumps(['6.1', '7.0']),
            'attributes_metadata': jsonutils.dumps({
                'test_attribute': 'test_value'
            }),
            'volumes_metadata': jsonutils.dumps([
                {'id': 'test_volume'}
            ]),
            'roles_metadata': jsonutils.dumps({
                'test_role': {}
            }),
            'deployment_tasks': jsonutils.dumps([
                {'id': 'test_role', 'type': 'group'}
            ]),
            'tasks': jsonutils.dumps([
                {'role': 'test_role', 'stage': 'pre_deployment'}
            ])
        }])

    db.commit()


class TestPluginAttributesMigration(base.BaseAlembicMigrationTest):

    def test_attributes_metadata_exists(self):
        result = db.execute(
            sa.select([self.meta.tables['plugins'].c.attributes_metadata]))
        attributes_metadata = jsonutils.loads(result.fetchone()[0])
        self.assertEqual(
            attributes_metadata, {'test_attribute': 'test_value'})

    def test_volumes_metadata_exists(self):
        result = db.execute(
            sa.select([self.meta.tables['plugins'].c.volumes_metadata]))
        volumes_metadata = jsonutils.loads(result.fetchone()[0])
        self.assertEqual(
            volumes_metadata, [{'id': 'test_volume'}])

    def test_role_metadata_exists(self):
        result = db.execute(
            sa.select([self.meta.tables['plugins'].c.roles_metadata]))
        roles_metadata = jsonutils.loads(result.fetchone()[0])
        self.assertEqual(
            roles_metadata, {'test_role': {}})

    def test_deployment_tasks_exists(self):
        result = db.execute(
            sa.select([self.meta.tables['plugins'].c.deployment_tasks]))
        deployment_tasks = jsonutils.loads(result.fetchone()[0])
        self.assertEqual(
            deployment_tasks, [{'id': 'test_role', 'type': 'group'}])

    def test_tasks_exists(self):
        result = db.execute(
            sa.select([self.meta.tables['plugins'].c.tasks]))
        tasks = jsonutils.loads(result.fetchone()[0])
        self.assertEqual(
            tasks, [{'role': 'test_role', 'stage': 'pre_deployment'}])
