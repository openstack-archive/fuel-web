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

import json
import os
import time

from fuel_agent_ci.tests import base

REGULAR_PARTED_INFO = {
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
        4:425MiB:4869MiB:4444MiB::primary:;
        1:4869MiB:10240MiB:5371MiB:free;""",
    'sdc': """BYT;
        /dev/sdc:10240MiB:scsi:512:512:gpt:QEMU QEMU HARDDISK;
        1:0.02MiB:1.00MiB:0.98MiB:free;
        1:1.00MiB:25.0MiB:24.0MiB::primary:bios_grub;
        2:25.0MiB:225MiB:200MiB::primary:;
        3:225MiB:425MiB:200MiB::primary:;
        4:425MiB:2396MiB:1971MiB::primary:;
        1:2396MiB:10240MiB:7844MiB:free;"""
}
CEPH_PARTED_INFO = {
    'sda': """BYT;
        /dev/sda:10240MiB:scsi:512:512:gpt:QEMU QEMU HARDDISK;
        1:0.02MiB:1.00MiB:0.98MiB:free;
        1:1.00MiB:25.0MiB:24.0MiB::primary:bios_grub;
        2:25.0MiB:225MiB:200MiB::primary:;
        3:225MiB:425MiB:200MiB::primary:;
        4:425MiB:625MiB:200MiB:ext2:primary:;
        5:625MiB:3958MiB:3333MiB::primary:;
        6:3958MiB:4758MiB:800MiB::primary:;
        7:4758MiB:8091MiB:3333MiB::primary:;
        8:8091MiB:8111MiB:20.0MiB::primary:;
        1:8111MiB:10240MiB:2129MiB:free;""",
    'sdb': """BYT;
        /dev/sdb:10240MiB:scsi:512:512:gpt:QEMU QEMU HARDDISK;
        1:0.02MiB:1.00MiB:0.98MiB:free;
        1:1.00MiB:25.0MiB:24.0MiB::primary:bios_grub;
        2:25.0MiB:225MiB:200MiB::primary:;
        3:225MiB:425MiB:200MiB::primary:;
        4:425MiB:4869MiB:4444MiB::primary:;
        5:4869MiB:8202MiB:3333MiB::primary:;
        1:8202MiB:10240MiB:2038MiB:free;""",
    'sdc': """BYT;
        /dev/sdc:10240MiB:scsi:512:512:gpt:QEMU QEMU HARDDISK;
        1:0.02MiB:1.00MiB:0.98MiB:free;
        1:1.00MiB:25.0MiB:24.0MiB::primary:bios_grub;
        2:25.0MiB:225MiB:200MiB::primary:;
        3:225MiB:425MiB:200MiB::primary:;
        4:425MiB:2396MiB:1971MiB::primary:;
        5:2396MiB:5729MiB:3333MiB::primary:;
        1:5729MiB:10240MiB:4511MiB:free;"""
}


class TestPartition(base.BaseFuelAgentCITest):
    def compare_output(self, expected, actual):
        def _split_strip_to_lines(data):
            return [s.strip() for s in data.split('\n')]

        return self.assertEqual(_split_strip_to_lines(expected),
                                _split_strip_to_lines(actual))

    def _test_partitioning(self, canned_parted_info):
        self.ssh.run('partition')

        #FIXME(agordeev): mdadm resyncing time
        time.sleep(10)

        for disk_name, expected_parted_info in canned_parted_info.items():
            actual_parted_info = self.ssh.run(
                'parted -s /dev/%s -m unit MiB print free' % disk_name)
            self.compare_output(expected_parted_info, actual_parted_info)

        actual_guid = self.ssh.run(
            'sgdisk -i 4 /dev/sda').split('\n')[0].split()[3]
        self.assertEqual("0FC63DAF-8483-4772-8E79-3D69D8477DE4", actual_guid)

        actual_md_output = self.ssh.run(
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
                                       /dev/sdb4;image;4312.00m;4444.00m
                                       /dev/sdc4;image;1840.00m;1971.00m"""
        pvdisplay_actual_output = self.ssh.run(
            'pvdisplay -C --noheading --units m --options '
            'pv_name,vg_name,pv_size,dev_size --separator ";"')
        self.compare_output(pvdisplay_expected_output, pvdisplay_actual_output)

        vgdisplay_expected_output = """image;6820.00m;5060.00m
                                       os;3204.00m;1260.00m"""
        vgdisplay_actual_output = self.ssh.run(
            'vgdisplay -C --noheading --units m --options '
            'vg_name,vg_size,vg_free --separator ";"')
        self.compare_output(vgdisplay_expected_output, vgdisplay_actual_output)

        lvdisplay_expected_output = """glance;1760.00m;image
                                       root;1900.00m;os
                                       swap;44.00m;os"""
        lvdisplay_actual_output = self.ssh.run(
            'lvdisplay -C --noheading --units m --options '
            'lv_name,lv_size,vg_name --separator ";"')
        self.compare_output(lvdisplay_expected_output, lvdisplay_actual_output)

        expected_fs_data = [('/dev/md0', 'ext2', ''),
                            ('/dev/sda4', 'ext2', ''),
                            ('/dev/mapper/os-root', 'ext4', ''),
                            ('/dev/mapper/os-swap', 'swap', ''),
                            ('/dev/mapper/image-glance', 'xfs', '')]
        for device, fs_type, label in expected_fs_data:
            fs_type_output = self.ssh.run(
                'blkid -o value -s TYPE %s' % device)
            self.assertEqual(fs_type, fs_type_output)
            label_output = self.ssh.run(
                'blkid -o value -s LABEL %s' % device)
            self.assertEqual(label, label_output)
            #TODO(agordeev): check fs options and mount point

    def test_do_partitioning_gpt(self):
        provision_data = self.render_template(
            template_data={
                'IP': self.dhcp_hosts[0]['ip'],
                'MAC': self.dhcp_hosts[0]['mac'],
                'MASTER_IP': self.net.ip,
                'MASTER_HTTP_PORT': self.http.port,
                'PROFILE': 'ubuntu_1204_x86_64'
            },
            template_name='provision.json'
        )
        self.ssh.put_content(provision_data, '/tmp/provision.json')
        self._test_partitioning(REGULAR_PARTED_INFO)

    def test_do_ceph_partitioning(self):
        provision_data = self.render_template(
            template_data={
                'IP': self.dhcp_hosts[0]['ip'],
                'MAC': self.dhcp_hosts[0]['mac'],
                'MASTER_IP': self.net.ip,
                'MASTER_HTTP_PORT': self.http.port,
                'PROFILE': 'ubuntu_1204_x86_64'
            },
            template_name='provision_ceph.json'
        )
        self.ssh.put_content(provision_data, '/tmp/provision.json')
        self._test_partitioning(CEPH_PARTED_INFO)
        # NOTE(agordeev): checking if GUIDs are correct for ceph partitions
        ceph_partitions = {'sda': 7, 'sdb': 5, 'sdc': 5}
        for disk_name, partition_num in ceph_partitions.items():
            actual_guid = self.ssh.run(
                'sgdisk -i %s /dev/%s' % (partition_num, disk_name)).\
                split('\n')[0].split()[3]
            self.assertEqual('4fbd7e29-9d25-41b8-afd0-062c0ceff05d'.upper(),
                             actual_guid)
        # FIXME(kozhukalov): check if ceph journals are created and their GUIDs
