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

from itertools import chain
import re

from alembic import op
from oslo_serialization import jsonutils
import six
import sqlalchemy as sa
from sqlalchemy.sql import text

from nailgun import consts
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
    """Negates condition."""
    return "not ({0})".format(condition)


def remove_question_operator(expression):
    """Removes '?' operator from expressions, it was deprecated in 6.0"""
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
    """Remove '?' operator from expressions"""
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
    """Convert role_metadata.depends values into roles_metadata.restrictions"""
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

            # for ubuntu we need to add 'trusty main'
            if release[1].lower() == 'ubuntu':
                repo_path += ' trusty main'

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


def move_orchestrator_data_to_attributes(connection):
    """Moving data from orchestrator data db table to cluster attributes

    :param connection: a database connection
    """

    select_query = text(
        "SELECT "
        "id, "
        "release_id, "
        "repo_metadata, "
        "puppet_manifests_source, "
        "puppet_modules_source "
        "FROM release_orchestrator_data")

    for odata in connection.execute(select_query):
        select_query = text(
            "SELECT id, attributes_metadata, operating_system "
            "   FROM releases WHERE id = :release_id")

        for release in connection.execute(select_query, release_id=odata[1]):
            repo_setup = {
                'metadata': {
                    # old releases shouldn't be able to edit
                    # repos
                    'restrictions': [{
                        'condition': 'true',
                        'action': 'hide',
                    }],
                    'label': 'Repositories',
                    'weight': 50,
                },
                'repos': {
                    'type': 'custom_repo_configuration',
                    'value': [],
                }}

            puppet = {
                'manifests': odata[3],
                'modules': odata[4],
            }

            if release[2].lower() == 'ubuntu':
                for name, repo in six.iteritems(jsonutils.loads(odata[2])):
                    uri, suite, section = repo.split()
                    repo_setup['repos']['value'].append({
                        'type': 'deb',
                        'name': name,
                        'uri': uri,
                        'suite': suite,
                        'section': section,
                        'priority': 1001
                    })
            elif release[2].lower() == 'centos':
                for name, repo in six.iteritems(jsonutils.loads(odata[2])):
                    repo_setup['repos']['value'].append({
                        'type': 'rpm',
                        'name': name,
                        'uri': repo,
                        'priority': 1
                    })

            # update releases
            attributes_metadata = jsonutils.loads(release[1])
            attributes_metadata['editable'].update({'repo_setup': repo_setup})
            attributes_metadata['generated'].update({'puppet': puppet})

            update_query = text(
                "UPDATE releases "
                "   SET attributes_metadata = :attributes_metadata "
                "   WHERE id = :release_id")
            connection.execute(
                update_query,
                attributes_metadata=jsonutils.dumps(attributes_metadata),
                release_id=odata[1])

            # update cluster attributes
            select_query = text(
                "SELECT a.id, a.editable, a.generated "
                "   FROM attributes as a INNER JOIN clusters as c "
                "      ON a.cluster_id = c.id "
                "   WHERE c.release_id = :release_id")

            for attr in connection.execute(select_query, release_id=odata[1]):
                editable = jsonutils.loads(attr[1])
                generated = jsonutils.loads(attr[2])

                editable.update({'repo_setup': repo_setup})
                generated.update({'puppet': puppet})

                connection.execute(
                    text(
                        "UPDATE attributes "
                        "   SET editable = :editable, generated = :generated "
                        "   WHERE id = :attr_id"),
                    editable=jsonutils.dumps(editable),
                    generated=jsonutils.dumps(generated),
                    attr_id=attr[0])


def upgrade_attributes_metadata_6_0_to_6_1(attributes_meta):
    attributes_meta['editable']['storage']['volumes_lvm']['description'] = \
        'It is recommended to have at least one Storage - Cinder LVM node.'
    attributes_meta['editable']['common']['use_vcenter'] = {
        "value": False,
        "weight": 30,
        "type": "hidden"
    }

    return attributes_meta


def upgrade_master_node_settings_6_0_to_6_1(master_node_settings):
    master_node_settings['statistics']['name']['type'] = 'hidden'
    master_node_settings['statistics']['email']['type'] = 'hidden'
    master_node_settings['statistics']['company']['type'] = 'hidden'
    master_node_settings['tracking'] = {
        "email": {
            "type": "text",
            "value": "",
            "label": "Mirantis Account Email",
            "weight": 10,
            "regex": {
                "source": "^\\S+@\\S+\.\\S+$",
                "error": "Invalid email"
            }
        },
        "password": {
            "type": "password",
            "value": "",
            "label": "Password",
            "weight": 20,
            "regex": {
                "source": "\\S",
                "error": "Password cannot be empty"
            }
        }
    }
    master_node_settings['statistics']['name']['regex'] = {}
    master_node_settings['statistics']['email']['regex'] = {}
    master_node_settings['statistics']['company']['regex'] = {}
    master_node_settings['statistics']['name']['restrictions'] = {}
    master_node_settings['statistics']['email']['restrictions'] = {}
    master_node_settings['statistics']['company']['restrictions'] = {}

    return master_node_settings


def upgrade_role_limits_6_0_to_6_1(roles_meta, _limits_to_update):
    for role_name, role_definition in six.iteritems(roles_meta):
        if role_name in _limits_to_update:
            role_definition['limits'] = _limits_to_update[role_name]

    return roles_meta


def upgrade_role_restrictions_6_0_to_6_1(roles_meta, _new_role_restrictions):
    for role_name, role_definition in six.iteritems(roles_meta):
        if role_name in _new_role_restrictions:
            role_definition['restrictions'] = _new_role_restrictions[role_name]

    return roles_meta


def upgrade_vip_types_6_0_to_6_1(connection):
    update_query_node_null = text(
        "UPDATE ip_addrs SET vip_type = :haproxy WHERE node IS NULL")

    connection.execute(update_query_node_null,
                       haproxy=consts.NETWORK_VIP_NAMES_61.haproxy)


def downgrade_vip_types_6_1_to_6_0(connection):
    delete_query = text(
        "DELETE FROM ip_addrs WHERE vip_type != :haproxy AND node IS NULL")
    connection.execute(delete_query, haproxy=consts.NETWORK_VIP_NAMES_61.haproxy)


def upgrade_6_0_to_6_1_plugins_cluster_attrs_use_ids_mapping(connection):
    """Convert plugin version mapping to plugin ids

    In Fuel 6.0 we had plugin version in cluster attributes
    to identify which plugin should be enabled or disabled.
    In 6.1 release we have plugins updates feature, it means
    that a single plugin can be updated/overwritten with newer
    version. For example 1.0.0 can be replaced with 1.0.1.
    As result we cannot rely on versions anymore, here we
    convert version mapping to plugin ids.

    See blueprint:
    https://blueprints.launchpad.net/fuel/+spec/plugins-security-fixes-delivery
    """
    select_attrs = text("""SELECT id, editable FROM attributes""")

    select_plugins = text(
        """SELECT id FROM plugins
        WHERE name = :plugin_name AND
        version = :plugin_version""")

    update_attrs = text(
        """UPDATE attributes
        SET editable = :editable
        WHERE id = :id""")

    attrs_list = connection.execute(select_attrs)
    for raw_attrs in attrs_list:
        attr_id = raw_attrs[0]
        attrs = jsonutils.loads(raw_attrs[1])

        for key, attr in six.iteritems(attrs):
            metadata = attr.get('metadata', {})
            plugin_version = metadata.get('plugin_version')
            if not plugin_version:
                continue

            plugin_name = key

            # If there is no plugin with such version
            # and name, it means that something was wrong
            # and somebody deleted the plugin from database
            # we must not fail migration in this case
            plugin_id = None

            plugins = list(connection.execute(
                select_plugins,
                plugin_name=plugin_name,
                plugin_version=plugin_version))

            if plugins:
                plugin_id = plugins[0][0]

            del attr['metadata']['plugin_version']
            attr['metadata']['plugin_id'] = plugin_id

        connection.execute(
            update_attrs,
            editable=jsonutils.dumps(attrs),
            id=attr_id)


def upgrade_networks_metadata_to_6_1(networks_meta, _bonding_metadata):
    networks_meta['bonding'] = _bonding_metadata

    nets = [k for k, v in six.iteritems(networks_meta) if v.get('networks')]
    for network in chain(*[networks_meta[net]['networks'] for net in nets]):
        network = create_default_vips(network)

    return networks_meta


def upgrade_network_groups_metadata_6_0_to_6_1(connection):
    select_query = text("SELECT id, meta FROM network_groups")
    update_query = text("UPDATE network_groups SET meta = :meta "
                        "WHERE id = :id")

    net_groups = connection.execute(select_query)

    for ng_id, ng_meta in net_groups:
        updated_meta = create_default_vips(jsonutils.loads(ng_meta))
        connection.execute(
            update_query,
            id=ng_id,
            meta=jsonutils.dumps(updated_meta)
        )


def create_default_vips(network):
    if "assign_vip" in network:
        if network["assign_vip"]:
            network["vips"] = [consts.NETWORK_VIP_NAMES_61.haproxy]

        del network["assign_vip"]

    return network


def upgrade_ubuntu_cobbler_profile_6_0_to_6_1(connection):
    select_query = text("SELECT id, generated FROM attributes")
    update_query = text(
        "UPDATE attributes SET generated = :generated WHERE id = :attr_id")
    for attr_id, generated in connection.execute(select_query):
        attrs = jsonutils.loads(generated)
        if attrs['cobbler']['profile'] == 'ubuntu_1204_x86_64':
            attrs['cobbler']['profile'] = 'ubuntu_1404_x86_64'
            connection.execute(
                update_query,
                generated=jsonutils.dumps(attrs),
                attr_id=attr_id)

    select_query = text("SELECT id, attributes_metadata FROM releases")
    update_query = text(
        "UPDATE releases SET attributes_metadata = :attrs_meta"
        " WHERE id = :release_id")
    for release_id, attributes_metadata in connection.execute(select_query):
        attrs = jsonutils.loads(attributes_metadata)
        if attrs['generated']['cobbler']['profile']['generator_arg'] == \
                'ubuntu_1204_x86_64':
            attrs['generated']['cobbler']['profile']['generator_arg'] = \
                'ubuntu_1404_x86_64'
            connection.execute(
                update_query,
                attrs_meta=jsonutils.dumps(attrs),
                release_id=release_id)


def upgrade_cluster_attributes_6_0_to_6_1(connection):
    select_query = text("""SELECT id, editable FROM attributes""")
    update_query = text(
        """UPDATE attributes SET editable = :editable WHERE id = :attr_id""")

    for attr_id, editable in connection.execute(select_query):
        attributes = jsonutils.loads(editable)
        attributes['common']['use_vcenter'] = {
            "value": False,
            "weight": 30,
            "type": "hidden"
        }

        connection.execute(
            update_query,
            editable=jsonutils.dumps(attributes),
            attr_id=attr_id)
