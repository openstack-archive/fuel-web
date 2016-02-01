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

import mock

from unittest2.case import TestCase

from nailgun.network.template import NetworkTemplate
from nailgun.orchestrator.neutron_serializers import \
    NeutronNetworkTemplateSerializer70 as ts


class TestNetworkTemplate(TestCase):
    def test_simple_substitution(self):
        template = NetworkTemplate("a: <%a%>, b: <%b%>")
        substituted_string = template.safe_substitute(a='aaa', b='bbb')

        self.assertEqual(substituted_string, "a: aaa, b: bbb")

    def test_substitution_with_spaces(self):
        template = NetworkTemplate("a: <% a%>, b: <%b %>, "
                                   "c: <% c %>, d: <%   d%>")
        substituted_string = template.safe_substitute(a='aaa', b='bbb',
                                                      c='ccc', d='ddd')

        self.assertEqual(substituted_string, "a: aaa, b: bbb, c: ccc, d: ddd")

    def test_substitution_with_no_match(self):
        template = NetworkTemplate("a: <%a b: <% b % >")
        substituted_string = template.safe_substitute(a='aaa', b='bbb')

        self.assertEqual(substituted_string, "a: <%a b: <% b % >")

    def test_substitution_with_extra_keys(self):
        template = NetworkTemplate("a: <%a%>")

        substituted_string = template.safe_substitute(a='aaa', b='bbb')
        self.assertEqual(substituted_string, "a: aaa")

        substituted_string = template.substitute(a='aaa', b='bbb')
        self.assertEqual(substituted_string, "a: aaa")

    def test_substitution_with_missed_key(self):
        template = NetworkTemplate("a: <%a%>")
        substituted_string = template.safe_substitute(b='bbb')

        self.assertEqual(substituted_string, "a: <%a%>")
        self.assertRaises(KeyError,
                          template.substitute,
                          b='bbb')

    def test_schemes_order(self):
        template = {
            "templates_for_node_role": {
                "cinder": [
                    "common",
                    "storage"
                ],
                "compute": [
                    "common",
                    "private",
                    "storage"
                ]
            },
            "templates": {
                "storage": {
                    "transformations": [
                        "storage"
                    ]
                },
                "common": {
                    "transformations": [
                        "common"
                    ]
                },
                "private": {
                    "transformations": [
                        "private"
                    ]
                },
            }
        }

        node = mock.Mock(network_template=template,
                         all_roles=['cinder', 'compute'])
        transformations = ts.generate_transformations(node)
        self.assertEqual(["common", "storage", "private"], transformations)
