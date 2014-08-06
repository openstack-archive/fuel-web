#    Copyright 2014 Mirantis, Inc.
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

from alembic import op
import os
import six
import sqlalchemy as sa
from sqlalchemy.sql import text
import yaml

from nailgun.db.sqlalchemy.fixman import load_fixture
from nailgun.openstack.common import jsonutils


def upgrade_enum(table, column_name, enum_name, old_options, new_options):
    old_type = sa.Enum(*old_options, name=enum_name)
    new_type = sa.Enum(*new_options, name=enum_name)
    tmp_type = sa.Enum(*new_options, name="_" + enum_name)
    # Create a temporary type, convert and drop the "old" type
    tmp_type.create(op.get_bind(), checkfirst=False)
    op.execute(
        u'ALTER TABLE {0} ALTER COLUMN {1} TYPE _{2}'
        u' USING {1}::text::_{2}'.format(
            table,
            column_name,
            enum_name
        )
    )
    old_type.drop(op.get_bind(), checkfirst=False)
    # Create and convert to the "new" type
    new_type.create(op.get_bind(), checkfirst=False)
    op.execute(
        u'ALTER TABLE {0} ALTER COLUMN {1} TYPE {2}'
        u' USING {1}::text::{2}'.format(
            table,
            column_name,
            enum_name
        )
    )
    tmp_type.drop(op.get_bind(), checkfirst=False)


def drop_enum(name):
    op.execute(
        u'DROP TYPE {0}'.format(name)
    )


def convert_condition_value(val):
    if isinstance(val, six.string_types):
        return "'{0}'".format(val)
    return str(val).lower()


def upgrade_release_attributes_50_to_51(attrs_meta):
    if not attrs_meta.get('editable'):
        return attrs_meta

    def depends_to_restrictions(depends, restrictions):
        for cond in depends:
            expr = cond.keys()[0]
            restrictions.append(
                expr + " != " + convert_condition_value(cond[expr]))

    def conflicts_to_restrictions(conflicts, restrictions):
        for cond in conflicts:
            expr = cond.keys()[0]
            restrictions.append(
                expr + " == " + convert_condition_value(cond[expr]))

    for _, group in six.iteritems(attrs_meta.get('editable')):
        for _, attr in six.iteritems(group):
            restrictions = []
            if attr.get('depends'):
                depends_to_restrictions(attr['depends'], restrictions)
                attr.pop('depends')
            if attr.get('conflicts'):
                conflicts_to_restrictions(attr['conflicts'], restrictions)
                attr.pop('conflicts')
            if restrictions:
                attr['restrictions'] = restrictions
    return attrs_meta


def upgrade_release_roles_50_to_51(roles_meta):
    for _, role in six.iteritems(roles_meta):
        if role.get('depends'):
            for depend in role['depends']:
                if isinstance(depend.get('condition'), dict):
                    cond = depend['condition']
                    expr = cond.keys()[0]
                    depend['condition'] = \
                        expr + " == " + convert_condition_value(cond[expr])
    return roles_meta


def upgrade_release_wizard_metadata_50_to_51(fixture_path=None):
    if not fixture_path:
        fixture_path = os.path.join(os.path.dirname(__file__), '..',
                                    'fixtures', 'openstack.yaml')

    with open(fixture_path, 'r') as fixture_file:
        fixt = load_fixture(fixture_file, loader=yaml)

    # wizard_meta is the same for all existing in db releases
    wizard_meta = fixt[0]['fields']['wizard_metadata']
    # remove nsx data from Network section of wizard_metadata
    wizard_meta['Network']['manager']['values'] = [
        n for n in wizard_meta['Network']['manager']['values']
        if n['data'] != 'neutron-nsx'
    ]

    return wizard_meta


def upgrade_clusters_replaced_info(connection):
    select = text(
        """SELECT id, replaced_provisioning_info, replaced_deployment_info
        FROM clusters""")
    clusters = connection.execute(select)
    for cluster in clusters:
        nodes_select = text(
            """SELECT id FROM nodes WHERE cluster_id=:id""")
        nodes = connection.execute(
            nodes_select,
            id=cluster[0])
        provisioning_info = jsonutils.loads(cluster[1])
        deployment_nodes = jsonutils.loads(cluster[2])
        provisioning_nodes = provisioning_info.pop('nodes', [])
        for node in nodes:
            node_deploy = [d for d in deployment_nodes
                           if d['uid'] == str(node[0])]
            node_provision = next((d for d in provisioning_nodes
                                   if d['uid'] == str(node[0])), {})
            update_node = text(
                """UPDATE nodes
                SET replaced_deployment_info = :deploy,
                    replaced_provisioning_info = :provision
                WHERE id = :id""")
            connection.execute(
                update_node,
                deploy=jsonutils.dumps(node_deploy),
                provision=jsonutils.dumps(node_provision),
                id=node[0])
        update_cluster = text(
            """UPDATE clusters
            SET replaced_deployment_info = :deploy,
                replaced_provisioning_info = :provision
            WHERE id = :id""")
        connection.execute(
            update_cluster,
            deploy=jsonutils.dumps({}),
            provision=jsonutils.dumps(provisioning_info),
            id=cluster[0])
