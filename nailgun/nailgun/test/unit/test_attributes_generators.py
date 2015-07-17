# -*- coding: utf-8 -*-
#    Copyright 2014 Mirantis, Inc.
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

import base64
import mock
import string
import struct

from nailgun.test.base import BaseTestCase
from nailgun.utils import AttributesGenerator


def fake_urandom(length):
    return 'f' * length


def fake_time():
    # Some time around when this was written.
    return 1437172408.238165


class TestAttributesGenerators(BaseTestCase):

    def is_hex(self, val):
        return all(c in string.hexdigits for c in val)

    def test_hexstring_generator(self):
        hex_str = AttributesGenerator.hexstring()
        self.assertEqual(len(hex_str), 8)
        self.assertTrue(all(hex_str))

        hex_str = AttributesGenerator.hexstring(32)
        self.assertEqual(len(hex_str), 32)
        self.assertTrue(all(hex_str))

    @mock.patch('os.urandom', side_effect=fake_urandom)
    @mock.patch('time.time', side_effect=fake_time)
    def test_chephx_key_generator(self, m_time, m_urandom):
        coded_key = AttributesGenerator.cephx_key()
        uncoded_key = base64.b64decode(coded_key)
        package = uncoded_key[:-16]
        key = uncoded_key[-16:]

        key_type, sec, usec, length = struct.unpack('<hiih', package)

        self.assertEqual(key, 'f' * 16)
        self.assertEqual(key_type, 1)
        self.assertEqual(sec, 1437172408)
        self.assertEqual(usec, 0)
        self.assertEqual(length, 16)
