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

"""Fuel 9.0.2

Revision ID: f2314e5d63c9
Revises: 675105097a69
Create Date: 2016-06-24 13:23:33.235613

"""

from distutils import version

from alembic import op
from oslo_serialization import jsonutils
import sqlalchemy as sa

from nailgun.db.sqlalchemy import utils


# revision identifiers, used by Alembic.
revision = 'f2314e5d63c9'
down_revision = '675105097a69'

rule_to_pick_bootdisk = [
    {'type': 'exclude_disks_by_name',
     'regex': '^nvme',
     'description': 'NVMe drives should be skipped as accessing such drives '
                    'during the boot typically requires using UEFI which is '
                    'still not supported by fuel-agent (it always installs '
                    'BIOS variant of  grub). '
                    'grub bug (http://savannah.gnu.org/bugs/?41883)'},
    {'type': 'pick_root_disk_if_disk_name_match',
     'regex': '^md',
     'root_mount': '/',
     'description': 'If we have /root on fake raid, then /boot partition '
                    'should land on to it too. We can\'t proceed with '
                    'grub-install otherwise.'}
]


def upgrade():
    upgrade_release_with_rules_to_pick_bootable_disk()
    upgrade_release_legacy_text_list()


def downgrade():
    downgrade_release_with_rules_to_pick_bootable_disk()
    downgrade_release_legacy_text_list()


def upgrade_release_with_rules_to_pick_bootable_disk():
    connection = op.get_bind()
    select_query = sa.sql.text(
        "SELECT id, volumes_metadata FROM releases "
        "WHERE volumes_metadata IS NOT NULL")
    update_query = sa.sql.text(
        "UPDATE releases SET volumes_metadata = :volumes_metadata "
        "WHERE id = :id")

    for id, volumes_metadata in connection.execute(select_query):
        volumes_metadata = jsonutils.loads(volumes_metadata)

        volumes_metadata['rule_to_pick_boot_disk'] = rule_to_pick_bootdisk

        connection.execute(
            update_query,
            id=id,
            volumes_metadata=jsonutils.dumps(volumes_metadata),
        )


def downgrade_release_with_rules_to_pick_bootable_disk():
    connection = op.get_bind()
    select_query = sa.sql.text(
        "SELECT id, volumes_metadata FROM releases "
        "WHERE volumes_metadata IS NOT NULL")
    update_query = sa.sql.text(
        "UPDATE releases SET volumes_metadata = :volumes_metadata "
        "WHERE id = :id")

    for id, volumes_metadata in connection.execute(select_query):
        volumes_metadata = jsonutils.loads(volumes_metadata)
        rule = volumes_metadata.pop('rule_to_pick_boot_disk', None)
        if rule is not None:
            connection.execute(
                update_query,
                id=id,
                volumes_metadata=jsonutils.dumps(volumes_metadata),
            )


def _get_old_releases_attributes():
    connection = op.get_bind()
    select_query = sa.sql.text(
        "SELECT id, version, attributes_metadata FROM releases"
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
                editable[section][name]['type'] = 'text'

        _update_release_attributes(id, attrs_meta)


def downgrade_release_legacy_text_list():
    for id, attrs_meta in _get_old_releases_attributes():
        editable = attrs_meta.get('editable', {})

        for section, name in LEGACY_TEXT_LIST_ATTRS:
            if section in editable:
                editable[section][name]['value']['generator'] = "from_settings"
                editable[section][name]['type'] = 'text_list'

        _update_release_attributes(id, attrs_meta)
