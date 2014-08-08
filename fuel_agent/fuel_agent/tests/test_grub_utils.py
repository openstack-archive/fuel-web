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
from fuel_agent.utils import utils


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

    @mock.patch.object(os.path, 'isfile')
    def test_guess_grub2_default(self, mock_isfile):
        side_effect_values = {
            '/target/etc/default/grub': True,
            '/target/etc/sysconfig/grub': False
        }
        def side_effect(key):
            return side_effect_values[key]

        mock_isfile.side_effect = side_effect
        self.assertEqual(gu.guess_grub2_default('/target'),
                         '/etc/default/grub')

        side_effect_values = {
            '/target/etc/default/grub': False,
            '/target/etc/sysconfig/grub': True
        }
        self.assertEqual(gu.guess_grub2_default('/target'),
                         '/etc/sysconfig/grub')

    @mock.patch.object(os.path, 'isfile')
    def test_guess_grub2_mkconfig(self, mock_isfile):
        side_effect_values = {
            '/target/sbin/grub-mkconfig': True,
            '/target/sbin/grub2-mkconfig': False,
            '/target/usr/sbin/grub-mkconfig': False,
            '/target/usr/sbin/grub2-mkconfig': False
        }
        def side_effect(key):
            return side_effect_values[key]

        mock_isfile.side_effect = side_effect
        self.assertEqual(gu.guess_grub2_mkconfig('/target'),
                         '/sbin/grub-mkconfig')

        side_effect_values = {
            '/target/sbin/grub-mkconfig': False,
            '/target/sbin/grub2-mkconfig': True,
            '/target/usr/sbin/grub-mkconfig': False,
            '/target/usr/sbin/grub2-mkconfig': False
        }
        self.assertEqual(gu.guess_grub2_mkconfig('/target'),
                         '/sbin/grub2-mkconfig')

        side_effect_values = {
            '/target/sbin/grub-mkconfig': False,
            '/target/sbin/grub2-mkconfig': False,
            '/target/usr/sbin/grub-mkconfig': True,
            '/target/usr/sbin/grub2-mkconfig': False
        }
        self.assertEqual(gu.guess_grub2_mkconfig('/target'),
                         '/usr/sbin/grub-mkconfig')

        side_effect_values = {
            '/target/sbin/grub-mkconfig': False,
            '/target/sbin/grub2-mkconfig': False,
            '/target/usr/sbin/grub-mkconfig': False,
            '/target/usr/sbin/grub2-mkconfig': True
        }
        self.assertEqual(gu.guess_grub2_mkconfig('/target'),
                         '/usr/sbin/grub2-mkconfig')

    @mock.patch.object(gu, 'guess_grub_install')
    @mock.patch.object(utils, 'execute')
    def test_guess_grub_version_1(self, mock_exec, mock_ggi):
        mock_ggi.return_value = '/grub_install'
        mock_exec.return_value = ('foo 0.97 bar', '')
        version = gu.guess_grub_version('/target')
        mock_exec.assert_called_once_with('/target/grub_install', '-v')
        self.assertEqual(version, 1)

    @mock.patch.object(gu, 'guess_grub_install')
    @mock.patch.object(utils, 'execute')
    def test_guess_grub_version_2(self, mock_exec, mock_ggi):
        mock_ggi.return_value = '/grub_install'
        mock_exec.return_value = ('foo bar', '')
        version = gu.guess_grub_version('/target')
        mock_exec.assert_called_once_with('/target/grub_install', '-v')
        self.assertEqual(version, 2)

    @mock.patch.object(os.path, 'isfile')
    def test_guess_grub(self, mock_isfile):
        side_effect_values = {
            '/target/sbin/grub': True,
            '/target/usr/sbin/grub': False
        }
        def side_effect(key):
            return side_effect_values[key]

        mock_isfile.side_effect = side_effect
        self.assertEqual(gu.guess_grub('/target'),
                         '/sbin/grub')

        side_effect_values = {
            '/target/sbin/grub': False,
            '/target/usr/sbin/grub': True
        }
        self.assertEqual(gu.guess_grub('/target'),
                         '/usr/sbin/grub')

        side_effect_values = {
            '/target/sbin/grub': False,
            '/target/usr/sbin/grub': False
        }
        self.assertRaises(Exception, gu.guess_grub, '/target')
