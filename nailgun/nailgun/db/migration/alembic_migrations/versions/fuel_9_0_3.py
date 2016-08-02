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

"""Fuel 9.0.3

Revision ID: 04e474f95313
Revises: f2314e5d63c9
Create Date: 2016-08-02 09:11:16.430633

"""

from distutils import version

from alembic import op
from oslo_serialization import jsonutils
import sqlalchemy as sa

from nailgun.db.sqlalchemy import utils

# revision identifiers, used by Alembic.
revision = '04e474f95313'
down_revision = 'f2314e5d63c9'


def upgrade():
    upgrade_release_legacy_text_list()


def downgrade():
    downgrade_release_legacy_text_list()


def _get_old_releases_attributes():
    connection = op.get_bind()
    select_query = sa.sql.text(
        "SELECT id, version, attributes_metadata FROM releases"
        " WHERE attributes_metadata IS NOT NULL"
    )
    for id, r_version, attributes_metadata in connection.execute(select_query):
        fuel_version = utils.fuel_version(r_version)
        if version.StrictVersion(fuel_version) >= version.StrictVersion('9.0'):
            continue
        yield id, jsonutils.loads(attributes_metadata)


def _update_release_attributes(id, attributes_metadata):
    connection = op.get_bind()
    update_query = sa.sql.text(
        "UPDATE releases SET attributes_metadata =:attributes_metadata"
        " WHERE id = :id"
    )

    connection.execute(
        update_query,
        id=id,
        attributes_metadata=jsonutils.dumps(attributes_metadata),
    )


LEGACY_TEXT_LIST_ATTRS = (
    ('external_dns', 'dns_list'),
    ('external_ntp', 'ntp_list'),
)


def upgrade_release_legacy_text_list():
    for id, attrs_meta in _get_old_releases_attributes():
        editable = attrs_meta.get('editable', {})

        for section, name in LEGACY_TEXT_LIST_ATTRS:
            if section in editable:
                editable[section][name]['value']['generator'] = (
                    "from_settings_legacy_text_list"
                )

        _update_release_attributes(id, attrs_meta)


def downgrade_release_legacy_text_list():
    for id, attrs_meta in _get_old_releases_attributes():
        editable = attrs_meta.get('editable', {})

        for section, name in LEGACY_TEXT_LIST_ATTRS:
            if section in editable:
                editable[section][name]['value']['generator'] = "from_settings"

        _update_release_attributes(id, attrs_meta)
