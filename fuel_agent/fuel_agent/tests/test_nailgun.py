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

import mock
from oslotest import base as test_base

from fuel_agent.drivers import nailgun
from fuel_agent import errors
from fuel_agent.utils import hardware_utils as hu


PROVISION_SAMPLE_DATA = {
    "profile": "ubuntu_1204_x86_64",
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


class TestNailgun(test_base.BaseTestCase):
    def setUp(self):
        super(TestNailgun, self).setUp()
        self.drv = nailgun.Nailgun(PROVISION_SAMPLE_DATA)

    def test_match_device_by_id_matches(self):
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

    def test_match_device_id_matches(self):
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
        self.assertTrue(nailgun.match_device(fake_hu_disk, fake_ks_disk))

    def test_match_device_dont_macthes(self):
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

    def test_configdrive_scheme(self):
        cd_scheme = self.drv.configdrive_scheme()
        self.assertEqual('fake_auth_key', cd_scheme.common.ssh_auth_key)
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
        self.assertEqual('ubuntu', cd_scheme.profile)

    @mock.patch.object(hu, 'list_block_devices')
    def test_partition_scheme(self, mock_lbd):
        mock_lbd.return_value = LIST_BLOCK_DEVICES_SAMPLE
        p_scheme = self.drv.partition_scheme()
        self.assertEqual(5, len(p_scheme.fss))
        self.assertEqual(4, len(p_scheme.pvs))
        self.assertEqual(3, len(p_scheme.lvs))
        self.assertEqual(2, len(p_scheme.vgs))
        self.assertEqual(1, len(p_scheme.mds))
        self.assertEqual(3, len(p_scheme.parteds))

    @mock.patch.object(hu, 'list_block_devices')
    def test_image_scheme(self, mock_lbd):
        mock_lbd.return_value = LIST_BLOCK_DEVICES_SAMPLE
        p_scheme = self.drv.partition_scheme()
        i_scheme = self.drv.image_scheme(p_scheme)
        self.assertEqual(1, len(i_scheme.images))
        img = i_scheme.images[0]
        self.assertEqual('gzip', img.container)
        self.assertEqual('ext4', img.image_format)
        self.assertEqual('/dev/mapper/os-root', img.target_device)
        self.assertEqual(
            'http://%s/targetimages/%s.img.gz' % (
                self.drv.data['ks_meta']['master_ip'],
                self.drv.data['profile'].split('_')[0]),
            img.uri)
        self.assertEqual(None, img.size)

    def test_getlabel(self):
        self.assertEqual('', self.drv._getlabel(None))
        long_label = '1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        self.assertEqual(' -L %s ' % long_label[:12],
                         self.drv._getlabel(long_label))

    @mock.patch.object(hu, 'list_block_devices')
    def test_disk_dev_not_found(self, mock_lbd):
        mock_lbd.return_value = LIST_BLOCK_DEVICES_SAMPLE
        fake_ks_disk = {
            "name": "fake",
            "extra": [
                "disk/by-id/fake_scsi_matches",
                "disk/by-id/fake_ata_dont_matches"
            ]
        }
        self.assertRaises(errors.DiskNotFoundError, self.drv._disk_dev,
                          fake_ks_disk)
