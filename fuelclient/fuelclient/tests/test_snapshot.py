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


from mock import call
from mock import patch

from fuelclient.tests import base


class TestSnapshot(base.UnitTestCase):

    @patch('fuelclient.cli.actions.snapshot.SnapshotTask.get_default_config')
    @patch('sys.stdout.write')
    def test_get_default_config(self, mwrite, mconf):

        mconf.return_value = {'key': 'value'}

        self.execute(['fuel', 'snapshot', '--conf'])
        self.assertEqual(mwrite.call_args_list, [call('key: value\n')])

    @patch('fuelclient.cli.actions.snapshot.SnapshotTask.start_snapshot_task')
    @patch('fuelclient.cli.actions.snapshot.'
           'download_snapshot_with_progress_bar')
    @patch('sys.stdin')
    def test_snapshot_with_provided_conf(self, mstdin, mbar, mstart):
        conf = 'key: value\n'

        mstdin.isatty.return_value = False
        mstdin.read.return_value = conf

        self.execute(['fuel', 'snapshot'])

        mstart.assert_called_once_with({'key': 'value'})
        self.assertEqual(mstdin.read.call_count, 1)

    @patch('fuelclient.cli.actions.snapshot.SnapshotTask.start_snapshot_task')
    @patch('fuelclient.cli.actions.snapshot.'
           'download_snapshot_with_progress_bar')
    @patch('sys.stdin')
    def test_snapshot_without_conf(self, mstdin, mbar, mstart):

        mstdin.isatty.return_value = True

        self.execute(['fuel', 'snapshot'])

        mstart.assert_called_once_with({})
