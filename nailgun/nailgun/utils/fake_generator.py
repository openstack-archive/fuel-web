# -*- coding: utf-8 -*-

#    Copyright 2015 Mirantis, Inc.
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

import copy
from itertools import cycle
from itertools import product
from netaddr import EUI
from netaddr import IPNetwork
from netaddr import mac_unix_expanded
import random
import six
import string


MANUFACTURERS = {
    'real': (
        'Supermicro',
        '80AD',
        'Dell',
        'Samsung',
    ),
    'virtual': (
        'VirtualBox',
    )
}

SAMPLE_CPUS = {
    'real': (
        {
            'model': 'Intel(R) Xeon(R) CPU E5-2620 0 @ 2.00GHz',
            'frequency': 2001
        },
        {
            'model': 'Intel(R) Xeon(R) CPU E31230 @ 3.20GHz',
            'frequency': 3201
        },
        {
            'model': 'Intel(R) Core(TM) i7-2670QM CPU @ 2.20GHz',
            'frequency': 2185
        }
    ),
    'virtual': (
        {
            'model': 'QEMU Virtual CPU version 1.0',
            'frequency': 1999
        },
    )
}

SAMPLE_INTERFACE_OFFLOADING_MODES = [
    {
        'name': 'tx-checksumming',
        'state': True,            # True, false, null
        'sub': [
            {
                'name': 'tx-checksum-sctp',
                'state': False,   # True, false, null
                'sub': []
            },
            {
                'name': 'tx-checksum-ipv6',
                'state': True,    # True, false, null
                'sub': []
            },
            {
                'name': 'tx-checksum-ipv4',
                'state': None,    # True, false, null
                'sub': []
            }
        ]
    },
    {
        'name': 'rx-checksumming',
        'state': None,
        'sub': []
    }
]

DISK_SAMPLES = [
    {
        'model': 'TOSHIBA MK1002TS',
        'name': 'sda',
        'disk': 'sda',
        'size': 1000204886016
    },
    {
        'model': 'Virtual Floppy0',
        'name': 'sde',
        'disk': 'sde',
        'size': 0
    },
    {
        'model': 'Virtual HDisk0',
        'name': 'sdf',
        'disk': 'sdf',
        'size': 0
    },
    {
        'model': 'Silicon-Power16G',
        'name': 'sdb',
        'disk': 'sdb',
        'size': 155692564480
    },
    {
        'model': 'WDC WD3200BPVT-7',
        'name': 'sda',
        'disk': 'sda',
        'size': 320072933376
    },
    {
        'model': 'QEMU HARDDISK',
        'name': 'sda',
        'disk': 'sda',
        'size': 68719476736
    }
]

MEMORY_DEVICE_SAMPLES = [
    {
        'frequency': 1333,
        'type': 'DDR3',
        'size': 8589934592
    },
    {
        'frequency': 1333,
        'type': 'DDR3',
        'size': 4294967296
    },
    {
        'type': 'RAM',
        'size': 10737418240
    },
    {
        'type': 'Flash',
        'size': 16777216
    }
]

NETWORK_1 = '10.20.0.0/16'
NETWORK_2 = '172.18.67.0/24'


class FakeNodesGenerator(object):
    """This class uses to generate fake nodes"""

    def __init__(self):
        self.net1 = IPNetwork(NETWORK_1)
        self.net1_ip_pool = cycle(self.net1.iter_hosts())
        self.net2 = IPNetwork(NETWORK_2)
        self.net2_ip_pool = cycle(self.net2.iter_hosts())

        self.mcounter = dict()
        self.mac_counter = 0

    def _get_network_data(self, net_name):
        if net_name == 'net1':
            return str(next(self.net1_ip_pool)), str(self.net1.netmask)
        if net_name == 'net2':
            return str(next(self.net2_ip_pool)), str(self.net2.netmask)
        return None, None

    def _generate_mac(self):
        # MAC's starts from FF:FF:FF:FF:FF:FE counting down
        mac = str(EUI(281474976710654 - self.mac_counter,
                      dialect=mac_unix_expanded))
        self.mac_counter += 1
        return mac

    @staticmethod
    def _get_disk_suffixes(amount):
        length = 1
        counter = 0
        while counter < amount:
            for item in product(string.ascii_lowercase, repeat=length):
                if counter == amount:
                    break
                counter += 1
                yield ''.join(item)
            length += 1

    def _generate_disks_meta(self, amount):
        disks = []
        total_size = 0
        for i, disk_suffix in enumerate(self._get_disk_suffixes(amount)):
            new_disk = copy.deepcopy(random.choice(DISK_SAMPLES))
            # disks total size shouldn't be 0
            if i == amount - 1 and total_size == 0:
                while new_disk['size'] == 0:
                    new_disk = copy.deepcopy(random.choice(DISK_SAMPLES))
            new_disk.update({
                'name': 'sd{0}'.format(disk_suffix),
                'disk': 'sd{0}'.format(disk_suffix)
            })
            total_size += new_disk['size']
            disks.append(new_disk)
        return disks

    @staticmethod
    def _get_random_iface_offloading_modes():
        offloading_modes = copy.deepcopy(SAMPLE_INTERFACE_OFFLOADING_MODES)
        for mode in offloading_modes:
            mode['state'] = random.choice([True, False, None])
            for sub in mode.get('sub', []):
                sub['state'] = random.choice([True, False, None])
        return offloading_modes

    def _generate_interfaces_meta(self, known_mac, known_ip, known_ip_mask,
                                  use_offload_iface, amount):
        ifaces = []
        driver = random.choice(['igb'] * 9 + ['mlx4_en', 'eth_ipoib', 'e1000'])
        name = random.choice(['eth'] * 8 + ['wlan', 'p2p'])
        know_interface_num = random.randint(0, amount - 1)

        for i in six.moves.range(amount):
            max_speed = random.choice([100, 1000, 56000])
            current_speed_set = [
                random.randint(max_speed * 0.5, max_speed) for _ in range(3)]
            current_speed_set.append(None)

            new_iface = {
                'name': '{0}{1}'.format(name, i),
                'driver': driver,
                'bus_info': '0000:0{0}:00.0'.format(i),
                'max_speed': max_speed,
                'current_speed': random.choice(current_speed_set),
                'pxe': random.choice([True, False])
            }
            if i == know_interface_num:
                new_iface.update({
                    'mac': known_mac,
                    'ip': known_ip,
                    'netmask': known_ip_mask
                })
            else:
                new_iface['mac'] = self._generate_mac()
                net = random.choice(['net1', 'net2', None])
                if net:
                    ip, netmask = self._get_network_data(net)
                    new_iface.update({
                        'ip': ip,
                        'netmask': netmask
                    })

            if use_offload_iface:
                new_iface['offloading_modes'] = \
                    self._get_random_iface_offloading_modes()

            ifaces.append(new_iface)
        return ifaces

    @staticmethod
    def _generate_systems_meta(hostname, manufacture, platform_name):
        return {
            'manufacturer': manufacture,
            'version': '{0}.{0}'.format(random.randint(0, 10),
                                        random.randint(0, 9)),
            'serial': ''.join(
                [str(random.randint(0, 9)) for _ in six.moves.range(10)]),
            'fqdn': '{0}.mirantis.net'.format(hostname),
            'product': platform_name,
            'family': 'To be filled by O.E.M.'
        }

    @staticmethod
    def _generate_cpu_meta(kind):
        real_proc = random.choice([0, 1, 2, 4])
        total_proc = real_proc * random.choice([1, 2, 4]) or 1
        proc = random.choice(SAMPLE_CPUS[kind])
        return {
            'real': real_proc,
            'total': total_proc,
            'spec': [copy.deepcopy(proc) for _ in six.moves.range(total_proc)]
        }

    @staticmethod
    def _generate_memory_meta(amount):
        max_capacity = 1024 ** 3 * random.choice([8, 16, 32, 64])
        total_capacity = 0
        devices = []
        for _ in six.moves.range(amount):
            new_memory = copy.deepcopy(
                random.choice(MEMORY_DEVICE_SAMPLES))
            if (total_capacity + new_memory['size']) > max_capacity:
                if total_capacity == 0:
                    new_memory['size'] = max_capacity
                else:
                    break
            total_capacity += new_memory['size']
            devices.append(new_memory)
        return {
            'slots': len(devices),
            'total': total_capacity,
            'maximum_capacity': max_capacity,
            'devices': devices
        }

    def generate_fake_node(self, hostname_postfix, is_online=True,
                           is_error=False, use_offload_iface=False,
                           min_ifaces_num=1):
        """Generate one fake node

        :param int hostname_postfix: node's name postfix
        :param bool is_online: node's online status
        :param bool is_error: node's error status
        :param bool use_offload_iface: use offloading_modes data for
                                       node's interfaces or not
        :param min_ifaces_num: minimal ifaces num for the node
        :returns: kwargs dict that represents fake node
        """

        kind = random.choice(['real', 'virtual'])
        manufacture = random.choice(MANUFACTURERS[kind])
        self.mcounter[manufacture] = self.mcounter.get(manufacture, 0) + 1
        hostname = 'node-{0}'.format(hostname_postfix)
        platform_name = random.choice(['', 'X9SCD', 'N5110', 'X9DRW'])
        mac = self._generate_mac()
        net = random.choice(['net1', 'net2'])
        ip, netmask = self._get_network_data(net)

        return {
            'model': 'nailgun.Node',
            'identity_fields': ['name', 'hostname'],
            'fields': {
                'status': 'error' if is_error else 'discover',
                'manufacturer': manufacture,
                'name': manufacture + ' {0}({1})'.format(
                    platform_name, self.mcounter.get(manufacture)),
                'hostname': hostname,
                'ip': ip,
                'mac': mac,
                'online': is_online,
                'labels': {},
                'pending_addition': False,
                'pending_deletion': False,
                'platform_name': platform_name,
                'os_platform': 'ubuntu',
                'progress': 0,
                'timestamp': '',
                'meta': {
                    'cpu': self._generate_cpu_meta(kind),
                    'interfaces': self._generate_interfaces_meta(
                        mac, ip, netmask, use_offload_iface,
                        random.randrange(min_ifaces_num, 7)),
                    'disks': self._generate_disks_meta(random.randint(1, 7)),
                    'system': self._generate_systems_meta(
                        hostname, manufacture, platform_name),
                    'memory': self._generate_memory_meta(random.randint(1, 8))
                }
            }
        }

    def generate_fake_nodes(self, total_nodes_count, error_nodes_count=None,
                            offline_nodes_count=None,
                            offloading_ifaces_nodes_count=None,
                            min_ifaces_num=1):
        """Generate list of fake nodes

        :param int total_nodes_count: total count of nodes to generate
        :param int error_nodes_count: count of error nodes (optional)
        :param int offline_nodes_count: count of offline nodes (optional)
        :param int offloading_ifaces_nodes_count: count of nodes with interface
                                                  using offloading (optional)
        :returns: list of dicts, each of which represents node
        """
        if error_nodes_count is None:
            error_nodes_count = int(0.09 * total_nodes_count)
        if offline_nodes_count is None:
            offline_nodes_count = int(0.08 * total_nodes_count)
        if error_nodes_count + offline_nodes_count > total_nodes_count:
            error_nodes_count = int(0.09 * total_nodes_count)
            offline_nodes_count = int(0.08 * total_nodes_count)
        if offloading_ifaces_nodes_count is None:
            offloading_ifaces_nodes_count = int(0.2 * total_nodes_count)

        total_nodes_range = six.moves.range(total_nodes_count)
        # Making error and offline random sets non intersecting
        error_nodes_indexes = set(random.sample(
            total_nodes_range, error_nodes_count))
        offline_nodes_indexes = set(random.sample(
            set(total_nodes_range) - error_nodes_indexes,
            offline_nodes_count
        ))
        offloading_ifaces_nodes_indexes = set(random.sample(
            total_nodes_range, offloading_ifaces_nodes_count))

        res = []
        for i in total_nodes_range:
            node = self.generate_fake_node(
                i + 1,
                is_online=i not in offline_nodes_indexes,
                is_error=i in error_nodes_indexes,
                use_offload_iface=i in offloading_ifaces_nodes_indexes,
                min_ifaces_num=min_ifaces_num
            )
            res.append(node)
        return res
