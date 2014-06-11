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

from fuel_agent.driver.nailgun import partition
from fuel_agent import errors

PARTITION_SCHEME = [
    {
        "name": "sda",
        "extra": [
            "disk/by-id/scsi-SATA_VBOX_HARDDISK_VB39e72f9e-d0da1fcd",
            "disk/by-id/ata-VBOX_HARDDISK_VB39e72f9e-d0da1fcd"
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
        "id": "disk/by-path/pci-0000:00:0d.0-scsi-0:0:0:0",
        "size": 65535
    },
    {
        "name": "sdb",
        "extra": [
            "disk/by-id/scsi-SATA_VBOX_HARDDISK_VB6dbf6500-ae917714",
            "disk/by-id/ata-VBOX_HARDDISK_VB6dbf6500-ae917714"
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
            "disk/by-id/scsi-SATA_VBOX_HARDDISK_VBa023ea88-b207b79c",
            "disk/by-id/ata-VBOX_HARDDISK_VBa023ea88-b207b79c"
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
        "id": "sdc",
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

class TestPartitionDriver(test_base.BaseTestCase):

    @mock.patch('fuel_agent.driver.nailgun.partition.PartitionDriver.__init__',
                mock.Mock(return_value=None))
    def setUp(self):
        super(TestPartitionDriver, self).setUp()
        self.pd = pd = partition.PartitionDriver()

    def test_validate_scheme_valid(self):
        # should not raise exception for a valid partition scheme
        self.assertIsNone(
            self.pd._validate_scheme(PARTITION_SCHEME))

    def test_validate_scheme_empty(self):
        # should raise exception if scheme is empty
        self.assertRaises(errors.WrongPartitionSchemeError,
                          self.pd._validate_scheme, [])

    def test_validate_scheme_there_is_no_disks(self):
        # should raise exception if there is no disks in a scheme
        self.assertRaises(errors.WrongPartitionSchemeError,
            self.pd._validate_scheme,
            [{'type': 'vg', 'id': 'id', 'volumes': []}])

    def test_validate_scheme_invalid(self):
        # should raise exception if scheme is invalid
        self.assertRaises(errors.WrongPartitionSchemeError,
            self.pd._validate_scheme,
            [{'invalid': 'scheme_element'}])
