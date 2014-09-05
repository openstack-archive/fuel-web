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

from fuel_agent.utils import fs_utils as fu
from fuel_agent.utils import utils


class TestFSUtils(test_base.BaseTestCase):

    @mock.patch.object(utils, 'execute')
    def test_make_fs(self, mock_exec):
        fu.make_fs('ext4', ' -F ', ' -L fake_label ', '/dev/fake')
        mock_exec.assert_called_once_with('mkfs.ext4', '-F', '-L',
                                          'fake_label', '/dev/fake')

    @mock.patch.object(utils, 'execute')
    def test_make_fs_swap(self, mock_exec):
        fu.make_fs('swap', ' -f ', ' -L fake_label ', '/dev/fake')
        mock_exec.assert_called_once_with('mkswap', '-f', '-L', 'fake_label',
                                          '/dev/fake')

    @mock.patch.object(utils, 'execute')
    def test_make_fs_uswap(self, mock_exec):
        #NOTE(agordeev): check that logic correctly works with unicode values
        fu.make_fs(u'swap', ' -f ', ' -L fake_label ', '/dev/fake')
        mock_exec.assert_called_once_with('mkswap', '-f', '-L', 'fake_label',
                                          '/dev/fake')
