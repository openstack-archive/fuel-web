#!/usr/bin/env python
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

import argparse
import collections
import copy
from itertools import cycle
from netaddr import EUI
from netaddr import IPNetwork
from netaddr import mac_unix
from oslo.serialization import jsonutils
import random
import string
import sys


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

SAMPLE_INTERFACE = {
    'mac': '00:25:90:6a:b1:10',
    'max_speed': 1000,
    'name': 'eth0',               # wlan, p2p1
    'current_speed': 1000,
    'driver': 'igb',              # mlx4_en, eth_ipoib
    'bus_info': '0000:01:00.0',
    'pxe': True
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
        'size': 15518924800
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
    }
]

NODE_SAMPLE = {
    "pk": 1,
    "model": "nailgun.node",
    "fields": {
        "manufacturer": "Supermicro",
        "status": "discover",
        "name": "Supermicro X9DRW",
        "hostname": "node-1",
        "mac": "58:91:cF:2a:c4:1b",
        "ip": "10.20.0.4",
        "online": True,
        "labels": {},
        "pending_addition": False,
        "pending_deletion": False,
        "platform_name": "",
        "os_platform": "ubuntu",
        "progress": 0,

        "timestamp": "",
        "meta": {
            "cpu": {
                "real": 0,
                "total": 0,
                "spec": []
            },
            "interfaces": [],
            "disks": [],
            "system": {
                "product": "X9DRW",
                "family": "To be filled by O.E.M.",
                "fqdn": "srv08-srt.srt.mirantis.net",
                "version": "0123456789",
                "serial": "0123456789",
                "manufacturer": "Supermicro"
            },
            "memory": {
                "slots": 1,
                "total": 137455730688,
                "maximum_capacity": 274894684160,
                "devices": []
            }
        }
    }
}


class FakeNodesGenerator:
    def __init__(self):
        self.net1 = IPNetwork('10.20.0.0/16')
        self.net1_next_ip = cycle(self.net1.iter_hosts()).next
        self.net2 = IPNetwork('172.18.67.0/24')
        self.net2_next_ip = cycle(self.net2.iter_hosts()).next

        self.mcounter = collections.Counter()
        self.mac_counter = 0

    def _get_network_data(self, net_name):
        if net_name == 'net1':
            return self.net1_next_ip(), self.net1.netmask
        if net_name == 'net2':
            return self.net2_next_ip(), self.net2.netmask
        return None, None

    def _generate_mac(self):
        # MAC's starts from FF:FF:FF:FF:FF:FF counting down
        mac = str(EUI(281474976710655 - self.mac_counter, dialect=mac_unix))
        self.mac_counter += 1
        return mac

    def _generate_disks_meta(self, amount):
        disks = []
        for i in range(amount):
            letter = string.ascii_lowercase[i]
            new_disk = copy.deepcopy(random.choice(DISK_SAMPLES))
            new_disk.update({
                'name': 'sd{0}'.format(letter),
                'disk': 'sd{0}'.format(letter)
            })
            disks.append(new_disk)
        return disks

    def _generate_ifaces(self, known_mac, known_ip, known_ip_mask, amount):
        ifaces = []
        driver = random.choice(['igb'] * 9 + ['mlx4_en', 'eth_ipoib', 'e1000'])
        name = random.choice(['eth'] * 8 + ['wlan', 'p2p'])
        add_offloading_modes = random.randint(0, 100) > 80

        for i in range(amount):
            new_iface = copy.deepcopy(SAMPLE_INTERFACE)
            max_speed = random.choice([100, 1000, 56000])
            current_speed_set = [
                random.randint(0, max_speed) for _ in range(3)]
            current_speed_set.append(None)

            new_iface.update({
                'name': '{0}{1}'.format(name, i),
                'mac': self._generate_mac(),
                'driver': driver,
                'bus_info': '0000:0{0}:00.0'.format(i),
                'max_speed': max_speed,
                'current_speed': random.choice(current_speed_set),
                'pxe': random.choice([True, False])
            })
            net = random.choice(['net1', 'net2', None])
            if net:
                ip, netmask = self._get_network_data(net)
                new_iface.update({
                    'ip': ip,
                    'netmask': netmask
                })

            if add_offloading_modes:
                new_iface['offloading_modes'] = \
                    copy.deepcopy(SAMPLE_INTERFACE_OFFLOADING_MODES)

            ifaces.append(new_iface)

        interface_num = random.randint(0, amount - 1)
        ifaces[interface_num]['mac'] = known_mac
        ifaces[interface_num]['ip'] = known_ip
        ifaces[interface_num]['netmask'] = known_ip_mask
        return ifaces

    def generate_fake_nodes(self, total_nodes_count, error_nodes_count,
                            offline_nodes_count):

        total_nodes_range = range(total_nodes_count)
        # Making error and offline random sets non intersecting
        error_nodes_indexes = random.sample(
            total_nodes_range, error_nodes_count)
        offline_nodes_indexes = random.sample(
            set(total_nodes_range) - set(error_nodes_indexes),
            offline_nodes_count
        )

        res = []
        for i in total_nodes_range:
            new_node = copy.deepcopy(NODE_SAMPLE)
            pk = i + 1
            new_node['pk'] = pk

            # update common fields
            kind = random.choice(['real', 'virtual'])
            manufacture = random.choice(MANUFACTURERS[kind])
            self.mcounter[manufacture] += 1
            platform_name = random.choice(['', 'X9SCD', 'N5110', 'X9DRW'])
            mac = self._generate_mac()
            net = random.choice(['net1', 'net2'])
            ip, netmask = self._get_network_data(net)

            node_data = new_node.get('fields')
            node_data.update({
                'manufacturer': manufacture,
                'name': manufacture + ' {0}({1})'.format(
                    platform_name, self.mcounter.get(manufacture)),
                'hostname': 'node-{0}'.format(pk),
                'ip': ip,
                'mac': mac,
                'platform_name': platform_name
            })
            if i in offline_nodes_indexes:
                node_data['online'] = False
            elif i in error_nodes_indexes:
                node_data['status'] = 'error'

            node_meta = node_data.get('meta')
            # update meta system
            node_system_meta = node_meta.get('system')
            node_system_meta.update({
                'manufacturer': manufacture,
                'version': '{0}.{0}'.format(random.randint(0, 10),
                                            random.randint(0, 9)),
                'serial': ''.join(
                    [str(random.randint(0, 9)) for _ in range(10)]),
                'fqdn': '{0}.mirantis.net'.format(node_data['hostname']),
                'product': platform_name,
                'family': 'To be filled by O.E.M.'
            })

            # update meta cpu
            node_cpu_meta = node_meta.get('cpu')
            real_proc = random.choice([0, 1, 2, 4])
            total_proc = real_proc * random.choice([1, 2, 4]) or 1
            proc = random.choice(SAMPLE_CPUS[kind])

            node_cpu_meta.update({
                'real': real_proc,
                'total': total_proc,
                'spec': [copy.deepcopy(proc) for i in range(total_proc)]
            })

            # update meta disks
            disks_count = random.randrange(1, 7)
            node_meta['disks'] = self._generate_disks_meta(disks_count)

            # update meta memory
            node_memory_meta = node_meta.get('memory')
            max_capacity = 1024 ** 3 * random.choice([8, 16, 32, 64])
            total_capacity = 0
            devices = []
            for i in range(random.randint(0, 9)):
                new_memory = copy.deepcopy(
                    random.choice(MEMORY_DEVICE_SAMPLES))
                if (total_capacity + new_memory['size']) > max_capacity:
                    break
                total_capacity += new_memory['size']
                devices.append(new_memory)
            node_memory_meta.update({
                'slots': len(devices),
                'total': total_capacity,
                'maximum_capacity': max_capacity,
                'devices': devices
            })

            # update meta interface
            node_meta['interfaces'] = self._generate_ifaces(
                mac, ip, netmask, random.randrange(1, 7))

            res.append(new_node)
        return res


if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Fake node generator')
    parser.add_argument('-n', '--total-nodes',
                        dest='total_nodes_count',
                        type=int,
                        default=50,
                        nargs='?',
                        help='total amount of nodes to create including '
                             'error and offline nodes [default: %default]')
    parser.add_argument('-e', '--error-nodes',
                        dest='error_nodes_count',
                        type=int,
                        default=4,
                        nargs='?',
                        help='number of nodes to put into error state '
                        '[default: %default]')
    parser.add_argument('-o', '--offline-nodes',
                        dest='offline_nodes_count',
                        type=int,
                        default=3,
                        nargs='?',
                        help='number of offline nodes [default: %default]')

    args = parser.parse_args()

    total_nodes_count = args.total_nodes_count
    error_nodes_count = args.error_nodes_count
    offline_nodes_count = args.offline_nodes_count
    if error_nodes_count + offline_nodes_count > total_nodes_count:
        error_nodes_count = int(0.09 * total_nodes_count)
        offline_nodes_count = int(0.08 * total_nodes_count)

    generator = FakeNodesGenerator()
    res = generator.generate_fake_nodes(total_nodes_count, error_nodes_count,
                                        offline_nodes_count)
    sys.stdout.write(jsonutils.dumps(res, indent=4))
