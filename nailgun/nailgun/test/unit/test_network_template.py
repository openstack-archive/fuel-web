# -*- coding: utf-8 -*-

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

from oslo_serialization import jsonutils

try:
    from unittest.case import TestCase
except ImportError:
    # Runing unit-tests in production environment
    from unittest2.case import TestCase

from nailgun.network.template import NetworkTemplate


class TestNetworkTemplate(TestCase):
    def test_simple_substitution(self):
        template = NetworkTemplate("a: <%a%>, b: <%b%>")
        substituted_string = template.safe_substitute(a='aaa', b='bbb')

        self.assertEqual(substituted_string, "a: aaa, b: bbb")

    def test_substitution_with_spaces(self):
        template = NetworkTemplate("a: <% a%>, b: <%b %>, c: <% c %>, d: <%   d%>")
        substituted_string = template.safe_substitute(a='aaa', b='bbb', c='ccc', d='ddd')

        self.assertEqual(substituted_string, "a: aaa, b: bbb, c: ccc, d: ddd")

    def test_substitution_with_no_match(self):
        template = NetworkTemplate("a: <%a b: <% b % >")
        substituted_string = template.safe_substitute(a='aaa', b='bbb')

        self.assertEqual(substituted_string, "a: <%a b: <%b % >")