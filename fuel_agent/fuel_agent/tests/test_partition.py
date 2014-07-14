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
