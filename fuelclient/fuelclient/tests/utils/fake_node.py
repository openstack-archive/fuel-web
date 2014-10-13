# -*- coding: utf-8 -*-
#
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

import random

from fuelclient import tests


def get_fake_node(cluster=None, hostname=None, node_id=None, cpu_model=None,
                  roles=None, mac=None, memory_b=None, os_platform=None,
                  status=None, node_name=None, group_id=None):
    """Creates a fake random node

    Returns the serialized and parametrized representation of a dumped Fuel
    environment. Represents the average amount of data.

    """
    host_name = hostname or tests.utils.random_string(15, prefix='fake-node-')

    return {"name": node_name or host_name,
            "error_type": None,
            "cluster": cluster or 1,
            "id": node_id or random.randint(1, 10000),
            "ip": "10.20.0.4",
            "kernel_params": None,
            "group_id": group_id or 1,
            "mac": mac or "d6:11:3f:b0:f1:43",
            "manufacturer": "VirtualBox",
            "online": True,
            "os_platform": os_platform or "centos",
            "pending_addition": False,
            "pending_deletion": False,
            "pending_roles": [],
            "platform_name": None,
            "progress": 100,
            "roles": roles or ["compute"],
            "status": status or "ready",
            "fqdn": "{hostname}.example.com".format(hostname=host_name),

            "meta": {"cpu": {"real": 0,
                             "spec": [{"frequency": 2553,
                                       "model": cpu_model or "Random CPU"}],
                             "total": 1},

                     "disks": [{"disk": "disk/by-path/pci:00:0d.0-scsi-2:0:0",
                                "extra": ["disk/by-id/scsi-SATA_VBOX_aef0bb5c",
                                          "disk/by-id/ata-VBOX_HARDDISK_VB37"],
                                "model": "VBOX HARDDISK",
                                "name": "sdc",
                                "removable": "0",
                                "size": 68718428160},

                               {"disk": "disk/by-path/pci:0:0d.0-scsi-1:0:0:0",
                                "extra": ["disk/by-id/scsi-SATA_VBOX_30fbc3bb",
                                          "disk/by-id/ata-VBOX_HARDD30fbc3bb"],
                                "model": "VBOX HARDDISK",
                                "name": "sdb",
                                "removable": "0",
                                "size": 68718428160},

                               {"disk": "disk/by-path/pci:00:d.0-scsi-0:0:0:0",
                                "extra": ["disk/by-id/scsi-SATA_VBOX-17e33653",
                                          "disk/by-id/ata-VBOX_HARDD17e33653"],
                                "model": "VBOX HARDDISK",
                                "name": "sda",
                                "removable": "0",
                                "size": 68718428160}],

                     "interfaces": [{"name": "eth2",
                                     "current_speed": 100,
                                     "mac": "08:00:27:88:9C:46",
                                     "max_speed": 100,
                                     "state": "unknown"},

                                    {"name": "eth1",
                                     "current_speed": 100,
                                     "mac": "08:00:27:24:BD:6D",
                                     "max_speed": 100,
                                     "state": "unknown"},

                                    {"name": "eth0",
                                     "current_speed": 100,
                                     "mac": "08:00:27:C1:C5:72",
                                     "max_speed": 100,
                                     "state": "unknown"}],
                     "memory": {"total": memory_b or 1968627712},

                     "system": {"family": "Virtual Machine",
                                "fqdn": host_name,
                                "manufacturer": "VirtualBox",
                                "serial": "0",
                                "version": "1.2"}},
            "network_data": [{"brd": "192.168.0.255",
                              "dev": "eth0",
                              "gateway": None,
                              "ip": "192.168.0.2/24",
                              "name": "management",
                              "netmask": "255.255.255.0",
                              "vlan": 101},

                             {"brd": "192.168.1.255",
                              "dev": "eth0",
                              "gateway": None,
                              "ip": "192.168.1.2/24",
                              "name": "storage",
                              "netmask": "255.255.255.0",
                              "vlan": 102},

                             {"brd": "172.16.0.255",
                              "dev": "eth1",
                              "gateway": "172.16.0.1",
                              "ip": "172.16.0.3/24",
                              "name": "public",
                              "netmask": "255.255.255.0",
                              "vlan": None},

                             {"dev": "eth0",
                              "name": "admin"}]}
