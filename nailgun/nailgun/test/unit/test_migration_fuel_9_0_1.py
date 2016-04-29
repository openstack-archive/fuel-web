#    Copyright 2016 Mirantis, Inc.
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
import sqlalchemy as sa

from nailgun.db import db
from nailgun.db import dropdb
from nailgun.db.migration import ALEMBIC_CONFIG
from nailgun.test import base

_prepare_revision = '11a9adc6d36a'
_test_revision = '675105097a69'


def setup_module():
    dropdb()
    alembic.command.upgrade(ALEMBIC_CONFIG, _prepare_revision)
    prepare()
    alembic.command.upgrade(ALEMBIC_CONFIG, _test_revision)


def prepare():
    meta = base.reflect_db_metadata()

    result = db.execute(
        meta.tables['releases'].insert(),
        [{
            'name': 'test_name',
            'version': 'mitaka-9.0',
            'operating_system': 'ubuntu',
            'state': 'available',
            'attributes_metadata': jsonutils.dumps({
                'editable': {}
            })
        }])
    releaseid = result.inserted_primary_key[0]

    result = db.execute(
        meta.tables['clusters'].insert(),
        [{
            'name': 'test_env',
            'release_id': releaseid,
            'mode': 'ha_compact',
            'status': 'new',
            'net_provider': 'neutron',
            'grouping': 'roles',
            'fuel_version': '9.0'
        }])
    cluster_id = result.inserted_primary_key[0]

    db.execute(
        meta.tables['attributes'].insert(),
        [{
            'cluster_id': cluster_id,
            'editable': '{}'
        }])

    db.commit()


class TestDeploymentHistoryMigration(base.BaseAlembicMigrationTest):
    def test_history_has_task_name_status_idx_index(self):
        tbl = self.meta.tables['deployment_history']
        self.assertIn('deployment_history_task_name_status_idx',
                      [i.name for i in tbl.indexes])


class TestClusterEditableAttributesMigration(base.BaseAlembicMigrationTest):
    def _get_clusters_attrs(self):
        clusters_editable_attrs = self.meta.tables['attributes'].c.editable
        for row in db.execute(sa.select([clusters_editable_attrs])).fetchall():
            yield jsonutils.loads(row[0])

    def test_cgroups_cluster_attrs(self):
        for cluster_attrs in self._get_clusters_attrs():
            self.assertIn('cgroups', cluster_attrs)
