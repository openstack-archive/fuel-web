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

"""Fuel 10.0

Revision ID: c6edea552f1e
Revises: 675105097a69
Create Date: 2016-04-08 15:20:43.989472

"""

from alembic import op
import copy
import sqlalchemy as sa

from oslo_serialization import jsonutils

from nailgun.db.sqlalchemy.models import fields
from nailgun.db.sqlalchemy.models import NodeNICInterface
from nailgun import objects


# revision identifiers, used by Alembic.
revision = 'c6edea552f1e'
down_revision = 'f2314e5d63c9'


def upgrade():
    upgrade_plugin_links_constraints()
    upgrade_release_with_nic_attributes()
    upgrade_node_nic_attributes()
    upgrade_plugin_with_nics_and_nodes_attributes()
    upgrade_node_deployment_info()
    upgrade_release_required_component_types()


def downgrade():
    downgrade_release_required_component_types()
    downgrade_node_deployment_info()
    downgrade_plugin_with_nics_and_nodes_attributes()
    downgrade_release_with_nic_attributes()
    downgrade_node_nic_attributes()
    downgrade_plugin_links_constraints()


default_release_nic_attributes = {
    "offloading": {
        "disable": {"type": "checkbox", "value": False,
                    "weight": 10, "label": "Disable offloading"},
        "modes": {"value": {}, "type": "offloading_modes",
                  "description": "Offloading modes", "weight": 20,
                  "label": "Offloading modes"},
        "metadata": {"weight": 10, "label": "Offloading"}
    },
    "mtu": {
        "value": {"type": "text", "value": None, "weight": 10,
                  "label": "MTU"},
        "metadata": {"weight": 20, "label": "MTU"}
    },
    "sriov": {
        "numvfs": {"min": 0, "type": "number", "value": None,
                   "weight": 20, "label": "Virtual functions"},
        "enabled": {"type": "checkbox", "value": None,
                    "weight": 10, "label": "SRIOV enabled"},
        "physnet": {"type": "text", "value": "", "weight": 30,
                    "label": "Physical network"},
        "metadata": {"weight": 30, "label": "SRIOV"}
    },
    "dpdk": {
        "enabled": {"type": "checkbox", "value": None,
                    "weight": 10, "label": "DPDK enabled"},
        "metadata": {"weight": 40, "label": "DPDK"}
    }
}


default_release_bond_attributes = {}


def upgrade_plugin_links_constraints():
    connection = op.get_bind()

    # plugin links
    plugin_links_remove_duplicates_query = sa.text("""
        DELETE FROM plugin_links
        WHERE id
        NOT IN (
          SELECT MIN(id)
          FROM plugin_links
          GROUP BY url
        )
    """)
    connection.execute(plugin_links_remove_duplicates_query)

    op.create_unique_constraint(
        'plugin_links_url_uc',
        'plugin_links',
        ['url'])

    # cluster plugin links
    cluster_plugin_links_remove_duplicates_query = sa.text("""
        DELETE FROM cluster_plugin_links
        WHERE id
        NOT IN (
          SELECT MIN(id)
          FROM cluster_plugin_links
          GROUP BY cluster_id,url
        )
    """)
    connection.execute(cluster_plugin_links_remove_duplicates_query)

    op.create_unique_constraint(
        'cluster_plugin_links_cluster_id_url_uc',
        'cluster_plugin_links',
        ['cluster_id', 'url'])


def downgrade_plugin_links_constraints():
    op.drop_constraint('cluster_plugin_links_cluster_id_url_uc',
                       'cluster_plugin_links')

    op.drop_constraint('plugin_links_url_uc', 'plugin_links')


def upgrade_plugin_with_nics_and_nodes_attributes():
    op.add_column(
        'plugins',
        sa.Column(
            'nic_attributes_metadata',
            fields.JSON(),
            nullable=False,
            server_default='{}'
        )
    )

    op.add_column(
        'plugins',
        sa.Column(
            'bond_attributes_metadata',
            fields.JSON(),
            nullable=False,
            server_default='{}'
        )
    )

    op.add_column(
        'plugins',
        sa.Column(
            'node_attributes_metadata',
            fields.JSON(),
            nullable=False,
            server_default='{}'
        )
    )

    op.add_column(
        'node_bond_interfaces',
        sa.Column(
            'attributes',
            fields.JSON(),
            nullable=False,
            server_default='{}'
        )
    )

    op.create_table(
        'node_nic_interface_cluster_plugins',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column(
            'attributes', fields.JSON(), nullable=False, server_default='{}'),
        sa.Column('cluster_plugin_id', sa.Integer(), nullable=False),
        sa.Column('interface_id', sa.Integer(), nullable=False),
        sa.Column('node_id', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(
            ['cluster_plugin_id'],
            ['cluster_plugins.id'],
            ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['interface_id'], ['node_nic_interfaces.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['node_id'], ['nodes.id'], ondelete='CASCADE')
    )

    op.create_table(
        'node_bond_interface_cluster_plugins',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column(
            'attributes', fields.JSON(), nullable=False, server_default='{}'),
        sa.Column('cluster_plugin_id', sa.Integer(), nullable=False),
        sa.Column('bond_id', sa.Integer(), nullable=False),
        sa.Column('node_id', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(
            ['cluster_plugin_id'],
            ['cluster_plugins.id'],
            ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['bond_id'], ['node_bond_interfaces.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['node_id'], ['nodes.id'], ondelete='CASCADE')
    )

    op.create_table(
        'node_cluster_plugins',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column(
            'attributes', fields.JSON(), nullable=False, server_default='{}'),
        sa.Column('cluster_plugin_id', sa.Integer(), nullable=False),
        sa.Column('node_id', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(
            ['cluster_plugin_id'],
            ['cluster_plugins.id'],
            ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['node_id'], ['nodes.id'], ondelete='CASCADE')
    )


def upgrade_release_required_component_types():
    op.add_column(
        'releases',
        sa.Column(
            'required_component_types',
            fields.JSON(),
            nullable=False,
            server_default='[]'
        )
    )
    connection = op.get_bind()
    connection.execute(
        sa.sql.text(
            "UPDATE releases SET required_component_types = :required_types"),
        required_types=jsonutils.dumps(['hypervisor', 'network', 'storage'])
    )


def upgrade_release_with_nic_attributes():
    # TODO(ekosareva): update releses with bond_attributes
    op.add_column(
        'releases',
        sa.Column(
            'nic_attributes',
            fields.JSON(),
            nullable=False,
            server_default='{}'
        )
    )
    op.add_column(
        'releases',
        sa.Column(
            'bond_attributes',
            fields.JSON(),
            nullable=False,
            server_default='{}'
        )
    )
    connection = op.get_bind()
    connection.execute(
        sa.sql.text(
            "UPDATE releases SET nic_attributes = :nic_attributes, "
            "bond_attributes = :bond_attributes"),
        nic_attributes=jsonutils.dumps(default_release_nic_attributes),
        bond_attributes=jsonutils.dumps(default_release_bond_attributes)
    )


def downgrade_release_with_nic_attributes():
    op.drop_column('releases', 'bond_attributes')
    op.drop_column('releases', 'nic_attributes')


def upgrade_node_nic_attributes():
    def _create_interface_meta(interface_properties):
        return {
            'offloading_modes': [],
            'sriov': {
                'available': interface_properties.get(
                    'sriov', {}).get('available', False),
                'pci_id': interface_properties.get(
                    'sriov', {}).get('pci_id', ''),
                'totalvfs': interface_properties.get(
                    'sriov', {}).get('sriov_totalvfs', 0)
            },
            'dpdk': {
                'available': interface_properties.get(
                    'dpdk', {}).get('available', False)
            },
            'pci_id': interface_properties.get('pci_id', ''),
            'numa_node': interface_properties.get('numa_node')
        }

    def _create_nic_attributes(interface_properties, offloading_modes):
        nic_attributes = copy.deepcopy(default_release_nic_attributes)
        nic_attributes['mtu']['value']['value'] = \
            interface_properties.get('mtu')
        nic_attributes['sriov']['enabled']['value'] = \
            interface_properties.get('sriov', {}).get('enabled', False)
        nic_attributes['sriov']['numvfs']['value'] = \
            interface_properties.get('sriov', {}).get('sriov_numvfs')
        nic_attributes['sriov']['physnet']['value'] = \
            interface_properties.get('sriov', {}).get('physnet', 'physnet2')
        nic_attributes['dpdk']['enabled']['value'] = \
            interface_properties.get('dpdk', {}).get('enabled', False)

        nic_attributes['offloading']['disable']['value'] = \
            interface_properties.get('disable_offloading', False)
        offloading_modes = \
            NodeNICInterface.offloading_modes_as_flat_dict(offloading_modes)
        nic_attributes['offloading']['modes']['value'] = offloading_modes
        return nic_attributes

    op.add_column(
        'node_nic_interfaces',
        sa.Column(
            'attributes',
            fields.JSON(),
            nullable=False,
            server_default='{}'
        )
    )

    op.add_column(
        'node_nic_interfaces',
        sa.Column(
            'meta',
            fields.JSON(),
            nullable=False,
            server_default='{}'
        )
    )
    connection = op.get_bind()
    connection.execute(
        sa.sql.text(
            "UPDATE releases SET nic_attributes = :nic_attributes"),
        nic_attributes=jsonutils.dumps(default_release_nic_attributes)
    )

    nodes_query = sa.sql.text(
        "SELECT id, meta,cluster_id FROM nodes"
    )
    interface_query = sa.sql.text(
        "SELECT id, interface_properties, offloading_modes "
        "FROM node_nic_interfaces WHERE node_id = :node_id AND mac = :mac"
    )
    upgrade_interface_query = sa.sql.text(
        "UPDATE node_nic_interfaces "
        "SET attributes = :attributes, meta = :meta "
        "WHERE id = :id"
    )

    for node_id, node_meta, cluster_id in connection.execute(nodes_query):
        node_meta = jsonutils.loads(node_meta)
        for node_interface in node_meta.get("interfaces", []):
            for id, interface_properties, offloading_modes in \
                    connection.execute(interface_query, node_id=node_id,
                                       mac=node_interface['mac']):
                interface_meta = _create_interface_meta(
                    node_interface.get('interface_properties', {}))
                nic_attributes = {}
                if cluster_id:
                    nic_attributes = _create_nic_attributes(
                        jsonutils.loads(interface_properties),
                        jsonutils.loads(offloading_modes)
                    )
                connection.execute(upgrade_interface_query,
                                   attributes=jsonutils.dumps(nic_attributes),
                                   meta=jsonutils.dumps(interface_meta),
                                   id=id)
    # TODO(ekosareva): drop interface_properties column ??


def downgrade_node_nic_attributes():
    # TODO(ekosareva): downgrade nic_attributes['offloading']['modes'] ->
    #                  'offloading_modes' ??
    def _create_interface_properties(meta, nic_attributes):
        sriov = nic_attributes.get('sriov', {})
        interface_properties = {
            'mtu': nic_attributes.get('mtu', {}).get('value', {}).get('value'),
            'disable_offloading': nic_attributes.get('offloading', {}).get(
                'disable', {}).get('value', False),
            'sriov': {
                'enabled': sriov.get('enabled', {}).get('value', False),
                'sriov_numvfs': sriov.get('numvfs', {}).get('value'),
                'physnet': sriov.get('physnet', {}).get('value', 'physnet2'),
            },
            'dpdk': {
                'enabled': nic_attributes.get('dpdk', {}).get(
                    'enabled', {}).get('value', False)
            }
        }
        meta_sriov = meta.get('sriov', {})
        interface_properties['sriov'].update({
            'pci_id': meta_sriov.get('pci_id', ''),
            'available': meta_sriov.get('available', False),
            'sriov_totalvfs': meta_sriov.get('totalvfs', 0),
        })
        interface_properties['dpdk']['available'] = \
            meta.get('dpdk', {}).get('available', False)
        return interface_properties

    interface_query = sa.sql.text(
        "SELECT id, attributes, meta FROM node_nic_interfaces"
    )
    upgrade_interface_query = sa.sql.text(
        "UPDATE node_nic_interfaces "
        "SET interface_properties = :interface_properties WHERE id = :id"
    )
    connection = op.get_bind()
    for id, attributes, meta in connection.execute(interface_query):
        interface_properties = _create_interface_properties(
            jsonutils.loads(meta), jsonutils.loads(attributes))
        connection.execute(
            upgrade_interface_query,
            interface_properties=jsonutils.dumps(interface_properties),
            id=id)

    op.drop_column('node_nic_interfaces', 'meta')
    op.drop_column('node_nic_interfaces', 'attributes')


def downgrade_plugin_with_nics_and_nodes_attributes():
    op.drop_table('node_cluster_plugins')
    op.drop_table('node_bond_interface_cluster_plugins')
    op.drop_table('node_nic_interface_cluster_plugins')
    op.drop_column('node_bond_interfaces', 'attributes')
    op.drop_column('plugins', 'node_attributes_metadata')
    op.drop_column('plugins', 'bond_attributes_metadata')
    op.drop_column('plugins', 'nic_attributes_metadata')


def upgrade_node_deployment_info():
    op.create_table(
        'node_deployment_info',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('node_uid', sa.String(20), nullable=True),
        sa.Column('task_id', sa.Integer(), nullable=False),
        sa.Column('deployment_info', fields.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(
            ['task_id'], ['tasks.id'], ondelete='CASCADE')
    )
    op.create_index('node_deployment_info_task_id_and_node_uid',
                    'node_deployment_info', ['task_id', 'node_uid'])

    connection = op.get_bind()
    select_query = sa.sql.text("""
        SELECT id, deployment_info
        FROM tasks
        WHERE deployment_info IS NOT NULL""")

    insert_query = sa.sql.text("""
        INSERT INTO node_deployment_info
            (task_id, node_uid, deployment_info)
        VALUES
            (:task_id, :node_uid, :deployment_info)""")

    for (task_id, deployment_info_str) in connection.execute(select_query):
        deployment_info = jsonutils.loads(deployment_info_str)
        for node_uid, node_deployment_info in deployment_info.iteritems():
            connection.execute(
                insert_query,
                task_id=task_id,
                node_uid=node_uid,
                deployment_info=jsonutils.dumps(node_deployment_info))

    update_query = sa.sql.text("UPDATE tasks SET deployment_info=NULL")
    connection.execute(update_query)


def downgrade_node_deployment_info():
    op.drop_table('node_deployment_info')


def downgrade_release_required_component_types():
    op.drop_column('releases', 'required_component_types')
