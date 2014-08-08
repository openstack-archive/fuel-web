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
import os
from oslotest import base as test_base

from fuel_agent.utils import grub_utils as gu


class TestGrubUtils(test_base.BaseTestCase):

    @mock.patch.object(os.path, 'isfile')
    def test_guess_grub2_conf(self, mock_isfile):
        side_effect_values = {
            '/target/boot/grub/grub.cfg': True,
            '/target/boot/grub2/grub.cfg': False
        }
        def side_effect(key):
            return side_effect_values[key]

        mock_isfile.side_effect = side_effect
        self.assertEqual(gu.guess_grub2_conf('/target'),
                         '/boot/grub/grub.cfg')

        side_effect_values = {
            '/target/boot/grub/grub.cfg': False,
            '/target/boot/grub2/grub.cfg': True
        }
        self.assertEqual(gu.guess_grub2_conf('/target'),
                         '/boot/grub2/grub.cfg')

