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

import time

from fuel_agent_ci.tests import utils as tu


class TestPartition(tu.BaseFuelAgentCITest):
    def compare_output(self, expected, actual):
        def _split_strip_to_lines(data):
            return [s.strip() for s in data.split('\n')]

        return self.assertEqual(_split_strip_to_lines(expected),
                                _split_strip_to_lines(actual))

    def test_do_partitioning_gpt(self):
        self.env.ssh_by_name(self.name).run(
            'partition', command_timeout=tu.SSH_COMMAND_TIMEOUT)
        #FIXME(agordeev): mdadm resyncing time
        time.sleep(20)

        canned_parted_info = {
            'sda': """BYT;
                /dev/sda:10240MiB:scsi:512:512:gpt:QEMU QEMU HARDDISK;
                1:0.02MiB:1.00MiB:0.98MiB:free;
                1:1.00MiB:25.0MiB:24.0MiB::primary:bios_grub;
                2:25.0MiB:225MiB:200MiB::primary:;
                3:225MiB:425MiB:200MiB::primary:;
                4:425MiB:625MiB:200MiB:ext2:primary:;
                5:625MiB:3958MiB:3333MiB::primary:;
                6:3958MiB:4758MiB:800MiB::primary:;
                7:4758MiB:4778MiB:20.0MiB::primary:;
                1:4778MiB:10240MiB:5462MiB:free;""",
            'sdb': """BYT;
                /dev/sdb:10240MiB:scsi:512:512:gpt:QEMU QEMU HARDDISK;
                1:0.02MiB:1.00MiB:0.98MiB:free;
                1:1.00MiB:25.0MiB:24.0MiB::primary:bios_grub;
                2:25.0MiB:225MiB:200MiB::primary:;
                3:225MiB:425MiB:200MiB::primary:;
                4:425MiB:9496MiB:9071MiB::primary:;
                1:9496MiB:10240MiB:744MiB:free;""",
            'sdc': """BYT;
                /dev/sdc:10240MiB:scsi:512:512:gpt:QEMU QEMU HARDDISK;
                1:0.02MiB:1.00MiB:0.98MiB:free;
                1:1.00MiB:25.0MiB:24.0MiB::primary:bios_grub;
                2:25.0MiB:225MiB:200MiB::primary:;
                3:225MiB:425MiB:200MiB::primary:;
                4:425MiB:5396MiB:4971MiB::primary:;
                1:5396MiB:10240MiB:4844MiB:free;"""
        }
        for disk_name, expected_parted_info in canned_parted_info.items():
            actual_parted_info = self.env.ssh_by_name(self.name).run(
                'parted -s /dev/%s -m unit MiB print free' % disk_name)
            self.compare_output(expected_parted_info, actual_parted_info)

        actual_md_output = self.env.ssh_by_name(self.name).run(
            'mdadm --detail %s' % '/dev/md0')

        #NOTE(agordeev): filter out lines with time stamps and UUID
        def _filter_mdadm_output(output):
            return "\n".join([s for s in output.split('\n')
                              if not any(('Time' in s, 'UUID' in s))])

        expected_md = """/dev/md0:
            Version : 1.2
            Raid Level : raid1
            Array Size : 204608 (199.85 MiB 209.52 MB)
            Used Dev Size : 204608 (199.85 MiB 209.52 MB)
            Raid Devices : 3
            Total Devices : 3
            Persistence : Superblock is persistent

            State : active
            Active Devices : 3
            Working Devices : 3
            Failed Devices : 0
            Spare Devices : 0

            Name : bootstrap:0  (local to host bootstrap)
            Events : 18

            Number   Major   Minor   RaidDevice State
            0       8        3        0      active sync   /dev/sda3
            1       8       19        1      active sync   /dev/sdb3
            2       8       35        2      active sync   /dev/sdc3"""
        self.compare_output(expected_md,
                            _filter_mdadm_output(actual_md_output))

        pvdisplay_expected_output = """/dev/sda5;os;3204.00m;3333.00m
                                       /dev/sda6;image;668.00m;800.00m
                                       /dev/sdb4;image;8940.00m;9071.00m
                                       /dev/sdc4;image;4840.00m;4971.00m"""
        pvdisplay_actual_output = self.env.ssh_by_name(self.name).run(
            'pvdisplay -C --noheading --units m --options '
            'pv_name,vg_name,pv_size,dev_size --separator ";"')
        self.compare_output(pvdisplay_expected_output, pvdisplay_actual_output)

        vgdisplay_expected_output = """image;14448.00m;12688.00m
                                       os;3204.00m;1260.00m"""
        vgdisplay_actual_output = self.env.ssh_by_name(self.name).run(
            'vgdisplay -C --noheading --units m --options '
            'vg_name,vg_size,vg_free --separator ";"')
        self.compare_output(vgdisplay_expected_output, vgdisplay_actual_output)

        lvdisplay_expected_output = """glance;1760.00m;image
                                       root;1900.00m;os
                                       swap;44.00m;os"""
        lvdisplay_actual_output = self.env.ssh_by_name(self.name).run(
            'lvdisplay -C --noheading --units m --options '
            'lv_name,lv_size,vg_name --separator ";"')
        self.compare_output(lvdisplay_expected_output, lvdisplay_actual_output)

        expected_fs_data = [('/dev/md0', 'ext2', ''),
                            ('/dev/sda4', 'ext2', ''),
                            ('/dev/mapper/os-root', 'ext4', ''),
                            ('/dev/mapper/os-swap', 'swap', ''),
                            ('/dev/mapper/image-glance', 'xfs', '')]
        for device, fs_type, label in expected_fs_data:
            fs_type_output = self.env.ssh_by_name(self.name).run(
                'blkid -o value -s TYPE %s' % device)
            self.assertEqual(fs_type, fs_type_output)
            label_output = self.env.ssh_by_name(self.name).run(
                'blkid -o value -s LABEL %s' % device)
            self.assertEqual(label, label_output)
            #TODO(agordeev): check fs options and mount point
