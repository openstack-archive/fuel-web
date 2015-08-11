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
    'available',
    'unavailable',
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
    'gre',
    'tun'
)

NODE_STATUSES = Enum(
    'ready',
    'discover',
    'provisioning',
    'provisioned',
    'deploying',
    'error',
    'removing',
)

NODE_ERRORS = Enum(
    'deploy',
    'provision',
    'deletion'
)

NODE_GROUPS = Enum(
    'default'
)

NODE_VIEW_MODES = Enum(
    'standard',
    'compact'
)

NETWORK_INTERFACE_TYPES = Enum(
    'ether',
    'bond'
)

NETWORK_VIP_TYPES = Enum(
    'haproxy',
    'vrouter',
)

BOND_MODES = Enum(
    # same for both OVS and linux
    'active-backup',
    # OVS modes
    'balance-slb',
    'lacp-balance-tcp',
    # linux modes
    'balance-rr',
    'balance-xor',
    'broadcast',
    '802.3ad',
    'balance-tlb',
    'balance-alb',
    names=(
        'active_backup',

        'balance_slb',
        'lacp_balance_tcp',

        'balance_rr',
        'balance_xor',
        'broadcast',
        'l_802_3ad',
        'balance_tlb',
        'balance_alb',
    )
)

BOND_PROPERTIES = Enum(
    'mode',
    'xmit_hash_policy',
    'lacp_rate',
    # not for orchestrator input
    'type__'
)

BOND_XMIT_HASH_POLICY = Enum(
    'layer2',
    'layer2+3',
    'layer3+4',
    'encap2+3',
    'encap3+4',
    names=(
        'layer2',
        'layer2_3',
        'layer3_4',
        'encap2_3',
        'encap3_4',
    )
)

BOND_LACP_RATES = Enum(
    'slow',
    'fast'
)

BOND_TYPES = Enum(
    'ovs',
    'linux'
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
    'spawn_vms',

    'node_deletion',
    'cluster_deletion',
    'check_before_deployment',

    # network
    'check_networks',
    'verify_networks',
    'check_dhcp',
    'verify_network_connectivity',
    'multicast_verification',
    'check_repo_availability',
    'check_repo_availability_with_setup',

    # dump
    'dump',

    'capacity_log',

    # statistics
    'create_stats_user',
    'remove_stats_user'
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
    'interfaces',
    'vmware_attributes'
)

PROVISION_METHODS = Enum(
    'cobbler',
    'image'
)

STAGES = Enum(
    'pre_deployment',
    'deploy',
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
    'failed',
    'updated',
    'skipped'
)

NOVA_SERVICE_TYPE = Enum(
    'compute',
)

VIRTUAL_NODE_TYPES = Enum(
    "virt",
)

OPENSTACK_IMAGES_SETTINGS = Enum(
    "OS-EXT-IMG-SIZE:size",
    "byte",
    names=(
        "size_attr_name",
        "size_unit"
    )
)

DEPLOY_STRATEGY = Enum(
    'parallel',
    'one_by_one'
)

ORCHESTRATOR_TASK_TYPES = Enum(
    'puppet',
    'shell',
    'sync',
    'upload_file',
    'group',
    'stage',
    'skipped',
    'reboot',
    'copy_files',
)

INTERNAL_TASKS = (ORCHESTRATOR_TASK_TYPES.group,
                  ORCHESTRATOR_TASK_TYPES.stage,
                  ORCHESTRATOR_TASK_TYPES.skipped)

ROLE_NAME_MAX_SIZE = 64
EXTENSION_NAME_MAX_SIZE = 64

ALL_ROLES = '*'
MASTER_ROLE = 'master'

# version of Fuel when we added granular deploy support
FUEL_GRANULAR_DEPLOY = '6.1'
# version of Fuel when we added remote repos
FUEL_REMOTE_REPOS = '6.1'
# version of Fuel when external mongo was added
FUEL_EXTERNAL_MONGO = '6.1'

# version of Fuel when classic provisioning is not available anymore.
FUEL_IMAGE_BASED_ONLY = '7.0'

OSWL_RESOURCE_TYPES = Enum(
    'vm',
    'tenant',
    'volume',
    'security_group',
    'keystone_user',
    'flavor',
    'cluster_stats',
    'image',
)

PROTOCOL = Enum(
    'http',
    'https',
)

NETWORK_NOTATION = Enum(
    "ip_ranges",
    "cidr",
)

# Minimal quantity of IPs to be fetched and checked within one request to DB.
MIN_IPS_PER_REQUEST = 5
