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

RELEASE_OS = Enum(
    'Ubuntu',
    'CentOS',
    names=(
        'ubuntu',
        'centos'
    )
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
    'remove',
    'update',
    'update_error'
)

NETWORKS = Enum(
    # Node networks
    'fuelweb_admin',
    'storage',
    # internal in terms of fuel
    'management',
    'public',

    # private in terms of fuel
    'fixed',
    'private'
)

NOVA_NET_MANAGERS = Enum(
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

NEUTRON_L23_PROVIDERS = Enum(
    'ovs',
    'nsx'
)

NEUTRON_SEGMENT_TYPES = Enum(
    'vlan',
    'gre'
)

NODE_STATUSES = Enum(
    'ready',
    'discover',
    'provisioning',
    'provisioned',
    'deploying',
    'error'
)

NODE_ERRORS = Enum(
    'deploy',
    'provision',
    'deletion'
)

NODE_GROUPS = Enum(
    'default'
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
    'update',

    'node_deletion',
    'cluster_deletion',
    'check_before_deployment',

    # network
    'check_networks',
    'verify_networks',
    'check_dhcp',
    'verify_network_connectivity',
    'multicast_verification',

    # dump
    'dump',

    'capacity_log'
)

NOTIFICATION_STATUSES = Enum(
    'read',
    'unread'
)

NOTIFICATION_TOPICS = Enum(
    'discover',
    'done',
    'error',
    'warning',
    'release',
)

CLUSTER_CHANGES = Enum(
    'networks',
    'attributes',
    'disks',
    'interfaces'
)

PROVISION_METHODS = Enum(
    'cobbler',
    'image'
)

STAGES = Enum(
    'pre_deployment',
    'post_deployment'
)

ACTION_TYPES = Enum(
    'http_request',
    'nailgun_task'
)

LOG_CHUNK_SEND_STATUS = Enum(
    'ok',
    'error'
)

LOG_RECORD_SEND_STATUS = Enum(
    'added',
    'existed',
    'failed'
)

NOVA_SERVICE_TYPE = Enum(
    'compute',
)

OPENSTACK_IMAGES_SETTINGS = Enum(
    "OS-EXT-IMG-SIZE:size",
    "byte",
    names=(
        "size_attr_name",
        "size_unit"
    )
)
