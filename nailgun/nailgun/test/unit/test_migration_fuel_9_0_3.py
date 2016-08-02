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

from nailgun.db import db
from nailgun.db import dropdb
from nailgun.db.migration import ALEMBIC_CONFIG
from nailgun.test import base
from oslo_serialization import jsonutils
import sqlalchemy as sa

_prepare_revision = 'f2314e5d63c9'
_test_revision = '04e474f95313'


def setup_module():
    dropdb()
    alembic.command.upgrade(ALEMBIC_CONFIG, _prepare_revision)
    prepare()
    alembic.command.upgrade(ALEMBIC_CONFIG, _test_revision)


def prepare():
    meta = base.reflect_db_metadata()
    db.execute(
        meta.tables['releases'].insert(),
        [{
            'name': 'test_name',
            'version': '2015.1-8.0',
            'operating_system': 'ubuntu',
            'state': 'available',
            'attributes_metadata': jsonutils.dumps({
                'editable': {
                    'external_dns': {
                        'dns_list': {
                            'value': {
                                'generator': 'from_settings',
                            },
                            'type': 'text',
                        }
                    },
                    'external_ntp': {
                        'ntp_list': {
                            'value': {
                                'generator': 'from_settings',
                            },
                            'type': 'text',
                        }
                    },
                },
            })
        }]
    )
    db.commit()


class TestLegacyTextList(base.BaseAlembicMigrationTest):

    def test_legacy_text_list_handling(self):
        result = db.execute(
            sa.select([self.meta.tables['releases'].c.attributes_metadata])
        ).fetchone()[0]
        attributes_metadata = jsonutils.loads(result)
        editable = attributes_metadata.get('editable', {})
        self.assertEqual(
            'from_settings_legacy_text_list',
            editable['external_dns']['dns_list']['value']['generator']
        )

        self.assertEqual(
            'from_settings_legacy_text_list',
            editable['external_dns']['dns_list']['value']['generator']
        )
