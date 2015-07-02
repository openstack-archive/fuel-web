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

from fuel_agent.utils import hardware as hu
from fuel_agent.utils import utils


class TestHardwareUtils(unittest2.TestCase):

    @mock.patch.object(utils, 'execute')
    def test_parse_dmidecode(self, exec_mock):
        exec_mock.return_value = ["""
System Slot Information
    Designation: PCIEX16_1
    ID: 1
    Bus Address: 0000:00:01.0
    Characteristics:
        3.3 V is provided
        PME signal is supported

System Slot Information
    Type: 32-bit PCI Express
    ID: 3
    Characteristics:
        Opening is shared
    Bus Address: 0000:00:1c.4


"""]

        expected = [{"designation": "PCIEX16_1",
                     "id": "1",
                     "characteristics": ["3.3 V is provided",
                                         "PME signal is supported"],
                     "bus address": "0000:00:01.0"},
                    {"type": "32-bit PCI Express",
                     "id": "3",
                     "characteristics": ["Opening is shared"],
                     "bus address": "0000:00:1c.4"}]

        self.assertEqual(expected, hu.parse_dmidecode("fake_type"))
        exec_mock.assert_called_once_with("dmidecode", "-q", "--type",
                                          "fake_type")

    @mock.patch.object(utils, 'execute')
    def test_parse_lspci(self, exec_mock):
        exec_mock.return_value = ["""Slot:   07:00.0
Class:  PCI bridge
Vendor: ASMedia Technology Inc.
Device: ASM1083/1085 PCIe to PCI Bridge
Rev:    01
ProgIf: 01

Slot:   09:00.0
Class:  IDE interface
Vendor: Marvell Technology Group Ltd.
Device: 88SE6121 SATA II / PATA Controller
SVendor:    ASUSTeK Computer Inc.
SDevice:    Device 82a2
Rev:    b2
ProgIf: 8f

"""]

        expected = [{'class': 'PCI bridge',
                     'device': 'ASM1083/1085 PCIe to PCI Bridge',
                     'progif': '01',
                     'rev': '01',
                     'slot': '07:00.0',
                     'vendor': 'ASMedia Technology Inc.'},
                    {'class': 'IDE interface',
                     'device': '88SE6121 SATA II / PATA Controller',
                     'progif': '8f',
                     'rev': 'b2',
                     'sdevice': 'Device 82a2',
                     'slot': '09:00.0',
                     'svendor': 'ASUSTeK Computer Inc.',
                     'vendor': 'Marvell Technology Group Ltd.'}]

        self.assertEqual(expected, hu.parse_lspci())
        exec_mock.assert_called_once_with('lspci', '-vmm', '-D')

    @mock.patch.object(utils, 'execute')
    def test_parse_simple_kv(self, exec_mock):
        exec_mock.return_value = ["""driver: r8169
version: 2.3LK-NAPI
firmware-version: rtl_nic/rtl8168e-2.fw
bus-info: 0000:06:00.0
supports-statistics: yes
supports-test: no
supports-eeprom-access: no
supports-register-dump: yes

"""]

        expected = {'driver': 'r8169',
                    'version': '2.3LK-NAPI',
                    'firmware-version': 'rtl_nic/rtl8168e-2.fw',
                    'bus-info': '0000:06:00.0',
                    'supports-statistics': 'yes',
                    'supports-test': 'no',
                    'supports-eeprom-access': 'no',
                    'supports-register-dump': 'yes'}

        self.assertEqual(expected, hu.parse_simple_kv('fake', 'cmd'))
        exec_mock.assert_called_once_with('fake', 'cmd')

    @mock.patch.object(utils, 'execute')
    def test_udevreport(self, mock_exec):
        # should run udevadm info OS command
        # in order to get udev properties for a device
        mock_exec.return_value = (
            'DEVLINKS=\'/dev/disk/by-id/fakeid1 /dev/disk/by-id/fakeid2\'\n'
            'DEVNAME=\'/dev/fake\'\n'
            'DEVPATH=\'/devices/fakepath\'\n'
            'DEVTYPE=\'disk\'\n'
            'MAJOR=\'11\'\n'
            'MINOR=\'0\'\n'
            'ID_BUS=\'fakebus\'\n'
            'ID_MODEL=\'fakemodel\'\n'
            'ID_SERIAL_SHORT=\'fakeserial\'\n'
            'ID_WWN=\'fakewwn\'\n'
            'ID_CDROM=\'1\'\n'
            'ANOTHER=\'another\'\n',
            ''
        )
        expected = {
            'DEVLINKS': ['/dev/disk/by-id/fakeid1', '/dev/disk/by-id/fakeid2'],
            'DEVNAME': '/dev/fake',
            'DEVPATH': '/devices/fakepath',
            'DEVTYPE': 'disk',
            'MAJOR': '11',
            'MINOR': '0',
            'ID_BUS': 'fakebus',
            'ID_MODEL': 'fakemodel',
            'ID_SERIAL_SHORT': 'fakeserial',
            'ID_WWN': 'fakewwn',
            'ID_CDROM': '1'
        }
        self.assertEqual(expected, hu.udevreport('/dev/fake'))
        mock_exec.assert_called_once_with('udevadm',
                                          'info',
                                          '--query=property',
                                          '--export',
                                          '--name=/dev/fake',
                                          check_exit_code=[0])

    @mock.patch.object(utils, 'execute')
    def test_blockdevreport(self, mock_exec):
        # should run blockdev OS command
        # in order to get block device properties
        cmd = ['blockdev', '--getsz', '--getro', '--getss', '--getpbsz',
               '--getsize64', '--getiomin', '--getioopt', '--getra',
               '--getalignoff', '--getmaxsect', '/dev/fake']
        mock_exec.return_value = (
            '625142448\n0\n512\n4096\n320072933376\n4096\n0\n256\n0\n1024',
            ''
        )
        expected = {
            'sz': '625142448',
            'ro': '0',
            'ss': '512',
            'pbsz': '4096',
            'size64': '320072933376',
            'iomin': '4096',
            'ioopt': '0',
            'ra': '256',
            'alignoff': '0',
            'maxsect': '1024'
        }
        self.assertEqual(expected, hu.blockdevreport('/dev/fake'))
        mock_exec.assert_called_once_with(*cmd, check_exit_code=[0])

    @mock.patch('six.moves.builtins.open')
    def test_extrareport(self, mock_open):
        # should read some files from sysfs e.g. /sys/block/fake/removable
        # in order to get some device properties
        def with_side_effect(arg):
            mock_with = mock.MagicMock()
            mock_with.__exit__.return_value = None
            mock_file = mock.Mock()
            if arg == '/sys/block/fake/removable':
                mock_file.read.return_value = '0\n'
            elif arg == '/sys/block/fake/device/state':
                mock_file.read.return_value = 'running\n'
            elif arg == '/sys/block/fake/device/timeout':
                mock_file.read.return_value = '30\n'
            mock_with.__enter__.return_value = mock_file
            return mock_with
        mock_open.side_effect = with_side_effect
        expected = {'removable': '0', 'state': 'running', 'timeout': '30'}
        self.assertEqual(expected, hu.extrareport('/dev/fake'))

    @mock.patch('six.moves.builtins.open')
    def test_extrareport_exceptions(self, mock_open):
        mock_open.side_effect = Exception('foo')
        expected = {}
        self.assertEqual(expected, hu.extrareport('/dev/fake'))

    @mock.patch.object(hu, 'blockdevreport')
    @mock.patch.object(hu, 'udevreport')
    def test_is_disk_uspec_bspec_none(self, mock_ureport, mock_breport):
        # should call udevreport if uspec is None
        # should call blockdevreport if bspec is None
        # should return True if uspec and bspec are empty
        mock_ureport.return_value = {}
        mock_breport.return_value = {}
        self.assertTrue(hu.is_disk('/dev/fake'))
        mock_ureport.assert_called_once_with('/dev/fake')
        mock_breport.assert_called_once_with('/dev/fake')

    @mock.patch.object(hu, 'udevreport')
    def test_is_disk_uspec_none(self, mock_ureport):
        # should call udevreport if uspec is None but bspec is not None
        bspec = {'key': 'value'}
        mock_ureport.return_value = {}
        hu.is_disk('/dev/fake', bspec=bspec)
        mock_ureport.assert_called_once_with('/dev/fake')

    @mock.patch.object(hu, 'blockdevreport')
    def test_is_disk_bspec_none(self, mock_breport):
        # should call blockdevreport if bspec is None but uspec is not None
        uspec = {'key': 'value'}
        mock_breport.return_value = {}
        hu.is_disk('/dev/fake', uspec=uspec)
        mock_breport.assert_called_once_with('/dev/fake')

    @mock.patch.object(hu, 'blockdevreport')
    def test_is_disk_cdrom(self, mock_breport):
        # should return False if udev ID_CDROM is set to 1
        mock_breport.return_value = {}
        uspec = {
            'ID_CDROM': '1'
        }
        self.assertFalse(hu.is_disk('/dev/fake', uspec=uspec))

    @mock.patch.object(hu, 'blockdevreport')
    def test_is_disk_partition(self, mock_breport):
        # should return False if udev DEVTYPE is partition
        mock_breport.return_value = {}
        uspec = {
            'DEVTYPE': 'partition'
        }
        self.assertFalse(hu.is_disk('/dev/fake', uspec=uspec))

    @mock.patch.object(hu, 'blockdevreport')
    def test_is_disk_major(self, mock_breport):
        # should return False if udev MAJOR is not in a list of
        # major numbers which are used for disks
        # look at kernel/Documentation/devices.txt
        mock_breport.return_value = {}
        valid_majors = [3, 8, 65, 66, 67, 68, 69, 70, 71, 104, 105,
                        106, 107, 108, 109, 110, 111, 202, 252, 253, 259]
        for major in (set(range(1, 261)) - set(valid_majors)):
            uspec = {
                'MAJOR': str(major)
            }
            self.assertFalse(hu.is_disk('/dev/fake', uspec=uspec))

    @mock.patch.object(hu, 'udevreport')
    def test_is_disk_readonly(self, mock_ureport):
        # should return False if device is read only
        mock_ureport.return_value = {}
        bspec = {
            'ro': '1'
        }
        self.assertFalse(hu.is_disk('/dev/fake', bspec=bspec))

    @mock.patch('fuel_agent.utils.hardware.utils.execute')
    def test_get_block_devices_from_udev_db(self, mock_exec):
        mock_exec.return_value = ("""P: /devices/virtual/block/loop0
N: loop0
E: DEVNAME=/dev/loop0
E: DEVPATH=/devices/virtual/block/loop0
E: DEVTYPE=disk
E: MAJOR=7
E: SUBSYSTEM=block

P: /devices/pci0000:00/0000:00:1f.2/ata1/host0/target0:0:0/0:0:0:0/block/sda
N: sda
S: disk/by-id/wwn-0x5000c5004008ac0f
S: disk/by-path/pci-0000:00:1f.2-scsi-0:0:0:0
E: DEVNAME=/dev/sda
E: DEVTYPE=disk
E: ID_ATA=1
E: MAJOR=8
E: SUBSYSTEM=block
E: UDEV_LOG=3

P: /devices/pci:00/:00:04.0/misc/nvme0
N: nvme0
E: DEVNAME=/dev/nvme0
E: DEVPATH=/devices/pci:00/:00:04.0/misc/nvme0
E: MAJOR=10
E: MINOR=57
E: SUBSYSTEM=misc

P: /devices/pci:00/:00:04.0/block/nvme0n1
N: nvme0n1
E: DEVNAME=/dev/nvme0n1
E: DEVPATH=/devices/pci:00/:00:04.0/block/nvme0n1
E: DEVTYPE=disk
E: MAJOR=259
E: MINOR=0
E: SUBSYSTEM=block
E: USEC_INITIALIZED=87744

P: /devices/pci0000:00/0000:00:1c.1/target16:0:0/16:0:0:0/block/sr0
E: DEVTYPE=disk
E: DEVNAME=/dev/sr0
E: MAJOR=11
E: MINOR=0
E: SEQNUM=4400
E: SUBSYSTEM=block

P: /devices/pci0000:00/0000:00:1f.2/ata1/host0/target0:0:0/0:0:0:0/block/sda
N: sda
S: disk/by-id/wwn-0x5000c5004008ac0f
S: disk/by-path/pci-0000:00:1f.2-scsi-0:0:0:0
E: DEVNAME=/dev/sda1
E: DEVTYPE=partition
E: ID_ATA=1
E: SUBSYSTEM=block
E: MAJOR=8
E: UDEV_LOG=3""", '')

        self.assertEqual(['/dev/sda', '/dev/nvme0n1', '/dev/sda1'],
                         hu.get_block_devices_from_udev_db())

    @mock.patch.object(hu, 'get_block_devices_from_udev_db')
    @mock.patch.object(hu, 'is_disk')
    @mock.patch.object(hu, 'extrareport')
    @mock.patch.object(hu, 'blockdevreport')
    @mock.patch.object(hu, 'udevreport')
    def test_list_block_devices(self, mock_ureport, mock_breport, mock_ereport,
                                mock_isdisk, mock_get_devs):
        # should run blockdev --report command
        # in order to get a list of block devices
        # should call report methods to get device info
        # should call is_disk method to filter out
        # those block devices which are not disks
        mock_get_devs.return_value = ['/dev/fake', '/dev/fake1', '/dev/sr0']

        def isdisk_side_effect(arg, uspec=None, bspec=None):
            if arg == '/dev/fake':
                return True
            elif arg in ('/dev/fake1', '/dev/sr0'):
                return False
        mock_isdisk.side_effect = isdisk_side_effect
        mock_ureport.return_value = {'key0': 'value0'}
        mock_breport.return_value = {'key1': 'value1'}
        mock_ereport.return_value = {'key2': 'value2'}

        expected = [{
            'device': '/dev/fake',
            'uspec': {'key0': 'value0'},
            'bspec': {'key1': 'value1'},
            'espec': {'key2': 'value2'}
        }]
        self.assertEqual(hu.list_block_devices(), expected)
        self.assertEqual(mock_ureport.call_args_list, [mock.call('/dev/fake'),
                         mock.call('/dev/fake1'), mock.call('/dev/sr0')])
        self.assertEqual(mock_breport.call_args_list, [mock.call('/dev/fake'),
                         mock.call('/dev/fake1'), mock.call('/dev/sr0')])
        self.assertEqual(mock_ereport.call_args_list, [mock.call('/dev/fake'),
                         mock.call('/dev/fake1'), mock.call('/dev/sr0')])

    @mock.patch.object(hu, 'get_block_devices_from_udev_db')
    @mock.patch.object(hu, 'is_disk')
    @mock.patch.object(hu, 'extrareport')
    @mock.patch.object(hu, 'blockdevreport')
    @mock.patch.object(hu, 'udevreport')
    def test_list_block_devices_removable_vendors(self, mock_ureport,
                                                  mock_breport, mock_ereport,
                                                  mock_isdisk, mock_get_devs):
        mock_get_devs.return_value = ['/dev/no_vendor_id',
                                      '/dev/wrong_vendor_id',
                                      '/dev/right_vendor_id']
        mock_isdisk.return_value = True
        mock_ureport.side_effect = [
            {},
            {'ID_VENDOR': 'Cisco'},
            {'ID_VENDOR': 'IBM'},
        ]
        mock_ereport.return_value = {'removable': '1'}
        mock_breport.return_value = {'key1': 'value1'}
        expected = [{
            'device': '/dev/right_vendor_id',
            'uspec': {'ID_VENDOR': 'IBM'},
            'bspec': {'key1': 'value1'},
            'espec': {'removable': '1'}
        }]
        self.assertEqual(hu.list_block_devices(), expected)
        self.assertEqual(
            mock_ureport.call_args_list,
            [mock.call('/dev/no_vendor_id'),
             mock.call('/dev/wrong_vendor_id'),
             mock.call('/dev/right_vendor_id')])
        mock_breport.assert_called_once_with('/dev/right_vendor_id')
        self.assertEqual(
            mock_ereport.call_args_list,
            [mock.call('/dev/no_vendor_id'),
             mock.call('/dev/wrong_vendor_id'),
             mock.call('/dev/right_vendor_id')])

    def test_match_device_devlinks(self):
        # should return true if at least one by-id link from first uspec
        # matches by-id link from another uspec
        uspec1 = {'DEVLINKS': ['/dev/disk/by-path/fakepath',
                               '/dev/disk/by-id/fakeid1',
                               '/dev/disk/by-id/fakeid2']}
        uspec2 = {'DEVLINKS': ['/dev/disk/by-id/fakeid2',
                               '/dev/disk/by-id/fakeid3']}
        self.assertTrue(hu.match_device(uspec1, uspec2))

    def test_match_device_wwn(self):
        # should return true if ID_WWN is given
        # and if it is the same in both uspecs
        # and if DEVTYPE is given and if DEVTYPE is disk
        # or if DEVTYPE is partition and MINOR is the same for both uspecs
        uspec1 = uspec2 = {'ID_WWN': 'fakewwn',
                           'DEVTYPE': 'disk'}
        self.assertTrue(hu.match_device(uspec1, uspec2))
        uspec1 = uspec2 = {'ID_WWN': 'fakewwn',
                           'DEVTYPE': 'partition',
                           'MINOR': '1'}
        self.assertTrue(hu.match_device(uspec1, uspec2))

    def test_match_device_wwn_false(self):
        # should return false if ID_WWN is given
        # and does not match each other
        uspec1 = {'ID_WWN': 'fakewwn1'}
        uspec2 = {'ID_WWN': 'fakewwn2'}
        self.assertFalse(hu.match_device(uspec1, uspec2))

    def test_match_device_devpath(self):
        # should return true if DEVPATH is given
        # and if it is the same for both uspecs
        uspec1 = uspec2 = {'DEVPATH': '/devices/fake'}
        self.assertTrue(hu.match_device(uspec1, uspec2))

    def test_match_device_serial(self):
        # should return true if ID_SERIAL_SHORT is given
        # and if it is the same for both uspecs
        # and if DEVTYPE is given and if it is 'disk'
        uspec1 = uspec2 = {'ID_SERIAL_SHORT': 'fakeserial',
                           'DEVTYPE': 'disk'}
        self.assertTrue(hu.match_device(uspec1, uspec2))

    def test_match_device_serial_false(self):
        # should return false if ID_SERIAL_SHORT is given
        # and if it does not match each other
        uspec1 = {'ID_SERIAL_SHORT': 'fakeserial1'}
        uspec2 = {'ID_SERIAL_SHORT': 'fakeserial2'}
        self.assertFalse(hu.match_device(uspec1, uspec2))

    def test_match_device_false(self):
        uspec1 = {'ID_WWN': 'fakewwn1', 'DEVTYPE': 'disk'}
        uspec2 = {'ID_WWN': 'fakewwn1', 'DEVTYPE': 'partition'}
        self.assertFalse(hu.match_device(uspec1, uspec2))
