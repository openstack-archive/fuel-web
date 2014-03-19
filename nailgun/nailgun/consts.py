# -*- coding: utf-8 -*-

#    Copyright 2013 Mirantis, Inc.
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

from collections import namedtuple


def Enum(*values, **kwargs):
    names = kwargs.get('names')
    if names:
        return namedtuple('Enum', names)(*values)
    return namedtuple('Enum', values)(*values)

RELEASE_STATES = Enum(
    'not_available',
    'downloading',
    'error',
    'available'
)

CLUSTER_MODES = Enum(
    'multinode',
    'ha_full',
    'ha_compact'
)

CLUSTER_STATUSES = Enum(
    'new',
    'deployment',
    'stopped',
    'operational',
    'error',
    'remove'
)

CLUSTER_NET_MANAGERS = Enum(
    'FlatDHCPManager',
    'VlanManager'
)

CLUSTER_GROUPING = Enum(
    'roles',
    'hardware',
    'both'
)

CLUSTER_NET_PROVIDERS = Enum(
    'nova_network',
    'neutron'
)

CLUSTER_NET_L23_PROVIDERS = Enum(
    'ovs'
)

CLUSTER_NET_SEGMENT_TYPES = Enum(
    'none',
    'vlan',
    'gre'
)

NETWORK_INTERFACE_TYPES = Enum(
    'ether',
    'bond'
)

OVS_BOND_MODES = Enum(
    'active-backup',
    'balance-slb',
    'lacp-balance-tcp',
    names=(
        'active_backup',
        'balance_slb',
        'lacp_balance_tcp',
    )
)

TASK_STATUSES = Enum(
    'ready',
    'running',
    'error'
)


TASK_NAMES = Enum(
    'super',

    # Cluster changes
    # For deployment supertask, it contains
    # two subtasks deployment and provision
    'deploy',
    'deployment',
    'provision',
    'stop_deployment',
    'reset_environment',

    'node_deletion',
    'cluster_deletion',
    'check_before_deployment',

    # network
    'check_networks',
    'verify_networks',
    'check_dhcp',
    'verify_network_connectivity',

    # red hat
    'redhat_setup',
    'redhat_check_credentials',
    'redhat_check_licenses',
    'redhat_download_release',
    'redhat_update_cobbler_profile',

    # dump
    'dump',

    'capacity_log'
)
