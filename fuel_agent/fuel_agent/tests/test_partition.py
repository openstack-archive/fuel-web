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
import unittest2

from fuel_agent import errors
from fuel_agent.objects import partition


class TestMD(unittest2.TestCase):

    def setUp(self):
        super(TestMD, self).setUp()
        self.md = partition.MD(name='name', level='level')

    def test_add_device_ok(self):
        self.assertEqual(0, len(self.md.devices))
        self.md.add_device('device')
        self.assertEqual(1, len(self.md.devices))
        self.assertEqual('device', self.md.devices[0])

    def test_add_device_in_spares_fail(self):
        self.assertEqual(0, len(self.md.devices))
        self.assertEqual(0, len(self.md.spares))
        self.md.add_spare('device')
        self.assertRaises(errors.MDDeviceDuplicationError, self.md.add_device,
                          'device')

    def test_add_device_in_devices_fail(self):
        self.assertEqual(0, len(self.md.devices))
        self.assertEqual(0, len(self.md.spares))
        self.md.add_device('device')
        self.assertRaises(errors.MDDeviceDuplicationError, self.md.add_device,
                          'device')

    def test_add_spare_in_spares_fail(self):
        self.assertEqual(0, len(self.md.devices))
        self.assertEqual(0, len(self.md.spares))
        self.md.add_spare('device')
        self.assertRaises(errors.MDDeviceDuplicationError, self.md.add_spare,
                          'device')

    def test_add_spare_in_devices_fail(self):
        self.assertEqual(0, len(self.md.devices))
        self.assertEqual(0, len(self.md.spares))
        self.md.add_device('device')
        self.assertRaises(errors.MDDeviceDuplicationError, self.md.add_spare,
                          'device')

    def test_conversion(self):
        self.md.add_device('device_a')
        self.md.add_spare('device_b')
        serialized = self.md.to_dict()
        assert serialized == {
            'name': 'name',
            'level': 'level',
            'devices': ['device_a', ],
            'sparses': ['device_b', ],
        }


class TestPartition(unittest2.TestCase):
    def setUp(self):
        super(TestPartition, self).setUp()
        self.pt = partition.Partition('name', 'count', 'device', 'begin',
                                      'end', 'partition_type')

    def test_set_flag(self):
        self.assertEqual(0, len(self.pt.flags))
        self.pt.set_flag('fake_flag')
        self.assertEqual(1, len(self.pt.flags))
        self.assertIn('fake_flag', self.pt.flags)

    def test_conversion(self):
        self.pt.flags.append('some_flag')
        self.pt.guid = 'some_guid'
        serialized = self.pt.to_dict()
        assert serialized == {
            'begin': 'begin',
            'configdrive': False,
            'count': 'count',
            'device': 'device',
            'end': 'end',
            'flags': ['some_flag', ],
            'guid': 'some_guid',
            'name': 'name',
            'partition_type': 'partition_type',
        }


class TestPartitionScheme(unittest2.TestCase):
    def setUp(self):
        super(TestPartitionScheme, self).setUp()
        self.p_scheme = partition.PartitionScheme()

    def test_root_device_not_found(self):
        self.assertRaises(errors.WrongPartitionSchemeError,
                          self.p_scheme.root_device)

    def test_fs_by_device(self):
        expected_fs = partition.FS('device')
        self.p_scheme.fss.append(expected_fs)
        self.p_scheme.fss.append(partition.FS('wrong_device'))
        actual_fs = self.p_scheme.fs_by_device('device')
        self.assertEqual(expected_fs, actual_fs)

    def test_fs_by_mount(self):
        expected_fs = partition.FS('d', mount='mount')
        self.p_scheme.fss.append(expected_fs)
        self.p_scheme.fss.append(partition.FS('w_d', mount='wrong_mount'))
        actual_fs = self.p_scheme.fs_by_mount('mount')
        self.assertEqual(expected_fs, actual_fs)

    def test_pv_by_name(self):
        expected_pv = partition.PV('pv')
        self.p_scheme.pvs.append(expected_pv)
        self.p_scheme.pvs.append(partition.PV('wrong_pv'))
        actual_pv = self.p_scheme.pv_by_name('pv')
        self.assertEqual(expected_pv, actual_pv)

    def test_vg_by_name(self):
        expected_vg = partition.VG('vg')
        self.p_scheme.vgs.append(expected_vg)
        self.p_scheme.vgs.append(partition.VG('wrong_vg'))
        actual_vg = self.p_scheme.vg_by_name('vg')
        self.assertEqual(expected_vg, actual_vg)

    def test_vg_attach_by_name(self):
        self.p_scheme.vg_attach_by_name('pvname', 'vgname')
        self.assertEqual(1, len(self.p_scheme.pvs))
        self.assertEqual(1, len(self.p_scheme.vgs))
        self.assertIn('pvname', self.p_scheme.vgs[0].pvnames)
        self.assertIn('vgname', self.p_scheme.vgs[0].name)

    def test_md_next_name_ok(self):
        expected_name = '/dev/md0'
        self.assertEqual(expected_name, self.p_scheme.md_next_name())

    def test_md_next_name_fail(self):
        self.p_scheme.mds = [
            partition.MD('/dev/md%s' % x, 'level') for x in range(0, 128)]
        self.assertRaises(errors.MDAlreadyExistsError,
                          self.p_scheme.md_next_name)

    def test_md_by_name(self):
        self.assertEqual(0, len(self.p_scheme.mds))
        expected_md = partition.MD('name', 'level')
        self.p_scheme.mds.append(expected_md)
        self.p_scheme.mds.append(partition.MD('wrong_name', 'level'))
        self.assertEqual(expected_md, self.p_scheme.md_by_name('name'))

    def test_md_by_mount(self):
        self.assertEqual(0, len(self.p_scheme.mds))
        self.assertEqual(0, len(self.p_scheme.fss))
        expected_md = partition.MD('name', 'level')
        expected_fs = partition.FS('name', mount='mount')
        self.p_scheme.mds.append(expected_md)
        self.p_scheme.fss.append(expected_fs)
        self.p_scheme.fss.append(partition.FS('wrong_name',
                                 mount='wrong_mount'))
        self.assertEqual(expected_md, self.p_scheme.md_by_mount('mount'))

    def test_md_attach_by_mount_md_exists(self):
        self.assertEqual(0, len(self.p_scheme.mds))
        self.assertEqual(0, len(self.p_scheme.fss))
        expected_md = partition.MD('name', 'level')
        expected_fs = partition.FS('name', mount='mount')
        self.p_scheme.mds.append(expected_md)
        self.p_scheme.fss.append(expected_fs)
        actual_md = self.p_scheme.md_attach_by_mount('device', 'mount')
        self.assertIn('device', actual_md.devices)
        self.assertEqual(expected_md, actual_md)

    def test_md_attach_by_mount_no_md(self):
        self.assertEqual(0, len(self.p_scheme.mds))
        self.assertEqual(0, len(self.p_scheme.fss))
        actual_md = self.p_scheme.md_attach_by_mount(
            'device', 'mount', fs_type='fs_type', fs_options='-F',
            fs_label='fs_label', name='name', level='level')
        self.assertIn('device', actual_md.devices)
        self.assertEqual(1, len(self.p_scheme.fss))
        self.assertEqual('name', self.p_scheme.fss[0].device)
        self.assertEqual('mount', self.p_scheme.fss[0].mount)
        self.assertEqual('fs_type', self.p_scheme.fss[0].type)
        self.assertEqual('fs_label', self.p_scheme.fss[0].label)
        self.assertEqual('-F', self.p_scheme.fss[0].options)


class TestParted(unittest2.TestCase):
    def setUp(self):
        super(TestParted, self).setUp()
        self.prtd = partition.Parted('name', 'label')

    @mock.patch.object(partition.Parted, 'next_count')
    @mock.patch.object(partition.Parted, 'next_type')
    def test_next_name_none(self, nt_mock, nc_mock):
        nc_mock.return_value = 1
        nt_mock.return_value = 'extended'
        self.assertEqual(None, self.prtd.next_name())

    @mock.patch.object(partition.Parted, 'next_count')
    @mock.patch.object(partition.Parted, 'next_type')
    def test_next_name_no_separator(self, nt_mock, nc_mock):
        nc_mock.return_value = 1
        nt_mock.return_value = 'not_extended'
        expected_name = '%s%s' % (self.prtd.name, 1)
        self.assertEqual(expected_name, self.prtd.next_name())

    @mock.patch.object(partition.Parted, 'next_count')
    @mock.patch.object(partition.Parted, 'next_type')
    def test_next_name_with_separator(self, nt_mock, nc_mock):
        nc_mock.return_value = 1
        nt_mock.return_value = 'not_extended'
        self.prtd.name = '/dev/cciss/c0d0'
        expected_name = '%sp%s' % (self.prtd.name, 1)
        self.assertEqual(expected_name, self.prtd.next_name())
        self.prtd.name = '/dev/loop123'
        expected_name = '%sp%s' % (self.prtd.name, 1)
        self.assertEqual(expected_name, self.prtd.next_name())
        self.prtd.name = '/dev/nvme0n1'
        expected_name = '%sp%s' % (self.prtd.name, 1)
        self.assertEqual(expected_name, self.prtd.next_name())

    def test_next_begin_empty_partitions(self):
        self.assertEqual(1, self.prtd.next_begin())

    def test_next_begin_last_extended_partition(self):
        self.prtd.partitions.append(
            partition.Partition('name', 'count', 'device', 'begin', 'end',
                                'extended'))
        self.assertEqual('begin', self.prtd.next_begin())

    def test_next_begin_no_last_extended_partition(self):
        self.prtd.partitions.append(
            partition.Partition('name', 'count', 'device', 'begin', 'end',
                                'primary'))
        self.assertEqual('end', self.prtd.next_begin())

    def test_next_count_no_logical(self):
        self.assertEqual(1, self.prtd.next_count('primary'))

    def test_next_count_has_logical(self):
        self.prtd.partitions.append(
            partition.Partition('name', 'count', 'device', 'begin', 'end',
                                'logical'))
        self.assertEqual(6, self.prtd.next_count('logical'))

    def test_next_type_gpt(self):
        self.prtd.label = 'gpt'
        self.assertEqual('primary', self.prtd.next_type())

    def test_next_type_no_extended(self):
        self.prtd.label = 'msdos'
        self.assertEqual('primary', self.prtd.next_type())
        self.prtd.partitions.extend(
            3 * [partition.Partition('name', 'count', 'device', 'begin',
                                     'end', 'primary')])
        self.assertEqual('extended', self.prtd.next_type())

    def test_next_type_has_extended(self):
        self.prtd.label = 'msdos'
        self.prtd.partitions.append(
            partition.Partition('name', 'count', 'device', 'begin', 'end',
                                'extended'))
        self.assertEqual('logical', self.prtd.next_type())

    def test_primary(self):
        expected_partitions = [partition.Partition('name', 'count', 'device',
                                                   'begin', 'end', 'primary')]
        self.prtd.partitions.extend(expected_partitions)
        self.assertEqual(expected_partitions, self.prtd.primary)

    def test_conversion(self):
        prt = partition.Partition(
            name='name',
            count='count',
            device='device',
            begin='begin',
            end='end',
            partition_type='primary'
        )
        self.prtd.partitions.append(prt)
        serialized = self.prtd.to_dict()
        assert serialized == {
            'label': 'label',
            'name': 'name',
            'partitions': [
                prt.to_dict(),
            ]
        }


class TestLV(unittest2.TestCase):

    def test_conversion(self):
        lv = partition.LV(
            name='lv-name',
            vgname='vg-name',
            size=1234
        )
        assert lv.to_dict() == {
            'name': 'lv-name',
            'vgname': 'vg-name',
            'size': 1234,
        }


class TestPV(unittest2.TestCase):

    def test_conversion(self):
        pv = partition.PV(
            name='pv-name',
            metadatasize=987,
            metadatacopies=112,
        )
        assert pv.to_dict() == {
            'name': 'pv-name',
            'metadatasize': 987,
            'metadatacopies': 112,
        }


class TestVG(unittest2.TestCase):

    def test_conversion(self):
        vg = partition.VG(
            name='vg-name',
            pvnames=['pv-name-a', ]
        )
        assert vg.to_dict() == {
            'name': 'vg-name',
            'pvnames': ['pv-name-a', ]
        }


class TestFS(unittest2.TestCase):

    def test_conversion(self):
        fs = partition.FS(
            device='some-device',
            mount='/mount',
            fs_type='type',
            fs_options='some-option',
            fs_label='some-label',
        )
        assert fs.to_dict() == {
            'device': 'some-device',
            'mount': '/mount',
            'fs_type': 'type',
            'fs_options': 'some-option',
            'fs_label': 'some-label',
        }
