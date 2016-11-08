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

"""Fuel 9.2

Revision ID: 3763c404ca48
Revises: f2314e5d63c9
Create Date: 2016-10-11 16:33:57.247855

"""

import copy

from alembic import op
from oslo_serialization import jsonutils

import six
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3763c404ca48'
down_revision = 'f2314e5d63c9'


DEFAULT_RELEASE_NIC_ATTRIBUTES = {
    'offloading': {
        'disable': {'type': 'checkbox', 'value': False,
                    'weight': 10, 'label': 'Disable offloading'},
        'modes': {'value': {}, 'type': 'offloading_modes',
                  'description': 'Offloading modes', 'weight': 20,
                  'label': 'Offloading modes'},
        'metadata': {'weight': 10, 'label': 'Offloading'}
    },
    'mtu': {
        'value': {'type': 'number', 'value': None, 'weight': 10,
                  'label': 'MTU'},
        'metadata': {'weight': 20, 'label': 'MTU'}
    },
    'sriov': {
        'numvfs': {'min': 0, 'type': 'number', 'value': None,
                   'weight': 20, 'label': 'Virtual functions'},
        'enabled': {'type': 'checkbox', 'value': False,
                    'weight': 10, 'label': 'SR-IOV enabled'},
        'physnet': {'type': 'text', 'value': '', 'weight': 30,
                    'label': 'Physical network'},
        'metadata': {'weight': 30, 'label': 'SR-IOV'}
    },
    'dpdk': {
        'enabled': {'type': 'checkbox', 'value': False,
                    'weight': 10, 'label': 'DPDK enabled'},
        'metadata': {'weight': 40, 'label': 'DPDK'}
    }
}

DEFAULT_RELEASE_BOND_ATTRIBUTES = {
    'lacp_rate': {
        'value': {'type': 'select', 'weight': 10, 'value': '',
                  'label': 'Lacp rate'},
        'metadata': {'weight': 60, 'label': 'Lacp rate'}
    },
    'xmit_hash_policy': {
        'value': {'type': 'select', 'weight': 10, 'value': '',
                  'label': 'Xmit hash policy'},
        'metadata': {'weight': 70, 'label': 'Xmit hash policy'}
    },
    'offloading': {
        'disable': {'type': 'checkbox', 'weight': 10, 'value': False,
                    'label': 'Disable offloading'},
        'modes': {'weight': 20, 'type': 'offloading_modes',
                  'description': 'Offloading modes', 'value': {},
                  'label': 'Offloading modes'},
        'metadata': {'weight': 20, 'label': 'Offloading'}
    },
    'mtu': {
        'value': {'type': 'number', 'weight': 10, 'value': None,
                  'label': 'MTU'},
        'metadata': {'weight': 30, 'label': 'MTU'}
    },
    'lacp': {
        'value': {'type': 'select', 'weight': 10, 'value': '',
                  'label': 'Lacp'},
        'metadata': {'weight': 50, 'label': 'Lacp'}
    },
    'mode': {
        'value': {'type': 'select', 'weight': 10, 'value': '',
                  'label': 'Mode'},
        'metadata': {'weight': 10, 'label': 'Mode'}
    },
    'type__': {'type': 'hidden', 'value': None},
    'dpdk': {
        'enabled': {'type': 'checkbox', 'weight': 10, 'value': None,
                    'label': 'DPDK enabled'},
        'metadata': {'weight': 40, 'label': 'DPDK'}
    }
}


VCENTER_INSECURE = {
    'name': "vcenter_insecure",
    'type': "checkbox",
    'label': "Bypass vCenter certificate verification"
}

VCENTER_SECURITY_DISABLED = {
    'name': "vcenter_security_disabled",
    'type': "checkbox",
    'label': "Bypass vCenter certificate verification"
}

VCENTER_CA_FILE = {
    'name': "vcenter_ca_file",
    'type': 'file',
    'label': "CA file",
    'description': ('File containing the trusted CA bundle that emitted '
                    'vCenter server certificate. Even if CA bundle is not '
                    'uploaded, certificate verification is turned on.'),
    'restrictions': [{
        'message': ('Bypass vCenter certificate verification should be '
                    'disabled.'),
        'condition': 'current_vcenter:vcenter_security_disabled == true'
    }]
}

CA_FILE = {
    'name': "ca_file",
    'type': 'file',
    'label': "CA file",
    'description': ('File containing the trusted CA bundle that emitted '
                    'vCenter server certificate. Even if CA bundle is not '
                    'uploaded, certificate verification is turned on.'),
    'restrictions': [{
        'message': ('Bypass vCenter certificate verification should be '
                    'disabled.'),
        'condition': 'glance:vcenter_security_disabled == true'
    }]
}


def upgrade():
    upgrade_vmware_attributes_metadata()
    upgrade_release_with_nic_and_bond_attributes()
    upgrade_node_nic_attributes()
    upgrade_node_bond_attributes()
    upgrade_cluster_roles()


def downgrade():
    downgrade_cluster_roles()
    downgrade_node_bond_attributes()
    downgrade_node_nic_attributes()
    downgrade_release_with_nic_and_bond_attributes()
    downgrade_vmware_attributes_metadata()


def update_vmware_attributes_metadata(upgrade):
    connection = op.get_bind()
    select_query = sa.sql.text(
        "SELECT id, vmware_attributes_metadata FROM releases "
        "WHERE vmware_attributes_metadata IS NOT NULL")
    update_query = sa.sql.text(
        "UPDATE releases SET vmware_attributes_metadata = "
        ":vmware_attributes_metadata WHERE id = :id")

    for id, attrs in connection.execute(select_query):
        attrs = jsonutils.loads(attrs)
        editable = attrs.setdefault('editable', {})
        metadata = editable.setdefault('metadata', [])
        value = editable.setdefault('value', {})

        for m in metadata:
            if not isinstance(m, dict):
                continue
            if m.get('name') == 'availability_zones':
                fields = m.setdefault('fields', [])
                names = [f['name'] for f in fields]
                av_z = value.setdefault('availability_zones', {})
                update_availability_zones(fields, av_z, names, upgrade)
            elif m.get('name') == 'glance':
                fields = m.setdefault('fields', [])
                names = [f['name'] for f in fields]
                glance = value.setdefault('glance', {})
                update_glance(fields, glance, names, upgrade)

        connection.execute(
            update_query,
            id=id,
            vmware_attributes_metadata=jsonutils.dumps(attrs))


def update_availability_zones(fields, values, names, upgrade):
    if upgrade:
        if 'vcenter_security_disabled' not in names:
            fields.insert(5, VCENTER_SECURITY_DISABLED)
            for value in values:
                value['vcenter_security_disabled'] = True
        if 'vcenter_insecure' in names:
            fields.remove(VCENTER_INSECURE)
            for value in values:
                del value['vcenter_insecure']
        for field in fields:
            if field['name'] == 'vcenter_ca_file':
                field['restrictions'] = VCENTER_CA_FILE['restrictions']
    else:
        if 'vcenter_insecure' not in names:
            fields.insert(5, VCENTER_INSECURE)
            for value in values:
                value['vcenter_insecure'] = True
        if 'vcenter_security_disabled' in names:
            fields.remove(VCENTER_SECURITY_DISABLED)
            for value in values:
                del value['vcenter_security_disabled']
        for field in fields:
            if field['name'] == 'vcenter_ca_file':
                del field['restrictions']


def update_glance(fields, values, names, upgrade):
    if upgrade:
        if 'vcenter_security_disabled' not in names:
            fields.insert(6, VCENTER_SECURITY_DISABLED)
            values['vcenter_security_disabled'] = True
        if 'vcenter_insecure' in names:
            fields.remove(VCENTER_INSECURE)
            del values['vcenter_insecure']
        for field in fields:
            if field['name'] == 'ca_file':
                field['restrictions'] = CA_FILE['restrictions']
    else:
        if 'vcenter_insecure' not in names:
            fields.insert(6, VCENTER_INSECURE)
            values['vcenter_insecure'] = True
        if 'vcenter_security_disabled' in names:
            fields.remove(VCENTER_SECURITY_DISABLED)
            del values['vcenter_security_disabled']
        for field in fields:
            if field['name'] == 'ca_file':
                del field['restrictions']


def upgrade_vmware_attributes_metadata():
    update_vmware_attributes_metadata(upgrade=True)


def downgrade_vmware_attributes_metadata():
    update_vmware_attributes_metadata(upgrade=False)


def upgrade_release_with_nic_and_bond_attributes():
    connection = op.get_bind()
    connection.execute(
        sa.sql.text(
            "UPDATE releases SET nic_attributes = :nic_attributes, "
            "bond_attributes = :bond_attributes"),
        nic_attributes=jsonutils.dumps(DEFAULT_RELEASE_NIC_ATTRIBUTES),
        bond_attributes=jsonutils.dumps(DEFAULT_RELEASE_BOND_ATTRIBUTES)
    )


def downgrade_release_with_nic_and_bond_attributes():
    connection = op.get_bind()
    connection.execute(
        sa.sql.text(
            "UPDATE releases SET nic_attributes = :nic_attributes, "
            "bond_attributes = :bond_attributes"),
        nic_attributes='{}',
        bond_attributes='{}'
    )


def upgrade_node_nic_attributes():
    def _create_interface_meta(interfaces_data):
        interface_properties = interfaces_data.get('interface_properties', {})
        return {
            'offloading_modes': interfaces_data.get('offloading_modes', []),
            'sriov': {
                'available': interface_properties.get(
                    'sriov', {}).get('available', False),
                'pci_id': interface_properties.get(
                    'sriov', {}).get('pci_id', ''),
                'totalvfs': interface_properties.get(
                    'sriov', {}).get('sriov_totalvfs', 0)
            },
            'dpdk': {
                'available': False
            },
            'pci_id': interface_properties.get('pci_id', ''),
            'numa_node': interface_properties.get('numa_node')
        }

    def _offloading_modes_as_flat_dict(modes):
        result = dict()
        if modes is None:
            return result
        for mode in modes:
            result[mode['name']] = mode['state']
            if mode.get('sub'):
                result.update(_offloading_modes_as_flat_dict(mode['sub']))
        return result

    def _create_nic_attributes(interface_properties, offloading_modes):
        nic_attributes = copy.deepcopy(DEFAULT_RELEASE_NIC_ATTRIBUTES)
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
        offloading_modes = _offloading_modes_as_flat_dict(offloading_modes)
        nic_attributes['offloading']['modes']['value'] = offloading_modes

        return nic_attributes

    nodes_query = sa.sql.text("SELECT id, meta, cluster_id FROM nodes")
    select_interface_query = sa.sql.text("""
        SELECT id, interface_properties, offloading_modes
        FROM node_nic_interfaces
        WHERE node_id = :node_id AND mac = :mac""")
    upgrade_interface_query = sa.sql.text("""
        UPDATE node_nic_interfaces
        SET attributes = :attributes, meta = :meta
        WHERE id = :id""")
    connection = op.get_bind()
    for node_id, node_meta, cluster_id in connection.execute(nodes_query):
        node_meta = jsonutils.loads(node_meta or "{}")
        for node_interface in node_meta.get('interfaces', []):
            for iface_id, interface_properties, offloading_modes in \
                connection.execute(
                    select_interface_query,
                    node_id=node_id,
                    mac=node_interface['mac']):
                interface_meta = _create_interface_meta(node_interface)
                nic_attributes = {}
                if cluster_id:
                    iface_properties = jsonutils.loads(interface_properties)
                    nic_attributes = _create_nic_attributes(
                        iface_properties,
                        jsonutils.loads(offloading_modes)
                    )
                    interface_meta['dpdk']['available'] = \
                        iface_properties.get('dpdk', {}).get(
                            'available', interface_meta['dpdk']['available'])

                connection.execute(
                    upgrade_interface_query,
                    attributes=jsonutils.dumps(nic_attributes),
                    meta=jsonutils.dumps(interface_meta),
                    id=iface_id)
    # TODO(apopovych): uncomment after removing redundant data
    # op.drop_column('node_nic_interfaces', 'offloading_modes')
    # op.drop_column('node_nic_interfaces', 'interface_properties')


def downgrade_node_nic_attributes():
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

    def _create_offloading_modes(meta, nic_attributes):
        def update_modes_with_state(modes, modes_states):
            for mode in modes:
                if modes_states.get(mode['name']):
                    mode['state'] = modes_states[mode['name']]
                if mode.get('sub'):
                    update_modes_with_state(mode['sub'], modes_states)

        offloading_mode_states = nic_attributes.get('offloading', {}).get(
            'modes', {}).get('value', {})
        offloading_modes = copy.deepcopy(meta.get('offloading_modes', []))
        if offloading_mode_states:
            update_modes_with_state(offloading_modes, offloading_mode_states)
        return offloading_modes

    select_interface_query = sa.sql.text(
        "SELECT id, attributes, meta FROM node_nic_interfaces")
    upgrade_interface_query = sa.sql.text("""
        UPDATE node_nic_interfaces
        SET attributes = :attributes, meta = :meta,
            interface_properties = :interface_properties,
            offloading_modes = :offloading_modes
        WHERE id = :id""")
    connection = op.get_bind()
    # TODO(apopovych): uncomment after removing redundant data
    # op.add_column(
    #     'node_nic_interfaces',
    #     sa.Column(
    #         'interface_properties',
    #         fields.JSON(),
    #         nullable=False,
    #         server_default='{}'
    #     )
    # )
    # op.add_column(
    #     'node_nic_interfaces',
    #     sa.Column(
    #         'offloading_modes',
    #         fields.JSON(),
    #         nullable=False,
    #         server_default='[]'
    #     )
    # )

    for iface_id, attributes, meta in connection.execute(
            select_interface_query):
        interface_properties = _create_interface_properties(
            jsonutils.loads(meta), jsonutils.loads(attributes))
        offloading_modes = _create_offloading_modes(
            jsonutils.loads(meta), jsonutils.loads(attributes))

        connection.execute(
            upgrade_interface_query,
            attributes="{}",
            meta="{}",
            interface_properties=jsonutils.dumps(interface_properties),
            offloading_modes=jsonutils.dumps(offloading_modes),
            id=iface_id
        )


def upgrade_node_bond_attributes():
    def _get_offloading_modes(slaves_offloading_modes_values):
        result = {}
        if slaves_offloading_modes_values:
            intersected_modes = six.moves.reduce(
                lambda x, y: x.intersection(y),
                slaves_offloading_modes_values[1:],
                set(slaves_offloading_modes_values[0])
            )
            for slave_offloading_modes in slaves_offloading_modes_values:
                for k in intersected_modes:
                    v = result.get(k, slave_offloading_modes[k])
                    v = (False if False in (v, slave_offloading_modes[k])
                         else v and slave_offloading_modes[k])
                    result[k] = v
        return result

    bond_interface_query = sa.sql.text("""
        SELECT id, mode, bond_properties, interface_properties
        FROM node_bond_interfaces""")
    bond_slaves_offloading_modes_query = sa.sql.text(
        "SELECT attributes FROM node_nic_interfaces "
        "WHERE parent_id = :parent_id")
    upgrade_bond_interface_query = sa.sql.text("""
        UPDATE node_bond_interfaces
        SET attributes = :attributes
        WHERE id = :id""")

    connection = op.get_bind()
    for result in connection.execute(bond_interface_query):
        attributes = copy.deepcopy(DEFAULT_RELEASE_BOND_ATTRIBUTES)
        bond_properties = jsonutils.loads(result['bond_properties'])
        interface_properties = jsonutils.loads(result['interface_properties'])

        attributes['mtu']['value']['value'] = interface_properties.get('mtu')
        attributes['offloading']['disable']['value'] = \
            interface_properties.get('disable_offloading', False)
        attributes['dpdk']['enabled']['value'] = \
            interface_properties.get('dpdk', {}).get('enabled')

        attributes['type__']['value'] = bond_properties.get('type__')
        attributes['mode']['value']['value'] = \
            bond_properties.get('mode') or result['mode'] or ''
        for k in ('lacp_rate', 'xmit_hash_policy', 'lacp'):
            if k in bond_properties:
                attributes[k]['value']['value'] = bond_properties[k]

        slaves_offloading_modes_flat_values = [
            jsonutils.loads(r['attributes']).get('offloading', {}).get(
                'modes', {}).get('value', {})
            for r in connection.execute(bond_slaves_offloading_modes_query,
                                        parent_id=result['id'])
        ]
        attributes['offloading']['modes']['value'] = _get_offloading_modes(
            slaves_offloading_modes_flat_values)

        connection.execute(upgrade_bond_interface_query,
                           attributes=jsonutils.dumps(attributes),
                           id=result['id'])

    # TODO(apopovych): uncomment after removing redundant data
    # op.drop_column('node_bond_interfaces', 'offloading_modes')
    # op.drop_column('node_bond_interfaces', 'interface_properties')
    # op.drop_column('node_bond_interfaces', 'bond_properties')


def downgrade_node_bond_attributes():
    bond_interface_query = sa.sql.text(
        "SELECT id, attributes FROM node_bond_interfaces"
    )
    bond_slaves_offloading_modes_query = sa.sql.text(
        "SELECT meta FROM node_nic_interfaces "
        "WHERE parent_id = :parent_id")
    upgrade_interface_query = sa.sql.text("""
        UPDATE node_bond_interfaces
        SET attributes = :attributes,
            bond_properties = :bond_properties,
            interface_properties = :interface_properties
        WHERE id = :id""")
    # TODO(apopovych): uncomment after removing redundant data
    # op.add_column(
    #     'node_bond_interfaces',
    #     sa.Column(
    #         'bond_properties',
    #         fields.JSON(),
    #         nullable=False,
    #         server_default='{}'
    #     )
    # )
    # op.add_column(
    #     'node_bond_interfaces',
    #     sa.Column(
    #         'interface_properties',
    #         fields.JSON(),
    #         nullable=False,
    #         server_default='{}'
    #     )
    # )
    # op.add_column(
    #     'node_bond_interfaces',
    #     sa.Column(
    #         'offloading_modes',
    #         fields.JSON(),
    #         nullable=False,
    #         server_default='[]'
    #     )
    # )

    connection = op.get_bind()
    for bond_id, attributes in connection.execute(bond_interface_query):
        attributes = jsonutils.loads(attributes)
        dpdk_available = False
        for slave_item in connection.execute(
                bond_slaves_offloading_modes_query, parent_id=bond_id):
            slave_attributes = jsonutils.loads(slave_item['meta'])
            if not slave_attributes.get('dpdk', {}).get('available'):
                break
        else:
            dpdk_available = True

        interface_properties = {
            'mtu': attributes['mtu']['value']['value'],
            'disable_offloading': attributes['offloading']['disable']['value'],
            'dpdk': {
                'available': dpdk_available,
                'enabled': attributes['dpdk']['enabled']['value']
            }
        }

        bond_properties = {
            'type__': attributes['type__']['value'],
            'mode': attributes['mode']['value']['value']
        }
        for k in ('lacp_rate', 'xmit_hash_policy', 'lacp'):
            # TODO(ekosareva): correct way is generate it based on
            #                  release.networks_metadata['bonding'] data
            if attributes[k]['value']['value'] != '':
                bond_properties[k] = attributes[k]['value']['value']

        connection.execute(
            upgrade_interface_query,
            bond_properties=jsonutils.dumps(bond_properties),
            interface_properties=jsonutils.dumps(interface_properties),
            attributes="{}",
            id=bond_id
        )


def upgrade_cluster_roles():
    op.add_column(
        'clusters',
        sa.Column('roles_metadata',
                  fields.JSON(),
                  default={},
                  server_default='{}'),
    )
    op.add_column(
        'clusters',
        sa.Column('volumes_metadata',
                  fields.JSON(),
                  default={},
                  server_default='{}'),
    )


def downgrade_cluster_roles():
    op.drop_column('clusters', 'roles_metadata')
    op.drop_column('clusters', 'volumes_metadata')
