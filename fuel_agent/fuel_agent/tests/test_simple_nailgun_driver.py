# -*- coding: utf-8 -*-

#    Copyright 2015 Mirantis, Inc.
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
import mock
import requests_mock
import unittest2

from fuel_agent.drivers import nailgun
from fuel_agent import objects
from fuel_agent.tests import base


@mock.patch.multiple(
    nailgun.NailgunSimpleDriver,
    parse_grub=lambda x: objects.Grub(),
    parse_configdrive_scheme=lambda x: objects.ConfigDriveScheme(),
    parse_image_scheme=lambda x: objects.ImageScheme())
class TestObjectDeserialization(unittest2.TestCase):

    def test_driver_always_has_correct_objects(self):
        driver = nailgun.NailgunSimpleDriver({})
        assert isinstance(driver.partition_scheme, objects.PartitionScheme)

    def test_lv_data_is_loaded(self):
        lv_data = {
            'partitioning': {
                'lv': [
                    {
                        'name': 'lv-name',
                        'size': 12345,
                        'vgname': 'vg-name',
                    },
                ]
            }
        }

        driver = nailgun.NailgunSimpleDriver(lv_data)
        lv = driver.partition_scheme.lvs[0]
        assert len(driver.partition_scheme.lvs) == 1
        assert isinstance(lv, objects.LV)
        assert lv.name == 'lv-name'
        assert lv.size == 12345
        assert lv.vgname == 'vg-name'

    def test_pv_data_is_loaded(self):
        pv_data = {
            'partitioning': {
                'pv': [
                    {
                        'metadatacopies': 2,
                        'metadatasize': 28,
                        'name': '/dev/sda5'
                    },
                ]
            }
        }

        driver = nailgun.NailgunSimpleDriver(pv_data)
        pv = driver.partition_scheme.pvs[0]
        assert len(driver.partition_scheme.pvs) == 1
        assert isinstance(pv, objects.PV)
        assert pv.name == '/dev/sda5'
        assert pv.metadatacopies == 2
        assert pv.metadatasize == 28

    def test_vg_data_is_loaded(self):
        vg_data = {
            'partitioning': {
                'vg': [
                    {
                        'name': 'image',
                        'pvnames': [
                            '/dev/sda6',
                            '/dev/sdb3',
                            '/dev/sdc3',
                        ]
                    },
                ]
            }
        }

        driver = nailgun.NailgunSimpleDriver(vg_data)
        vg = driver.partition_scheme.vgs[0]
        assert len(driver.partition_scheme.vgs) == 1
        assert isinstance(vg, objects.VG)
        assert vg.name == 'image'
        self.assertItemsEqual(
            vg.pvnames,
            (
                '/dev/sda6',
                '/dev/sdb3',
                '/dev/sdc3',
            )
        )

    def test_fs_data_is_loaded(self):
        fs_data = {
            'partitioning': {
                'fs': [
                    {
                        'device': '/dev/sda3',
                        'fs_label': 'some-label',
                        'fs_options': 'some-options',
                        'fs_type': 'ext2',
                        'mount': '/boot'
                    },
                ]
            }
        }

        driver = nailgun.NailgunSimpleDriver(fs_data)
        fs = driver.partition_scheme.fss[0]
        assert len(driver.partition_scheme.fss) == 1
        assert isinstance(fs, objects.FS)
        assert fs.device == '/dev/sda3'
        assert fs.label == 'some-label'
        assert fs.options == 'some-options'
        assert fs.type == 'ext2'
        assert fs.mount == '/boot'

    def test_parted_data_is_loaded(self):
        parted_data = {
            'partitioning': {
                'parted': [
                    {
                        'label': 'gpt',
                        'name': '/dev/sdb',
                        'partitions': [
                            {
                                'begin': 1,
                                'configdrive': False,
                                'count': 1,
                                'device': '/dev/sdb',
                                'end': 25,
                                'flags': [
                                    'bios_grub',
                                    'xyz',
                                ],
                                'guid': None,
                                'name': '/dev/sdb1',
                                'partition_type': 'primary'
                            },
                        ]
                    },
                ]
            }
        }

        driver = nailgun.NailgunSimpleDriver(parted_data)
        parted = driver.partition_scheme.parteds[0]
        partition = parted.partitions[0]
        assert len(driver.partition_scheme.parteds) == 1
        assert isinstance(parted, objects.Parted)
        assert parted.label == 'gpt'
        assert parted.name == '/dev/sdb'
        assert len(parted.partitions) == 1
        assert partition.begin == 1
        assert partition.configdrive is False
        assert partition.count == 1
        assert partition.device == '/dev/sdb'
        assert partition.end == 25
        self.assertItemsEqual(partition.flags, ['bios_grub', 'xyz'])
        assert partition.guid is None
        assert partition.name == '/dev/sdb1'
        assert partition.type == 'primary'

    def test_md_data_is_loaded(self):
        md_data = {
            'partitioning': {
                'md': [
                    {
                        'name': 'some-raid',
                        'level': 1,
                        'devices': [
                            '/dev/sda',
                            '/dev/sdc',
                        ],
                        'spares': [
                            '/dev/sdb',
                            '/dev/sdd',
                        ]
                    },
                ]
            }
        }

        driver = nailgun.NailgunSimpleDriver(md_data)
        md = driver.partition_scheme.mds[0]
        assert len(driver.partition_scheme.mds) == 1
        assert isinstance(md, objects.MD)
        assert md.name == 'some-raid'
        assert md.level == 1
        self.assertItemsEqual(md.devices, ['/dev/sda', '/dev/sdc'])
        self.assertItemsEqual(md.spares, ['/dev/sdb', '/dev/sdd'])


@requests_mock.mock()
class TestFullDataRead(unittest2.TestCase):

    PROVISION_DATA = base.load_fixture('simple_nailgun_driver.json')

    def test_read_with_no_error(self, mock_requests):
        mock_requests.get('http://fake.host.org:123/imgs/fake_image.img.gz',
                          text='{}')
        driver = nailgun.NailgunSimpleDriver(self.PROVISION_DATA)
        scheme = driver.partition_scheme
        assert len(scheme.fss) == 5
        assert len(scheme.lvs) == 3
        assert len(scheme.mds) == 0
        assert len(scheme.parteds) == 2
        assert len(scheme.pvs) == 4
        assert len(scheme.vgs) == 2
