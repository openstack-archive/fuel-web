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

from fuel_agent.utils import img_utils as iu


class TestTarget(test_base.BaseTestCase):
    def setUp(self):
        super(TestTarget, self).setUp()
        self.tgt = iu.Target()

    def test_target_next(self):
        self.assertRaises(StopIteration, self.tgt.next)

    @mock.patch.object(iu.Target, '__iter__')
    def test_target_target(self, mock_iter):
        mock_iter.return_value = iter(['chunk1', 'chunk2', 'chunk3'])
        m = mock.mock_open()
        with mock.patch('six.moves.builtins.open', m):
            self.tgt.target()

        mock_write_expected_calls = [mock.call('chunk1'), mock.call('chunk2'),
                                     mock.call('chunk3')]
        file_handle = m()
        self.assertEqual(mock_write_expected_calls,
                         file_handle.write.call_args_list)
        file_handle.flush.assert_called_once_with()


class TestLocalFile(test_base.BaseTestCase):
    def setUp(self):
        super(TestLocalFile, self).setUp()
        self.lf = iu.LocalFile('/dev/null')

    def test_localfile_next(self):
        self.lf.fileobj = mock.Mock()
        self.lf.fileobj.read.side_effect = ['some_data', 'another_data']
        self.assertEqual('some_data', self.lf.next())
        self.assertEqual('another_data', self.lf.next())
        self.assertRaises(StopIteration, self.lf.next)
