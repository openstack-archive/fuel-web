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

from nailgun.db.sqlalchemy.models import fields
from nailgun.utils import dict_update
from nailgun.utils import is_feature_supported
from nailgun.utils import migration


# revision identifiers, used by Alembic.
revision = '3763c404ca48'
down_revision = 'f2314e5d63c9'


def upgrade():
    upgrade_vmware_attributes_metadata()
    upgrade_attributes_metadata()
    upgrade_cluster_roles()
    upgrade_tags_meta()
    upgrade_primary_unit()
    upgrade_release_with_nic_and_bond_attributes()
    upgrade_node_nic_attributes()
    upgrade_node_bond_attributes()
    upgrade_tags_set()
    upgrade_networks_metadata()
    upgrade_transaction_names()


def downgrade():
    downgrade_transaction_names()
    downgrade_networks_metadata()
    downgrade_tags_set()
    downgrade_node_bond_attributes()
    downgrade_node_nic_attributes()
    downgrade_release_with_nic_and_bond_attributes()
    downgrade_primary_unit()
    downgrade_tags_meta()
    downgrade_cluster_roles()
    downgrade_attributes_metadata()
    downgrade_vmware_attributes_metadata()

# version of Fuel when tags was introduced
FUEL_TAGS_SUPPORT = '9.0'

NEW_ROLES_META = {
    'controller': {
        'tags': [
            'controller',
            'rabbitmq',
            'database',
            'keystone',
            'neutron'
        ]
    }
}

OLD_ROLES_META = {
    'controller': {
        'tags': [
            'controller'
        ]
    }
}

NEW_TAGS_META = {
    'rabbitmq': {
        'has_primary': True
    },
    'database': {
        'has_primary': True
    },
    'keystone': {
        'has_primary': True
    },
    'neutron': {
        'has_primary': True
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

SECURITY_GROUPS = {
    'value': 'iptables_hybrid',
    'values': [
        {
            'data': 'openvswitch',
            'label': 'Open vSwitch Firewall Driver',
            'description': 'Choose this driver for OVS based security groups '
                           'implementation. NOTE: Open vSwitch Firewall '
                           'Driver requires kernel version >= 4.3 '
                           'for non-dpdk case.'
        },
        {
            'data': 'iptables_hybrid',
            'label': 'Iptables-based Firewall Driver'
                     ' (No firewall for DPDK case)',
            'description': 'Choose this driver for iptables/linux bridge '
                           'based security groups implementation.'
        }
    ],
    'group': 'security',
    'weight': 20,
    'type': 'radio',
}

DEFAULT_RELEASE_NIC_ATTRIBUTES = {
    'offloading': {
        'disable': {'type': 'checkbox', 'value': False,
                    'weight': 10, 'label': 'Disable Offloading'},
        'modes': {'value': {}, 'type': 'offloading_modes', 'weight': 20,
                  'label': 'Offloading Modes'},
        'metadata': {'weight': 10, 'label': 'Offloading'}
    },
    'mtu': {
        'value': {'type': 'number', 'value': None, 'weight': 10,
                  'label': 'Use Custom MTU', 'nullable': True,
                  'min': 42, 'max': 65536},
        'metadata': {'weight': 20, 'label': 'MTU'}
    }
}

DEFAULT_RELEASE_NIC_NFV_ATTRIBUTES = {
    'sriov': {
        'numvfs': {'min': 1, 'type': 'number', 'value': None, 'nullable': True,
                   'weight': 20, 'label': 'Custom Number of Virtual Functions',
                   'restrictions': ['nic_attributes:sriov.enabled.value == "'
                                    'false"']
                   },
        'enabled': {'type': 'checkbox', 'value': False,
                    'weight': 10, 'label': 'Enable SR-IOV',
                    'description': 'Single-root I/O Virtualization (SR-IOV) '
                                   'is a specification that, when implemented '
                                   'by a physical PCIe device, enables it to '
                                   'appear as multiple separate PCIe devices. '
                                   'This enables multiple virtualized guests '
                                   'to share direct access to the physical '
                                   'device, offering improved performance '
                                   'over an equivalent virtual device.',
                    'restrictions': [{'settings:common.libvirt_type.value != '
                                      '\'kvm\'': '"Only KVM hypervisor works '
                                      'with SR-IOV"'}]},
        'physnet': {'type': 'text', 'value': '', 'weight': 30,
                    'label': 'Physical Network Name',
                    'regex': {
                        'source': '^[A-Za-z0-9 _]*[A-Za-z0-9][A-Za-z0-9 _]*$',
                        'error': 'Invalid physical network name'
                    },
                    'restrictions': [
                        'nic_attributes:sriov.enabled.value == false',
                        {'condition': "nic_attributes:sriov.physnet.value "
                                      "!= 'physnet2'",
                         'message': 'Only "physnet2" will be configured by '
                                    'Fuel in Neutron. Configuration of other '
                                    'physical networks is up to Operator or '
                                    'plugin. Fuel will just configure '
                                    'appropriate pci_passthrough_whitelist '
                                    'option in nova.conf for such interface '
                                    'and physical networks.',
                         'action': 'none'
                         }
                    ]},
        'metadata': {'weight': 30, 'label': 'SR-IOV'}
    },
    'dpdk': {
        'enabled': {'type': 'checkbox', 'value': False,
                    'weight': 10, 'label': 'Enable DPDK',
                    'description': 'The Data Plane Development Kit (DPDK) '
                                   'provides high-performance packet '
                                   'processing libraries and user space '
                                   'drivers.',
                    'restrictions': [
                        {'settings:common.libvirt_type.value != \'kvm\'':
                         'Only KVM hypervisor works with DPDK'}
                    ]},
        'metadata': {
            'weight': 40, 'label': 'DPDK',
            'restrictions': [{
                'condition': "not ('experimental' in version:feature_groups)",
                'action': "hide"
            }]
        }
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
                    'label': 'Disable Offloading'},
        'modes': {'weight': 20, 'type': 'offloading_modes',
                  'value': {}, 'label': 'Offloading Modes'},
        'metadata': {'weight': 20, 'label': 'Offloading'}
    },
    'mtu': {
        'value': {'type': 'number', 'weight': 10, 'value': None,
                  'label': 'Use Custom MTU', 'nullable': True,
                  'min': 42, 'max': 65536},
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
    'type__': {'type': 'hidden', 'value': None}
}

DEFAULT_RELEASE_BOND_NFV_ATTRIBUTES = {
    'dpdk': {
        'enabled': {'type': 'checkbox', 'value': False,
                    'weight': 10, 'label': 'Enable DPDK',
                    'description': 'The Data Plane Development Kit (DPDK) '
                                   'provides high-performance packet '
                                   'processing libraries and user space '
                                   'drivers.',
                    'restrictions': [
                        {'settings:common.libvirt_type.value != \'kvm\'':
                         'Only KVM hypervisor works with DPDK'}
                    ]},
        'metadata': {
            'weight': 40, 'label': 'DPDK',
            'restrictions': [{
                'condition': "not ('experimental' in version:feature_groups)",
                'action': "hide"
            }]
        }
    }
}


NEW_BONDING_AVAILABILITY = [
    {'dpdkovs': "'experimental' in version:feature_groups and "
                "interface:pxe == false and nic_attributes:dpdk.enabled.value "
                "and not nic_attributes:sriov.enabled.value"},
    {'linux': "not nic_attributes:sriov.enabled.value"}
]

OLD_BONDING_AVAILABILITY = [
    {'dpdkovs': "'experimental' in version:feature_groups and interface:pxe =="
                " false and interface:interface_properties.dpdk.enabled "
                "and not interface:interface_properties.sriov.enabled"},
    {'linux': "not interface:interface_properties.sriov.enabled"}
]
# version of Fuel when security group switch was added
FUEL_SECURITY_GROUPS_VERSION = '9.0'

# version of Fuel when DPDK hugepages was introduced
FUEL_DPDK_HUGEPAGES_VERSION = '9.0'

TASK_NAMES_OLD = (
    'super',

    # Cluster changes
    # For deployment supertask, it contains
    # two subtasks deployment and provision
    'deploy',
    'deployment',
    'provision',
    'stop_deployment',
    'reset_environment',
    'update',
    'spawn_vms',

    'node_deletion',
    'cluster_deletion',
    'remove_images',
    'check_before_deployment',

    # network
    'check_networks',
    'verify_networks',
    'check_dhcp',
    'verify_network_connectivity',
    'multicast_verification',
    'check_repo_availability',
    'check_repo_availability_with_setup',
    'dry_run_deployment',

    # dump
    'dump',

    'capacity_log',

    # statistics
    'create_stats_user',
    'remove_stats_user',

    # setup dhcp via dnsmasq for multi-node-groups
    'update_dnsmasq'
)

TASK_NAMES_NEW = TASK_NAMES_OLD + (
    'reset_nodes',
    'remove_keys',
    'remove_ironic_bootstrap',
)


def upgrade_transaction_names():
    migration.upgrade_enum(
        'tasks',
        'name',
        'task_name',
        TASK_NAMES_OLD,
        TASK_NAMES_NEW
    )


def downgrade_transaction_names():
    migration.upgrade_enum(
        'tasks',
        'name',
        'task_name',
        TASK_NAMES_NEW,
        TASK_NAMES_OLD
    )


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


def upgrade_attributes_metadata():
    connection = op.get_bind()
    upgrade_release_attributes_metadata(connection)
    upgrade_cluster_attributes(connection)


def upgrade_release_attributes_metadata(connection):
    select_query = sa.sql.text(
        'SELECT id, attributes_metadata, version FROM releases '
        'WHERE attributes_metadata IS NOT NULL')

    update_query = sa.sql.text(
        'UPDATE releases SET attributes_metadata = :attributes_metadata '
        'WHERE id = :release_id')

    for release_id, attrs, release_version in connection.execute(select_query):
        if not migration.is_security_groups_available(
                release_version, FUEL_SECURITY_GROUPS_VERSION):
            continue
        attrs = jsonutils.loads(attrs)
        common = attrs.setdefault('editable', {}).setdefault('common', {})
        common.setdefault('security_groups', SECURITY_GROUPS)
        connection.execute(
            update_query,
            release_id=release_id,
            attributes_metadata=jsonutils.dumps(attrs))


def upgrade_cluster_attributes(connection):
    select_query = sa.sql.text(
        'SELECT cluster_id, editable, version FROM attributes INNER JOIN '
        'clusters ON clusters.id = attributes.cluster_id INNER JOIN releases '
        'ON releases.id = clusters.release_id WHERE editable IS NOT NULL')

    update_query = sa.sql.text(
        'UPDATE attributes SET editable = :editable WHERE cluster_id = '
        ':cluster_id')

    for cluster_id, editable, release_version in connection.execute(
            select_query
    ):
        if not migration.is_security_groups_available(
                release_version, FUEL_SECURITY_GROUPS_VERSION):
            continue
        editable = jsonutils.loads(editable)
        editable.setdefault('common', {}).setdefault('security_groups',
                                                     SECURITY_GROUPS)
        connection.execute(
            update_query,
            cluster_id=cluster_id,
            editable=jsonutils.dumps(editable))


def downgrade_attributes_metadata():
    connection = op.get_bind()
    downgrade_cluster_attributes(connection)
    downgrade_release_attributes_metadata(connection)


def downgrade_release_attributes_metadata(connection):
    select_query = sa.sql.text(
        'SELECT id, attributes_metadata FROM releases '
        'WHERE attributes_metadata IS NOT NULL')

    update_query = sa.sql.text(
        'UPDATE releases SET attributes_metadata = :attributes_metadata '
        'WHERE id = :release_id')

    for release_id, attrs in connection.execute(select_query):
        attrs = jsonutils.loads(attrs)
        attrs.setdefault('editable', {}).setdefault('common', {}).pop(
            'security_groups', None)
        connection.execute(
            update_query,
            release_id=release_id,
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
        editable.setdefault('common', {}).pop('security_groups', None)
        connection.execute(
            update_query,
            cluster_id=cluster_id,
            editable=jsonutils.dumps(editable))


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
    op.drop_column('clusters', 'volumes_metadata')
    op.drop_column('clusters', 'roles_metadata')


def upgrade_tags_meta():
    connection = op.get_bind()
    op.add_column(
        'releases',
        sa.Column('tags_metadata',
                  fields.JSON(),
                  server_default='{}',
                  nullable=False),
    )
    op.add_column(
        'clusters',
        sa.Column('tags_metadata',
                  fields.JSON(),
                  server_default='{}',
                  nullable=False),
    )
    op.add_column(
        'plugins',
        sa.Column('tags_metadata',
                  fields.JSON(),
                  server_default='{}',
                  nullable=False),
    )

    q_get_role_meta = "SELECT id, roles_metadata FROM {}"
    q_update_role_tags_meta = '''
        UPDATE {}
        SET roles_metadata = :roles_meta, tags_metadata = :tags_meta
        WHERE id = :obj_id
    '''

    for table in ['releases', 'plugins']:
        for obj_id, roles_meta in connection.execute(
                sa.text(q_get_role_meta.format(table))):
            tags_meta = {}
            roles_meta = jsonutils.loads(roles_meta or '{}')
            for role_name, meta in six.iteritems(roles_meta):
                meta['tags'] = [role_name]
                tags_meta[role_name] = {'has_primary': meta.get('has_primary',
                                                                False)}
            connection.execute(sa.text(q_update_role_tags_meta.format(table)),
                               roles_meta=jsonutils.dumps(roles_meta),
                               tags_meta=jsonutils.dumps(tags_meta),
                               obj_id=obj_id)


def downgrade_tags_meta():
    op.drop_column('plugins', 'tags_metadata')
    op.drop_column('clusters', 'tags_metadata')
    op.drop_column('releases', 'tags_metadata')
    downgrade_role_tags()


def upgrade_primary_unit():
    op.alter_column('nodes', 'primary_roles', new_column_name='primary_tags')


def downgrade_primary_unit():
    connection = op.get_bind()
    q_get_roles = sa.text('''
        SELECT id, roles, pending_roles, primary_tags
        FROM nodes
    ''')
    q_update_primary_tags = sa.text('''
        UPDATE nodes
        SET primary_tags = :primary_tags
        WHERE id = :node_id
    ''')
    for node_id, roles, p_roles, pr_tags in connection.execute(q_get_roles):
        primary_tags = list(set(roles + p_roles) & set(pr_tags))
        connection.execute(
            q_update_primary_tags,
            node_id=node_id,
            primary_tags=primary_tags
        )
    op.alter_column('nodes', 'primary_tags', new_column_name='primary_roles')


def upgrade_release_with_nic_and_bond_attributes():
    connection = op.get_bind()
    select_query = sa.sql.text(
        "SELECT id, version FROM releases")
    update_query = sa.sql.text(
        "UPDATE releases SET nic_attributes = :nic_attributes, "
        "bond_attributes = :bond_attributes WHERE id = :id")

    for id, version in connection.execute(select_query):
        new_nic_attrs = copy.deepcopy(DEFAULT_RELEASE_NIC_ATTRIBUTES)
        new_bond_attrs = copy.deepcopy(DEFAULT_RELEASE_BOND_ATTRIBUTES)
        if is_feature_supported(version, FUEL_DPDK_HUGEPAGES_VERSION):
            new_nic_attrs.update(DEFAULT_RELEASE_NIC_NFV_ATTRIBUTES)
            new_bond_attrs.update(DEFAULT_RELEASE_BOND_NFV_ATTRIBUTES)
        connection.execute(
            update_query,
            id=id,
            nic_attributes=jsonutils.dumps(new_nic_attrs),
            bond_attributes=jsonutils.dumps(new_bond_attrs)
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

    def _create_nic_attributes(interface_properties, offloading_modes,
                               support_nfv=False):
        nic_attributes = copy.deepcopy(DEFAULT_RELEASE_NIC_ATTRIBUTES)
        nic_attributes['mtu']['value']['value'] = \
            interface_properties.get('mtu')
        if support_nfv:
            nic_attributes.update(DEFAULT_RELEASE_NIC_NFV_ATTRIBUTES)
            nic_attributes['sriov']['enabled']['value'] = \
                interface_properties.get('sriov', {}).get('enabled', False)
            nic_attributes['sriov']['numvfs']['value'] = \
                interface_properties.get('sriov', {}).get('sriov_numvfs')
            nic_attributes['sriov']['physnet']['value'] = \
                interface_properties.get('sriov', {}).get('physnet',
                                                          'physnet2')
            nic_attributes['dpdk']['enabled']['value'] = \
                interface_properties.get('dpdk', {}).get('enabled', False)
        nic_attributes['offloading']['disable']['value'] = \
            interface_properties.get('disable_offloading', False)
        offloading_modes = _offloading_modes_as_flat_dict(offloading_modes)
        nic_attributes['offloading']['modes']['value'] = offloading_modes

        return nic_attributes

    nodes_query = sa.sql.text("SELECT nodes.id, meta, cluster_id, version "
                              "FROM nodes INNER JOIN clusters "
                              "ON clusters.id = nodes.cluster_id "
                              "INNER JOIN releases "
                              "ON releases.id = clusters.release_id")
    select_interface_query = sa.sql.text("""
        SELECT id, interface_properties, offloading_modes
        FROM node_nic_interfaces
        WHERE node_id = :node_id AND mac = :mac""")
    upgrade_interface_query = sa.sql.text("""
        UPDATE node_nic_interfaces
        SET attributes = :attributes, meta = :meta
        WHERE id = :id""")
    connection = op.get_bind()
    query_result = connection.execute(nodes_query)
    for node_id, node_meta, cluster_id, version in query_result:
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
                        jsonutils.loads(offloading_modes),
                        is_feature_supported(version,
                                             FUEL_DPDK_HUGEPAGES_VERSION)
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
            'pci_id': meta.get('pci_id', ''),
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
        SELECT node_bond_interfaces.id, node_bond_interfaces.mode,
        bond_properties, interface_properties, version
        FROM node_bond_interfaces
        INNER JOIN nodes ON nodes.id = node_bond_interfaces.node_id
        INNER JOIN clusters ON clusters.id = nodes.cluster_id
        INNER JOIN releases ON releases.id = clusters.release_id """)
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
        if is_feature_supported(result['version'],
                                FUEL_DPDK_HUGEPAGES_VERSION):
            attributes.update(DEFAULT_RELEASE_BOND_NFV_ATTRIBUTES)
            attributes['dpdk']['enabled']['value'] = \
                interface_properties.get('dpdk', {}).get('enabled', False)

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


def upgrade_tags_set():
    connection = op.get_bind()
    q_get_role_tags_meta = sa.text(
        "SELECT id, version, roles_metadata, tags_metadata FROM releases")
    q_update_role_tags_meta = sa.text(
        "UPDATE releases "
        "SET roles_metadata = :roles_meta, tags_metadata = :tags_meta "
        "WHERE id = :obj_id")

    for obj_id, version, roles_meta, tags_meta in connection.execute(
            q_get_role_tags_meta):

        if not is_feature_supported(version, FUEL_TAGS_SUPPORT):
            continue

        roles_meta = jsonutils.loads(roles_meta or '{}')
        tags_meta = jsonutils.loads(tags_meta or '{}')
        dict_update(roles_meta, NEW_ROLES_META)
        dict_update(tags_meta, NEW_TAGS_META)
        connection.execute(q_update_role_tags_meta,
                           roles_meta=jsonutils.dumps(roles_meta),
                           tags_meta=jsonutils.dumps(tags_meta),
                           obj_id=obj_id)


def downgrade_tags_set():
    connection = op.get_bind()
    q_get_role_tags_meta = sa.text("SELECT id, roles_metadata, tags_metadata "
                                   "FROM releases")
    q_update_role_tags_meta = sa.text(
        "UPDATE releases "
        "SET roles_metadata = :roles_meta, tags_metadata = :tags_meta "
        "WHERE id = :obj_id")

    for obj_id, roles_meta, tags_meta in connection.execute(
            q_get_role_tags_meta):
        roles_meta = jsonutils.loads(roles_meta or '{}')
        tags_meta = jsonutils.loads(tags_meta or '{}')
        dict_update(roles_meta, OLD_ROLES_META)

        tags_to_remove = set(NEW_TAGS_META) & set(tags_meta)

        for tag_name in tags_to_remove:
            tags_meta.pop(tag_name)

        connection.execute(q_update_role_tags_meta,
                           roles_meta=jsonutils.dumps(roles_meta),
                           tags_meta=jsonutils.dumps(tags_meta),
                           obj_id=obj_id)


def downgrade_role_tags():
    connection = op.get_bind()
    q_get_role_meta = "SELECT id, roles_metadata FROM {}"
    q_update_role_tags_meta = '''
        UPDATE {}
        SET roles_metadata = :roles_meta WHERE id = :obj_id
    '''
    tables = ["releases", "clusters", "plugins"]
    for table in tables:
        for obj_id, roles_meta in connection.execute(
                sa.text(q_get_role_meta.format(table))):
            roles_meta = jsonutils.loads(roles_meta or '{}')
            for role, meta in six.iteritems(roles_meta):
                meta.pop("tags")
            connection.execute(sa.text(q_update_role_tags_meta.format(table)),
                               roles_meta=jsonutils.dumps(roles_meta),
                               obj_id=obj_id)


def upgrade_networks_metadata():
    update_bonding_availability(NEW_BONDING_AVAILABILITY)


def downgrade_networks_metadata():
    update_bonding_availability(OLD_BONDING_AVAILABILITY)


def update_bonding_availability(bonding_availability):
    connection = op.get_bind()
    select_query = sa.sql.text(
        "SELECT id, version, networks_metadata FROM releases "
        "WHERE networks_metadata IS NOT NULL")
    update_query = sa.sql.text(
        "UPDATE releases SET networks_metadata = :networks_metadata "
        "WHERE id = :id")
    for id, version, nets in connection.execute(select_query):
        if not is_feature_supported(version, FUEL_DPDK_HUGEPAGES_VERSION):
            continue
        nets = jsonutils.loads(nets)
        if 'bonding' in nets and 'availability' in nets['bonding']:
            nets['bonding']['availability'] = bonding_availability

        connection.execute(
            update_query,
            id=id,
            networks_metadata=jsonutils.dumps(nets))
