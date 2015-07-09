# Copyright 2014 Mirantis, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import copy
import mock
from oslotest import base as test_base

import yaml

from fuel_agent.drivers import nailgun
from fuel_agent import errors
from fuel_agent.objects import image
from fuel_agent.utils import hardware as hu
from fuel_agent.utils import utils


CEPH_JOURNAL = {
    "partition_guid": "45b0969e-9b03-4f30-b4c6-b4b80ceff106",
    "name": "cephjournal",
    "mount": "none",
    "disk_label": "",
    "type": "partition",
    "file_system": "none",
    "size": 0
}
CEPH_DATA = {
    "partition_guid": "4fbd7e29-9d25-41b8-afd0-062c0ceff05d",
    "name": "ceph",
    "mount": "none",
    "disk_label": "",
    "type": "partition",
    "file_system": "none",
    "size": 3333
}
PROVISION_SAMPLE_DATA = {
    "profile": "pro_fi-le",
    "name_servers_search": "\"domain.tld\"",
    "uid": "1",
    "interfaces": {
        "eth2": {
            "static": "0",
            "mac_address": "08:00:27:b1:d7:15"
        },
        "eth1": {
            "static": "0",
            "mac_address": "08:00:27:46:43:60"
        },
        "eth0": {
            "ip_address": "10.20.0.3",
            "dns_name": "node-1.domain.tld",
            "netmask": "255.255.255.0",
            "static": "0",
            "mac_address": "08:00:27:79:da:80"
        }
    },
    "interfaces_extra": {
        "eth2": {
            "onboot": "no",
            "peerdns": "no"
        },
        "eth1": {
            "onboot": "no",
            "peerdns": "no"
        },
        "eth0": {
            "onboot": "yes",
            "peerdns": "no"
        }
    },
    "power_type": "ssh",
    "power_user": "root",
    "kernel_options": {
        "udevrules": "08:00:27:79:da:80_eth0,08:00:27:46:43:60_eth1,"
                     "08:00:27:b1:d7:15_eth2",
        "netcfg/choose_interface": "08:00:27:79:da:80"
    },
    "power_address": "10.20.0.253",
    "name_servers": "\"10.20.0.2\"",
    "ks_meta": {
        "gw": "10.20.0.1",
        "image_data": {
            "/": {
                "uri": "http://fake.host.org:123/imgs/fake_image.img.gz",
                "format": "ext4",
                "container": "gzip"
            }
        },
        "timezone": "America/Los_Angeles",
        "master_ip": "10.20.0.2",
        "mco_enable": 1,
        "mco_vhost": "mcollective",
        "mco_pskey": "unset",
        "mco_user": "mcollective",
        "puppet_enable": 0,
        "fuel_version": "5.0.1",
        "install_log_2_syslog": 1,
        "mco_password": "marionette",
        "puppet_auto_setup": 1,
        "puppet_master": "fuel.domain.tld",
        "mco_auto_setup": 1,
        "auth_key": "fake_auth_key",
        "authorized_keys": ["fake_authorized_key1", "fake_authorized_key2"],
        "repo_setup": {
            "repos": [
                {
                    "name": "repo1",
                    "type": "deb",
                    "uri": "uri1",
                    "suite": "suite",
                    "section": "section",
                    "priority": 1001
                },
                {
                    "name": "repo2",
                    "type": "deb",
                    "uri": "uri2",
                    "suite": "suite",
                    "section": "section",
                    "priority": 1001
                }
            ]
        },
        "pm_data": {
            "kernel_params": "console=ttyS0,9600 console=tty0 rootdelay=90 "
                             "nomodeset",
            "ks_spaces": [
                {
                    "name": "sda",
                    "extra": [
                        "disk/by-id/scsi-SATA_VBOX_HARDDISK_VB69050467-"
                        "b385c7cd",
                        "disk/by-id/ata-VBOX_HARDDISK_VB69050467-b385c7cd"
                    ],
                    "free_space": 64907,
                    "volumes": [
                        {
                            "type": "boot",
                            "size": 300
                        },
                        {
                            "mount": "/boot",
                            "size": 200,
                            "type": "raid",
                            "file_system": "ext2",
                            "name": "Boot"
                        },
                        {
                            "mount": "/tmp",
                            "size": 200,
                            "type": "partition",
                            "file_system": "ext2",
                            "partition_guid": "fake_guid",
                            "name": "TMP"
                        },
                        {
                            "type": "lvm_meta_pool",
                            "size": 0
                        },
                        {
                            "size": 19438,
                            "type": "pv",
                            "lvm_meta_size": 64,
                            "vg": "os"
                        },
                        {
                            "size": 45597,
                            "type": "pv",
                            "lvm_meta_size": 64,
                            "vg": "image"
                        }
                    ],
                    "type": "disk",
                    "id": "sda",
                    "size": 65535
                },
                {
                    "name": "sdb",
                    "extra": [
                        "disk/by-id/scsi-SATA_VBOX_HARDDISK_VBf2923215-"
                            "708af674",
                        "disk/by-id/ata-VBOX_HARDDISK_VBf2923215-708af674"
                    ],
                    "free_space": 64907,
                    "volumes": [
                        {
                            "type": "boot",
                            "size": 300
                        },
                        {
                            "mount": "/boot",
                            "size": 200,
                            "type": "raid",
                            "file_system": "ext2",
                            "name": "Boot"
                        },
                        {
                            "type": "lvm_meta_pool",
                            "size": 64
                        },
                        {
                            "size": 0,
                            "type": "pv",
                            "lvm_meta_size": 0,
                            "vg": "os"
                        },
                        {
                            "size": 64971,
                            "type": "pv",
                            "lvm_meta_size": 64,
                            "vg": "image"
                        }
                    ],
                    "type": "disk",
                    "id": "sdb",
                    "size": 65535
                },
                {
                    "name": "sdc",
                    "extra": [
                        "disk/by-id/scsi-SATA_VBOX_HARDDISK_VB50ee61eb-"
                            "84e74fdf",
                        "disk/by-id/ata-VBOX_HARDDISK_VB50ee61eb-84e74fdf"
                    ],
                    "free_space": 64907,
                    "volumes": [
                        {
                            "type": "boot",
                            "size": 300
                        },
                        {
                            "mount": "/boot",
                            "size": 200,
                            "type": "raid",
                            "file_system": "ext2",
                            "name": "Boot"
                        },
                        {
                            "type": "lvm_meta_pool",
                            "size": 64
                        },
                        {
                            "size": 0,
                            "type": "pv",
                            "lvm_meta_size": 0,
                            "vg": "os"
                        },
                        {
                            "size": 64971,
                            "type": "pv",
                            "lvm_meta_size": 64,
                            "vg": "image"
                        }
                    ],
                    "type": "disk",
                    "id": "disk/by-path/pci-0000:00:0d.0-scsi-0:0:0:0",
                    "size": 65535
                },
                {
                    "_allocate_size": "min",
                    "label": "Base System",
                    "min_size": 19374,
                    "volumes": [
                        {
                            "mount": "/",
                            "size": 15360,
                            "type": "lv",
                            "name": "root",
                            "file_system": "ext4"
                        },
                        {
                            "mount": "swap",
                            "size": 4014,
                            "type": "lv",
                            "name": "swap",
                            "file_system": "swap"
                        }
                    ],
                    "type": "vg",
                    "id": "os"
                },
                {
                    "_allocate_size": "min",
                    "label": "Zero size volume",
                    "min_size": 0,
                    "volumes": [
                        {
                            "mount": "none",
                            "size": 0,
                            "type": "lv",
                            "name": "zero_size",
                            "file_system": "xfs"
                        }
                    ],
                    "type": "vg",
                    "id": "zero_size"
                },
                {
                    "_allocate_size": "all",
                    "label": "Image Storage",
                    "min_size": 5120,
                    "volumes": [
                        {
                            "mount": "/var/lib/glance",
                            "size": 175347,
                            "type": "lv",
                            "name": "glance",
                            "file_system": "xfs"
                        }
                    ],
                    "type": "vg",
                    "id": "image"
                }
            ]
        },
        "mco_connector": "rabbitmq",
        "mco_host": "10.20.0.2"
    },
    "name": "node-1",
    "hostname": "node-1.domain.tld",
    "slave_name": "node-1",
    "power_pass": "/root/.ssh/bootstrap.rsa",
    "netboot_enabled": "1"
}

LIST_BLOCK_DEVICES_SAMPLE = [
    {'uspec':
        {'DEVLINKS': [
            'disk/by-id/scsi-SATA_VBOX_HARDDISK_VB69050467-b385c7cd',
            '/dev/disk/by-id/ata-VBOX_HARDDISK_VB69050467-b385c7cd',
            '/dev/disk/by-id/wwn-fake_wwn_1',
            '/dev/disk/by-path/pci-0000:00:1f.2-scsi-0:0:0:0'],
         'ID_SERIAL_SHORT': 'fake_serial_1',
         'ID_WWN': 'fake_wwn_1',
         'DEVPATH': '/devices/pci0000:00/0000:00:1f.2/ata1/host0/'
                    'target0:0:0/0:0:0:0/block/sda',
         'ID_MODEL': 'fake_id_model',
         'DEVNAME': '/dev/sda',
         'MAJOR': '8',
         'DEVTYPE': 'disk', 'MINOR': '0', 'ID_BUS': 'ata'
         },
     'startsec': '0',
     'device': '/dev/sda',
     'espec': {'state': 'running', 'timeout': '30', 'removable': '0'},
     'bspec': {
         'sz': '976773168', 'iomin': '4096', 'size64': '500107862016',
         'ss': '512', 'ioopt': '0', 'alignoff': '0', 'pbsz': '4096',
         'ra': '256', 'ro': '0', 'maxsect': '1024'
         },
     'size': 500107862016},
    {'uspec':
        {'DEVLINKS': [
            '/dev/disk/by-id/ata-VBOX_HARDDISK_VBf2923215-708af674',
            '/dev/disk/by-id/scsi-SATA_VBOX_HARDDISK_VBf2923215-708af674',
            '/dev/disk/by-id/wwn-fake_wwn_2'],
         'ID_SERIAL_SHORT': 'fake_serial_2',
         'ID_WWN': 'fake_wwn_2',
         'DEVPATH': '/devices/pci0000:00/0000:00:3f.2/ata2/host0/'
                    'target0:0:0/0:0:0:0/block/sdb',
         'ID_MODEL': 'fake_id_model',
         'DEVNAME': '/dev/sdb',
         'MAJOR': '8',
         'DEVTYPE': 'disk', 'MINOR': '0', 'ID_BUS': 'ata'
         },
     'startsec': '0',
     'device': '/dev/sdb',
     'espec': {'state': 'running', 'timeout': '30', 'removable': '0'},
     'bspec': {
         'sz': '976773168', 'iomin': '4096', 'size64': '500107862016',
         'ss': '512', 'ioopt': '0', 'alignoff': '0', 'pbsz': '4096',
         'ra': '256', 'ro': '0', 'maxsect': '1024'},
     'size': 500107862016},
    {'uspec':
        {'DEVLINKS': [
            '/dev/disk/by-id/ata-VBOX_HARDDISK_VB50ee61eb-84e74fdf',
            '/dev/disk/by-id/scsi-SATA_VBOX_HARDDISK_VB50ee61eb-84e74fdf',
            '/dev/disk/by-id/wwn-fake_wwn_3',
            '/dev/disk/by-path/pci-0000:00:0d.0-scsi-0:0:0:0'],
         'ID_SERIAL_SHORT': 'fake_serial_3',
         'ID_WWN': 'fake_wwn_3',
         'DEVPATH': '/devices/pci0000:00/0000:00:0d.0/ata4/host0/target0:0:0/'
                    '0:0:0:0/block/sdc',
         'ID_MODEL': 'fake_id_model',
         'DEVNAME': '/dev/sdc',
         'MAJOR': '8',
         'DEVTYPE': 'disk', 'MINOR': '0', 'ID_BUS': 'ata'},
     'startsec': '0',
     'device': '/dev/sdc',
     'espec': {'state': 'running', 'timeout': '30', 'removable': '0'},
     'bspec': {
         'sz': '976773168', 'iomin': '4096', 'size64': '500107862016',
         'ss': '512', 'ioopt': '0', 'alignoff': '0', 'pbsz': '4096',
         'ra': '256', 'ro': '0', 'maxsect': '1024'},
     'size': 500107862016},
]

SINGLE_DISK_KS_SPACES = [
    {
        "name": "sda",
        "extra": ["sda"],
        "free_space": 1024,
        "volumes": [
            {
                "type": "boot",
                "size": 300
            },
            {
                "mount": "/boot",
                "size": 200,
                "type": "partition",
                "file_system": "ext2",
                "name": "Boot"
            },
            {
                "mount": "/",
                "size": 200,
                "type": "partition",
                "file_system": "ext4",
                "name": "Root",
                "keep_data": True
            },
        ],
        "type": "disk",
        "id": "sda",
        "size": 102400
    }
]

NO_BOOT_KS_SPACES = [
    {
        "name": "sda",
        "extra": ["sda"],
        "free_space": 1024,
        "volumes": [
            {
                "type": "boot",
                "size": 300
            },
            {
                "mount": "/",
                "size": 200,
                "type": "partition",
                "file_system": "ext4",
                "name": "Root"
            },
        ],
        "type": "disk",
        "id": "sda",
        "size": 102400
    }
]

FIRST_DISK_HUGE_KS_SPACES = [
    {
        "name": "sda",
        "extra": ["sda"],
        "free_space": 1024,
        "volumes": [
            {
                "type": "boot",
                "size": 300
            },
            {
                "mount": "/boot",
                "size": 200,
                "type": "raid",
                "file_system": "ext2",
                "name": "Boot"
            },
            {
                "mount": "/",
                "size": 200,
                "type": "partition",
                "file_system": "ext4",
                "name": "Root"
            },
        ],
        "type": "disk",
        "id": "sda",
        "size": 2097153
    },
    {
        "name": "sdb",
        "extra": ["sdb"],
        "free_space": 1024,
        "volumes": [
            {
                "type": "boot",
                "size": 300
            },
            {
                "mount": "/boot",
                "size": 200,
                "type": "raid",
                "file_system": "ext2",
                "name": "Boot"
            },
            {
                "mount": "/tmp",
                "size": 200,
                "type": "partition",
                "file_system": "ext2",
                "name": "TMP"
            },
        ],
        "type": "disk",
        "id": "sdb",
        "size": 65535
    }
]

MANY_HUGE_DISKS_KS_SPACES = [
    {
        "name": "sda",
        "extra": ["sda"],
        "free_space": 1024,
        "volumes": [
            {
                "type": "boot",
                "size": 300
            },
            {
                "mount": "/boot",
                "size": 200,
                "type": "raid",
                "file_system": "ext2",
                "name": "Boot"
            },
            {
                "mount": "/",
                "size": 200,
                "type": "partition",
                "file_system": "ext4",
                "name": "Root"
            },
        ],
        "type": "disk",
        "id": "sda",
        "size": 2097153
    },
    {
        "name": "sdb",
        "extra": ["sdb"],
        "free_space": 1024,
        "volumes": [
            {
                "type": "boot",
                "size": 300
            },
            {
                "mount": "/boot",
                "size": 200,
                "type": "raid",
                "file_system": "ext2",
                "name": "Boot"
            },
            {
                "mount": "/tmp",
                "size": 200,
                "type": "partition",
                "file_system": "ext2",
                "name": "TMP"
            },
        ],
        "type": "disk",
        "id": "sdb",
        "size": 2097153
    }
]


class TestNailgun(test_base.BaseTestCase):

    def test_match_device_by_id_matches(self):
        # matches by 'by-id' links
        fake_ks_disk = {
            "extra": [
                "disk/by-id/fake_scsi_matches",
                "disk/by-id/fake_ata_dont_matches"
            ]
        }
        fake_hu_disk = {
            "uspec": {
                "DEVLINKS": [
                    "/dev/disk/by-id/fake_scsi_matches",
                    "/dev/disk/by-path/fake_path"
                ]
            }
        }
        self.assertTrue(nailgun.match_device(fake_hu_disk, fake_ks_disk))

    def test_match_device_id_dont_matches_non_empty_extra(self):
        # Shouldn't match. If non empty extra present it will match by what is
        # presented `extra` field, ignoring the `id` at all. Eg.: on VirtualBox
        fake_ks_disk = {
            "extra": [
                "disk/by-id/fake_scsi_dont_matches",
                "disk/by-id/fake_ata_dont_matches"
            ],
            "id": "sdd"
        }
        fake_hu_disk = {
            "uspec": {
                "DEVLINKS": [
                    "/dev/disk/by-id/fake_scsi_matches",
                    "/dev/disk/by-path/fake_path",
                    "/dev/sdd"
                ]
            }
        }
        self.assertFalse(nailgun.match_device(fake_hu_disk, fake_ks_disk))

    def test_match_device_id_matches_empty_extra(self):
        # since `extra` is empty, it will match by `id`
        fake_ks_disk = {
            "extra": [],
            "id": "sdd"
        }
        fake_hu_disk = {
            "uspec": {
                "DEVLINKS": [
                    "/dev/disk/by-id/fake_scsi_matches",
                    "/dev/disk/by-path/fake_path",
                    "/dev/sdd"
                ]
            }
        }
        self.assertTrue(nailgun.match_device(fake_hu_disk, fake_ks_disk))

    def test_match_device_id_matches_missing_extra(self):
        # `extra` is empty or just missing entirely, it will match by `id`
        fake_ks_disk = {"id": "sdd"}
        fake_hu_disk = {
            "uspec": {
                "DEVLINKS": [
                    "/dev/disk/by-id/fake_scsi_matches",
                    "/dev/disk/by-path/fake_path",
                    "/dev/sdd"
                ]
            }
        }
        self.assertTrue(nailgun.match_device(fake_hu_disk, fake_ks_disk))

    def test_match_device_dont_macthes(self):
        # Mismatches totally
        fake_ks_disk = {
            "extra": [
                "disk/by-id/fake_scsi_dont_matches",
                "disk/by-id/fake_ata_dont_matches"
            ],
            "id": "sda"
        }
        fake_hu_disk = {
            "uspec": {
                "DEVLINKS": [
                    "/dev/disk/by-id/fake_scsi_matches",
                    "/dev/disk/by-path/fake_path",
                    "/dev/sdd"
                ]
            }
        }
        self.assertFalse(nailgun.match_device(fake_hu_disk, fake_ks_disk))

    def test_match_device_dont_macthes_by_id(self):
        # disks are different but both of have same `by-path` link.
        # it will match by `extra` ignoring `id`
        fake_ks_disk = {
            "extra": [
                "disk/by-id/fake_scsi_dont_matches",
                "disk/by-id/fake_ata_dont_matches"
            ],
            "id": "disk/by-path/pci-fake_path"
        }
        fake_hu_disk = {
            "uspec": {
                "DEVLINKS": [
                    "/dev/disk/by-id/fake_scsi_matches",
                    "/dev/disk/by-path/pci-fake_path",
                    "/dev/sdd"
                ]
            }
        }
        self.assertFalse(nailgun.match_device(fake_hu_disk, fake_ks_disk))

    @mock.patch('yaml.load')
    @mock.patch.object(utils, 'init_http_request')
    @mock.patch.object(hu, 'list_block_devices')
    def test_configdrive_scheme(self, mock_lbd, mock_http, mock_yaml):
        mock_lbd.return_value = LIST_BLOCK_DEVICES_SAMPLE
        cd_scheme = nailgun.Nailgun(PROVISION_SAMPLE_DATA).configdrive_scheme
        self.assertEqual(['fake_authorized_key1', 'fake_authorized_key2',
                          'fake_auth_key'], cd_scheme.common.ssh_auth_keys)
        self.assertEqual('node-1.domain.tld', cd_scheme.common.hostname)
        self.assertEqual('node-1.domain.tld', cd_scheme.common.fqdn)
        self.assertEqual('node-1.domain.tld', cd_scheme.common.fqdn)
        self.assertEqual('"10.20.0.2"', cd_scheme.common.name_servers)
        self.assertEqual('"domain.tld"', cd_scheme.common.search_domain)
        self.assertEqual('10.20.0.2', cd_scheme.common.master_ip)
        self.assertEqual('http://10.20.0.2:8000/api',
                         cd_scheme.common.master_url)
        self.assertEqual('08:00:27:79:da:80_eth0,08:00:27:46:43:60_eth1,'
                         '08:00:27:b1:d7:15_eth2', cd_scheme.common.udevrules)
        self.assertEqual('08:00:27:79:da:80', cd_scheme.common.admin_mac)
        self.assertEqual('10.20.0.3', cd_scheme.common.admin_ip)
        self.assertEqual('255.255.255.0', cd_scheme.common.admin_mask)
        self.assertEqual('eth0', cd_scheme.common.admin_iface_name)
        self.assertEqual('America/Los_Angeles', cd_scheme.common.timezone)
        self.assertEqual('fuel.domain.tld', cd_scheme.puppet.master)
        self.assertEqual('unset', cd_scheme.mcollective.pskey)
        self.assertEqual('mcollective', cd_scheme.mcollective.vhost)
        self.assertEqual('10.20.0.2', cd_scheme.mcollective.host)
        self.assertEqual('mcollective', cd_scheme.mcollective.user)
        self.assertEqual('marionette', cd_scheme.mcollective.password)
        self.assertEqual('rabbitmq', cd_scheme.mcollective.connector)
        self.assertEqual('pro_fi-le', cd_scheme.profile)
        self.assertEqual(
            [
                {
                    "name": "repo1",
                    "type": "deb",
                    "uri": "uri1",
                    "suite": "suite",
                    "section": "section",
                    "priority": 1001
                },
                {
                    "name": "repo2",
                    "type": "deb",
                    "uri": "uri2",
                    "suite": "suite",
                    "section": "section",
                    "priority": 1001
                }
            ],
            cd_scheme.common.ks_repos)

    @mock.patch('yaml.load')
    @mock.patch.object(utils, 'init_http_request')
    @mock.patch.object(hu, 'list_block_devices')
    def test_partition_scheme(self, mock_lbd, mock_http_req, mock_yaml):
        mock_lbd.return_value = LIST_BLOCK_DEVICES_SAMPLE
        drv = nailgun.Nailgun(PROVISION_SAMPLE_DATA)
        p_scheme = drv.partition_scheme
        self.assertEqual(5, len(p_scheme.fss))
        self.assertEqual(4, len(p_scheme.pvs))
        self.assertEqual(3, len(p_scheme.lvs))
        self.assertEqual(2, len(p_scheme.vgs))
        self.assertEqual(3, len(p_scheme.parteds))

    @mock.patch('yaml.load')
    @mock.patch.object(utils, 'init_http_request')
    @mock.patch.object(hu, 'list_block_devices')
    def test_image_scheme(self, mock_lbd, mock_http_req, mock_yaml):
        mock_lbd.return_value = LIST_BLOCK_DEVICES_SAMPLE
        drv = nailgun.Nailgun(PROVISION_SAMPLE_DATA)
        p_scheme = drv.partition_scheme
        i_scheme = drv.image_scheme
        expected_images = []
        for fs in p_scheme.fss:
            if fs.mount not in PROVISION_SAMPLE_DATA['ks_meta']['image_data']:
                continue
            i_data = PROVISION_SAMPLE_DATA['ks_meta']['image_data'][fs.mount]
            expected_images.append(image.Image(
                uri=i_data['uri'],
                target_device=fs.device,
                format=i_data['format'],
                container=i_data['container'],
            ))
        expected_images = sorted(expected_images, key=lambda x: x.uri)
        for i, img in enumerate(sorted(i_scheme.images, key=lambda x: x.uri)):
            self.assertEqual(img.uri, expected_images[i].uri)
            self.assertEqual(img.target_device,
                             expected_images[i].target_device)
            self.assertEqual(img.format,
                             expected_images[i].format)
            self.assertEqual(img.container,
                             expected_images[i].container)
            self.assertIsNone(img.size)
            self.assertIsNone(img.md5)

    @mock.patch.object(utils, 'init_http_request')
    @mock.patch.object(hu, 'list_block_devices')
    def test_image_scheme_with_checksums(self, mock_lbd, mock_http_req):
        fake_image_meta = {'images': [{'raw_md5': 'fakeroot', 'raw_size': 1,
                                       'container_name': 'fake_image.img.gz'}]}
        prop_mock = mock.PropertyMock(return_value=yaml.dump(fake_image_meta))
        type(mock_http_req.return_value).text = prop_mock
        mock_lbd.return_value = LIST_BLOCK_DEVICES_SAMPLE
        p_data = PROVISION_SAMPLE_DATA.copy()
        drv = nailgun.Nailgun(p_data)
        p_scheme = drv.partition_scheme
        i_scheme = drv.image_scheme
        mock_http_req.assert_called_once_with(
            'http://fake.host.org:123/imgs/fake_image.yaml')
        expected_images = []
        for fs in p_scheme.fss:
            if fs.mount not in PROVISION_SAMPLE_DATA['ks_meta']['image_data']:
                continue
            i_data = PROVISION_SAMPLE_DATA['ks_meta']['image_data'][fs.mount]
            expected_images.append(image.Image(
                uri=i_data['uri'],
                target_device=fs.device,
                format=i_data['format'],
                container=i_data['container'],
            ))
        expected_images = sorted(expected_images, key=lambda x: x.uri)
        for i, img in enumerate(sorted(i_scheme.images, key=lambda x: x.uri)):
            self.assertEqual(img.uri, expected_images[i].uri)
            self.assertEqual(img.target_device,
                             expected_images[i].target_device)
            self.assertEqual(img.format,
                             expected_images[i].format)
            self.assertEqual(img.container,
                             expected_images[i].container)
            self.assertEqual(
                img.size, fake_image_meta['images'][0]['raw_size'])
            self.assertEqual(img.md5, fake_image_meta['images'][0]['raw_md5'])

    @mock.patch('yaml.load')
    @mock.patch.object(utils, 'init_http_request')
    @mock.patch.object(hu, 'list_block_devices')
    def test_getlabel(self, mock_lbd, mock_http_req, mock_yaml):
        mock_lbd.return_value = LIST_BLOCK_DEVICES_SAMPLE
        drv = nailgun.Nailgun(PROVISION_SAMPLE_DATA)
        self.assertEqual('', drv._getlabel(None))
        long_label = '1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        self.assertEqual(' -L %s ' % long_label[:12],
                         drv._getlabel(long_label))

    @mock.patch('yaml.load')
    @mock.patch.object(utils, 'init_http_request')
    @mock.patch.object(hu, 'list_block_devices')
    def test_disk_dev_not_found(self, mock_lbd, mock_http_req, mock_yaml):
        mock_lbd.return_value = LIST_BLOCK_DEVICES_SAMPLE
        drv = nailgun.Nailgun(PROVISION_SAMPLE_DATA)
        fake_ks_disk = {
            "name": "fake",
            "extra": [
                "disk/by-id/fake_scsi_matches",
                "disk/by-id/fake_ata_dont_matches"
            ]
        }
        self.assertRaises(errors.DiskNotFoundError, drv._disk_dev,
                          fake_ks_disk)

    @mock.patch('yaml.load')
    @mock.patch.object(utils, 'init_http_request')
    @mock.patch.object(hu, 'list_block_devices')
    def test_get_partition_count(self, mock_lbd, mock_http_req, mock_yaml):
        mock_lbd.return_value = LIST_BLOCK_DEVICES_SAMPLE
        drv = nailgun.Nailgun(PROVISION_SAMPLE_DATA)
        self.assertEqual(3, drv._get_partition_count('Boot'))
        self.assertEqual(1, drv._get_partition_count('TMP'))

    @mock.patch('yaml.load')
    @mock.patch.object(utils, 'init_http_request')
    @mock.patch.object(hu, 'list_block_devices')
    def test_partition_scheme_ceph(self, mock_lbd, mock_http_req, mock_yaml):
        # TODO(agordeev): perform better testing of ceph logic
        p_data = copy.deepcopy(PROVISION_SAMPLE_DATA)
        for i in range(0, 3):
            p_data['ks_meta']['pm_data']['ks_spaces'][i]['volumes'].append(
                CEPH_JOURNAL)
            p_data['ks_meta']['pm_data']['ks_spaces'][i]['volumes'].append(
                CEPH_DATA)
        mock_lbd.return_value = LIST_BLOCK_DEVICES_SAMPLE
        drv = nailgun.Nailgun(p_data)
        p_scheme = drv.partition_scheme
        self.assertEqual(5, len(p_scheme.fss))
        self.assertEqual(4, len(p_scheme.pvs))
        self.assertEqual(3, len(p_scheme.lvs))
        self.assertEqual(2, len(p_scheme.vgs))
        self.assertEqual(3, len(p_scheme.parteds))
        self.assertEqual(3, drv._get_partition_count('ceph'))
        # NOTE(agordeev): (-2, -1, -1) is the list of ceph data partition
        # counts corresponding to (sda, sdb, sdc) disks respectively.
        for disk, part in enumerate((-2, -1, -1)):
            self.assertEqual(CEPH_DATA['partition_guid'],
                             p_scheme.parteds[disk].partitions[part].guid)

    @mock.patch('fuel_agent.drivers.nailgun.yaml.load')
    @mock.patch('fuel_agent.drivers.nailgun.utils.init_http_request')
    @mock.patch('fuel_agent.drivers.nailgun.hu.list_block_devices')
    def test_grub_centos_26(self, mock_lbd, mock_http_req, mock_yaml):
        data = copy.deepcopy(PROVISION_SAMPLE_DATA)
        data['profile'] = 'centos'
        data['ks_meta']['kernel_lt'] = 0
        mock_lbd.return_value = LIST_BLOCK_DEVICES_SAMPLE
        drv = nailgun.Nailgun(data)
        self.assertEqual(drv.grub.kernel_params,
                         ' ' + data['ks_meta']['pm_data']['kernel_params'])
        self.assertEqual(drv.grub.kernel_regexp, r'^vmlinuz-2\.6.*')
        self.assertEqual(drv.grub.initrd_regexp, r'^initramfs-2\.6.*')
        self.assertIsNone(drv.grub.version)
        self.assertIsNone(drv.grub.kernel_name)
        self.assertIsNone(drv.grub.initrd_name)

    @mock.patch('fuel_agent.drivers.nailgun.yaml.load')
    @mock.patch('fuel_agent.drivers.nailgun.utils.init_http_request')
    @mock.patch('fuel_agent.drivers.nailgun.hu.list_block_devices')
    def test_grub_centos_lt(self, mock_lbd, mock_http_req, mock_yaml):
        data = copy.deepcopy(PROVISION_SAMPLE_DATA)
        data['profile'] = 'centos'
        data['ks_meta']['kernel_lt'] = 1
        mock_lbd.return_value = LIST_BLOCK_DEVICES_SAMPLE
        drv = nailgun.Nailgun(data)
        self.assertEqual(drv.grub.kernel_params,
                         ' ' + data['ks_meta']['pm_data']['kernel_params'])
        self.assertIsNone(drv.grub.kernel_regexp)
        self.assertIsNone(drv.grub.initrd_regexp)
        self.assertIsNone(drv.grub.version)
        self.assertIsNone(drv.grub.kernel_name)
        self.assertIsNone(drv.grub.initrd_name)

    @mock.patch('fuel_agent.drivers.nailgun.yaml.load')
    @mock.patch('fuel_agent.drivers.nailgun.utils.init_http_request')
    @mock.patch('fuel_agent.drivers.nailgun.hu.list_block_devices')
    def test_grub_ubuntu(self, mock_lbd, mock_http_req, mock_yaml):
        data = copy.deepcopy(PROVISION_SAMPLE_DATA)
        data['profile'] = 'ubuntu'
        data['ks_meta']['kernel_lt'] = 0
        mock_lbd.return_value = LIST_BLOCK_DEVICES_SAMPLE
        drv = nailgun.Nailgun(data)
        self.assertEqual(drv.grub.kernel_params,
                         ' ' + data['ks_meta']['pm_data']['kernel_params'])
        self.assertIsNone(drv.grub.version)
        self.assertIsNone(drv.grub.kernel_regexp)
        self.assertIsNone(drv.grub.initrd_regexp)
        self.assertIsNone(drv.grub.kernel_name)
        self.assertIsNone(drv.grub.initrd_name)

    @mock.patch('fuel_agent.drivers.nailgun.yaml.load')
    @mock.patch('fuel_agent.drivers.nailgun.utils.init_http_request')
    @mock.patch('fuel_agent.drivers.nailgun.hu.list_block_devices')
    def test_boot_partition_ok_single_disk(self, mock_lbd,
                                           mock_http_req, mock_yaml):
        data = copy.deepcopy(PROVISION_SAMPLE_DATA)
        data['ks_meta']['pm_data']['ks_spaces'] = SINGLE_DISK_KS_SPACES
        mock_lbd.return_value = LIST_BLOCK_DEVICES_SAMPLE
        drv = nailgun.Nailgun(data)
        self.assertEqual(
            drv.partition_scheme.fs_by_mount('/boot').device,
            '/dev/sda3')

    @mock.patch('fuel_agent.drivers.nailgun.yaml.load')
    @mock.patch('fuel_agent.drivers.nailgun.utils.init_http_request')
    @mock.patch('fuel_agent.drivers.nailgun.hu.list_block_devices')
    def test_elevate_keep_data_single_disk(self, mock_lbd,
                                           mock_http_req, mock_yaml):
        data = copy.deepcopy(PROVISION_SAMPLE_DATA)
        data['ks_meta']['pm_data']['ks_spaces'] = SINGLE_DISK_KS_SPACES
        mock_lbd.return_value = LIST_BLOCK_DEVICES_SAMPLE
        drv = nailgun.Nailgun(data)
        self.assertTrue(drv.partition_scheme.fs_by_mount('/').keep_data)

        for parted in drv.partition_scheme.parteds:
            for partition in parted.partitions:
                self.assertFalse(partition.keep_data)

        for md in drv.partition_scheme.mds:
            self.assertFalse(md.keep_data)

        for pv in drv.partition_scheme.pvs:
            self.assertFalse(pv.keep_data)

        for vg in drv.partition_scheme.vgs:
            self.assertFalse(vg.keep_data)

        for lv in drv.partition_scheme.lvs:
            self.assertFalse(lv.keep_data)

        for fs in drv.partition_scheme.fss:
            if fs.mount != '/':
                self.assertFalse(fs.keep_data)

    @mock.patch('fuel_agent.drivers.nailgun.yaml.load')
    @mock.patch('fuel_agent.drivers.nailgun.utils.init_http_request')
    @mock.patch('fuel_agent.drivers.nailgun.hu.list_block_devices')
    def test_boot_partition_ok_many_normal_disks(self, mock_lbd,
                                                 mock_http_req, mock_yaml):
        data = copy.deepcopy(PROVISION_SAMPLE_DATA)
        mock_lbd.return_value = LIST_BLOCK_DEVICES_SAMPLE
        drv = nailgun.Nailgun(data)
        self.assertEqual(
            drv.partition_scheme.fs_by_mount('/boot').device,
            '/dev/sda3')

    @mock.patch('fuel_agent.drivers.nailgun.yaml.load')
    @mock.patch('fuel_agent.drivers.nailgun.utils.init_http_request')
    @mock.patch('fuel_agent.drivers.nailgun.hu.list_block_devices')
    def test_boot_partition_ok_first_disk_huge(self, mock_lbd,
                                               mock_http_req, mock_yaml):
        data = copy.deepcopy(PROVISION_SAMPLE_DATA)
        data['ks_meta']['pm_data']['ks_spaces'] = FIRST_DISK_HUGE_KS_SPACES
        mock_lbd.return_value = LIST_BLOCK_DEVICES_SAMPLE
        drv = nailgun.Nailgun(data)
        self.assertEqual(
            drv.partition_scheme.fs_by_mount('/boot').device,
            '/dev/sdb3')

    @mock.patch('fuel_agent.drivers.nailgun.yaml.load')
    @mock.patch('fuel_agent.drivers.nailgun.utils.init_http_request')
    @mock.patch('fuel_agent.drivers.nailgun.hu.list_block_devices')
    def test_boot_partition_ok_many_huge_disks(self, mock_lbd,
                                               mock_http_req, mock_yaml):
        data = copy.deepcopy(PROVISION_SAMPLE_DATA)
        data['ks_meta']['pm_data']['ks_spaces'] = MANY_HUGE_DISKS_KS_SPACES
        mock_lbd.return_value = LIST_BLOCK_DEVICES_SAMPLE
        drv = nailgun.Nailgun(data)
        self.assertEqual(
            drv.partition_scheme.fs_by_mount('/boot').device,
            '/dev/sda3')

    @mock.patch('fuel_agent.drivers.nailgun.yaml.load')
    @mock.patch('fuel_agent.drivers.nailgun.utils.init_http_request')
    @mock.patch('fuel_agent.drivers.nailgun.hu.list_block_devices')
    def test_boot_partition_no_boot(self, mock_lbd,
                                    mock_http_req, mock_yaml):
        data = copy.deepcopy(PROVISION_SAMPLE_DATA)
        data['ks_meta']['pm_data']['ks_spaces'] = NO_BOOT_KS_SPACES
        mock_lbd.return_value = LIST_BLOCK_DEVICES_SAMPLE
        self.assertRaises(errors.WrongPartitionSchemeError,
                          nailgun.Nailgun, data)
