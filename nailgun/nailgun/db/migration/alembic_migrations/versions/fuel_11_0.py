#    Copyright 2016 Mirantis, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the 'License'); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an 'AS IS' BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

'''Fuel 11.0

Revision ID: de475d3a79d6
Revises: c6edea552f1e
Create Date: 2016-11-11 11:29:43.786720

'''

from alembic import op
from distutils import version
from oslo_serialization import jsonutils
import sqlalchemy as sa

from nailgun import consts
from nailgun import objects

# revision identifiers, used by Alembic.
revision = 'de475d3a79d6'
down_revision = 'c6edea552f1e'


def upgrade():
    upgrade_attributes_metadata()


def downgrade():
    downgrade_attributes_metadata()


SECURITY_GROUP = {
    'value': 'iptables_hybrid',
    'values': [
        {
            'data': 'openvswitch',
            'label': 'Open vSwitch Firewall Driver',
            'description': 'Choose this type of firewall driver if you'
                           ' use OVS Brige for networking needs.'
        },
        {
            'data': 'iptables_hybrid',
            'label': 'Iptables-based Firewall Driver',
            'description': 'Choose this type of firewall driver if you'
                           ' use Linux Bridge for networking needs.'
        }
    ],
    'group': 'security',
    'weight': 20,
    'type': 'radio',
}


def upgrade_attributes_metadata():
    connection = op.get_bind()
    upgrade_release_attributes_metadata(connection)
    upgrade_cluster_attributes(connection)


def upgrade_release_attributes_metadata(connection):
    select_query = sa.sql.text(
        'SELECT id, attributes_metadata FROM releases '
        'WHERE attributes_metadata IS NOT NULL')

    update_query = sa.sql.text(
        'UPDATE releases SET attributes_metadata = :attributes_metadata '
        'WHERE id = :id')

    for id, attrs in connection.execute(select_query):
        if _is_not_available_version_for_security_group(
                objects.Release.get_by_uid(id).environment_version):
            continue
        attrs = jsonutils.loads(attrs)
        editable = attrs.setdefault('editable', {})
        if _check_security_group_exist_in_editable_attributes(
                editable
        ):
            continue
        common = editable.setdefault('common', {})
        common.setdefault('security_group', SECURITY_GROUP)
        connection.execute(
            update_query,
            id=id,
            attributes_metadata=jsonutils.dumps(attrs))


def upgrade_cluster_attributes(connection):
    select_query = sa.sql.text(
        'SELECT cluster_id, editable FROM attributes WHERE editable IS NOT '
        'NULL')

    update_query = sa.sql.text(
        'UPDATE attributes SET editable = :editable WHERE cluster_id = '
        ':cluster_id')

    for id, editable in connection.execute(select_query):
        if _is_not_available_version_for_security_group(
                objects.Cluster.get_by_uid(id).release.environment_version):
            continue
        editable = jsonutils.loads(editable)
        if _check_security_group_exist_in_editable_attributes(editable):
            continue
        common = editable.setdefault('common', {})
        common.setdefault('security_group', SECURITY_GROUP)
        connection.execute(
            update_query,
            cluster_id=id,
            editable=jsonutils.dumps(editable))


def downgrade_attributes_metadata():
    connection = op.get_bind()
    downgrade_release_attributes_metadata(connection)
    downgrade_cluster_attributes(connection)


def downgrade_release_attributes_metadata(connection):
    select_query = sa.sql.text(
        'SELECT id, attributes_metadata FROM releases '
        'WHERE attributes_metadata IS NOT NULL')

    update_query = sa.sql.text(
        'UPDATE releases SET attributes_metadata = :attributes_metadata '
        'WHERE id = :id')

    for id, attrs in connection.execute(select_query):
        attrs = jsonutils.loads(attrs)
        editable = attrs.setdefault('editable', {})
        common = editable.setdefault('common', {})
        common.pop('security_group', None)
        connection.execute(
            update_query,
            id=id,
            attributes_metadata=jsonutils.dumps(attrs))


def downgrade_cluster_attributes(connection):
    select_query = sa.sql.text(
        'SELECT cluster_id, editable FROM attributes '
        'WHERE editable IS NOT NULL')

    update_query = sa.sql.text(
        'UPDATE attributes SET editable = :editable '
        'WHERE cluster_id = :cluster_id')

    for cluster_id, editable in connection.execute(select_query):
        editable = jsonutils.loads(editable)
        common = editable.setdefault('common', {})
        common.pop('security_group', None)
        connection.execute(
            update_query,
            cluster_id=cluster_id,
            editable=jsonutils.dumps(editable))


def _is_not_available_version_for_security_group(environment_version):
    if version.StrictVersion(environment_version) < version.StrictVersion(
            consts.FUEL_SECURITY_GROUP_AVAILABLE_SINCE):
        return True
    return False


def _check_security_group_exist_in_editable_attributes(editable):
    return editable.setdefault('common', {}).get('security_group')
