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


import string

from mock import patch
from nailgun.test.base import BaseTestCase
from nailgun.utils import AttributesGenerator


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

    def test_password_generator_alpha_numeric(self):
        pwd = AttributesGenerator.password()
        self.assertTrue(all(c in string.letters + string.digits for c in pwd))

    def test_password_generator_arg_100(self):
        pwd = AttributesGenerator.password(arg=100)
        self.assertEqual(len(pwd), 100)

    def test_password_generator_arg_none(self):
        pwd = AttributesGenerator.password()
        self.assertEqual(len(pwd), 8)

    def test_password_generator_arg_string(self):
        pwd = AttributesGenerator.password(arg='hello')
        self.assertEqual(len(pwd), 8)

    def test_ip_generator_arg_not_admin_or_master(self):
        ip = AttributesGenerator.ip(arg='something')
        self.assertEqual(ip, '127.0.0.1')

    @patch('nailgun.settings.settings.MASTER_IP', "master_ip")
    def test_ip_generator_arg_admin_or_master(self):
        ip = AttributesGenerator.ip(arg='admin')
        self.assertEqual(ip, "master_ip")

        ip = AttributesGenerator.ip(arg='master')
        self.assertEqual(ip, "master_ip")

    def test_identical(self):
        for arg in (None, 1, 'a', {'a': 1}, [1, 2], (1, 2)):
            identical = AttributesGenerator.identical(arg=arg)
            self.assertEqual(identical, str(arg))

    @patch('nailgun.settings.settings.some', "thing")
    def test_from_settings(self):
        value = AttributesGenerator.from_settings('some')
        self.assertEqual(value, "thing")
