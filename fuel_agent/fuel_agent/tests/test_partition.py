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

from fuel_agent import errors
from fuel_agent.objects import partition


class TestMD(test_base.BaseTestCase):
    def setUp(self):
        super(TestMD, self).setUp()
        self.md = partition.Md('name', 'level')

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


class TestPartition(test_base.BaseTestCase):
    def setUp(self):
        super(TestPartition, self).setUp()
        self.pt = partition.Partition('name', 'count', 'device', 'begin',
                                      'end', 'partition_type')

    def test_set_flag(self):
        self.assertEqual(0, len(self.pt.flags))
        self.pt.set_flag('fake_flag')
        self.assertEqual(1, len(self.pt.flags))
        self.assertIn('fake_flag', self.pt.flags)


class TestPartitionScheme(test_base.BaseTestCase):
    def setUp(self):
        super(TestPartitionScheme, self).setUp()
        self.p_scheme = partition.PartitionScheme()

    def test_root_device_not_found(self):
        self.assertRaises(errors.WrongPartitionSchemeError,
                          self.p_scheme.root_device)

    def test_fs_by_device(self):
        expected_fs = partition.Fs('device')
        self.p_scheme.fss.append(expected_fs)
        self.p_scheme.fss.append(partition.Fs('wrong_device'))
        actual_fs = self.p_scheme.fs_by_device('device')
        self.assertEqual(expected_fs, actual_fs)

    def test_fs_by_mount(self):
        expected_fs = partition.Fs('d', mount='mount')
        self.p_scheme.fss.append(expected_fs)
        self.p_scheme.fss.append(partition.Fs('w_d', mount='wrong_mount'))
        actual_fs = self.p_scheme.fs_by_mount('mount')
        self.assertEqual(expected_fs, actual_fs)

    def test_pv_by_name(self):
        expected_pv = partition.Pv('pv')
        self.p_scheme.pvs.append(expected_pv)
        self.p_scheme.pvs.append(partition.Pv('wrong_pv'))
        actual_pv = self.p_scheme.pv_by_name('pv')
        self.assertEqual(expected_pv, actual_pv)

    def test_vg_by_name(self):
        expected_vg = partition.Vg('vg')
        self.p_scheme.vgs.append(expected_vg)
        self.p_scheme.vgs.append(partition.Vg('wrong_vg'))
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
            partition.Md('/dev/md%s' % x, 'level') for x in range(0, 128)]
        self.assertRaises(errors.MDAlreadyExistsError,
                          self.p_scheme.md_next_name)

    def test_md_by_name(self):
        self.assertEqual(0, len(self.p_scheme.mds))
        expected_md = partition.Md('name', 'level')
        self.p_scheme.mds.append(expected_md)
        self.p_scheme.mds.append(partition.Md('wrong_name', 'level'))
        self.assertEqual(expected_md, self.p_scheme.md_by_name('name'))

    def test_md_by_mount(self):
        self.assertEqual(0, len(self.p_scheme.mds))
        self.assertEqual(0, len(self.p_scheme.fss))
        expected_md = partition.Md('name', 'level')
        expected_fs = partition.Fs('name', mount='mount')
        self.p_scheme.mds.append(expected_md)
        self.p_scheme.fss.append(expected_fs)
        self.p_scheme.fss.append(partition.Fs('wrong_name',
                                 mount='wrong_mount'))
        self.assertEqual(expected_md, self.p_scheme.md_by_mount('mount'))

    def test_md_attach_by_mount_md_exists(self):
        self.assertEqual(0, len(self.p_scheme.mds))
        self.assertEqual(0, len(self.p_scheme.fss))
        expected_md = partition.Md('name', 'level')
        expected_fs = partition.Fs('name', mount='mount')
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


class TestParted(test_base.BaseTestCase):
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
        self.prtd.name = 'cciss or loop'
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
