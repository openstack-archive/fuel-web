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
import json
import os
import re
import six
import sqlalchemy as sa
from sqlalchemy.sql import text
import uuid
import yaml

from nailgun.db.sqlalchemy.fixman import load_fixture
from nailgun.openstack.common import jsonutils
from nailgun.settings import settings


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


def negate_condition(condition):
    """Negates condition.
    """
    return "not ({0})".format(condition)


def remove_question_operator(expression):
    """Removes '?' operator from expressions, it was deprecated in 6.0
    """
    return re.sub(r'(:[\w\.\-]+)\?', '\\1', expression)


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


def upgrade_release_attributes_51_to_60(attrs_meta):
    """Remove '?' operator from expressions
    """
    if not attrs_meta.get('editable'):
        return attrs_meta

    def convert_restrictions(restrictions):
        result = []
        for restriction in restrictions:
            if isinstance(restriction, basestring):
                restriction = remove_question_operator(restriction)
            else:
                restriction['condition'] = remove_question_operator(
                    restriction['condition'])
            result.append(restriction)
        return result

    for _, group in six.iteritems(attrs_meta.get('editable')):
        for _, attr in six.iteritems(group):
            if 'restrictions' in attr:
                attr['restrictions'] = convert_restrictions(
                    attr['restrictions'])
            if 'values' in attr:
                for value in attr['values']:
                    if 'restrictions' in value:
                        value['restrictions'] = convert_restrictions(
                            value['restrictions'])

    return attrs_meta


def upgrade_release_roles_50_to_51(roles_meta):
    for _, role in six.iteritems(roles_meta):
        if role.get('depends'):
            for depend in role['depends']:
                cond = depend.get('condition')
                if isinstance(cond, dict):
                    expr = cond.keys()[0]
                    depend['condition'] = \
                        expr + " == " + convert_condition_value(cond[expr])
    return roles_meta


def upgrade_release_roles_51_to_60(roles_meta, add_meta=None):
    """Convert all role_metadata.depends values into
    roles_metadata.restrictions.
    """
    add_meta = add_meta or {}
    for role_name, role in six.iteritems(roles_meta):
        for depend in role.get('depends', []):
            cond = depend.get('condition')
            new_restriction = {
                'condition': remove_question_operator(negate_condition(cond))
            }
            if 'warning' in depend:
                new_restriction['message'] = depend['warning']

            role.setdefault('restrictions', [])
            role['restrictions'].append(new_restriction)

        if 'depends' in role:
            del role['depends']

        if role_name in add_meta:
            role.update(add_meta[role_name])
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


def upgrade_release_set_deployable_false(connection, versions):
    """Set deployable=False for a given versions list.

    :param connection: a database connection
    :param versions: a list of versions to be forbidden
    """
    update_query = text(
        "UPDATE releases SET is_deployable = 'false' "
        "   WHERE version IN :versions")

    connection.execute(update_query, versions=tuple(versions))


def upgrade_release_fill_orchestrator_data(connection, versions):
    """Fill release_orchestrator_data if it's not filled yet.

    :param connection: a database connection
    :param versions: a list of versions to be forbidden
    """
    for version in versions:
        select_query = text(
            "SELECT id, operating_system FROM releases "
            "   WHERE version LIKE :version AND id NOT IN ("
            "       SELECT release_id FROM release_orchestrator_data "
            "   )")

        releases = connection.execute(select_query, version=version)

        for release in releases:
            insert_query = text(
                "INSERT INTO release_orchestrator_data ("
                "       release_id, repo_metadata, puppet_manifests_source, "
                "       puppet_modules_source)"
                "   VALUES ("
                "       :release_id, "
                "       :repo_metadata, "
                "       :puppet_manifests_source, "
                "       :puppet_modules_source)")

            # if release_orchestrator_data isn't filled then releases'
            # repos stores in unversioned directory with "fuelweb" word
            repo_path = 'http://{MASTER_IP}:8080/{OS}/fuelweb/x86_64'.format(
                MASTER_IP=settings.MASTER_IP, OS=release[1].lower())

            # for ubuntu we need to add 'precise main'
            if release[1].lower() == 'ubuntu':
                repo_path += ' precise main'

            connection.execute(
                insert_query,
                release_id=release[0],
                repo_metadata=(
                    '{{ "nailgun": "{0}" }}'.format(repo_path)),
                puppet_manifests_source=(
                    'rsync://{MASTER_IP}:/puppet/manifests/'.format(
                        MASTER_IP=settings.MASTER_IP)),
                puppet_modules_source=(
                    'rsync://{MASTER_IP}:/puppet/modules/'.format(
                        MASTER_IP=settings.MASTER_IP)),
            )


def dump_master_node_settings(connection, fixture_path=None):
    """Generate uuid for master node installation and update
    master_node_settings table by generated value

    Arguments:
    connection - a database connection
    """

    if not fixture_path:
        fixture_path = os.path.join(os.path.dirname(__file__), '..',
                                    'fixtures', 'master_node_settings.yaml')

    with open(fixture_path, 'r') as fixture_file:
        fixt = load_fixture(fixture_file, loader=yaml)

    settings = json.dumps(fixt[0]["fields"]["settings"])

    generated_uuid = str(uuid.uuid4())

    insert_query = text(
        "INSERT INTO master_node_settings (master_node_uid, settings) "
        "   VALUES (:master_node_uid, :settings)"
    )

    connection.execute(insert_query, master_node_uid=generated_uuid,
                       settings=settings)
