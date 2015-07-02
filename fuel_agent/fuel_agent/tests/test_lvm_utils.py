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
from fuel_agent.utils import lvm as lu
from fuel_agent.utils import utils


class TestLvmUtils(unittest2.TestCase):

    @mock.patch.object(utils, 'execute')
    def test_pvdisplay(self, mock_exec):
        # should run os command pvdisplay
        # in order to get actual pv configuration
        mock_exec.return_value = (
            '/dev/fake1;vg;892.00m;1024.00m;'
            '123456-1234-1234-1234-1234-1234-000000\n'
            '/dev/fake2;;1024.00m;1024.00m;'
            '123456-1234-1234-1234-1234-1234-111111\n',
            ''
        )
        expected = [
            {
                'uuid': '123456-1234-1234-1234-1234-1234-000000',
                'vg': 'vg',
                'devsize': 1024,
                'psize': 892,
                'name': '/dev/fake1',
            },
            {
                'uuid': '123456-1234-1234-1234-1234-1234-111111',
                'vg': None,
                'devsize': 1024,
                'psize': 1024,
                'name': '/dev/fake2',
            }
        ]

        pvs = lu.pvdisplay()
        mock_exec.assert_called_once_with(
            'pvdisplay',
            '-C',
            '--noheading',
            '--units', 'm',
            '--options', 'pv_name,vg_name,pv_size,dev_size,pv_uuid',
            '--separator', ';',
            check_exit_code=[0]
        )
        key = lambda x: x['name']
        self.assertEqual(sorted(expected, key=key), sorted(pvs, key=key))

    @mock.patch.object(lu, 'pvdisplay')
    @mock.patch.object(utils, 'execute')
    def test_pvcreate_ok(self, mock_exec, mock_pvdisplay):
        # should set metadatasize=64 and metadatacopies=2 if they are not set
        # should run pvcreate command
        mock_pvdisplay.return_value = [{'name': '/dev/another'}]

        lu.pvcreate('/dev/fake1', metadatasize=32, metadatacopies=1)
        lu.pvcreate('/dev/fake2', metadatacopies=1)
        lu.pvcreate('/dev/fake3', metadatasize=32)
        lu.pvcreate('/dev/fake4')

        expected_calls = [
            mock.call('pvcreate',
                      '--metadatacopies', '1',
                      '--metadatasize', '32m',
                      '/dev/fake1',
                      check_exit_code=[0]),
            mock.call('pvcreate',
                      '--metadatacopies', '1',
                      '--metadatasize', '64m',
                      '/dev/fake2',
                      check_exit_code=[0]),
            mock.call('pvcreate',
                      '--metadatacopies', '2',
                      '--metadatasize', '32m',
                      '/dev/fake3',
                      check_exit_code=[0]),
            mock.call('pvcreate',
                      '--metadatacopies', '2',
                      '--metadatasize', '64m',
                      '/dev/fake4',
                      check_exit_code=[0])
        ]
        self.assertEqual(mock_exec.call_args_list, expected_calls)

    @mock.patch.object(lu, 'pvdisplay')
    def test_pvcreate_duplicate(self, mock_pvdisplay):
        # should check if pv exists
        # then raise exception if it exists
        mock_pvdisplay.return_value = [{'name': '/dev/fake'}]
        self.assertRaises(
            errors.PVAlreadyExistsError, lu.pvcreate, '/dev/fake')

    @mock.patch.object(lu, 'pvdisplay')
    @mock.patch.object(utils, 'execute')
    def test_pvremove_ok(self, mock_exec, mock_pvdisplay):
        # should check if pv exists and is not attached to some vg
        # then should run pvremove command
        mock_pvdisplay.return_value = [{'vg': None, 'name': '/dev/fake'}]
        lu.pvremove('/dev/fake')
        mock_exec.assert_called_once_with('pvremove', '-ff', '-y', '/dev/fake',
                                          check_exit_code=[0])

    @mock.patch.object(lu, 'pvdisplay')
    def test_pvremove_attached_to_vg(self, mock_pvdisplay):
        # should check if pv exists and is not attached to some vg
        # then raise exception if it is attached to some vg
        mock_pvdisplay.return_value = [{'vg': 'some', 'name': '/dev/fake'}]
        self.assertRaises(errors.PVBelongsToVGError, lu.pvremove, '/dev/fake')

    @mock.patch.object(lu, 'pvdisplay')
    def test_pvremove_notfound(self, mock_pvdisplay):
        # should check if pv exists
        # then should raise exception if it does not exist
        mock_pvdisplay.return_value = [{'name': '/dev/another'}]
        self.assertRaises(errors.PVNotFoundError, lu.pvremove, '/dev/fake')

    @mock.patch.object(utils, 'execute')
    def test_vgdisplay(self, mock_exec):
        # should run os command vgdisplay
        # in order to get actual vg configuration
        mock_exec.return_value = (
            'vg1;123456-1234-1234-1234-1234-1234-000000;2040.00m;2040.00m\n'
            'vg2;123456-1234-1234-1234-1234-1234-111111;2040.00m;1020.00m\n',
            ''
        )
        expected = [
            {
                'uuid': '123456-1234-1234-1234-1234-1234-000000',
                'size': 2040,
                'free': 2040,
                'name': 'vg1',
            },
            {
                'uuid': '123456-1234-1234-1234-1234-1234-111111',
                'size': 2040,
                'free': 1020,
                'name': 'vg2',
            }
        ]

        vg = lu.vgdisplay()
        mock_exec.assert_called_once_with(
            'vgdisplay',
            '-C',
            '--noheading',
            '--units', 'm',
            '--options', 'vg_name,vg_uuid,vg_size,vg_free',
            '--separator', ';',
            check_exit_code=[0]
        )
        key = lambda x: x['name']
        self.assertEqual(sorted(expected, key=key), sorted(vg, key=key))

    @mock.patch.object(lu, 'pvdisplay')
    @mock.patch.object(lu, 'vgdisplay')
    @mock.patch.object(utils, 'execute')
    def test_vgcreate_ok(self, mock_exec, mock_vgdisplay, mock_pvdisplay):
        # should check if vg already exists
        # should check if all necessary pv exist
        # should run vgcreate command
        mock_vgdisplay.return_value = [{'name': 'some'}, {'name': 'another'}]
        mock_pvdisplay.return_value = [{'vg': None, 'name': '/dev/fake1'},
                                       {'vg': None, 'name': '/dev/fake2'}]

        # one pvname
        lu.vgcreate('vgname', '/dev/fake1')
        # several pvnames
        lu.vgcreate('vgname', '/dev/fake1', '/dev/fake2')

        expected_calls = [
            mock.call('vgcreate', 'vgname', '/dev/fake1',
                      check_exit_code=[0]),
            mock.call('vgcreate', 'vgname', '/dev/fake1', '/dev/fake2',
                      check_exit_code=[0])
        ]
        self.assertEqual(mock_exec.call_args_list, expected_calls)

    @mock.patch.object(lu, 'vgdisplay')
    def test_vgcreate_duplicate(self, mock_vgdisplay):
        # should check if vg exists
        # should raise exception if it exists
        mock_vgdisplay.return_value = [{'name': 'vgname'}, {'name': 'some'}]
        self.assertRaises(errors.VGAlreadyExistsError,
                          lu.vgcreate, 'vgname', '/dev/fake')

    @mock.patch.object(lu, 'pvdisplay')
    @mock.patch.object(lu, 'vgdisplay')
    def test_vgcreate_pv_not_found(self, mock_vgdisplay, mock_pvdisplay):
        # should check if all necessary pv exist
        # should raise error if at least one pv does not
        mock_vgdisplay.return_value = []
        mock_pvdisplay.return_value = [{'vg': None, 'name': '/dev/fake1'},
                                       {'vg': None, 'name': '/dev/fake2'}]
        self.assertRaises(errors.PVNotFoundError,
                          lu.vgcreate, 'vgname', '/dev/fake', '/dev/fake2')

    @mock.patch.object(lu, 'pvdisplay')
    @mock.patch.object(lu, 'vgdisplay')
    def test_vgcreate_pv_attached(self, mock_vgdisplay, mock_pvdisplay):
        # should check if all necessary pv are not attached to some vg
        # should raise error if at least one pv is attached
        mock_vgdisplay.return_value = []
        mock_pvdisplay.return_value = [{'vg': None, 'name': '/dev/fake1'},
                                       {'vg': 'some', 'name': '/dev/fake2'}]
        self.assertRaises(errors.PVBelongsToVGError,
                          lu.vgcreate, 'vgname', '/dev/fake1', '/dev/fake2')

    @mock.patch.object(lu, 'pvdisplay')
    @mock.patch.object(lu, 'vgdisplay')
    @mock.patch.object(utils, 'execute')
    def test_vgextend_ok(self, mock_exec, mock_vgdisplay, mock_pvdisplay):
        # should check if vg exists
        # should check if all necessary pv exist and not attached to any vg
        # should run vgextend command
        mock_vgdisplay.return_value = [{'name': 'some'}, {'name': 'another'}]
        mock_pvdisplay.return_value = [{'vg': None, 'name': '/dev/fake1'},
                                       {'vg': None, 'name': '/dev/fake2'}]
        lu.vgextend('some', '/dev/fake1', '/dev/fake2')
        mock_exec.assert_called_once_with(
            'vgextend', 'some', '/dev/fake1', '/dev/fake2',
            check_exit_code=[0])

    @mock.patch.object(lu, 'vgdisplay')
    @mock.patch.object(utils, 'execute')
    def test_vgextend_not_found(self, mock_exec, mock_vgdisplay):
        # should check if vg exists
        # should raise error if it does not
        mock_vgdisplay.return_value = [{'name': 'some'}]
        self.assertRaises(errors.VGNotFoundError,
                          lu.vgextend, 'vgname', '/dev/fake1')

    @mock.patch.object(lu, 'pvdisplay')
    @mock.patch.object(lu, 'vgdisplay')
    def test_vgextend_pv_not_found(self, mock_vgdisplay, mock_pvdisplay):
        # should check if all necessary pv exist
        # should raise error if at least one pv does not
        mock_vgdisplay.return_value = [{'name': 'vgname'}]
        mock_pvdisplay.return_value = [{'vg': None, 'name': '/dev/fake1'},
                                       {'vg': None, 'name': '/dev/fake2'}]
        self.assertRaises(errors.PVNotFoundError,
                          lu.vgextend, 'vgname', '/dev/fake', '/dev/fake2')

    @mock.patch.object(lu, 'pvdisplay')
    @mock.patch.object(lu, 'vgdisplay')
    def test_vgextend_pv_attached(self, mock_vgdisplay, mock_pvdisplay):
        # should check if all necessary pv are not attached to some vg
        # should raise error if at least one pv is attached
        mock_vgdisplay.return_value = [{'name': 'vgname'}]
        mock_pvdisplay.return_value = [{'vg': None, 'name': '/dev/fake1'},
                                       {'vg': 'some', 'name': '/dev/fake2'}]
        self.assertRaises(errors.PVBelongsToVGError,
                          lu.vgextend, 'vgname', '/dev/fake1', '/dev/fake2')

    @mock.patch.object(lu, 'vgdisplay')
    @mock.patch.object(utils, 'execute')
    def test_vgremove_ok(self, mock_exec, mock_vgdisplay):
        # should check if vg exists
        # then run vgremove command if it exists
        mock_vgdisplay.return_value = [{'name': 'vgname'}, {'name': 'some'}]
        lu.vgremove('vgname')
        mock_exec.assert_called_once_with('vgremove', '-f', 'vgname',
                                          check_exit_code=[0])

    @mock.patch.object(lu, 'vgdisplay')
    @mock.patch.object(utils, 'execute')
    def test_vgremove_not_found(self, mock_exec, mock_vgdisplay):
        # should check if vg exists
        # then raise error if it doesn't
        mock_vgdisplay.return_value = [{'name': 'some'}]
        self.assertRaises(errors.VGNotFoundError, lu.vgremove, 'vgname')

    @mock.patch.object(lu, 'lvdisplay')
    @mock.patch.object(utils, 'execute')
    def test_lvremove_ok(self, mock_exec, mock_lvdisplay):
        mock_lvdisplay.return_value = [{'path': '/dev/vg/lv'},
                                       {'path': '/dev/vg2/lv2'}]
        lu.lvremove('/dev/vg/lv')
        mock_exec.assert_called_once_with('lvremove', '-f', '/dev/vg/lv',
                                          check_exit_code=[0])

    @mock.patch.object(lu, 'lvdisplay')
    @mock.patch.object(utils, 'execute')
    def test_lvremove_not_found(self, mock_exec, mock_lvdisplay):
        mock_lvdisplay.return_value = [{'path': '/dev/vg/lv'}]
        self.assertRaises(errors.LVNotFoundError, lu.lvremove, '/dev/vg/lv2')

    @mock.patch.object(lu, 'vgdisplay')
    @mock.patch.object(lu, 'lvdisplay')
    @mock.patch.object(utils, 'execute')
    def test_lvcreate_ok(self, mock_exec, mock_lvdisplay, mock_vgdisplay):
        mock_vgdisplay.return_value = [{'name': 'vgname', 'free': 2000},
                                       {'name': 'some'}]
        mock_lvdisplay.return_value = [{'name': 'some'}]
        lu.lvcreate('vgname', 'lvname', 1000)
        mock_exec.assert_called_once_with('lvcreate', '--yes', '-L', '1000m',
                                          '-n', 'lvname', 'vgname',
                                          check_exit_code=[0])

    @mock.patch.object(lu, 'vgdisplay')
    @mock.patch.object(utils, 'execute')
    def test_lvcreate_not_found(self, mock_exec, mock_vgdisplay):
        mock_vgdisplay.return_value = [{'name': 'some'}]
        self.assertRaises(errors.VGNotFoundError, lu.lvcreate, 'vgname',
                          'lvname', 1)

    @mock.patch.object(lu, 'vgdisplay')
    @mock.patch.object(utils, 'execute')
    def test_lvcreate_not_enough_space(self, mock_exec, mock_vgdisplay):
        mock_vgdisplay.return_value = [{'name': 'vgname', 'free': 1},
                                       {'name': 'some'}]
        self.assertRaises(errors.NotEnoughSpaceError, lu.lvcreate, 'vgname',
                          'lvname', 2)

    @mock.patch.object(lu, 'vgdisplay')
    @mock.patch.object(lu, 'lvdisplay')
    @mock.patch.object(utils, 'execute')
    def test_lvcreate_lv_already_exists(self, mock_exec, mock_lvdisplay,
                                        mock_vgdisplay):
        mock_vgdisplay.return_value = [{'name': 'vgname', 'free': 2000},
                                       {'name': 'some'}]
        mock_lvdisplay.return_value = [{'name': 'lvname', 'vg': 'vgname'}]
        self.assertRaises(errors.LVAlreadyExistsError, lu.lvcreate, 'vgname',
                          'lvname', 1000)

    @mock.patch.object(lu, 'vgdisplay')
    @mock.patch.object(lu, 'lvdisplay')
    @mock.patch.object(utils, 'execute')
    def test_lvcreate_lv_name_collision(self, mock_exec, mock_lvdisplay,
                                        mock_vgdisplay):
        # lv lvname already exists in another pv
        mock_vgdisplay.return_value = [{'name': 'vgname', 'free': 2000},
                                       {'name': 'some', 'free': 2000}]
        mock_lvdisplay.return_value = [{'name': 'lvname', 'vg': 'some'}]
        lu.lvcreate('vgname', 'lvname', 1000)
        mock_exec.assert_called_once_with('lvcreate', '--yes', '-L', '1000m',
                                          '-n', 'lvname', 'vgname',
                                          check_exit_code=[0])

    @mock.patch.object(utils, 'execute')
    def test_lvdisplay(self, mock_exec):
        mock_exec.return_value = [
            '  lv_name1;1234.12m;vg_name;lv_uuid1\n'
            '  lv_name2;5678.79m;vg_name;lv_uuid2\n  ']
        expected_lvs = [{'name': 'lv_name1', 'size': 1235, 'vg': 'vg_name',
                         'uuid': 'lv_uuid1', 'path': '/dev/vg_name/lv_name1'},
                        {'name': 'lv_name2', 'size': 5679, 'vg': 'vg_name',
                         'uuid': 'lv_uuid2', 'path': '/dev/vg_name/lv_name2'}]
        actual_lvs = lu.lvdisplay()
        self.assertEqual(expected_lvs, actual_lvs)
        mock_exec.assert_called_once_with('lvdisplay', '-C', '--noheading',
                                          '--units', 'm', '--options',
                                          'lv_name,lv_size,vg_name,lv_uuid',
                                          '--separator', ';',
                                          check_exit_code=[0])

    @mock.patch.object(lu, 'pvdisplay')
    @mock.patch.object(lu, 'vgdisplay')
    @mock.patch.object(utils, 'execute')
    def test_vgreduce_ok(self, mock_exec, mock_vgdisplay, mock_pvdisplay):
        mock_vgdisplay.return_value = [{'name': 'vgname'}, {'name': 'some'}]
        mock_pvdisplay.return_value = [{'vg': 'vgname', 'name': '/dev/fake1'},
                                       {'vg': 'vgname', 'name': '/dev/fake2'}]
        lu.vgreduce('vgname', '/dev/fake1', '/dev/fake2')
        mock_exec.assert_called_once_with('vgreduce', '-f', 'vgname',
                                          '/dev/fake1', '/dev/fake2',
                                          check_exit_code=[0])

    @mock.patch.object(lu, 'vgdisplay')
    def test_vgreduce_vg_not_found(self, mock_vgdisplay):
        mock_vgdisplay.return_value = [{'name': 'some'}]
        self.assertRaises(errors.VGNotFoundError, lu.vgreduce, 'vgname1',
                          '/dev/fake1', '/dev/fake2')

    @mock.patch.object(lu, 'pvdisplay')
    @mock.patch.object(lu, 'vgdisplay')
    @mock.patch.object(utils, 'execute')
    def test_vgreduce_pv_not_attached(self, mock_exec, mock_vgdisplay,
                                      mock_pvdisplay):
        mock_vgdisplay.return_value = [{'name': 'vgname'}, {'name': 'some'}]
        mock_pvdisplay.return_value = [{'vg': None, 'name': '/dev/fake1'},
                                       {'vg': None, 'name': '/dev/fake2'}]
        self.assertRaises(errors.PVNotFoundError, lu.vgreduce, 'vgname',
                          '/dev/fake1', '/dev/fake2')
