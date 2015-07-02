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
import six
import unittest2

from fuel_agent import errors
from fuel_agent.utils import hardware as hu
from fuel_agent.utils import md as mu
from fuel_agent.utils import utils


if six.PY2:
    OPEN_FUNCTION_NAME = '__builtin__.open'
else:
    OPEN_FUNCTION_NAME = 'builtins.open'


class TestMdUtils(unittest2.TestCase):

    @mock.patch('fuel_agent.utils.md.utils.execute')
    def test_mddisplay_nostate_detail(self, mock_exec):
        mock_exec.return_value = (
            """/dev/md127:
        Version : imsm
     Raid Level : container
  Total Devices : 2

Working Devices : 2


           UUID : 46a4fc60:21554de1:1edfad0f:c137ddac
  Member Arrays :

    Number   Major   Minor   RaidDevice

       0       8        0        -        /dev/sda
       1       8       16        -        /dev/sdb""",
            ''
        )

        expected = [{
            'Raid Level': 'container',
            'UUID': '46a4fc60:21554de1:1edfad0f:c137ddac',
            'Version': 'imsm',
            'devices': ['/dev/sda', '/dev/sdb'],
            'name': '/dev/md127',
        }]

        mds = mu.mddisplay(['/dev/md127'])
        mock_exec.assert_called_once_with(
            'mdadm', '--detail', '/dev/md127', check_exit_code=[0])

        self.assertItemsEqual(expected, mds)

    @mock.patch.object(utils, 'execute')
    def test_mddisplay(self, mock_exec):
        # should read file /proc/mdstat
        # should get detailed description for all md devices
        # should return list of dicts representing md devices

        mock_open_data = """Personalities : [raid1]
md0 : active raid1 loop5[1] loop4[0]
      102272 blocks super 1.2 [2/2] [UU]

unused devices: <none>


        """
        mock_open = mock.mock_open(read_data=mock_open_data)
        patcher = mock.patch(OPEN_FUNCTION_NAME, new=mock_open)
        patcher.start()

        mock_exec.return_value = (
            """/dev/md0:
        Version : 1.2
  Creation Time : Wed Jun 18 18:44:57 2014
     Raid Level : raid1
     Array Size : 102272 (99.89 MiB 104.73 MB)
  Used Dev Size : 102272 (99.89 MiB 104.73 MB)
   Raid Devices : 2
  Total Devices : 2
    Persistence : Superblock is persistent

    Update Time : Wed Jun 18 18:45:01 2014
          State : clean
 Active Devices : 2
Working Devices : 2
 Failed Devices : 0
  Spare Devices : 0

           Name : localhost.localdomain:0  (local to host
localhost.localdomain)
           UUID : 12dd4cfc:6b2ac9db:94564538:a6ffee82
         Events : 17

    Number   Major   Minor   RaidDevice State
       0       7        4        0      active sync   /dev/loop4
       1       7        5        1      active sync   /dev/loop5""",
            ''
        )

        expected = [{
            'name': '/dev/md0',
            'Version': '1.2',
            'Raid Level': 'raid1',
            'Raid Devices': '2',
            'Active Devices': '2',
            'Spare Devices': '0',
            'Failed Devices': '0',
            'State': 'clean',
            'UUID': '12dd4cfc:6b2ac9db:94564538:a6ffee82',
            'devices': ['/dev/loop4', '/dev/loop5']
        }]

        mds = mu.mddisplay()
        mock_exec.assert_called_once_with(
            'mdadm', '--detail', '/dev/md0', check_exit_code=[0])

        key = lambda x: x['name']
        self.assertEqual(sorted(expected, key=key), sorted(mds, key=key))
        patcher.stop()

    @mock.patch.object(mu, 'mdclean')
    @mock.patch.object(hu, 'list_block_devices')
    @mock.patch.object(mu, 'mddisplay')
    @mock.patch.object(utils, 'execute')
    def test_mdcreate_ok(self, mock_exec, mock_mddisplay,
                         mock_bdevs, mock_mdclean):
        # should check if md already exists
        # should check if md level is valid
        # should check if all necessary devices exist
        # should check if all devices are not parts of some md
        # should clean md metadata which possibly are on all devices
        # should run mdadm command to create new md

        mock_mddisplay.return_value = \
            [{'name': '/dev/md10', 'devices': ['/dev/fake10']},
             # should also accept devices with missing 'devices' entry
             {'name': '/dev/md11'}]
        mock_bdevs.return_value = [{'device': '/dev/fake1'},
                                   {'device': '/dev/fake2'}]

        mu.mdcreate('/dev/md0', 'mirror', '/dev/fake1', '/dev/fake2')
        mock_mdclean_expected_calls = [mock.call('/dev/fake1'),
                                       mock.call('/dev/fake2')]
        self.assertEqual(mock_mdclean_expected_calls,
                         mock_mdclean.call_args_list)
        mock_exec.assert_called_once_with(
            'mdadm', '--create', '--force', '/dev/md0', '-e0.90',
            '--level=mirror',
            '--raid-devices=2', '/dev/fake1', '/dev/fake2',
            check_exit_code=[0])

    @mock.patch.object(mu, 'mddisplay')
    def test_mdcreate_duplicate(self, mock_mddisplay):
        # should check if md already exists
        # should raise error if it exists
        mock_mddisplay.return_value = [{'name': '/dev/md0'}]
        self.assertRaises(
            errors.MDAlreadyExistsError, mu.mdcreate,
            '/dev/md0', 'mirror', '/dev/fake')

    @mock.patch.object(mu, 'mddisplay')
    def test_mdcreate_unsupported_level(self, mock_mddisplay):
        # should check if md level is valid
        # should raise error if it is not
        mock_mddisplay.return_value = [{'name': '/dev/md10'}]
        self.assertRaises(
            errors.MDWrongSpecError, mu.mdcreate,
            '/dev/md0', 'badlevel', '/dev/fake')

    @mock.patch.object(hu, 'list_block_devices')
    @mock.patch.object(mu, 'mddisplay')
    def test_mdcreate_device_not_found(self, mock_mddisplay, mock_bdevs):
        # should check if all devices exist
        # should raise error if at least one device does not
        mock_mddisplay.return_value = [{'name': '/dev/md10'}]
        mock_bdevs.return_value = [{'device': '/dev/fake1'},
                                   {'device': '/dev/fake10'}]
        self.assertRaises(
            errors.MDNotFoundError, mu.mdcreate,
            '/dev/md0', 'mirror', '/dev/fake1', '/dev/fake2')

    @mock.patch.object(hu, 'list_block_devices')
    @mock.patch.object(mu, 'mddisplay')
    def test_mdcreate_device_attached(self, mock_mddisplay, mock_bdevs):
        # should check if all necessary devices are not attached to some md
        # should raise error if at least one device is attached
        mock_mddisplay.return_value = [{'name': '/dev/md10',
                                        'devices': ['/dev/fake2']}]
        mock_bdevs.return_value = [{'device': '/dev/fake1'},
                                   {'device': '/dev/fake2'}]
        self.assertRaises(
            errors.MDDeviceDuplicationError, mu.mdcreate,
            '/dev/md0', 'mirror', '/dev/fake1', '/dev/fake2')

    @mock.patch.object(utils, 'execute')
    @mock.patch.object(mu, 'mdclean')
    @mock.patch.object(hu, 'list_block_devices')
    @mock.patch.object(mu, 'mddisplay')
    def test_mdcreate_device_clean(self, mock_mddisplay,
                                   mock_bdevs, mock_mdclean, mock_exec):
        # should clean md metadata on all devices before building new md
        mock_mddisplay.return_value = []
        mock_bdevs.return_value = [{'device': '/dev/fake1'},
                                   {'device': '/dev/fake2'}]
        mu.mdcreate('/dev/md0', 'mirror', '/dev/fake1', '/dev/fake2')
        expected_calls = [mock.call('/dev/fake1'), mock.call('/dev/fake2')]
        self.assertEqual(mock_mdclean.call_args_list, expected_calls)

    @mock.patch.object(mu, 'mdclean')
    @mock.patch.object(mu, 'mdremove')
    @mock.patch.object(mu, 'mddisplay')
    def test_mdclean_all(self, mock_mddisplay, mock_mdremove, mock_mdclean):
        mock_mddisplay.side_effect = [
            [{'name': '/dev/md10', 'devices': ['/dev/fake10']},
             {'name': '/dev/md11'}],
            [{'name': '/dev/md11'}],
            []
        ]
        mu.mdclean_all()
        mock_mdremove_expected_calls = [
            mock.call('/dev/md10'), mock.call('/dev/md11'),
            mock.call('/dev/md11')]
        mock_mdclean.assert_called_once_with('/dev/fake10')
        self.assertEqual(mock_mdremove.call_args_list,
                         mock_mdremove_expected_calls)

    @mock.patch.object(mu, 'mdclean')
    @mock.patch.object(mu, 'mdremove')
    @mock.patch.object(mu, 'mddisplay')
    def test_mdclean_all_fail(self, mock_mddisplay, mock_mdremove,
                              mock_mdclean):
        mock_mddisplay.return_value = [{'name': '/dev/md11'}]
        self.assertRaises(errors.MDRemovingError, mu.mdclean_all)

    @mock.patch.object(utils, 'execute')
    @mock.patch.object(mu, 'get_mdnames')
    def test_mdremove_ok(self, mock_get_mdn, mock_exec):
        # should check if md exists
        # should run mdadm command to remove md device
        mock_get_mdn.return_value = ['/dev/md0']
        expected_calls = [
            mock.call('udevadm', 'settle', '--quiet', check_exit_code=[0]),
            mock.call('mdadm', '--stop', '/dev/md0', check_exit_code=[0]),
            mock.call('mdadm', '--remove', '/dev/md0', check_exit_code=[0, 1])
        ]
        mu.mdremove('/dev/md0')
        self.assertEqual(mock_exec.call_args_list, expected_calls)

    @mock.patch.object(mu, 'get_mdnames')
    def test_mdremove_notfound(self, mock_get_mdn):
        # should check if md exists
        # should raise error if it does not
        mock_get_mdn.return_value = ['/dev/md0']
        self.assertRaises(
            errors.MDNotFoundError, mu.mdremove, '/dev/md1')

    @mock.patch.object(utils, 'execute')
    def test_mdclean(self, mock_exec):
        mu.mdclean('/dev/md0')
        mock_exec.assert_called_once_with('mdadm', '--zero-superblock',
                                          '--force', '/dev/md0',
                                          check_exit_code=[0])
